# CryptoPulse — Serverless Crypto Market Data Lake on AWS

CryptoPulse is an educational data-engineering project that collects CoinGecko Demo API
responses into an immutable Bronze data contract. It is not a trading bot and does not provide
investment advice.

The repository currently contains the tested foundation: typed settings, a reviewed job catalog,
secret-safe JSON logging, deterministic gzip serialization, and a synchronous HTTP client with
bounded retries. Local storage, transformations, analytics, and AWS adapters are planned but are
not implemented or deployed.

## Repository layout

```text
.
├── src/cryptopulse/       # application and domain code
├── tests/
│   ├── unit/              # fast isolated behavior tests
│   ├── contract/          # fixture and data-contract tests
│   ├── integration/       # explicit opt-in external checks
│   ├── glue/              # Glue runtime boundary check
│   └── fixtures/          # sanitized CoinGecko responses
├── docs/
│   ├── architecture.md    # local and deferred AWS design
│   └── data-model.md      # Bronze, Silver, and Gold contracts
└── pyproject.toml         # package, dependencies, and tool configuration
```

The project uses the standard Python `src` layout so tests exercise the installed package rather
than importing an accidental copy from the repository root.

## Development

Use Python 3.14 for the application. AWS Glue 5.1 uses Python 3.11 and is treated as a separate
Spark compatibility boundary.

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Run the quality gate:

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest --cov=cryptopulse --cov-report=term-missing
python -m build
```

`make docker-test` runs the normal suite with networking disabled. `make glue-test` runs the
separate Spark/Python compatibility check. Normal tests use `httpx.MockTransport` and make no live
API calls. A live integration requires both `CRYPTOPULSE_RUN_INTEGRATION=1` and
`CRYPTOPULSE_ALLOW_LIVE_API=1`.

Generated caches, build output, coverage reports, virtual environments, secrets, and local data
are ignored by Git. Run `make clean` to remove generated project artifacts.

## Safety boundaries

- The client only calls reviewed CoinGecko Demo endpoints and never accepts arbitrary URLs.
- HTTP 408, 429, transport errors, and 5xx responses receive at most three retries.
- Secrets are accepted only through process environment variables and are redacted from logs.
- Local data belongs under ignored `data/` paths; no AWS resource is currently deployed.

Data is provided by [CoinGecko](https://www.coingecko.com/en/api). No repository license has been
selected yet.
