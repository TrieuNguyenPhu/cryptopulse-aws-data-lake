from __future__ import annotations

import copy
import gzip
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from cryptopulse.bronze import (
    BronzeContractError,
    BronzeEnvelope,
    BronzeMetadata,
    build_object_key,
    count_records,
    serialize_envelope,
)

RUN_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"


def metadata(job_name: str, endpoint: str, record_count: int) -> BronzeMetadata:
    return BronzeMetadata(
        source="coingecko",
        endpoint=endpoint,
        job_name=job_name,
        run_id=RUN_ID,
        requested_at=datetime(2026, 8, 4, 0, 0, tzinfo=UTC),
        received_at=datetime(2026, 8, 4, 0, 0, 0, 250000, tzinfo=UTC),
        http_status=200,
        latency_ms=250,
        record_count=record_count,
        parameters={"vs_currency": "usd"},
    )


def test_serialize_envelope_preserves_payload_and_required_shape(
    load_fixture: Callable[[str], Any],
) -> None:
    payload = load_fixture("market_snapshot")
    original = copy.deepcopy(payload)
    envelope = BronzeEnvelope(metadata("market_snapshot", "/coins/markets", len(payload)), payload)

    first = serialize_envelope(envelope)
    second = serialize_envelope(envelope)
    document = json.loads(gzip.decompress(first))

    assert first == second
    assert payload == original
    assert document["payload"] == original
    assert set(document) == {"metadata", "payload"}
    assert set(document["metadata"]) == {
        "source",
        "endpoint",
        "job_name",
        "run_id",
        "requested_at",
        "received_at",
        "http_status",
        "latency_ms",
        "record_count",
        "parameters",
    }
    assert document["metadata"]["requested_at"] == "2026-08-04T00:00:00.000000Z"


def test_object_key_matches_partition_and_uniqueness_contract() -> None:
    value = metadata("coin_ohlc", "/coins/bitcoin/ohlc", 2)

    key = build_object_key(value, REQUEST_ID, scope_id="bitcoin")

    assert key == (
        "bronze/coingecko/entity=coin_ohlc/year=2026/month=08/day=04/hour=00/"
        "coin_ohlc_bitcoin_20260804T000000Z_"
        f"{RUN_ID}_{REQUEST_ID}.json.gz"
    )
    assert "coin_id=" not in key


def test_backfill_uses_historical_market_entity() -> None:
    value = metadata("historical_backfill", "/coins/bitcoin/market_chart", 2)
    key = build_object_key(value, REQUEST_ID, scope_id="bitcoin")
    assert "entity=historical_market/" in key


@pytest.mark.parametrize(
    ("job_name", "fixture_name", "expected"),
    [
        ("market_snapshot", "market_snapshot", 2),
        ("global_market", "global_market", 1),
        ("trending", "trending", 3),
        ("categories", "categories", 1),
        ("exchanges", "exchanges", 1),
        ("coin_list", "coin_list", 20),
        ("coin_metadata", "coin_metadata", 1),
        ("coin_ohlc", "coin_ohlc", 2),
        ("historical_backfill", "historical_market", 2),
    ],
)
def test_record_count_rules(
    load_fixture: Callable[[str], Any], job_name: str, fixture_name: str, expected: int
) -> None:
    assert count_records(job_name, load_fixture(fixture_name)) == expected


def test_envelope_rejects_record_count_mismatch(load_fixture: Callable[[str], Any]) -> None:
    payload = load_fixture("market_snapshot")
    with pytest.raises(BronzeContractError, match="record_count"):
        BronzeEnvelope(metadata("market_snapshot", "/coins/markets", 250), payload)


def test_metadata_rejects_non_success_and_secret_parameter() -> None:
    values = {
        "source": "coingecko",
        "endpoint": "/global",
        "job_name": "global_market",
        "run_id": RUN_ID,
        "requested_at": datetime(2026, 8, 4, tzinfo=UTC),
        "received_at": datetime(2026, 8, 4, 0, 0, 1, tzinfo=UTC),
        "latency_ms": 1000,
        "record_count": 1,
    }
    with pytest.raises(BronzeContractError, match="HTTP 200"):
        BronzeMetadata(http_status=429, parameters={}, **values)
    with pytest.raises(BronzeContractError, match="secrets"):
        BronzeMetadata(
            http_status=200,
            parameters={"x-cg-demo-api-key": "fixture-secret"},
            **values,
        )


@pytest.mark.parametrize(
    "parameters",
    [
        {1: "usd"},
        {"ids": ["bitcoin"]},
        {"price": float("nan")},
        {"price": float("inf")},
    ],
)
def test_metadata_rejects_non_json_or_non_finite_parameters(parameters: Any) -> None:
    with pytest.raises(BronzeContractError, match="parameter"):
        BronzeMetadata(
            source="coingecko",
            endpoint="/global",
            job_name="global_market",
            run_id=RUN_ID,
            requested_at=datetime(2026, 8, 4, tzinfo=UTC),
            received_at=datetime(2026, 8, 4, 0, 0, 1, tzinfo=UTC),
            http_status=200,
            latency_ms=1000,
            record_count=1,
            parameters=parameters,
        )


def test_serializer_rejects_non_finite_payload_number() -> None:
    envelope = BronzeEnvelope(
        metadata("market_snapshot", "/coins/markets", 1),
        [{"current_price": float("nan")}],
    )

    with pytest.raises(BronzeContractError, match="non-JSON"):
        serialize_envelope(envelope)


def test_object_key_enforces_scope_rules() -> None:
    scoped = metadata("coin_metadata", "/coins/bitcoin", 1)
    unscoped = metadata("global_market", "/global", 1)

    with pytest.raises(BronzeContractError, match="requires"):
        build_object_key(scoped, REQUEST_ID)
    with pytest.raises(BronzeContractError, match="does not accept"):
        build_object_key(unscoped, REQUEST_ID, scope_id="bitcoin")


def test_unknown_record_count_job_is_rejected() -> None:
    with pytest.raises(BronzeContractError, match="unsupported"):
        count_records("unknown", {})
