# CryptoPulse delivery tasks

Legend: `[ ]` pending, `[x]` complete. A phase is complete only when its required checks pass and README/TASKS are updated. Do not begin the next phase automatically.

## Phase 0 — Planning and repository foundation

- [x] Inspect every repository entry before creating files (workspace was empty).
- [x] Confirm there is no `.codegraph/` index or existing Git worktree.
- [x] Verify requested endpoints and parameters against CoinGecko's official Demo documentation index.
- [x] Calculate 31-day scheduled API usage and manual-backfill impact.
- [x] Present assumptions, risks, service boundaries, and intended repository structure before implementation.
- [x] Create `docs/implementation-plan.md`.
- [x] Create `docs/architecture.md`.
- [x] Create `docs/data-model.md`.
- [x] Create `docs/decisions.md`.
- [x] Create `TASKS.md`, README, ignore rules, and editor settings.
- [x] Verify the supplied local key path exists without reading its contents.
- [x] Initialize the local Git repository on `main`.
- [x] Run Phase 0 documentation/secret-pattern validation.
- [x] Record the Phase 0 report and stop.

## Phase 1 — Python project and contracts

- [x] Resolve D-019: approve the complete configured top-20 metadata CoinGecko ID list.
- [x] Add `pyproject.toml` for Python 3.12 and pinned compatible dependency ranges.
- [x] Configure Ruff, MyPy, Pytest, pytest-cov, and package metadata.
- [x] Add Makefile commands for install, format, lint, typecheck, unit, contract, integration, build, and clean.
- [x] Add pre-commit hooks.
- [x] Add Docker local development and Glue-compatible Spark test targets.
- [x] Add `.env.example` with names only and no secret values.
- [x] Add static `config/jobs.json` with allow-listed paths, supported parameters, scopes, schedules, and criticality.
- [x] Add typed settings with UTC/default-region validation.
- [x] Add structured JSON logging and a mandatory redaction filter.
- [x] Add Bronze envelope types, gzip serializer, object-key builder, and record-count rules.
- [x] Add sanitized response fixtures for all nine collection entities.
- [x] Add configuration, logging-redaction, envelope, key, and fixture contract tests.
- [x] Run Ruff, MyPy, Pytest/coverage, package build, and the Python 3.12 application-container smoke check.
- [x] Run the official Glue 5.0 container smoke check with external networking disabled.
- [x] Update README/TASKS and report Phase 1.

## Phase 2 — CoinGecko API client

- [x] Implement one reusable synchronous `httpx` client.
- [x] Add injected client/transport, clock, sleep, random, logger, and usage gate seams.
- [x] Configure explicit connect, read, write, and pool timeouts.
- [x] Add stable run/request identity propagation and monotonic latency measurement.
- [x] Add typed exceptions for transport, 400, 401, 403/plan restriction, 429, and 5xx exhaustion.
- [x] Implement exponential backoff with jitter and a maximum of three retries after the initial attempt.
- [x] Parse numeric and HTTP-date `Retry-After` safely.
- [x] Prove permanent 4xx errors are never retried.
- [x] Prove request headers, query secrets, and API keys never reach logs/exceptions.
- [x] Test all endpoint parameter builders with MockTransport/respx; prohibit live network.
- [x] Run the complete Phase 2 check suite.
- [x] Update README/TASKS and report Phase 2.

## Local Phase 3 — Application ports and JobRunner

- [ ] Define narrow ports for Bronze storage, checkpoints, metrics, secrets, and clocks.
- [ ] Implement a transport-independent `JobRunner` that orchestrates validated jobs through injected ports.
- [ ] Implement `EnvironmentSecretProvider`; read `COINGECKO_API_KEY` from process environment only.
- [ ] Add a local CLI for explicit single-job execution and manual-only backfill routing.
- [ ] Keep live CoinGecko access behind explicit opt-in; default CLI/test behavior remains offline.
- [ ] Keep scoped metadata, OHLC, and backfill requests sequential.
- [ ] Prove storage failure after HTTP 200 causes zero additional HTTP calls.
- [ ] Prove unit, contract, and normal integration tests consume zero live API credits.
- [ ] Run the complete Local Phase 3 check suite.
- [ ] Update README/TASKS and report Local Phase 3 without starting Phase 4A.

## Local Phase 4A — Immutable local Bronze storage

- [ ] Implement `LocalBronzeStore` behind the Bronze storage port.
- [ ] Write one immutable gzip JSON document per successful response under `data/bronze/`.
- [ ] Preserve the existing Bronze envelope, record-count, filename, and partition contracts.
- [ ] Use create-only writes and fail rather than replace an existing path.
- [ ] Keep successful response bytes in memory across local storage retries; never refetch after HTTP 200.
- [ ] Add local filesystem contract, immutability, gzip, and failure-path tests.
- [ ] Confirm `data/bronze/` remains ignored and untracked.
- [ ] Run the complete Local Phase 4A check suite.

## Local Phase 4B — Local checkpoints and metrics

- [ ] Implement `LocalCheckpointStore` under `data/checkpoints/` with atomic replacement of checkpoint metadata.
- [ ] Implement `LocalMetricsSink` with secret-safe structured events and no cloud dependency.
- [ ] Preserve run/request identity and attempt-budget signals across local adapters.
- [ ] Add restart, duplicate-run, corruption, and redaction tests.
- [ ] Confirm `data/checkpoints/` remains ignored and untracked.
- [ ] Run the complete Local Phase 4B check suite.

## Optional local scheduler — separate PR, disabled by default

- [ ] Do not start this work automatically or combine it with Local Phase 4B.
- [ ] If separately approved, add a local scheduler adapter behind the same job-trigger boundary.
- [ ] Require an explicit enable flag; default installation and normal tests schedule nothing.
- [ ] Keep `historical_backfill` manual-only.

## Local Phase 5A — Bronze-to-Silver PySpark

- [ ] Add reusable explicit Spark schemas for every Bronze response and Silver table.
- [ ] Implement envelope validation and safe UTC/decimal conversion helpers.
- [ ] Implement all eight existing Silver table contracts.
- [ ] Implement deterministic business-key deduplication.
- [ ] Read bounded local Bronze paths and write run-scoped Parquet under `data/silver/`.
- [ ] Add Spark unit, boundary, schema, and deduplication tests using sanitized fixtures.
- [ ] Confirm `data/silver/` remains ignored and untracked.
- [ ] Run the complete Local Phase 5A check suite.

## Local Phase 5B — Data quality, quarantine, and reports

- [ ] Implement observed-vs-expected schema fingerprint and drift reports.
- [ ] Implement the existing reusable row/batch quality result model.
- [ ] Implement generic quarantine output with all failure reasons under `data/quarantine/`.
- [ ] Implement missing-window, stale-source, scoped-completeness, and count-reconciliation checks.
- [ ] Produce deterministic local quality reports without AWS services.
- [ ] Add quarantine, drift, reconciliation, and report contract tests.
- [ ] Confirm `data/quarantine/` remains ignored and untracked.
- [ ] Run the complete Local Phase 5B check suite.

## Local Phase 6 — Gold analytics and DuckDB validation

- [ ] Implement the eight existing Gold table contracts as deterministic Silver-to-Gold transforms.
- [ ] Write run-scoped Gold Parquet under `data/gold/` only after Silver and quality checks pass.
- [ ] Validate Gold schemas, counts, business keys, and representative queries with DuckDB.
- [ ] Add stable aggregate fixtures and Bronze/Silver/Gold reconciliation tests.
- [ ] Keep Athena SQL as source-only and explicitly AWS-unvalidated.
- [ ] Confirm `data/gold/` remains ignored and untracked.
- [ ] Run the complete Local Phase 6 check suite.

## Local Phase 7 — Streamlit over local Gold Parquet

- [ ] Implement a local read-only Streamlit data adapter over Gold Parquet, validated with DuckDB.
- [ ] Add market overview, performance, ranks, categories, trending, exchanges, dominance, and quality views.
- [ ] Display last-updated/data-freshness status.
- [ ] Display `Data provided by CoinGecko` with a direct API link.
- [ ] Display the educational/non-commercial/non-investment disclaimer.
- [ ] Prove the dashboard neither requires nor exposes the CoinGecko key.
- [ ] Run dashboard unit and startup smoke tests without live HTTP or AWS.
- [ ] Run the complete Local Phase 7 check suite.

## Deferred Local Phase 8 — AWS adapters and infrastructure source

- [ ] Keep AWS deployment and validation blocked until the account is unlocked and separately approved.
- [ ] Add AWS Secrets Manager, S3, DynamoDB, CloudWatch, and event-source adapters behind existing ports.
- [ ] Add a thin Lambda adapter that composes the same `JobRunner` through dependency injection.
- [ ] Add Terraform source only for storage, usage counter, Lambda, Scheduler, SQS, alarms, IAM, Catalog, Glue, Athena, and required tags.
- [ ] Keep secret values outside Terraform state and Lambda environment declarations.
- [ ] Add source-only CI checks for Terraform and AWS adapters without credentials or AWS calls.
- [ ] Keep Athena SQL explicitly AWS-unvalidated until an approved deployment exists.
- [ ] Do not claim any AWS feature is deployed based on source code, mocks, local containers, or static validation.
- [ ] Resolve D-020 before any shared plan/apply workflow.
- [ ] Add deployment, runbook, cost, cleanup, and AWS integration work only after separate authorization.

## Persistent acceptance criteria

- [ ] No committed, printed, logged, planned, or state-stored API key.
- [ ] `.env` remains local, ignored, and untracked; `.env.example` contains names only.
- [ ] No unit/contract CI job can reach CoinGecko.
- [ ] Live CoinGecko use requires explicit opt-in and is excluded from normal tests and CI.
- [ ] `data/bronze/`, `data/silver/`, `data/gold/`, `data/quarantine/`, and `data/checkpoints/` remain ignored and untracked.
- [ ] No unverified CoinGecko endpoint or parameter.
- [ ] No successful response refetched because an S3 write failed.
- [ ] Estimated outbound attempt 9,001 is atomically blocked.
- [ ] Bronze payload remains exact and original versions are preserved.
- [ ] Invalid Silver rows are quarantined with reasons.
- [ ] No `coin_id` partitioning.
- [ ] Every taggable AWS resource has all four required tags.
- [ ] No prohibited service appears in Terraform or architecture.
- [ ] No AWS feature is described as deployed until an approved deployment and AWS validation both succeed.
- [ ] Athena SQL remains marked AWS-unvalidated until it runs in an approved account.
- [ ] Every phase stops on a failed required check.
