from __future__ import annotations

import json
from pathlib import Path

import pytest

from cryptopulse.jobs import (
    DEFAULT_JOB_CONFIG,
    JobConfigError,
    UnknownJobError,
    load_job_catalog,
)


def test_job_catalog_loads_reviewed_contract() -> None:
    catalog = load_job_catalog()

    assert catalog.schema_version == 1
    assert len(catalog.jobs) == 9
    assert catalog.get("market_snapshot").parameters["per_page"] == 250
    assert catalog.get("historical_backfill").manual_only is True
    assert catalog.get("historical_backfill").schedule is None
    assert len(catalog.get("coin_metadata").coin_ids) == 20
    assert catalog.get("coin_ohlc").coin_ids == catalog.get("historical_backfill").coin_ids


def test_job_catalog_rejects_unknown_job_lookup() -> None:
    with pytest.raises(UnknownJobError):
        load_job_catalog().get("not_a_job")


def test_job_catalog_rejects_unreviewed_parameter(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_JOB_CONFIG.read_text(encoding="utf-8"))
    document["jobs"]["coin_ohlc"]["parameters"]["days"] = "2"
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(JobConfigError, match="reviewed contract"):
        load_job_catalog(path)


def test_job_catalog_rejects_pro_api_host(tmp_path: Path) -> None:
    document = json.loads(DEFAULT_JOB_CONFIG.read_text(encoding="utf-8"))
    document["base_url"] = "https://pro-api.coingecko.com/api/v3"
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(JobConfigError, match="Demo API"):
        load_job_catalog(path)


def test_job_catalog_wraps_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "jobs.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(JobConfigError, match="cannot read"):
        load_job_catalog(path)
