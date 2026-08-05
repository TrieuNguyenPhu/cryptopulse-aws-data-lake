"""Reviewed CoinGecko collection jobs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

type ParameterValue = str | int | float | bool | None
type Criticality = Literal["critical", "non-critical"]

TOP_COIN_IDS = (
    "bitcoin",
    "ethereum",
    "tether",
    "binancecoin",
    "solana",
    "usd-coin",
    "ripple",
    "dogecoin",
    "cardano",
    "avalanche-2",
    "tron",
    "chainlink",
    "polkadot",
    "bitcoin-cash",
    "stellar",
    "shiba-inu",
    "litecoin",
    "wrapped-bitcoin",
    "sui",
    "near",
)


class UnknownJobError(KeyError):
    """Raised when a job is not in the reviewed catalog."""


@dataclass(frozen=True, slots=True)
class JobDefinition:
    name: str
    entity: str
    endpoint: str
    schedule: str | None
    criticality: Criticality
    parameters: Mapping[str, ParameterValue]
    coin_ids: tuple[str, ...] = ()

    @property
    def manual_only(self) -> bool:
        return self.schedule is None


@dataclass(frozen=True, slots=True)
class JobCatalog:
    jobs: Mapping[str, JobDefinition]

    def get(self, name: str) -> JobDefinition:
        try:
            return self.jobs[name]
        except KeyError as error:
            raise UnknownJobError(name) from error


def _job(
    name: str,
    endpoint: str,
    schedule: str | None,
    *,
    entity: str | None = None,
    criticality: Criticality = "non-critical",
    parameters: Mapping[str, ParameterValue] = MappingProxyType({}),
    coin_ids: tuple[str, ...] = (),
) -> JobDefinition:
    return JobDefinition(
        name=name,
        entity=entity or name,
        endpoint=endpoint,
        schedule=schedule,
        criticality=criticality,
        parameters=MappingProxyType(dict(parameters)),
        coin_ids=coin_ids,
    )


_JOBS = (
    _job(
        "market_snapshot",
        "/coins/markets",
        "cron(0/10 * * * ? *)",
        criticality="critical",
        parameters={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": False,
            "price_change_percentage": "1h,24h,7d",
        },
    ),
    _job("global_market", "/global", "cron(2 * * * ? *)", criticality="critical"),
    _job("trending", "/search/trending", "cron(4 * * * ? *)"),
    _job("categories", "/coins/categories", "cron(6 0/6 * * ? *)"),
    _job(
        "exchanges",
        "/exchanges",
        "cron(10 1 * * ? *)",
        parameters={"per_page": 250, "page": 1},
    ),
    _job(
        "coin_list",
        "/coins/list",
        "cron(15 1 * * ? *)",
        parameters={"include_platform": False, "status": "active"},
    ),
    _job(
        "coin_metadata",
        "/coins/{id}",
        "cron(20 2 ? * SUN *)",
        parameters={
            "localization": False,
            "tickers": False,
            "market_data": False,
            "community_data": False,
            "developer_data": False,
            "sparkline": False,
        },
        coin_ids=TOP_COIN_IDS,
    ),
    _job(
        "coin_ohlc",
        "/coins/{id}/ohlc",
        "cron(45 0 * * ? *)",
        parameters={"vs_currency": "usd", "days": "1"},
        coin_ids=TOP_COIN_IDS[:10],
    ),
    _job(
        "historical_backfill",
        "/coins/{id}/market_chart",
        None,
        entity="historical_market",
        parameters={"vs_currency": "usd", "days": "365", "interval": "daily"},
        coin_ids=TOP_COIN_IDS[:10],
    ),
)

JOB_CATALOG = JobCatalog(MappingProxyType({job.name: job for job in _JOBS}))
