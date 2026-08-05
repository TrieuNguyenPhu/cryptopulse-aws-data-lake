# Implementation plan

## Phase 0 status

The workspace was inspected on 2026-08-04 before files were created. It contained no files, Git metadata, or CodeGraph index, so there is no prior implementation or user work to preserve. This phase creates planning documentation and repository metadata only; it does not implement application or infrastructure code.

## Phase 1 status

Implemented and reviewed on 2026-08-04: the Python 3.12 project foundation, reviewed job catalog, typed settings, mandatory JSON-log redaction, immutable strict-JSON Bronze envelope/key contract, sanitized fixtures, local/container tooling, and unit/contract tests. The review tightened external-network opt-in so ordinary integration tests remain loopback-only.

## Phase 2 status

Implemented on 2026-08-04: one synchronous allow-listed `httpx` client, explicit timeouts, stable run/request IDs, monotonic latency, an injected pre-attempt budget hook, typed error mapping, permanent-4xx fail-fast behavior, bounded exponential backoff with jitter, numeric/HTTP-date `Retry-After`, and offline MockTransport coverage. Phase 3 collection, durable usage counting, S3 writes, and Lambda behavior are intentionally absent.

## Local-first roadmap status

The AWS account is locked, so deployment and AWS validation are blocked. No AWS feature is considered deployed. The next approved work is Local Phases 3–7, using filesystem, process-environment, PySpark, DuckDB, and Streamlit adapters behind ports. Deferred Local Phase 8 may add AWS adapters, a Lambda composition adapter, and Terraform source only after separate approval; no AWS call or resource creation belongs to the active roadmap.

One explicitly authorized CoinGecko `/ping` smoke test passed with one request. It established local credential and client connectivity only; it did not validate collection jobs, AWS services, deployment, or Athena. The key remains local in ignored `.env`, and normal tests and CI remain offline.

## Goal and guardrails

CryptoPulse will first be a local, micro-batch data platform with replaceable adapters that:

1. Collects only supported CoinGecko Demo REST API data.
2. Writes each successful response once to immutable-by-design local Bronze storage.
3. Produces validated Silver and analytical Gold Parquet datasets with local PySpark.
4. Validates local analytical outputs and queries with DuckDB.
5. Serves a local, read-only Streamlit dashboard over Gold Parquet with visible CoinGecko attribution.

The existing AWS architecture remains the deferred target. Ports and dependency injection will allow local secret, Bronze, checkpoint, and metric adapters to be replaced later by AWS adapters without changing the core `JobRunner` or data contracts.

It will not trade, advise on investments, stream data, or introduce unrequested infrastructure. Specifically excluded are Kinesis, Firehose, ECS, EC2, RDS, API Gateway, NAT Gateway, Kubernetes, QuickSight, WebSocket, and Webhook integrations.

## Assumptions

- The AWS account is locked. Account access, a Terraform remote-state approach, and GitHub OIDC deployment roles must be supplied and separately approved before deployment or AWS validation.
- The repository directory is the repository root even though its local folder name differs from `cryptopulse-aws-data-lake`.
- Python 3.12 is used for local development, tests, packaging, and Lambda. AWS Glue 5.1 currently runs Spark 3.5.6 with Python 3.11, so Glue scripts remain Python 3.11-compatible. AWS currently publishes its local Docker image for Glue 5.0/Spark 3.5.4; that image provides compatibility coverage, while exact 5.1 parity is verified later by opt-in AWS integration tests.
- All schedules and timestamps use UTC. EventBridge Scheduler flexible time windows are disabled.
- `COINGECKO_API_KEY` is read locally only through `EnvironmentSecretProvider` from the current process. `.env` remains local and untracked. In deferred AWS work, a Secrets Manager adapter will pass the value directly to the same injected client because Terraform must not place the value in Lambda environment state.
- The supplied top-ten coin IDs are authoritative for OHLC and backfill. The remaining ten IDs for weekly metadata are an explicit Phase 1 configuration decision and will be validated against `/coins/list` before deployment.
- Local runtime data uses ignored `data/bronze/`, `data/silver/`, `data/gold/`, `data/quarantine/`, and `data/checkpoints/` paths. The deferred AWS target remains one private S3 bucket with prefix-level IAM isolation.
- Local execution is explicit through the CLI. Any optional local scheduler is disabled by default and must be implemented in a separate PR. Bronze-to-Silver runs before Silver-to-Gold, and Gold never publishes after a failed Silver or quality run.
- CoinGecko's external developer dashboard remains the source of truth for billed usage. The platform counter is intentionally conservative and counts every outbound attempt.

## Verified CoinGecko API contract

All routes below appear in the official [Demo endpoint overview](https://docs.coingecko.com/demo/reference/endpoint-overview). Authentication uses the `x-cg-demo-api-key` header and `https://api.coingecko.com/api/v3`, as specified by the official [Demo authentication documentation](https://docs.coingecko.com/demo/reference/authentication).

| Job | Demo endpoint | UTC schedule | Parameters | Requests per run | Criticality |
|---|---|---:|---|---:|---|
| `market_snapshot` | [`/coins/markets`](https://docs.coingecko.com/demo/reference/coins-markets) | every 10 minutes | `vs_currency=usd`, `order=market_cap_desc`, `per_page=250`, `page=1`, `sparkline=false`, `price_change_percentage=1h,24h,7d` | 1 | critical |
| `global_market` | [`/global`](https://docs.coingecko.com/demo/reference/crypto-global) | hourly | none | 1 | critical |
| `trending` | [`/search/trending`](https://docs.coingecko.com/demo/reference/trending-search) | hourly | none | 1 | non-critical |
| `categories` | [`/coins/categories`](https://docs.coingecko.com/demo/reference/coins-categories) | every 6 hours | none | 1 | non-critical |
| `exchanges` | [`/exchanges`](https://docs.coingecko.com/demo/reference/exchanges) | daily | `per_page=250`, `page=1` | 1 | non-critical |
| `coin_list` | [`/coins/list`](https://docs.coingecko.com/demo/reference/coins-list) | daily | `include_platform=false`, `status=active` | 1 | non-critical |
| `coin_metadata` | [`/coins/{id}`](https://docs.coingecko.com/demo/reference/coins-id) | weekly | `localization=false`, `tickers=false`, `market_data=false`, `community_data=false`, `developer_data=false`, `sparkline=false` | 20 | non-critical |
| `coin_ohlc` | [`/coins/{id}/ohlc`](https://docs.coingecko.com/demo/reference/coins-id-ohlc) | daily at 00:45 | `vs_currency=usd`, `days=1` | 10 | non-critical |
| `historical_backfill` | [`/coins/{id}/market_chart`](https://docs.coingecko.com/demo/reference/coins-id-market-chart) | manual only | `vs_currency=usd`, `days=365`, `interval=daily` | 10 | non-critical |

The OHLC run is scheduled after 00:35 UTC because CoinGecko documents that the last completed UTC day becomes available at that time. The backfill uses only `daily`, not the Enterprise-only `5m` interval, and stays within the Demo plan's 365-day historical limit.

## API-credit calculation

The safety model uses a worst-case 31-day calendar month and five weekly executions:

| Scheduled job | Calculation | Maximum calls |
|---|---:|---:|
| `market_snapshot` | 6/hour × 24 hours × 31 days | 4,464 |
| `global_market` | 24 × 31 | 744 |
| `trending` | 24 × 31 | 744 |
| `categories` | 4 × 31 | 124 |
| `exchanges` | 1 × 31 | 31 |
| `coin_list` | 1 × 31 | 31 |
| `coin_metadata` | 20 coins × 5 weeks | 100 |
| `coin_ohlc` | 10 coins × 31 | 310 |
| **Scheduled total** |  | **6,548** |
| Optional manual backfill | 10 coins × 1 request | **10** |

Scheduled headroom below the 9,000 ceiling is 2,452 attempts; after one backfill it is 2,442. The runtime counter increments atomically before every outbound attempt, including retries and failed responses. A conditional increment prevents attempt 9,001. Structured warnings are emitted when crossing 7,000 and 8,500. At 9,000, all new external requests are suppressed; non-critical jobs are explicitly reported as budget-disabled. Resumption requires the next counter period or an operator-reviewed override, never an automatic reset inside a run.

CoinGecko currently documents that only HTTP 200 responses consume monthly credits, while every response status counts toward the per-minute limit. Counting all attempts is therefore conservative. External usage by the same key can make the internal estimate low, so the runbook will require dashboard reconciliation and CoinGecko call-consumption alerts.

## Delivery phases

### Phase 0 — Planning and foundation

- Inspect the repository and secret-file presence without reading the secret.
- Validate all requested API routes and parameters against official Demo documentation.
- Record architecture, data contracts, risks, decisions, phased tasks, and credit math.
- Create README, ignore rules, editor settings, and initialize Git.
- Exit criterion: documentation links resolve, required sections exist, and no implementation code exists.

### Phase 1 — Python project and contracts

- Add `pyproject.toml` for Python 3.12, Ruff, MyPy, Pytest, coverage, httpx, boto3, and development-only test dependencies.
- Add Makefile, pre-commit, a Python 3.12 development image, an official Glue 5.0 compatibility test target, typed settings, job configuration, logging primitives, and sanitized fixtures.
- Resolve and validate the configured top-20 metadata IDs.
- Add tests for configuration validation, secret redaction, and Bronze envelope serialization.
- Exit criterion: formatting, lint, typing, and unit tests pass without network access.

### Phase 2 — CoinGecko client

- Implement one injectable `httpx.Client`-based client with separate connect/read timeouts.
- Add typed exceptions for transport, bad request, authentication, authorization/plan restriction, rate limiting, and server failure.
- Retry transport errors, HTTP 408, 429, and 5xx with exponential backoff plus jitter, at most three retries after the first attempt.
- Do not retry permanent 400, 401, or 403 responses. Honor numeric or HTTP-date `Retry-After` values.
- Emit structured JSON logs with run/request IDs and latency, with header/query sanitization.
- Test solely through `httpx.MockTransport` or `respx`.
- Exit criterion: the error/retry matrix and no-secret logging tests pass.

### Local Phase 3 — Ports, JobRunner, CLI, and environment secrets

- Define narrow storage, checkpoint, metrics, secret, and clock ports around existing domain contracts.
- Implement `JobRunner` as the application orchestrator and compose it with `EnvironmentSecretProvider` in a local CLI.
- Keep job names, endpoints, and parameters allow-listed. Keep scoped calls sequential and backfill manual-only.
- Require explicit live opt-in for any real CoinGecko request; fixtures and injected transports remain the default.
- Exit criterion: CLI and runner tests prove deterministic orchestration, redaction, and no refetch after a post-HTTP storage failure.

### Local Phase 4A — LocalBronzeStore

- Implement create-only immutable gzip JSON writes under `data/bronze/` using the existing Bronze envelope and key contracts.
- Preserve successful response bytes in memory across storage handling; a storage failure must not trigger another API call.
- Add filesystem, collision, gzip, partition, and failure-path tests.
- Exit criterion: local Bronze artifacts are contract-valid, immutable, ignored, and untracked.

### Local Phase 4B — LocalCheckpointStore and LocalMetricsSink

- Implement atomic local checkpoint metadata under `data/checkpoints/` and a secret-safe local metrics sink.
- Preserve run/request identity, attempt-budget events, restart behavior, and corruption visibility without cloud services.
- Exit criterion: restart, duplicate, corruption, and redaction tests pass and no local state is tracked.

### Optional local scheduler — separate PR

- Keep scheduling disabled by default. Explicit CLI execution is the supported path through Local Phase 7.
- If separately approved, implement a scheduler adapter behind the trigger boundary without changing `JobRunner`.
- Exit criterion: scheduler installation alone starts nothing, enablement is explicit, and backfill remains manual-only.

### Local Phase 5A — Bronze to Silver

- Implement existing explicit schemas, deterministic deduplication, decimal casts, UTC normalization, and bounded local partition rebuilds in PySpark.
- Read local Bronze and write run-scoped Parquet under `data/silver/`; preserve all eight Silver contracts.
- Exit criterion: local Spark schema, boundary, and deduplication tests pass against sanitized fixtures.

### Local Phase 5B — Data quality and quarantine

- Implement schema-drift comparison, row/batch checks, count reconciliation, missing-window checks, generic quarantine records, and deterministic quality reports.
- Write ignored local artifacts under `data/quarantine/`; never include credentials or headers.
- Exit criterion: quarantine, drift, reconciliation, and quality-report contracts pass.

### Local Phase 6 — Gold analytics and DuckDB validation

- Implement the eight existing Gold datasets as deterministic Silver-to-Gold PySpark transforms under `data/gold/`.
- Validate schemas, business keys, counts, representative analytics, and Bronze/Silver/Gold reconciliation with DuckDB.
- Keep Athena SQL as source-only and explicitly AWS-unvalidated.
- Exit criterion: Gold fixtures and DuckDB checks produce stable expected results.

### Local Phase 7 — Streamlit over local Gold Parquet

- Implement a local read-only data adapter and Streamlit dashboard over validated Gold Parquet.
- Add freshness, CoinGecko attribution, and educational/non-investment disclaimers without requiring the API key.
- Exit criterion: dashboard unit/startup tests pass without live HTTP or AWS access.

### Deferred Local Phase 8 — AWS adapters, Lambda, and Terraform source only

- After separate approval, implement AWS Secrets Manager, S3, DynamoDB, CloudWatch, and event-source adapters behind the same ports.
- Add a thin Lambda adapter that composes `JobRunner`; retain separate HTTP/storage retry boundaries and zero-refetch behavior.
- Add Terraform source for the existing private serverless target, but do not deploy or claim validation while the account is locked.
- Keep secret values outside Terraform state, retain least-privilege/tagging requirements, and keep Athena SQL marked AWS-unvalidated.
- Exit criterion before account unlock: source-only static checks pass without credentials or AWS calls. Deployment, Glue/Athena checks, alarms, DLQ validation, and cleanup evidence remain blocked.

## Test policy

- Tests run after every implementation phase. Work stops on the first failing required check.
- Unit and contract tests categorically block live HTTP by using injected transports.
- Integration tests require `CRYPTOPULSE_RUN_INTEGRATION=1`; live CoinGecko access additionally requires `CRYPTOPULSE_ALLOW_LIVE_API=1` and separate authorization. The approved one-request `/ping` smoke passed, but live checks are never part of normal CI.
- `.env` must remain local, ignored, and untracked. Local data and checkpoints under `data/` must also remain ignored and untracked.
- Sanitized fixtures contain no headers, request URLs with keys, account identifiers, or raw secrets.
- Coverage begins with a practical 85% line threshold and can increase only when it adds meaningful protection.
- Local PySpark transformations run without AWS credentials or calls. Glue-container compatibility may remain an offline boundary check, but exact Glue/Athena behavior is AWS-unvalidated while the account is locked.

## Principal risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| CoinGecko response schema changes | Dropped or invalid Silver data | Preserve raw payload, explicit schemas, drift manifests, contract fixtures, quarantine incompatible rows |
| Shared key use outside CryptoPulse | Counter underestimates billed usage | Conservative attempt counter, warnings, CoinGecko dashboard reconciliation and account alerts |
| Retries amplify call volume | Ceiling reached early | Four-attempt maximum, jitter, `Retry-After`, atomic pre-attempt cap, no permanent-4xx retry |
| Local runtime artifacts are committed | Data volume or sensitive operational context enters Git | Ignore all local data/checkpoint roots, scan tracked files, and keep `.env` local and untracked |
| Local adapter behavior diverges from future AWS adapters | Deployment changes domain behavior | Define narrow ports now and replace adapters through dependency injection with shared contract tests |
| AWS account remains locked | Deployment, Glue, Athena, and operational validation cannot run | Keep Local Phase 8 source-only and label every AWS claim and Athena SQL as unvalidated |
| S3 failure after successful HTTP | Duplicate paid request or lost raw response | Independent S3 retries with response held in memory, zero Lambda function retries, DLQ/manual recovery |
| Scheduler DLQ does not represent every Lambda code failure | Missing failure visibility | Configure both Scheduler target DLQ handling and Lambda asynchronous failure destination/DLQ metrics |
| Plain Parquet has no row-level merge | Duplicate or inconsistent reruns | Rebuild bounded affected date partitions into run-scoped prefixes, then publish validated Catalog partition locations |
| Glue runtime differs from Python 3.12 and its published local image trails 5.1 | Production-only failures | Test application code on 3.12, Glue-compatible code in the official Glue 5.0 image, avoid 3.12-only Glue syntax, and verify exact 5.1 behavior in AWS integration |
| Bronze is not compliance WORM | Privileged account admin could delete a version | Unique keys, versioning, create-only collector IAM, delete denial for workload roles; Object Lock remains an explicit future hardening option |
| Many small Bronze objects | S3 request/list overhead | Accept at portfolio scale, gzip payloads, compact into daily Parquet, lifecycle expiry after 365 days |
| Daily Glue cadence delays analytics | Dashboard may be up to one day behind | Clearly show freshness; increase cadence only after measuring value and cost |
| Financial precision overflow or rounding | Incorrect analytics | Use documented decimal types, safe casts, quarantine overflow, contract boundary tests |
| Missing top-20 metadata configuration | Weekly job cannot be finalized | Resolve IDs in Phase 1 and validate against a sanitized `/coins/list` fixture before deployment |

## Required end-of-phase report

Every phase completion report must include:

1. Files created or changed.
2. Commands executed.
3. Tests and exact results.
4. Remaining risks or deferred decisions.
5. The proposed next phase, without starting it automatically.
