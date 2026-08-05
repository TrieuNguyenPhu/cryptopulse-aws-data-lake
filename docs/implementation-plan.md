# Implementation plan

## Phase 0 status

The workspace was inspected on 2026-08-04 before files were created. It contained no files, Git metadata, or CodeGraph index, so there is no prior implementation or user work to preserve. This phase creates planning documentation and repository metadata only; it does not implement application or infrastructure code.

## Phase 1 status

Implemented and reviewed on 2026-08-04: the Python 3.12 project foundation, reviewed job catalog, typed settings, mandatory JSON-log redaction, immutable strict-JSON Bronze envelope/key contract, sanitized fixtures, local/container tooling, and unit/contract tests. The review tightened external-network opt-in so ordinary integration tests remain loopback-only.

## Phase 2 status

Implemented on 2026-08-04: one synchronous allow-listed `httpx` client, explicit timeouts, stable run/request IDs, monotonic latency, an injected pre-attempt budget hook, typed error mapping, permanent-4xx fail-fast behavior, bounded exponential backoff with jitter, numeric/HTTP-date `Retry-After`, and offline MockTransport coverage. Phase 3 collection, durable usage counting, S3 writes, and Lambda behavior are intentionally absent.

## Goal and guardrails

CryptoPulse will be a serverless, micro-batch AWS data platform that:

1. Collects only supported CoinGecko Demo REST API data.
2. Writes each successful response once to immutable-by-design S3 Bronze storage.
3. Produces validated Silver and analytical Gold Parquet datasets with AWS Glue PySpark.
4. Publishes explicit schemas to Glue Data Catalog for Athena.
5. Serves a local, read-only Streamlit dashboard with visible CoinGecko attribution.

It will not trade, advise on investments, stream data, or introduce unrequested infrastructure. Specifically excluded are Kinesis, Firehose, ECS, EC2, RDS, API Gateway, NAT Gateway, Kubernetes, QuickSight, WebSocket, and Webhook integrations.

## Assumptions

- AWS account access, a Terraform remote-state approach, and GitHub OIDC deployment roles will be supplied before deployment.
- The repository directory is the repository root even though its local folder name differs from `cryptopulse-aws-data-lake`.
- Python 3.12 is used for local development, tests, packaging, and Lambda. AWS Glue 5.1 currently runs Spark 3.5.6 with Python 3.11, so Glue scripts remain Python 3.11-compatible. AWS currently publishes its local Docker image for Glue 5.0/Spark 3.5.4; that image provides compatibility coverage, while exact 5.1 parity is verified later by opt-in AWS integration tests.
- All schedules and timestamps use UTC. EventBridge Scheduler flexible time windows are disabled.
- `COINGECKO_API_KEY` is the local client default. In AWS, the Lambda adapter retrieves the value at runtime from Secrets Manager and passes it directly to the same injected client because Terraform must not place the value in Lambda environment state.
- The supplied top-ten coin IDs are authoritative for OHLC and backfill. The remaining ten IDs for weekly metadata are an explicit Phase 1 configuration decision and will be validated against `/coins/list` before deployment.
- One private S3 bucket with `bronze/`, `silver/`, `gold/`, `quarantine/`, and `athena-results/` prefixes is sufficient for this portfolio workload. IAM isolates access by prefix.
- Daily transformation is the cost-conscious default. Collection remains micro-batch at the requested frequencies; Bronze-to-Silver runs daily, followed by Silver-to-Gold only on success.
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

### Phase 3 — Collector and Bronze storage

- Route a validated EventBridge job event through one Lambda handler.
- Resolve the AWS secret in memory, reserve budget atomically, fetch once, build the envelope, gzip it, and create a unique S3 object.
- Keep HTTP retry scope separate from S3 SDK retry scope so S3 failures never call CoinGecko again within the invocation.
- Configure zero Lambda asynchronous function retries; exhausted S3 failures go to SQS rather than re-fetching a successful API response.
- Add S3 tests with moto and replay/idempotency tests.
- Exit criterion: all collection jobs produce contract-valid Bronze objects using fixtures, and failure tests prove no refetch after S3 errors.

### Phase 4 — Terraform core and collection deployment

- Implement storage, secret metadata, usage counter, Lambda, Scheduler, SQS DLQ, alarms, logs, and least-privilege IAM modules.
- Configure encryption, S3 public-access block, versioning, Bronze lifecycle, create-only collector permissions, log retention, and mandatory tags.
- Add dev environment variables and outputs without secret values.
- Run `terraform fmt`, `terraform validate`, TFLint, and Checkov.
- Exit criterion: static validation succeeds and the plan contains no secret value or prohibited service.

### Phase 5 — Silver and data quality

- Implement explicit Spark schemas, schema-drift comparison, deterministic deduplication, decimal casts, UTC normalization, bounded partition rebuilds, and generic quarantine records.
- Publish the eight requested Silver tables through explicit Data Catalog definitions; no crawler.
- Implement all required quality and collection-window checks.
- Exit criterion: local Spark tests and schema contracts pass against sanitized fixtures.

### Phase 6 — Gold analytics

- Implement the eight requested Gold datasets as deterministic Silver-to-Gold transforms.
- Add reconciliation tests from Bronze counts through Silver accepted/quarantined counts to Gold aggregates.
- Exit criterion: Gold fixtures produce stable expected rows and quality summaries.

### Phase 7 — Athena and Streamlit

- Add Athena workgroup, encrypted query-result prefix, saved SQL, and a local read-only Streamlit dashboard.
- Add visible `Data provided by CoinGecko` attribution and educational/non-investment disclaimer in the dashboard.
- Exit criterion: Athena smoke queries and dashboard startup checks pass without exposing credentials.

### Phase 8 — CI/CD and operations

- Add PR checks for Ruff, MyPy, Pytest/coverage, Terraform fmt/validate, TFLint, Checkov, Trivy, and secret scanning.
- Add main workflow for Lambda artifact build, Terraform plan, protected-environment manual approval, apply, and smoke tests through GitHub OIDC.
- Complete the runbook, AWS Budget setup documentation, cost analysis, disaster/replay procedures, and cleanup commands.
- Exit criterion: workflows lint successfully and a dry-run deployment checklist is complete.

### Phase 9 — Integration and portfolio hardening

- Run opt-in AWS integration tests under an explicit flag and a separately authorized Demo API smoke test capped to one known request.
- Validate alarms, DLQ behavior, partition discovery, Athena queries, budget suppression, cleanup, and README evidence.
- Exit criterion: final acceptance checklist passes and all known limitations are documented.

## Test policy

- Tests run after every implementation phase. Work stops on the first failing required check.
- Unit and contract tests categorically block live HTTP by using injected transports.
- Integration tests require `CRYPTOPULSE_RUN_INTEGRATION=1`; live CoinGecko smoke additionally requires a separate `CRYPTOPULSE_ALLOW_LIVE_API=1` flag and is never part of normal CI.
- Sanitized fixtures contain no headers, request URLs with keys, account identifiers, or raw secrets.
- Coverage begins with a practical 85% line threshold and can increase only when it adds meaningful protection.
- PySpark transformations are tested against the Glue-compatible Spark/Python matrix, while application code remains Python 3.12.

## Principal risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| CoinGecko response schema changes | Dropped or invalid Silver data | Preserve raw payload, explicit schemas, drift manifests, contract fixtures, quarantine incompatible rows |
| Shared key use outside CryptoPulse | Counter underestimates billed usage | Conservative attempt counter, warnings, CoinGecko dashboard reconciliation and account alerts |
| Retries amplify call volume | Ceiling reached early | Four-attempt maximum, jitter, `Retry-After`, atomic pre-attempt cap, no permanent-4xx retry |
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
