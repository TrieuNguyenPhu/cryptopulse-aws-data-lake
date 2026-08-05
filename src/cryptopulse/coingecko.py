"""CoinGecko Demo API client with bounded retries and safe observability."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from random import random
from typing import Self
from uuid import UUID, uuid4

import httpx

from cryptopulse.bronze import JsonValue
from cryptopulse.config import COINGECKO_BASE_URL
from cryptopulse.jobs import JOB_CATALOG, JobCatalog, ParameterValue

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=15.0, pool=5.0)
MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = frozenset({408, 429})


@dataclass(frozen=True, slots=True)
class PreparedRequest:
    job_name: str
    criticality: str
    endpoint: str
    parameters: Mapping[str, ParameterValue]
    coin_id: str | None


@dataclass(frozen=True, slots=True)
class AttemptContext:
    job_name: str
    criticality: str
    run_id: str
    request_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class CoinGeckoResponse:
    payload: JsonValue
    endpoint: str
    parameters: Mapping[str, ParameterValue]
    run_id: str
    request_id: str
    requested_at: datetime
    received_at: datetime
    http_status: int
    latency_ms: int


class CoinGeckoError(RuntimeError):
    """Base error containing safe request context and no response body or headers."""

    def __init__(
        self,
        message: str,
        *,
        request: PreparedRequest,
        run_id: str,
        request_id: str,
        attempts: int,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.job_name = request.job_name
        self.endpoint = request.endpoint
        self.run_id = run_id
        self.request_id = request_id
        self.attempts = attempts
        self.status_code = status_code
        self.retry_after = retry_after
        status = f" status={status_code}" if status_code is not None else ""
        super().__init__(
            f"{message}; job={request.job_name} endpoint={request.endpoint}{status} "
            f"request_id={request_id} attempts={attempts}"
        )


class TransportError(CoinGeckoError):
    """Transport failure after the retry policy is exhausted."""


class BadRequestError(CoinGeckoError):
    """Permanent HTTP 400 response."""


class AuthenticationError(CoinGeckoError):
    """Permanent HTTP 401 response."""


class AuthorizationError(CoinGeckoError):
    """Permanent HTTP 403 or plan-restriction response."""


class PermanentHttpError(CoinGeckoError):
    """Other permanent HTTP 4xx response."""


class RequestTimeoutError(CoinGeckoError):
    """HTTP 408 response after the retry policy is exhausted."""


class RateLimitError(CoinGeckoError):
    """HTTP 429 response after the retry policy is exhausted."""


class ServerError(CoinGeckoError):
    """HTTP 5xx response after the retry policy is exhausted."""


class UnexpectedStatusError(CoinGeckoError):
    """Unexpected non-200 response outside the retry/error matrix."""


class ResponseDecodeError(CoinGeckoError):
    """HTTP 200 response that is not strict JSON."""


def prepare_request(
    catalog: JobCatalog,
    job_name: str,
    *,
    coin_id: str | None = None,
) -> PreparedRequest:
    """Resolve one allow-listed request without accepting arbitrary URLs or parameters."""

    job = catalog.get(job_name)
    is_scoped = "{id}" in job.endpoint
    if is_scoped:
        if coin_id is None:
            raise ValueError(f"{job_name} requires coin_id")
        if coin_id not in job.coin_ids:
            raise ValueError(f"coin_id is not configured for {job_name}")
        endpoint = job.endpoint.replace("{id}", coin_id)
    else:
        if coin_id is not None:
            raise ValueError(f"{job_name} does not accept coin_id")
        endpoint = job.endpoint

    return PreparedRequest(
        job_name=job.name,
        criticality=job.criticality,
        endpoint=endpoint,
        parameters=job.parameters,
        coin_id=coin_id,
    )


class CoinGeckoClient:
    """Synchronous Demo client; one logical request may make at most four attempts."""

    def __init__(
        self,
        api_key: str,
        *,
        catalog: JobCatalog | None = None,
        http_client: httpx.Client | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        jitter: Callable[[], float] = random,
        request_id_factory: Callable[[], str] = lambda: str(uuid4()),
        before_attempt: Callable[[AttemptContext], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("CoinGecko Demo API key is required")
        if not normalized_key.isascii() or any(
            not 33 <= ord(character) <= 126 for character in normalized_key
        ):
            raise ValueError("CoinGecko Demo API key has an invalid format")
        if not 0 <= max_retries <= MAX_RETRIES:
            raise ValueError(f"max_retries must be between 0 and {MAX_RETRIES}")
        if not math.isfinite(backoff_seconds) or backoff_seconds < 0:
            raise ValueError("backoff_seconds must be finite and non-negative")

        self._api_key = normalized_key
        self._catalog = JOB_CATALOG if catalog is None else catalog
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._monotonic = monotonic
        self._now = now
        self._jitter = jitter
        self._request_id_factory = request_id_factory
        self._before_attempt = before_attempt
        self._logger = logger or logging.getLogger("cryptopulse.coingecko")
        self._owns_client = http_client is None
        self._http = httpx.Client(trust_env=False) if http_client is None else http_client

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def fetch(
        self,
        job_name: str,
        *,
        run_id: str,
        coin_id: str | None = None,
    ) -> CoinGeckoResponse:
        request = prepare_request(self._catalog, job_name, coin_id=coin_id)
        canonical_run_id = _uuid(run_id, "run_id")
        request_id = _uuid(self._request_id_factory(), "request_id")
        url = f"{COINGECKO_BASE_URL}{request.endpoint}"

        for attempt in range(1, self._max_retries + 2):
            context = AttemptContext(
                job_name=request.job_name,
                criticality=request.criticality,
                run_id=canonical_run_id,
                request_id=request_id,
                attempt=attempt,
            )
            if self._before_attempt is not None:
                self._before_attempt(context)

            requested_at = _utc(self._now(), "now")
            started = self._monotonic()
            self._log(logging.INFO, "coingecko_request_started", request, context)
            transport_error: TransportError | None = None
            try:
                response = self._http.get(
                    url,
                    params=dict(request.parameters),
                    headers={
                        "accept": "application/json",
                        "x-cg-demo-api-key": self._api_key,
                    },
                    timeout=self._timeout,
                )
            except httpx.TransportError:
                latency_ms = _latency_ms(started, self._monotonic())
                self._log(
                    logging.WARNING,
                    "coingecko_transport_error",
                    request,
                    context,
                    latency_ms=latency_ms,
                )
                if attempt > self._max_retries:
                    transport_error = TransportError(
                        "CoinGecko transport failed",
                        request=request,
                        run_id=canonical_run_id,
                        request_id=request_id,
                        attempts=attempt,
                    )
                else:
                    self._schedule_retry(request, context, retry_after=None)
                    continue
            if transport_error is not None:
                raise transport_error

            received_at = _utc(self._now(), "now")
            latency_ms = _latency_ms(started, self._monotonic())
            self._log(
                logging.INFO,
                "coingecko_response_received",
                request,
                context,
                status_code=response.status_code,
                latency_ms=latency_ms,
            )

            if response.status_code == 200:
                decode_error: ResponseDecodeError | None = None
                try:
                    payload = _json_value(response.json())
                except ValueError:
                    decode_error = ResponseDecodeError(
                        "CoinGecko returned invalid JSON",
                        request=request,
                        run_id=canonical_run_id,
                        request_id=request_id,
                        attempts=attempt,
                        status_code=200,
                    )
                if decode_error is not None:
                    raise decode_error
                return CoinGeckoResponse(
                    payload=payload,
                    endpoint=request.endpoint,
                    parameters=request.parameters,
                    run_id=canonical_run_id,
                    request_id=request_id,
                    requested_at=requested_at,
                    received_at=received_at,
                    http_status=200,
                    latency_ms=latency_ms,
                )

            retry_after = parse_retry_after(response.headers.get("retry-after"), received_at)
            if _is_retryable(response.status_code):
                if attempt <= self._max_retries:
                    self._schedule_retry(request, context, retry_after=retry_after)
                    continue
                raise _status_error(
                    response.status_code,
                    request=request,
                    run_id=canonical_run_id,
                    request_id=request_id,
                    attempts=attempt,
                    retry_after=retry_after,
                )

            raise _status_error(
                response.status_code,
                request=request,
                run_id=canonical_run_id,
                request_id=request_id,
                attempts=attempt,
                retry_after=retry_after,
            )

        raise AssertionError("retry loop exhausted without a result")

    def _schedule_retry(
        self,
        request: PreparedRequest,
        context: AttemptContext,
        *,
        retry_after: float | None,
    ) -> None:
        retry_index = context.attempt - 1
        jitter_value = self._jitter()
        jitter = min(max(jitter_value, 0.0), 1.0) if math.isfinite(jitter_value) else 0.0
        delay = self._backoff_seconds * (2**retry_index + jitter)
        if retry_after is not None:
            delay = max(delay, retry_after)
        self._log(
            logging.WARNING,
            "coingecko_retry_scheduled",
            request,
            context,
            retry_delay_seconds=delay,
        )
        self._sleep(delay)

    def _log(
        self,
        level: int,
        event: str,
        request: PreparedRequest,
        context: AttemptContext,
        **extra: int | float,
    ) -> None:
        self._logger.log(
            level,
            event,
            extra={
                "event": event,
                "job_name": request.job_name,
                "endpoint": request.endpoint,
                "parameters": dict(request.parameters),
                "run_id": context.run_id,
                "request_id": context.request_id,
                "attempt": context.attempt,
                **extra,
            },
        )


def parse_retry_after(value: str | None, now: datetime) -> float | None:
    """Parse Retry-After seconds or HTTP-date; invalid values use normal backoff."""

    if value is None:
        return None
    text = value.strip()
    try:
        seconds = float(text)
    except ValueError:
        try:
            instant = parsedate_to_datetime(text)
        except TypeError, ValueError, OverflowError:
            return None
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        seconds = (instant.astimezone(UTC) - _utc(now, "now")).total_seconds()
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return seconds


def _status_error(
    status_code: int,
    *,
    request: PreparedRequest,
    run_id: str,
    request_id: str,
    attempts: int,
    retry_after: float | None,
) -> CoinGeckoError:
    error_type: type[CoinGeckoError]
    message: str
    if status_code == 400:
        error_type, message = BadRequestError, "CoinGecko rejected the request"
    elif status_code == 401:
        error_type, message = AuthenticationError, "CoinGecko authentication failed"
    elif status_code == 403:
        error_type, message = AuthorizationError, "CoinGecko authorization failed"
    elif status_code == 408:
        error_type, message = RequestTimeoutError, "CoinGecko request timed out"
    elif status_code == 429:
        error_type, message = RateLimitError, "CoinGecko rate limit persisted"
    elif 500 <= status_code <= 599:
        error_type, message = ServerError, "CoinGecko server failure persisted"
    elif 400 <= status_code <= 499:
        error_type, message = PermanentHttpError, "CoinGecko returned a permanent client error"
    else:
        error_type, message = UnexpectedStatusError, "CoinGecko returned an unexpected status"
    return error_type(
        message,
        request=request,
        run_id=run_id,
        request_id=request_id,
        attempts=attempts,
        status_code=status_code,
        retry_after=retry_after,
    )


def _is_retryable(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS_CODES or 500 <= status_code <= 599


def _uuid(value: str, field_name: str) -> str:
    try:
        return str(UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a UUID") from error


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _latency_ms(started: float, finished: float) -> int:
    return max(0, round((finished - started) * 1000))


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        raise ValueError("JSON numbers must be finite")
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _json_value(item) for key, item in value.items()}
    raise ValueError("response is not a JSON value")
