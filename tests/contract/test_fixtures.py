from __future__ import annotations

import json
from pathlib import Path

import pytest

from cryptopulse.bronze import count_records
from cryptopulse.jobs import load_job_catalog

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures"
FIXTURE_BY_JOB = {
    "market_snapshot": "market_snapshot.json",
    "global_market": "global_market.json",
    "trending": "trending.json",
    "categories": "categories.json",
    "exchanges": "exchanges.json",
    "coin_list": "coin_list.json",
    "coin_metadata": "coin_metadata.json",
    "coin_ohlc": "coin_ohlc.json",
    "historical_backfill": "historical_market.json",
}


@pytest.mark.contract
@pytest.mark.parametrize(("job_name", "fixture_name"), FIXTURE_BY_JOB.items())
def test_each_job_has_a_countable_sanitized_fixture(job_name: str, fixture_name: str) -> None:
    text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
    payload = json.loads(text)

    assert count_records(job_name, payload) > 0
    assert "x-cg-demo-api-key" not in text.lower()
    assert "x_cg_demo_api_key" not in text.lower()
    assert "fixture-secret" not in text


@pytest.mark.contract
def test_configured_coin_ids_exist_in_coin_list_fixture() -> None:
    coin_list = json.loads((FIXTURE_DIR / "coin_list.json").read_text(encoding="utf-8"))
    fixture_ids = {coin["id"] for coin in coin_list}
    catalog = load_job_catalog()

    assert len(fixture_ids) == 20
    assert set(catalog.get("coin_metadata").coin_ids) == fixture_ids
    assert set(catalog.get("coin_ohlc").coin_ids) <= fixture_ids
    assert set(catalog.get("historical_backfill").coin_ids) <= fixture_ids


@pytest.mark.contract
def test_market_fixture_contains_requested_change_windows() -> None:
    payload = json.loads((FIXTURE_DIR / "market_snapshot.json").read_text(encoding="utf-8"))
    required = {
        "price_change_percentage_1h_in_currency",
        "price_change_percentage_24h_in_currency",
        "price_change_percentage_7d_in_currency",
    }
    assert all(required <= set(coin) for coin in payload)
