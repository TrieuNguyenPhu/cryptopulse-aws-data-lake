# CryptoPulse — Serverless Crypto Market Data Lake on AWS

CryptoPulse is an educational, non-commercial portfolio project for collecting cryptocurrency market data from the CoinGecko Demo REST API into an AWS serverless data lake. It is a data engineering demonstration, not a trading bot, and it does not provide investment recommendations.

> Data provided by [CoinGecko](https://www.coingecko.com/en/api).

## Status

Phases 0–2 are implemented. The repository now has the Python 3.12 foundation, static collection-job contracts, typed settings, strict Bronze serialization, sanitized fixtures, and one synchronous CoinGecko Demo client with bounded retries, typed errors, request/run correlation, latency measurement, pre-attempt budget hooks, and secret-safe JSON logging. Lambda collection, AWS infrastructure, Glue transformations, SQL, and the dashboard remain intentionally unimplemented.

The current design documents are:

- [Implementation plan](docs/implementation-plan.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Decision log](docs/decisions.md)
- [Delivery tasks](TASKS.md)

## Planned system

```text
EventBridge Scheduler -> Lambda collector -> CoinGecko Demo REST API
                                           -> S3 Bronze JSON.gz

S3 Bronze -> AWS Glue PySpark -> S3 Silver/Gold Parquet
                              -> Glue Data Catalog -> Athena
Athena -> local Streamlit dashboard
```

The AWS default region is `ap-southeast-1`. Terraform will manage infrastructure without placing the CoinGecko API key value in state. All resources will be private, encrypted, versioned where applicable, least-privilege, and tagged with the required project metadata.

## API safety

The scheduled 31-day worst case is estimated at 6,548 successful calls. A manual one-year backfill for ten coins adds 10 calls. Runtime enforcement will warn at 7,000 and 8,500 estimated attempts and stop new API requests at the 9,000-call internal ceiling.

The local key source supplied for future phases is outside this repository. Repository setup verifies only that the file exists; it does not read or copy the value. Secrets must never be committed, printed, logged, passed through Terraform variables, or exposed to the Streamlit client. `.env.example` contains names only.

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

## Scope boundaries

The design deliberately excludes Kinesis, Firehose, ECS, EC2, RDS, API Gateway, NAT Gateway, Kubernetes, and QuickSight. Historical backfill is manual-only. Unit and contract tests use sanitized fixtures and never call the live CoinGecko API.

## License

No repository license has been selected yet. Add one only after the owner chooses the intended terms.
