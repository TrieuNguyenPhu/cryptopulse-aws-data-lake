"""Static CoinGecko job configuration and validation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from cryptopulse.config import COINGECKO_BASE_URL

type ParameterValue = str | int | float | bool | None

DEFAULT_JOB_CONFIG = Path(__file__).resolve().parents[2] / "config" / "jobs.json"

_ENDPOINTS = {
    "market_snapshot": ("market_snapshot", "/coins/markets"),
    "global_market": ("global_market", "/global"),
    "trending": ("trending", "/search/trending"),
    "categories": ("categories", "/coins/categories"),
    "exchanges": ("exchanges", "/exchanges"),
    "coin_list": ("coin_list", "/coins/list"),
    "coin_metadata": ("coin_metadata", "/coins/{id}"),
    "coin_ohlc": ("coin_ohlc", "/coins/{id}/ohlc"),
    "historical_backfill": ("historical_market", "/coins/{id}/market_chart"),
}

_PARAMETERS: dict[str, dict[str, ParameterValue]] = {
    "market_snapshot": {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d",
    },
    "global_market": {},
    "trending": {},
    "categories": {},
    "exchanges": {"per_page": 250, "page": 1},
    "coin_list": {"include_platform": False, "status": "active"},
    "coin_metadata": {
        "localization": False,
        "tickers": False,
        "market_data": False,
        "community_data": False,
        "developer_data": False,
        "sparkline": False,
    },
    "coin_ohlc": {"vs_currency": "usd", "days": "1"},
    "historical_backfill": {
        "vs_currency": "usd",
        "days": "365",
        "interval": "daily",
    },
}

_SAFE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class JobConfigError(ValueError):
    """Raised when job configuration differs from the reviewed API contract."""


class UnknownJobError(KeyError):
    """Raised for a job name that is not on the static allow-list."""


@dataclass(frozen=True, slots=True)
class JobDefinition:
    name: str
    entity: str
    endpoint: str
    schedule: str | None
    manual_only: bool
    criticality: str
    parameters: Mapping[str, ParameterValue]
    coin_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JobCatalog:
    schema_version: int
    base_url: str
    jobs: Mapping[str, JobDefinition]

    def get(self, name: str) -> JobDefinition:
        try:
            return self.jobs[name]
        except KeyError as error:
            raise UnknownJobError(name) from error


def _object(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise JobConfigError(f"{field_name} must be a JSON object")
    return cast(dict[str, object], value)


def _parameters(value: object, job_name: str) -> dict[str, ParameterValue]:
    raw = _object(value, f"jobs.{job_name}.parameters")
    parsed: dict[str, ParameterValue] = {}
    for key, item in raw.items():
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise JobConfigError(f"unsupported parameter type for {job_name}.{key}")
        parsed[key] = item
    if parsed != _PARAMETERS[job_name]:
        raise JobConfigError(f"parameters for {job_name} differ from the reviewed contract")
    return parsed


def _coin_ids(value: object, job_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise JobConfigError(f"jobs.{job_name}.coin_ids must be a string array")
    coin_ids = tuple(cast(list[str], value))
    has_duplicates = len(set(coin_ids)) != len(coin_ids)
    has_invalid_id = any(not _SAFE_ID.fullmatch(item) for item in coin_ids)
    if has_duplicates or has_invalid_id:
        raise JobConfigError(f"jobs.{job_name}.coin_ids contains an invalid or duplicate ID")
    return coin_ids


def _job(name: str, value: object) -> JobDefinition:
    raw = _object(value, f"jobs.{name}")
    expected_entity, expected_endpoint = _ENDPOINTS[name]
    entity = raw.get("entity")
    endpoint = raw.get("endpoint")
    schedule = raw.get("schedule")
    manual_only = raw.get("manual_only")
    criticality = raw.get("criticality")

    if entity != expected_entity or endpoint != expected_endpoint:
        raise JobConfigError(f"endpoint or entity for {name} differs from the allow-list")
    if schedule is not None and not isinstance(schedule, str):
        raise JobConfigError(f"jobs.{name}.schedule must be a string or null")
    if not isinstance(manual_only, bool):
        raise JobConfigError(f"jobs.{name}.manual_only must be boolean")
    if manual_only != (name == "historical_backfill"):
        raise JobConfigError("historical_backfill must be the only manual job")
    if manual_only != (schedule is None):
        raise JobConfigError(f"manual/schedule mismatch for {name}")
    if criticality not in {"critical", "non-critical"}:
        raise JobConfigError(f"invalid criticality for {name}")

    return JobDefinition(
        name=name,
        entity=expected_entity,
        endpoint=expected_endpoint,
        schedule=schedule,
        manual_only=manual_only,
        criticality=criticality,
        parameters=MappingProxyType(_parameters(raw.get("parameters"), name)),
        coin_ids=_coin_ids(raw.get("coin_ids"), name),
    )


def load_job_catalog(path: Path = DEFAULT_JOB_CONFIG) -> JobCatalog:
    """Load and validate the reviewed static job catalog."""

    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise JobConfigError(f"cannot read job configuration: {path}") from error

    root = _object(loaded, "root")
    if root.get("schema_version") != 1:
        raise JobConfigError("unsupported jobs.json schema_version")
    if root.get("base_url") != COINGECKO_BASE_URL:
        raise JobConfigError("jobs.json must use the CoinGecko Demo API base URL")

    raw_jobs = _object(root.get("jobs"), "jobs")
    if set(raw_jobs) != set(_ENDPOINTS):
        raise JobConfigError("jobs.json job names differ from the allow-list")
    jobs = {name: _job(name, raw_jobs[name]) for name in _ENDPOINTS}

    top_ten = jobs["coin_ohlc"].coin_ids
    if len(top_ten) != 10 or jobs["historical_backfill"].coin_ids != top_ten:
        raise JobConfigError("OHLC and backfill must use the same ten coin IDs")
    metadata_ids = jobs["coin_metadata"].coin_ids
    if len(metadata_ids) != 20 or metadata_ids[:10] != top_ten:
        raise JobConfigError("metadata scope must be twenty IDs beginning with the top-ten scope")
    for name, job in jobs.items():
        if name not in {"coin_metadata", "coin_ohlc", "historical_backfill"} and job.coin_ids:
            raise JobConfigError(f"unscoped job {name} cannot define coin IDs")

    return JobCatalog(
        schema_version=1,
        base_url=COINGECKO_BASE_URL,
        jobs=MappingProxyType(jobs),
    )
