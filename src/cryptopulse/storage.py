"""Immutable local Bronze storage."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator, Mapping
from pathlib import Path

from cryptopulse.bronze import (
    BronzeEnvelope,
    BronzeMetadata,
    JsonValue,
    build_object_key,
    count_records,
    serialize_envelope,
)
from cryptopulse.coingecko import CoinGeckoResponse

DATA_DIR = Path("data")


def write_bronze(
    response: CoinGeckoResponse,
    job_name: str,
    *,
    data_dir: Path = DATA_DIR,
    scope_id: str | None = None,
) -> Path:
    """Persist one successful response with create-only semantics."""

    metadata = BronzeMetadata(
        source="coingecko",
        endpoint=response.endpoint,
        job_name=job_name,
        run_id=response.run_id,
        requested_at=response.requested_at,
        received_at=response.received_at,
        http_status=response.http_status,
        latency_ms=response.latency_ms,
        record_count=count_records(job_name, response.payload),
        parameters=response.parameters,
    )
    envelope = BronzeEnvelope(metadata=metadata, payload=response.payload)
    path = data_dir / build_object_key(metadata, response.request_id, scope_id=scope_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(serialize_envelope(envelope))
    return path


def iter_bronze(job_name: str, *, data_dir: Path = DATA_DIR) -> Iterator[Mapping[str, JsonValue]]:
    """Yield stored envelopes for one job in collection order."""

    root = data_dir / "bronze" / "coingecko"
    if not root.exists():
        return
    for path in sorted(root.rglob(f"{job_name}_*.json.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                document = json.load(stream)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot read Bronze object: {path}") from error
        if not isinstance(document, dict):
            raise ValueError(f"Bronze object must contain a JSON document: {path}")
        yield document
