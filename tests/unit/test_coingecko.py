from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import httpx
import pytest

from cryptopulse.coingecko import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    CoinGeckoClient,
    PermanentHttpError,
    RateLimitError,
    RequestTimeoutError,
    ResponseDecodeError,
    ServerError,
    TransportError,
    UnexpectedStatusError,
    parse_retry_after,
    prepare_request,
)
from cryptopulse.config import COINGECKO_BASE_URL
from cryptopulse.jobs import load_job_catalog
from cryptopulse.logging import configure_json_logging

API_KEY = "fixture-super-secret"
RUN_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 8, 4, 0, 0, tzinfo=UTC)


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> tuple[CoinGeckoClient, httpx.Client]:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = CoinGeckoClient(
        API_KEY,
        http_client=http_client,
        request_id_factory=lambda: REQUEST_ID,
        now=lambda: NOW,
        **kwargs,
    )
    return client, http_client


@pytest.mark.parametrize(
    ("job_name", "coin_id", "endpoint"),
    [
        ("market_snapshot", None, "/coins/markets"),
        ("global_market", None, "/global"),
        ("trending", None, "/search/trending"),
        ("categories", None, "/coins/categories"),
        ("exchanges", None, "/exchanges"),
        ("coin_list", None, "/coins/list"),
        ("coin_metadata", "bitcoin", "/coins/bitcoin"),
        ("coin_ohlc", "bitcoin", "/coins/bitcoin/ohlc"),
        ("historical_backfill", "bitcoin", "/coins/bitcoin/market_chart"),
    ],
)
def test_prepare_request_covers_every_allowlisted_endpoint(
    job_name: str, coin_id: str | None, endpoint: str
) -> None:
    request = prepare_request(load_job_catalog(), job_name, coin_id=coin_id)

    assert request.endpoint == endpoint
    assert "x-cg-demo-api-key" not in request.parameters
    assert "x_cg_demo_api_key" not in request.parameters


def test_prepare_request_rejects_invalid_scope_usage() -> None:
    catalog = load_job_catalog()

    with pytest.raises(ValueError, match="requires coin_id"):
        prepare_request(catalog, "coin_metadata")
    with pytest.raises(ValueError, match="not configured"):
        prepare_request(catalog, "coin_metadata", coin_id="not-configured")
    with pytest.raises(ValueError, match="does not accept"):
        prepare_request(catalog, "global_market", coin_id="bitcoin")


def test_success_uses_demo_header_timeouts_ids_latency_and_safe_json_logs() -> None:
    stream = StringIO()
    logger = configure_json_logging(
        logger=logging.getLogger("cryptopulse.test.client.success"),
        secrets=(API_KEY,),
        stream=stream,
    )
    monotonic_values = iter([10.0, 10.125])
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(f"{COINGECKO_BASE_URL}/coins/markets?")
        assert request.headers["x-cg-demo-api-key"] == API_KEY
        assert request.url.params["vs_currency"] == "usd"
        assert request.url.params["sparkline"] == "false"
        assert request.extensions["timeout"] == {
            "connect": 5.0,
            "read": 15.0,
            "write": 15.0,
            "pool": 5.0,
        }
        return httpx.Response(200, json=[{"id": "bitcoin"}])

    client, http_client = make_client(
        handler,
        monotonic=lambda: next(monotonic_values),
        before_attempt=lambda context: attempts.append(context.attempt),
        logger=logger,
    )
    try:
        result = client.fetch("market_snapshot", run_id=RUN_ID)
    finally:
        http_client.close()

    assert result.payload == [{"id": "bitcoin"}]
    assert result.run_id == RUN_ID
    assert result.request_id == REQUEST_ID
    assert result.latency_ms == 125
    assert result.requested_at == NOW
    assert result.received_at == NOW
    assert attempts == [1]
    output = stream.getvalue()
    assert API_KEY not in output
    events = [json.loads(line)["event"] for line in output.splitlines()]
    assert events == ["coingecko_request_started", "coingecko_response_received"]


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, AuthorizationError),
        (404, PermanentHttpError),
    ],
)
def test_permanent_4xx_is_never_retried_and_does_not_expose_body(
    status_code: int, error_type: type[Exception]
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json={"error": f"echo {API_KEY}"})

    client, http_client = make_client(handler, sleep=sleeps.append)
    try:
        with pytest.raises(error_type) as captured:
            client.fetch("global_market", run_id=RUN_ID)
    finally:
        http_client.close()

    assert calls == 1
    assert sleeps == []
    assert API_KEY not in str(captured.value)


@pytest.mark.parametrize("status_code", [408, 429, 500, 502, 503])
def test_retryable_status_recovers_without_changing_logical_request_id(status_code: int) -> None:
    calls = 0
    contexts: list[tuple[int, str]] = []
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status_code)
        return httpx.Response(200, json={"data": {}})

    client, http_client = make_client(
        handler,
        sleep=sleeps.append,
        jitter=lambda: 0.0,
        before_attempt=lambda value: contexts.append((value.attempt, value.request_id)),
    )
    try:
        result = client.fetch("global_market", run_id=RUN_ID)
    finally:
        http_client.close()

    assert result.request_id == REQUEST_ID
    assert calls == 2
    assert contexts == [(1, REQUEST_ID), (2, REQUEST_ID)]
    assert sleeps == [1.0]


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [(408, RequestTimeoutError), (429, RateLimitError), (500, ServerError)],
)
def test_retryable_status_stops_after_three_retries(
    status_code: int, error_type: type[Exception]
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code)

    client, http_client = make_client(
        handler,
        sleep=sleeps.append,
        jitter=lambda: 0.25,
    )
    try:
        with pytest.raises(error_type) as captured:
            client.fetch("global_market", run_id=RUN_ID)
    finally:
        http_client.close()

    assert calls == 4
    assert captured.value.attempts == 4
    assert sleeps == [1.25, 2.25, 4.25]


def test_retry_after_numeric_is_a_minimum_delay() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "7"})

    client, http_client = make_client(handler, max_retries=1, sleep=sleeps.append)
    try:
        with pytest.raises(RateLimitError) as captured:
            client.fetch("global_market", run_id=RUN_ID)
    finally:
        http_client.close()

    assert calls == 2
    assert sleeps == [7.0]
    assert captured.value.retry_after == 7.0


def test_retry_after_parses_http_date_and_rejects_invalid_values() -> None:
    future = NOW + timedelta(seconds=30)
    header = future.strftime("%a, %d %b %Y %H:%M:%S GMT")

    assert parse_retry_after(header, NOW) == 30.0
    assert parse_retry_after("invalid", NOW) is None
    assert parse_retry_after("-1", NOW) is None
    assert parse_retry_after(None, NOW) is None


def test_transport_errors_retry_without_leaking_exception_text() -> None:
    stream = StringIO()
    logger = configure_json_logging(
        logger=logging.getLogger("cryptopulse.test.client.transport"),
        secrets=(API_KEY,),
        stream=stream,
    )
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(f"transport leaked {API_KEY}", request=request)

    client, http_client = make_client(
        handler,
        max_retries=1,
        sleep=sleeps.append,
        jitter=lambda: 0.0,
        logger=logger,
    )
    try:
        with pytest.raises(TransportError) as captured:
            client.fetch("global_market", run_id=RUN_ID)
    finally:
        http_client.close()

    assert calls == 2
    assert sleeps == [1.0]
    assert API_KEY not in str(captured.value)
    assert captured.value.__context__ is None
    assert API_KEY not in stream.getvalue()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, content=b'{"value":NaN}'),
    ],
)
def test_invalid_success_payload_is_not_requested_again(response: httpx.Response) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response

    client, http_client = make_client(handler)
    try:
        with pytest.raises(ResponseDecodeError) as captured:
            client.fetch("global_market", run_id=RUN_ID)
    finally:
        http_client.close()

    assert calls == 1
    assert captured.value.__context__ is None


def test_budget_hook_blocks_before_any_http_attempt() -> None:
    calls = 0

    class BudgetBlocked(RuntimeError):
        pass

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    def block(_context: object) -> None:
        raise BudgetBlocked

    client, http_client = make_client(handler, before_attempt=block)
    try:
        with pytest.raises(BudgetBlocked):
            client.fetch("global_market", run_id=RUN_ID)
    finally:
        http_client.close()

    assert calls == 0


def test_unexpected_status_and_invalid_identity_are_not_retried() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302)

    client, http_client = make_client(handler)
    try:
        with pytest.raises(UnexpectedStatusError):
            client.fetch("global_market", run_id=RUN_ID)
        with pytest.raises(ValueError, match="run_id"):
            client.fetch("global_market", run_id="invalid")
    finally:
        http_client.close()

    assert calls == 1


@pytest.mark.parametrize("max_retries", [-1, 4])
def test_client_rejects_retry_counts_outside_safety_limit(max_retries: int) -> None:
    with pytest.raises(ValueError, match="max_retries"):
        CoinGeckoClient(API_KEY, max_retries=max_retries)


@pytest.mark.parametrize("api_key", ["", "  ", "line\nbreak", "null\x00byte", "khóa"])
def test_client_rejects_blank_or_header_unsafe_api_keys(api_key: str) -> None:
    with pytest.raises(ValueError, match="API key"):
        CoinGeckoClient(api_key)


@pytest.mark.parametrize("backoff", [-1.0, float("nan"), float("inf")])
def test_client_rejects_unsafe_backoff_values(backoff: float) -> None:
    with pytest.raises(ValueError, match="backoff_seconds"):
        CoinGeckoClient(API_KEY, backoff_seconds=backoff)
