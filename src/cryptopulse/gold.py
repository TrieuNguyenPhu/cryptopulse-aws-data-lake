"""Silver-to-Gold market overview analytics."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

from cryptopulse.storage import DATA_DIR


def build_gold(*, data_dir: Path = DATA_DIR) -> Path:
    """Build the current market-overview Gold row from Silver datasets."""

    market_path = data_dir / "silver" / "market_snapshot.parquet"
    global_path = data_dir / "silver" / "global_market.parquet"
    if not market_path.exists() or not global_path.exists():
        raise FileNotFoundError("build Silver before building Gold")

    gold_dir = data_dir / "gold"
    output = gold_dir / "market_overview.parquet"
    temporary = output.with_suffix(".tmp")
    gold_dir.mkdir(parents=True, exist_ok=True)

    with duckdb.connect() as connection:
        connection.execute(
            f"""
            COPY (
                WITH latest_market AS (
                    SELECT *
                    FROM read_parquet('{_sql_path(market_path)}')
                    QUALIFY dense_rank() OVER (
                        ORDER BY collected_at DESC, run_id DESC
                    ) = 1
                ),
                latest_global AS (
                    SELECT *
                    FROM read_parquet('{_sql_path(global_path)}')
                    QUALIFY dense_rank() OVER (
                        ORDER BY collected_at DESC, run_id DESC
                    ) = 1
                ),
                breadth AS (
                    SELECT
                        count(*) FILTER (WHERE change_24h > 0) AS gainers,
                        count(*) FILTER (WHERE change_24h < 0) AS losers,
                        count(*) FILTER (WHERE change_24h = 0 OR change_24h IS NULL) AS unchanged,
                        count(*) AS tracked_coins
                    FROM latest_market
                )
                SELECT
                    g.collected_at,
                    g.source_updated_at,
                    g.active_cryptocurrencies,
                    g.total_market_cap_usd,
                    g.total_volume_usd,
                    g.btc_dominance,
                    g.eth_dominance,
                    g.market_cap_change_24h,
                    g.total_volume_usd / nullif(g.total_market_cap_usd, 0)
                        AS volume_to_market_cap,
                    breadth.gainers,
                    breadth.losers,
                    breadth.unchanged,
                    breadth.tracked_coins,
                    breadth.gainers / nullif(breadth.tracked_coins, 0)::DOUBLE AS market_breadth
                FROM latest_global AS g
                CROSS JOIN breadth
            ) TO '{_sql_path(temporary)}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
    os.replace(temporary, output)
    return output


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")
