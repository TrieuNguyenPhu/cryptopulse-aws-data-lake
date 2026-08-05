"""Read-only Streamlit dashboard for local Silver and Gold data."""

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

import duckdb
import streamlit as st

from cryptopulse.storage import DATA_DIR

st.set_page_config(page_title="CryptoPulse", page_icon=None, layout="wide")
st.html(
    """
    <!--
    THESIS: CryptoPulse is a chain of operational decisions, not a generic crypto metric-card dashboard.
    OWN-WORLD: Matte black and warm off-white surfaces; terminal yellow belongs only to direction, focus, and warning; framed sign bands and dense tables share one grammar.
    STORY: Verify local provenance, choose Overview or Screener, narrow the market, and inspect traceable results.
    FIRST VIEWPORT: A slim provenance band, two wide destinations, route-strip filters, one breadth board, then the full-width screener table.
    FORM: Terminal Wayfinding, selected grounded direction 6, seed 49302c09.
    FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
    -->
    """
)

_CSS = """
<style>
:root {
  --route-yellow: #f7c948;
  --ink: #111111;
  --paper: #f4f1e8;
  --surface: #ffffff;
  --muted: #5f625f;
  --line: #c9c7be;
}

[data-testid="stAppViewContainer"] { background: var(--paper); color: var(--ink); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 1480px; padding: 1.4rem 2rem 3rem; }
html, body, [class*="st-"] { font-family: "Segoe UI", Frutiger, Arial, sans-serif; }
h1, h2, h3 { color: var(--ink); letter-spacing: -0.025em; }
h1 { font-size: clamp(2rem, 3vw, 2.75rem); margin: 0; }

.provenance {
  align-items: center;
  background: var(--ink);
  color: white;
  display: grid;
  gap: 1rem;
  grid-template-columns: minmax(12rem, 1fr) auto auto;
  margin-bottom: 0.75rem;
  padding: 0.75rem 1rem;
}
.brand { font-size: 1.45rem; font-weight: 750; letter-spacing: -0.03em; }
.local-state {
  background: var(--route-yellow);
  color: var(--ink);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  padding: 0.45rem 0.65rem;
  text-transform: uppercase;
}
.freshness { color: #f1efe7; font-variant-numeric: tabular-nums; }

[data-testid="stSegmentedControl"] { margin-bottom: 1rem; }
[data-testid="stSegmentedControl"] button {
  border-radius: 0 !important;
  min-height: 3.3rem;
  padding-inline: 1.25rem;
}
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
  background: var(--route-yellow);
  color: var(--ink);
}

.route-board {
  animation: board-in 420ms cubic-bezier(.2,.8,.2,1) both;
  background: var(--ink);
  border: 2px solid var(--route-yellow);
  border-radius: 12px;
  color: white;
  display: grid;
  gap: 0;
  grid-template-columns: repeat(4, 1fr);
  margin: 1rem 0 1.4rem;
  overflow: hidden;
}
.route-board > div { min-width: 0; padding: 1rem 1.2rem 1.1rem; }
.route-board > div + div { border-left: 1px solid #858585; }
.route-label { color: #e4e1d7; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
.route-value { color: var(--route-yellow); font-size: clamp(1.55rem, 3vw, 2.65rem); font-weight: 780; line-height: 1.1; margin-top: 0.35rem; }
.route-detail { color: #efede5; font-size: 0.85rem; margin-top: 0.4rem; }

.breadth-board { grid-template-columns: 1.2fr repeat(3, 1fr) 1.4fr; }
.breadth-heading { align-content: center; }
.positive { color: #45d483; }
.negative { color: #ff6973; }
.neutral { color: #dedbd2; }

.section-heading { align-items: baseline; display: flex; gap: 0.8rem; justify-content: space-between; margin: 2.2rem 0 0.8rem; }
.section-heading h2 { font-size: 1.65rem; margin: 0; }
.section-heading p { color: var(--muted); margin: 0; }

[data-testid="stForm"] {
  background: var(--ink);
  border: 2px solid var(--route-yellow);
  border-radius: 12px;
  padding: 0.8rem 1rem 0.25rem;
}
[data-testid="stForm"] label, [data-testid="stForm"] p { color: white !important; }
[data-testid="stForm"] [data-baseweb="input"] > div,
[data-testid="stForm"] [data-baseweb="select"] > div { border-radius: 4px; }
[data-testid="stFormSubmitButton"] button {
  background: var(--route-yellow);
  border: 0;
  border-radius: 4px;
  color: var(--ink);
  font-weight: 800;
  min-height: 2.7rem;
  width: 100%;
}
button:focus-visible, input:focus-visible, [role="slider"]:focus-visible {
  outline: 3px solid var(--route-yellow) !important;
  outline-offset: 2px;
}

[data-testid="stDataFrame"] {
  background: var(--surface);
  border-radius: 12px;
  box-shadow: 0 8px 22px rgba(17, 17, 17, 0.09);
  overflow: hidden;
}
.result-count { color: var(--muted); font-weight: 650; margin: 0.7rem 0; }
.footer-note { border-top: 1px solid var(--line); color: var(--muted); margin-top: 2rem; padding-top: 1rem; }
.footer-note a { color: var(--ink); font-weight: 750; }

@keyframes board-in {
  from { clip-path: inset(0 100% 0 0); }
  to { clip-path: inset(0 0 0 0); }
}
@media (prefers-reduced-motion: reduce) { .route-board { animation: none; } }
@media (max-width: 900px) {
  [data-testid="stMainBlockContainer"] { padding-inline: 1rem; }
  .provenance { grid-template-columns: 1fr auto; }
  .freshness { grid-column: 1 / -1; }
  .route-board, .breadth-board { grid-template-columns: 1fr; }
  .route-board > div + div { border-left: 0; border-top: 1px solid #858585; }
  .section-heading { align-items: flex-start; flex-direction: column; }
}
</style>
"""


def run() -> None:
    st.html(_CSS)
    data_dir = Path(os.environ.get("CRYPTOPULSE_DATA_DIR", DATA_DIR))
    market_path = data_dir / "silver" / "market_snapshot.parquet"
    global_path = data_dir / "silver" / "global_market.parquet"
    overview_path = data_dir / "gold" / "market_overview.parquet"

    timestamp = _latest_timestamp(overview_path) if overview_path.exists() else None
    _header(timestamp)
    destination = st.segmented_control(
        "Điểm đến",
        ["Tổng quan thị trường", "Bộ lọc coin"],
        default="Tổng quan thị trường",
        label_visibility="collapsed",
    )

    if not all(path.exists() for path in (market_path, global_path, overview_path)):
        _empty_state(data_dir)
        _footer()
        return

    try:
        if destination == "Bộ lọc coin":
            _screener(market_path, overview_path)
        else:
            _overview(market_path, global_path, overview_path)
    except (duckdb.Error, OSError, ValueError) as error:
        st.error(f"Không thể đọc dữ liệu local: {error}. Chạy lại `python -m cryptopulse build`.")
    _footer()


def _header(timestamp: Any | None) -> None:
    freshness = "Chưa có dữ liệu"
    if timestamp is not None:
        freshness = f"Thu thập gần nhất: {timestamp:%Y-%m-%d %H:%M UTC}"
    st.html(
        f"""
        <header class="provenance">
          <div class="brand">CryptoPulse</div>
          <div class="local-state">Local data</div>
          <div class="freshness">{html.escape(freshness)}</div>
        </header>
        """
    )


def _overview(market_path: Path, global_path: Path, overview_path: Path) -> None:
    overview = _row(overview_path)
    st.title("Tổng quan thị trường")
    st.caption("Snapshot local mới nhất từ `/global` và `/coins/markets`.")
    st.html(
        f"""
        <section class="route-board" aria-label="Chỉ số tổng quan thị trường">
          {_metric("Tổng vốn hóa", _money(overview["total_market_cap_usd"]), _percent(overview["market_cap_change_24h"]))}
          {_metric("Khối lượng 24h", _money(overview["total_volume_usd"]), f"Volume / Market cap: {_percent(overview['volume_to_market_cap'] * 100)}")}
          {_metric("BTC dominance", _percent(overview["btc_dominance"]), f"ETH: {_percent(overview['eth_dominance'])}")}
          {_metric("Crypto đang hoạt động", f"{overview['active_cryptocurrencies']:,.0f}", f"Theo dõi: {overview['tracked_coins']:,.0f} coin")}
        </section>
        """
    )
    _breadth(overview)

    st.html(
        '<div class="section-heading"><h2>Thị trường dẫn đầu</h2><p>Cùng một snapshot, hai góc nhìn.</p></div>'
    )
    cap_tab, volume_tab = st.tabs(["Theo vốn hóa", "Theo khối lượng 24h"])
    with cap_tab:
        st.dataframe(_top_coins(market_path, "market_cap"), hide_index=True, width="stretch")
    with volume_tab:
        st.dataframe(_top_coins(market_path, "total_volume"), hide_index=True, width="stretch")

    history = _history(global_path)
    st.html(
        '<div class="section-heading"><h2>Biến động toàn thị trường</h2><p>Lịch sử hình thành từ các lần polling manual.</p></div>'
    )
    if len(history.index) < 2:
        st.info("Cần ít nhất hai lần collection global để hiển thị đường lịch sử.")
    else:
        st.line_chart(history, x="Thời gian", y="Tổng vốn hóa (USD)", color="#111111")


def _screener(market_path: Path, overview_path: Path) -> None:
    overview = _row(overview_path)
    st.title("Bộ lọc coin")
    st.caption("Lọc trên snapshot top 250 đã lưu local; thao tác này không gọi CoinGecko.")

    with st.form("screener-filters"):
        search_col, rank_col, price_col, cap_col, volume_col = st.columns([1.4, 0.8, 1, 1, 1])
        search = search_col.text_input("Tìm coin", placeholder="Bitcoin, BTC…")
        rank = rank_col.selectbox("Xếp hạng", [10, 25, 50, 100, 250], index=4)
        min_price = price_col.number_input("Giá tối thiểu", min_value=0.0, value=0.0)
        min_cap = cap_col.number_input(
            "Vốn hóa tối thiểu", min_value=0.0, value=0.0, step=1_000_000.0
        )
        min_volume = volume_col.number_input(
            "Volume tối thiểu", min_value=0.0, value=0.0, step=1_000_000.0
        )
        change_24h = st.slider("Biến động 24h (%)", -100.0, 100.0, (-100.0, 100.0))
        st.form_submit_button("Áp dụng bộ lọc")

    _breadth(overview)
    results = _screen(
        market_path,
        search=search,
        rank=rank,
        min_price=min_price,
        min_cap=min_cap,
        min_volume=min_volume,
        min_change=change_24h[0],
        max_change=change_24h[1],
    )
    st.html(f'<p class="result-count">{len(results.index):,} coin phù hợp</p>')
    if results.empty:
        st.warning("Không có coin phù hợp. Giảm một hoặc nhiều ngưỡng lọc để tiếp tục.")
        return
    st.dataframe(
        results,
        hide_index=True,
        width="stretch",
        height=620,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.6f"),
            "1h %": st.column_config.NumberColumn(format="%.2f%%"),
            "24h %": st.column_config.NumberColumn(format="%.2f%%"),
            "7d %": st.column_config.NumberColumn(format="%.2f%%"),
            "Market cap": st.column_config.NumberColumn(format="$%.0f"),
            "24h volume": st.column_config.NumberColumn(format="$%.0f"),
            "Circulating supply": st.column_config.NumberColumn(format="%.0f"),
            "ATH": st.column_config.NumberColumn(format="$%.6f"),
            "ATL": st.column_config.NumberColumn(format="$%.6f"),
        },
    )


def _breadth(overview: Any) -> None:
    tracked = max(float(overview["tracked_coins"]), 1)
    st.html(
        f"""
        <section class="route-board breadth-board" aria-label="Độ rộng thị trường">
          <div class="breadth-heading"><div class="route-label">Độ rộng thị trường</div><div class="route-detail">Top coin trong snapshot</div></div>
          {_metric("Tăng", f"{overview['gainers']:,.0f}", _percent(overview["gainers"] / tracked * 100), "positive")}
          {_metric("Không đổi", f"{overview['unchanged']:,.0f}", _percent(overview["unchanged"] / tracked * 100), "neutral")}
          {_metric("Giảm", f"{overview['losers']:,.0f}", _percent(overview["losers"] / tracked * 100), "negative")}
          {_metric("Market breadth", _percent(overview["market_breadth"] * 100), "Tỷ lệ coin tăng")}
        </section>
        """
    )


def _empty_state(data_dir: Path) -> None:
    st.title("Chưa có dữ liệu để điều hướng")
    st.write("Thu thập hai endpoint MVP, sau đó build Silver và Gold.")
    st.code(
        f'python -m cryptopulse --data-dir "{data_dir}" collect all\n'
        f'python -m cryptopulse --data-dir "{data_dir}" dashboard',
        language="powershell",
    )
    st.info("Collection là manual. Dashboard không tự gọi API và không cần API key.")


def _footer() -> None:
    st.html(
        """
        <footer class="footer-note">
          <a href="https://www.coingecko.com/en/api" target="_blank" rel="noreferrer">Data provided by CoinGecko</a>
          · Dữ liệu local — không phải thời gian thực · Không phải lời khuyên đầu tư.
        </footer>
        """
    )


@st.cache_data(show_spinner=False)
def _row(path: Path) -> Any:
    with duckdb.connect() as connection:
        return (
            connection.execute(f"SELECT * FROM read_parquet('{_sql_path(path)}')").fetchdf().iloc[0]
        )


@st.cache_data(show_spinner=False)
def _latest_timestamp(path: Path) -> Any | None:
    if not path.exists():
        return None
    with duckdb.connect() as connection:
        row = connection.execute(
            f"SELECT collected_at FROM read_parquet('{_sql_path(path)}') LIMIT 1"
        ).fetchone()
        return row[0] if row is not None else None


@st.cache_data(show_spinner=False)
def _top_coins(path: Path, order_by: str) -> Any:
    if order_by not in {"market_cap", "total_volume"}:
        raise ValueError("unsupported top-coin order")
    return _query_dataframe(
        path,
        "market_snapshot",
        f"""
        WITH latest AS (
            SELECT *
            FROM market_snapshot
            QUALIFY dense_rank() OVER (ORDER BY collected_at DESC, run_id DESC) = 1
        )
        SELECT market_cap_rank AS Rank, symbol AS Symbol, name AS Coin,
               current_price AS Price, change_24h AS "24h %",
               market_cap AS "Market cap", total_volume AS "24h volume"
        FROM latest
        ORDER BY {order_by} DESC NULLS LAST
        LIMIT 10
        """,
    )


@st.cache_data(show_spinner=False)
def _history(path: Path) -> Any:
    return _query_dataframe(
        path,
        "global_market",
        """
        SELECT source_updated_at AS "Thời gian", total_market_cap_usd AS "Tổng vốn hóa (USD)"
        FROM global_market
        ORDER BY source_updated_at
        """,
    )


@st.cache_data(show_spinner=False)
def _screen(
    path: Path,
    *,
    search: str,
    rank: int,
    min_price: float,
    min_cap: float,
    min_volume: float,
    min_change: float,
    max_change: float,
) -> Any:
    pattern = f"%{search.strip()}%"
    return _query_dataframe(
        path,
        "market_snapshot",
        """
        WITH latest AS (
            SELECT *
            FROM market_snapshot
            QUALIFY dense_rank() OVER (ORDER BY collected_at DESC, run_id DESC) = 1
        )
        SELECT market_cap_rank AS Rank, symbol AS Symbol, name AS Coin,
               current_price AS Price, change_1h AS "1h %", change_24h AS "24h %",
               change_7d AS "7d %", market_cap AS "Market cap",
               total_volume AS "24h volume", circulating_supply AS "Circulating supply",
               ath AS ATH, atl AS ATL, source_updated_at AS "Last updated"
        FROM latest
        WHERE market_cap_rank <= ?
          AND coalesce(current_price, 0) >= ?
          AND coalesce(market_cap, 0) >= ?
          AND coalesce(total_volume, 0) >= ?
          AND coalesce(change_24h, 0) BETWEEN ? AND ?
          AND (? = '%%' OR name ILIKE ? OR symbol ILIKE ? OR coin_id ILIKE ?)
        ORDER BY market_cap_rank NULLS LAST
        """,
        [
            rank,
            min_price,
            min_cap,
            min_volume,
            min_change,
            max_change,
            pattern,
            pattern,
            pattern,
            pattern,
        ],
    )


def _query_dataframe(
    path: Path,
    view_name: str,
    query: str,
    parameters: list[object] | None = None,
) -> Any:
    if view_name not in {"market_snapshot", "global_market"}:
        raise ValueError("unsupported dataset")
    with duckdb.connect() as connection:
        connection.execute(
            f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{_sql_path(path)}')"
        )
        return connection.execute(query, parameters or []).fetchdf()


def _metric(label: str, value: str, detail: str, value_class: str = "") -> str:
    return (
        "<div>"
        f'<div class="route-label">{html.escape(label)}</div>'
        f'<div class="route-value {html.escape(value_class)}">{html.escape(value)}</div>'
        f'<div class="route-detail">{html.escape(detail)}</div>'
        "</div>"
    )


def _money(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if absolute >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if absolute >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.2f}"


def _percent(value: float) -> str:
    return f"{value:+.2f}%"


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


if __name__ == "__main__":
    run()
