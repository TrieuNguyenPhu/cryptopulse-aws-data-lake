"""Bronze envelope, serialization, counting, and object-key contracts."""

from __future__ import annotations

import gzip
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_LIST_JOBS = frozenset({"market_snapshot", "categories", "exchanges", "coin_list", "coin_ohlc"})
_OBJECT_JOBS = frozenset({"global_market", "coin_metadata"})
_SCOPED_JOBS = frozenset({"coin_metadata", "coin_ohlc", "historical_backfill"})
_ENTITY_BY_JOB = {"historical_backfill": "historical_market"}
_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_SAFE_SCOPE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SENSITIVE_PARAMETER_NAMES = frozenset(
    {"api_key", "authorization", "coingecko_api_key", "secret", "token", "x_cg_demo_api_key"}
)


class BronzeContractError(ValueError):
    """Raised when a Bronze object would violate the documented contract."""


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise BronzeContractError(f"{field_name} must be timezone-aware UTC")


def _uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise BronzeContractError(f"{field_name} must be a UUID") from error


@dataclass(frozen=True, slots=True)
class BronzeMetadata:
    source: str
    endpoint: str
    job_name: str
    run_id: str
    requested_at: datetime
    received_at: datetime
    http_status: int
    latency_ms: int
    record_count: int
    parameters: Mapping[str, JsonScalar]

    def __post_init__(self) -> None:
        if self.source != "coingecko":
            raise BronzeContractError("source must be coingecko")
        if not self.endpoint.startswith("/") or "?" in self.endpoint or "://" in self.endpoint:
            raise BronzeContractError("endpoint must be a safe path without a query string")
        if not _SAFE_NAME.fullmatch(self.job_name):
            raise BronzeContractError("job_name is invalid")
        _uuid(self.run_id, "run_id")
        _require_utc(self.requested_at, "requested_at")
        _require_utc(self.received_at, "received_at")
        if self.received_at < self.requested_at:
            raise BronzeContractError("received_at cannot precede requested_at")
        if self.http_status != 200:
            raise BronzeContractError("only HTTP 200 responses belong in Bronze")
        if self.latency_ms < 0 or self.record_count < 0:
            raise BronzeContractError("latency_ms and record_count must be non-negative")
        for key, value in self.parameters.items():
            if not isinstance(key, str):
                raise BronzeContractError("parameter names must be strings")
            normalized = key.lower().replace("-", "_")
            if normalized in _SENSITIVE_PARAMETER_NAMES:
                raise BronzeContractError("parameters cannot contain secrets")
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise BronzeContractError("parameter values must be JSON scalars")
            if isinstance(value, float) and not math.isfinite(value):
                raise BronzeContractError("parameter numbers must be finite")


@dataclass(frozen=True, slots=True)
class BronzeEnvelope:
    metadata: BronzeMetadata
    payload: JsonValue

    def __post_init__(self) -> None:
        actual_count = count_records(self.metadata.job_name, self.payload)
        if actual_count != self.metadata.record_count:
            raise BronzeContractError(
                f"record_count is {self.metadata.record_count}; payload contains {actual_count}"
            )


def count_records(job_name: str, payload: JsonValue) -> int:
    """Return the endpoint-specific Bronze record count."""

    if job_name in _LIST_JOBS:
        if not isinstance(payload, list):
            raise BronzeContractError(f"{job_name} payload must be an array")
        return len(payload)
    if job_name in _OBJECT_JOBS:
        if not isinstance(payload, dict):
            raise BronzeContractError(f"{job_name} payload must be an object")
        return 1
    if job_name == "trending":
        if not isinstance(payload, dict):
            raise BronzeContractError("trending payload must be an object")
        arrays = [payload.get(name) for name in ("coins", "nfts", "categories")]
        if not all(isinstance(items, list) for items in arrays):
            raise BronzeContractError("trending payload must contain three arrays")
        return sum(len(cast(list[JsonValue], items)) for items in arrays)
    if job_name == "historical_backfill":
        if not isinstance(payload, dict):
            raise BronzeContractError("historical_backfill payload must be an object")
        timestamps: set[int | float] = set()
        for series_name in ("prices", "market_caps", "total_volumes"):
            series = payload.get(series_name)
            if not isinstance(series, list):
                raise BronzeContractError(f"historical payload is missing {series_name}")
            for point in series:
                if (
                    not isinstance(point, list)
                    or len(point) < 2
                    or not isinstance(point[0], (int, float))
                ):
                    raise BronzeContractError(f"invalid point in historical {series_name}")
                timestamps.add(point[0])
        return len(timestamps)
    raise BronzeContractError(f"unsupported job_name: {job_name}")


def serialize_envelope(envelope: BronzeEnvelope) -> bytes:
    """Serialize a Bronze envelope to deterministic gzip-compressed UTF-8 JSON."""

    metadata = envelope.metadata
    document: dict[str, JsonValue] = {
        "metadata": {
            "source": metadata.source,
            "endpoint": metadata.endpoint,
            "job_name": metadata.job_name,
            "run_id": metadata.run_id,
            "requested_at": _timestamp(metadata.requested_at),
            "received_at": _timestamp(metadata.received_at),
            "http_status": metadata.http_status,
            "latency_ms": metadata.latency_ms,
            "record_count": metadata.record_count,
            "parameters": dict(metadata.parameters),
        },
        "payload": envelope.payload,
    }
    try:
        raw = json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise BronzeContractError("envelope contains a non-JSON value") from error
    return gzip.compress(raw, compresslevel=9, mtime=0)


def build_object_key(
    metadata: BronzeMetadata,
    request_id: str,
    *,
    scope_id: str | None = None,
) -> str:
    """Build a unique, partitioned Bronze key without high-cardinality ID partitions."""

    canonical_run_id = str(_uuid(metadata.run_id, "run_id"))
    canonical_request_id = str(_uuid(request_id, "request_id"))
    is_scoped = metadata.job_name in _SCOPED_JOBS
    if is_scoped and (scope_id is None or not _SAFE_SCOPE.fullmatch(scope_id)):
        raise BronzeContractError(f"{metadata.job_name} requires a safe scope_id")
    if not is_scoped and scope_id is not None:
        raise BronzeContractError(f"{metadata.job_name} does not accept scope_id")

    instant = metadata.requested_at.astimezone(UTC)
    entity = _ENTITY_BY_JOB.get(metadata.job_name, metadata.job_name)
    filename_parts = [metadata.job_name]
    if scope_id is not None:
        filename_parts.append(scope_id)
    filename_parts.extend(
        [instant.strftime("%Y%m%dT%H%M%SZ"), canonical_run_id, canonical_request_id]
    )
    filename = "_".join(filename_parts) + ".json.gz"
    return (
        f"bronze/coingecko/entity={entity}/year={instant:%Y}/month={instant:%m}/"
        f"day={instant:%d}/hour={instant:%H}/{filename}"
    )


def _timestamp(value: datetime) -> str:
    _require_utc(value, "timestamp")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
