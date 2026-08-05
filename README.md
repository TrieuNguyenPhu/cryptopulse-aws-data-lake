# CryptoPulse

CryptoPulse is a local crypto market data pipeline and read-only dashboard. The implemented MVP
collects CoinGecko Demo responses, preserves immutable Bronze files, builds Parquet datasets with
DuckDB, and serves Market Overview plus Coin Screener in Streamlit.

It is not real-time software, a trading bot, or investment advice.

## Pipeline

```text
CoinGecko Demo API
        ↓ manual collection
Bronze JSON.gz
        ↓ deterministic build
Silver Parquet
        ↓ analytics
Gold Parquet
        ↓ local queries
DuckDB + Streamlit
```

Only `/coins/markets` and `/global` feed the first dashboard slice. Category filters, coin detail,
trending analytics, scheduling, authentication, and AWS deployment remain out of scope until a
real consumer requires them.

## Setup

Use Python 3.14. The project virtual environment is the only Python runtime needed.

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `COINGECKO_API_KEY` in the ignored `.env` file, then collect both MVP endpoints and open the
dashboard:

```powershell
python -m cryptopulse collect all
python -m cryptopulse dashboard
```

The collection command automatically rebuilds Silver and Gold once both Bronze sources exist.
You can also run each step explicitly:

```powershell
python -m cryptopulse collect market
python -m cryptopulse collect global
python -m cryptopulse build
python -m cryptopulse dashboard
```

Use `--data-dir <path>` before the subcommand to select another local data root. Collection is
manual; the dashboard never calls CoinGecko and does not need the API key.

## Repository layout

```text
src/cryptopulse/
├── cli.py          # collect, build, dashboard commands
├── jobs.py         # allow-listed CoinGecko requests
├── coingecko.py    # HTTP client and bounded retry policy
├── bronze.py       # immutable envelope contract
├── storage.py      # local Bronze persistence
├── silver.py       # Bronze → Parquet normalization
├── gold.py         # market overview analytics
├── dashboard.py    # Streamlit Overview and Screener
├── config.py       # environment settings
└── logging.py      # secret-safe JSON logs
```

Runtime output lives under ignored `data/bronze`, `data/silver`, and `data/gold`. There are no
speculative `services`, `repositories`, `ports`, `adapters`, or scheduler packages.

## Quality gate

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest --cov=cryptopulse --cov-report=term-missing
python -m build
```

Normal tests use sanitized fixtures and block external networking. A live integration requires
both `CRYPTOPULSE_RUN_INTEGRATION=1` and `CRYPTOPULSE_ALLOW_LIVE_API=1`.

Data is provided by [CoinGecko](https://www.coingecko.com/en/api).
