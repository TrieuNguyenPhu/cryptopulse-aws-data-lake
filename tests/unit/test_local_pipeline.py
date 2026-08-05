from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import duckdb
import pytest
from streamlit.testing.v1 import AppTest

from cryptopulse.bronze import JsonValue
from cryptopulse.coingecko import CoinGeckoResponse
from cryptopulse.gold import build_gold
from cryptopulse.silver import build_silver
from cryptopulse.storage import iter_bronze, write_bronze

RUN_ID = "11111111-1111-4111-8111-111111111111"
MARKET_REQUEST_ID = "22222222-2222-4222-8222-222222222222"
GLOBAL_REQUEST_ID = "33333333-3333-4333-8333-333333333333"
COLLECTED_AT = datetime(2026, 8, 4, 0, 0, tzinfo=UTC)


def _response(
    payload: JsonValue,
    job_name: str,
    *,
    run_id: str = RUN_ID,
    request_id: str | None = None,
    received_at: datetime = COLLECTED_AT + timedelta(seconds=1),
) -> CoinGeckoResponse:
    is_market = job_name == "market_snapshot"
    return CoinGeckoResponse(
        payload=payload,
        endpoint="/coins/markets" if is_market else "/global",
        parameters={"vs_currency": "usd"} if is_market else {},
        run_id=run_id,
        request_id=request_id or (MARKET_REQUEST_ID if is_market else GLOBAL_REQUEST_ID),
        requested_at=COLLECTED_AT,
        received_at=received_at,
        http_status=200,
        latency_ms=1000,
    )


def _seed_bronze(
    data_dir: Path,
    load_fixture: Callable[[str], Any],
) -> tuple[Path, Path]:
    market = cast(JsonValue, load_fixture("market_snapshot"))
    global_market = cast(JsonValue, load_fixture("global_market"))
    return (
        write_bronze(_response(market, "market_snapshot"), "market_snapshot", data_dir=data_dir),
        write_bronze(
            _response(global_market, "global_market"),
            "global_market",
            data_dir=data_dir,
        ),
    )


def test_local_pipeline_writes_immutable_bronze_and_builds_analytics(
    tmp_path: Path,
    load_fixture: Callable[[str], Any],
) -> None:
    market_bronze, global_bronze = _seed_bronze(tmp_path, load_fixture)

    assert market_bronze.suffixes == [".json", ".gz"]
    assert global_bronze.exists()
    assert len(list(iter_bronze("market_snapshot", data_dir=tmp_path))) == 1
    with pytest.raises(FileExistsError):
        write_bronze(
            _response(cast(JsonValue, load_fixture("market_snapshot")), "market_snapshot"),
            "market_snapshot",
            data_dir=tmp_path,
        )

    market_silver, global_silver = build_silver(data_dir=tmp_path)
    gold = build_gold(data_dir=tmp_path)

    with duckdb.connect() as connection:
        market = connection.execute(
            "SELECT symbol, market_cap_rank FROM read_parquet(?) ORDER BY market_cap_rank",
            [str(market_silver)],
        ).fetchall()
        global_values = connection.execute(
            "SELECT active_cryptocurrencies, btc_dominance FROM read_parquet(?)",
            [str(global_silver)],
        ).fetchone()
        overview = connection.execute(
            """
            SELECT gainers, losers, tracked_coins, market_breadth, volume_to_market_cap
            FROM read_parquet(?)
            """,
            [str(gold)],
        ).fetchone()

    assert market == [("BTC", 1), ("ETH", 2)]
    assert global_values == (17_000, 55.5)
    assert overview is not None
    assert overview[:4] == (2, 0, 2, 1.0)
    assert overview[4] == pytest.approx(0.034)


def test_gold_uses_one_latest_market_batch(
    tmp_path: Path,
    load_fixture: Callable[[str], Any],
) -> None:
    _seed_bronze(tmp_path, load_fixture)
    newer_market = load_fixture("market_snapshot")
    for coin in newer_market:
        coin["price_change_percentage_24h_in_currency"] = -1.0
    response = _response(
        cast(JsonValue, newer_market),
        "market_snapshot",
        run_id="44444444-4444-4444-8444-444444444444",
        request_id="55555555-5555-4555-8555-555555555555",
        received_at=COLLECTED_AT + timedelta(minutes=1),
    )
    write_bronze(response, "market_snapshot", data_dir=tmp_path)

    market_silver, _ = build_silver(data_dir=tmp_path)
    gold = build_gold(data_dir=tmp_path)

    with duckdb.connect() as connection:
        breadth = connection.execute(
            "SELECT gainers, losers, tracked_coins FROM read_parquet(?)",
            [str(gold)],
        ).fetchone()
    assert breadth == (0, 2, 2)

    from cryptopulse.dashboard import _screen

    screened = _screen(
        market_silver,
        search="",
        rank=250,
        min_price=0,
        min_cap=0,
        min_volume=0,
        min_change=-100,
        max_change=100,
    )
    assert len(screened.index) == 2
    assert screened["24h %"].tolist() == [-1.0, -1.0]


def test_build_requires_both_mvp_sources(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="market and global"):
        build_silver(data_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="Silver"):
        build_gold(data_dir=tmp_path)


def test_invalid_bronze_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "bronze" / "coingecko" / "market_snapshot_bad.json.gz"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not-gzip")

    with pytest.raises(ValueError, match="cannot read Bronze"):
        list(iter_bronze("market_snapshot", data_dir=tmp_path))


def test_dashboard_opens_overview_and_screener_from_local_data(
    tmp_path: Path,
    load_fixture: Callable[[str], Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_bronze(tmp_path, load_fixture)
    build_silver(data_dir=tmp_path)
    build_gold(data_dir=tmp_path)
    monkeypatch.setenv("CRYPTOPULSE_DATA_DIR", str(tmp_path))
    dashboard = Path(__file__).parents[2] / "src" / "cryptopulse" / "dashboard.py"

    app = AppTest.from_file(str(dashboard)).run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "Tổng quan thị trường"
    app.segmented_control[0].set_value("Bộ lọc coin").run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "Bộ lọc coin"
