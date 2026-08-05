import pytest

from cryptopulse.jobs import JOB_CATALOG, UnknownJobError


def test_job_catalog_contains_reviewed_contract() -> None:
    assert len(JOB_CATALOG.jobs) == 9
    assert JOB_CATALOG.get("market_snapshot").parameters["per_page"] == 250
    assert JOB_CATALOG.get("historical_backfill").manual_only is True
    assert JOB_CATALOG.get("historical_backfill").schedule is None
    assert len(JOB_CATALOG.get("coin_metadata").coin_ids) == 20
    assert JOB_CATALOG.get("coin_ohlc").coin_ids == JOB_CATALOG.get("historical_backfill").coin_ids


def test_job_catalog_rejects_unknown_job_lookup() -> None:
    with pytest.raises(UnknownJobError):
        JOB_CATALOG.get("not_a_job")
