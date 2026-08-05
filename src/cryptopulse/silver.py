"""Bronze-to-Silver transforms for the first local MVP."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import duckdb

from cryptopulse.bronze import JsonValue
from cryptopulse.storage import DATA_DIR, iter_bronze

MARKET_COLUMNS = (
    "collected_at",
    "run_id",
    "source_updated_at",
    "coin_id",
    "symbol",
    "name",
    "image",
    "current_price",
    "change_1h",
    "change_24h",
    "change_7d",
    "market_cap",
    "market_cap_rank",
    "total_volume",
    "circulating_supply",
    "ath",
    "atl",
)


def build_silver(*, data_dir: Path = DATA_DIR) -> tuple[Path, Path]:
    """Rebuild deterministic Silver Parquet from immutable local Bronze files."""

    market_rows = [
        row
        for document in iter_bronze("market_snapshot", data_dir=data_dir)
        for row in _market_rows(document)
    ]
    global_rows = [
        _global_row(document) for document in iter_bronze("global_market", data_dir=data_dir)
    ]
    if not market_rows or not global_rows:
        raise FileNotFoundError("collect both market and global data before building Silver")

    silver_dir = data_dir / "silver"
    market_path = silver_dir / "market_snapshot.parquet"
    global_path = silver_dir / "global_market.parquet"
    silver_dir.mkdir(parents=True, exist_ok=True)

    # ponytail: rebuild is O(all Bronze files); switch to incremental partitions after a month
    # of local history makes refresh time measurable.
    with duckdb.connect() as connection:
        connection.execute(
            """
            CREATE TABLE market_snapshot (
                collected_at TIMESTAMPTZ,
                run_id VARCHAR,
                source_updated_at TIMESTAMPTZ,
                coin_id VARCHAR,
                symbol VARCHAR,
                name VARCHAR,
                image VARCHAR,
                current_price DOUBLE,
                change_1h DOUBLE,
                change_24h DOUBLE,
                change_7d DOUBLE,
                market_cap DOUBLE,
                market_cap_rank INTEGER,
                total_volume DOUBLE,
                circulating_supply DOUBLE,
                ath DOUBLE,
                atl DOUBLE
            )
            """
        )
        connection.executemany(
            f"INSERT INTO market_snapshot VALUES ({','.join('?' for _ in MARKET_COLUMNS)})",
            market_rows,
        )
        connection.execute(
            """
            CREATE TABLE global_market (
                collected_at TIMESTAMPTZ,
                run_id VARCHAR,
                source_updated_at TIMESTAMPTZ,
                active_cryptocurrencies INTEGER,
                total_market_cap_usd DOUBLE,
                total_volume_usd DOUBLE,
                btc_dominance DOUBLE,
                eth_dominance DOUBLE,
                market_cap_change_24h DOUBLE
            )
            """
        )
        connection.executemany("INSERT INTO global_market VALUES (?,?,?,?,?,?,?,?,?)", global_rows)
        _copy_parquet(connection, "market_snapshot", market_path)
        _copy_parquet(connection, "global_market", global_path)

    return market_path, global_path


def _market_rows(document: Mapping[str, JsonValue]) -> list[tuple[object, ...]]:
    metadata = _object(document.get("metadata"), "metadata")
    payload = document.get("payload")
    if not isinstance(payload, list):
        raise ValueError("market_snapshot Bronze payload must be an array")
    collected_at = _timestamp(metadata.get("received_at"), "metadata.received_at")
    run_id = _text(metadata.get("run_id"), "metadata.run_id")

    rows: list[tuple[object, ...]] = []
    for item in payload:
        coin = _object(item, "market coin")
        rows.append(
            (
                collected_at,
                run_id,
                _timestamp(coin.get("last_updated"), "last_updated"),
                _text(coin.get("id"), "id"),
                _text(coin.get("symbol"), "symbol").upper(),
                _text(coin.get("name"), "name"),
                _optional_text(coin.get("image")),
                _number(coin.get("current_price")),
                _number(coin.get("price_change_percentage_1h_in_currency")),
                _number(coin.get("price_change_percentage_24h_in_currency")),
                _number(coin.get("price_change_percentage_7d_in_currency")),
                _number(coin.get("market_cap")),
                _integer(coin.get("market_cap_rank")),
                _number(coin.get("total_volume")),
                _number(coin.get("circulating_supply")),
                _number(coin.get("ath")),
                _number(coin.get("atl")),
            )
        )
    return rows


def _global_row(document: Mapping[str, JsonValue]) -> tuple[object, ...]:
    metadata = _object(document.get("metadata"), "metadata")
    payload = _object(document.get("payload"), "global payload")
    data = _object(payload.get("data"), "global data")
    market_cap = _object(data.get("total_market_cap"), "total_market_cap")
    volume = _object(data.get("total_volume"), "total_volume")
    dominance = _object(data.get("market_cap_percentage"), "market_cap_percentage")
    updated_at = _integer(data.get("updated_at"))
    if updated_at is None:
        raise ValueError("global updated_at is required")
    return (
        _timestamp(metadata.get("received_at"), "metadata.received_at"),
        _text(metadata.get("run_id"), "metadata.run_id"),
        datetime.fromtimestamp(updated_at, tz=UTC),
        _integer(data.get("active_cryptocurrencies")),
        _number(market_cap.get("usd")),
        _number(volume.get("usd")),
        _number(dominance.get("btc")),
        _number(dominance.get("eth")),
        _number(data.get("market_cap_change_percentage_24h_usd")),
    )


def _copy_parquet(connection: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    temporary = path.with_suffix(".tmp")
    escaped = temporary.as_posix().replace("'", "''")
    connection.execute(f"COPY {table} TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    os.replace(temporary, path)


def _object(value: object, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return cast(Mapping[str, JsonValue], value)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("numeric market field has an invalid value")
    return float(value)


def _integer(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("integer market field has an invalid value")
    return value


def _timestamp(value: object, name: str) -> datetime:
    text = _text(value, name)
    try:
        instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO timestamp") from error
    if instant.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return instant
