# CryptoPulse — Serverless Crypto Market Data Lake on AWS

CryptoPulse is an educational, non-commercial portfolio project for collecting cryptocurrency market data from the CoinGecko Demo REST API into an AWS serverless data lake. It is a data engineering demonstration, not a trading bot, and it does not provide investment recommendations.

> Data provided by [CoinGecko](https://www.coingecko.com/en/api).

## Status

Phases 0–2 are implemented through the existing eight-PR delivery stack. The repository has the Python 3.12 foundation, static collection-job contracts, typed settings, strict Bronze serialization, sanitized fixtures, and one synchronous CoinGecko Demo client with bounded retries, typed errors, request/run correlation, latency measurement, pre-attempt budget hooks, and secret-safe JSON logging.

The active roadmap is now local-first. Local Phases 3–7 will add ports and dependency injection, a `JobRunner` and CLI, immutable local Bronze storage, local checkpoints and metrics, PySpark Silver/Gold processing, DuckDB validation, and a Streamlit dashboard over local Gold Parquet. AWS adapters, Lambda, Terraform, deployment, and managed-service validation are deferred to Local Phase 8 because the AWS account is locked. No AWS feature is considered deployed.

An explicitly authorized one-request CoinGecko `/ping` smoke test passed. Normal tests and CI remain offline; live CoinGecko access is never part of the normal quality gate and requires explicit opt-in.

The current design documents are:

- [Implementation plan](docs/implementation-plan.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Decision log](docs/decisions.md)
- [Delivery tasks](TASKS.md)

## Local-first roadmap

```text
CLI -> JobRunner -> CoinGecko Demo REST API (explicit live opt-in only)
                 -> LocalBronzeStore -> data/bronze/*.json.gz

data/bronze -> local PySpark -> data/silver Parquet
                              -> data/quarantine + quality reports
data/silver -> local PySpark -> data/gold Parquet -> DuckDB validation
data/gold -> local read-only Streamlit dashboard
```

The delivery order is Local Phase 3 (ports, `JobRunner`, CLI, and `EnvironmentSecretProvider`), Local Phase 4A (`LocalBronzeStore`), Local Phase 4B (`LocalCheckpointStore` and `LocalMetricsSink`), Local Phase 5A (Bronze-to-Silver PySpark), Local Phase 5B (quality, quarantine, and reports), Local Phase 6 (Silver-to-Gold plus DuckDB validation), and Local Phase 7 (Streamlit over local Gold Parquet). An optional local scheduler is disabled by default and belongs in a separate PR.

Local adapters are intentionally behind ports so later AWS adapters can replace them through dependency injection without changing core collection or transformation contracts. Local Phase 8 may add source-only AWS adapters, a Lambda adapter, and Terraform after the account is unlocked and separately approved. AWS deployment and validation remain blocked; Athena SQL remains AWS-unvalidated.

## API safety

The scheduled 31-day worst case is estimated at 6,548 successful calls. A manual one-year backfill for ten coins adds 10 calls. Runtime enforcement will warn at 7,000 and 8,500 estimated attempts and stop new API requests at the 9,000-call internal ceiling.

The live key belongs only in the ignored local `.env`. That file must remain local and untracked, and secrets must never be committed, printed, logged, passed through Terraform variables, or exposed to the Streamlit client. `.env.example` contains names only.

Every outbound attempt, including a retry, invokes an injected budget hook before HTTP. The durable monthly counter and 7,000/8,500/9,000 enforcement belong to Phase 3; Phase 2 tests prove the hook can block an attempt before the transport is called. HTTP 400, 401, 403, and other permanent 4xx responses are never retried. Transport failures, 408, 429, and 5xx responses receive at most three retries, honoring valid `Retry-After` values.

## Local development

Create and activate a Python 3.12 virtual environment, then install the development dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Run the current quality gate:

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest --cov=cryptopulse --cov-report=term-missing
python -m build
```

`make docker-test` runs the normal suite in Python 3.12 with container networking disabled. `make glue-test` uses AWS's official Glue 5.0 image to check the Python 3.11/Spark 3.5 compatibility boundary; exact Glue 5.1 behavior remains an opt-in AWS integration check. Unit and contract tests use `httpx.MockTransport`, never use the live API, and consume zero credits. A future live test must carry the `live_api` marker and requires both `CRYPTOPULSE_RUN_INTEGRATION=1` and `CRYPTOPULSE_ALLOW_LIVE_API=1`.

Local runtime artifacts are disposable and must not be committed: `data/bronze/`, `data/silver/`, `data/gold/`, `data/quarantine/`, and `data/checkpoints/`.

## Scope boundaries

The design deliberately excludes Kinesis, Firehose, ECS, EC2, RDS, API Gateway, NAT Gateway, Kubernetes, and QuickSight. Historical backfill is manual-only. Unit and contract tests use sanitized fixtures and never call the live CoinGecko API. No AWS calls, resource creation, deployment, or validation are allowed while the account remains locked.

## License

No repository license has been selected yet. Add one only after the owner chooses the intended terms.
