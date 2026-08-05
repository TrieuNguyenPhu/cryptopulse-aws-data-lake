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

## Phase 3 — Lambda collector and Bronze

- [ ] Implement validated `job_name` routing.
- [ ] Implement local environment and AWS Secrets Manager credential providers.
- [ ] Implement DynamoDB attempt reservation and thresholds at 7,000/8,500/9,000.
- [ ] Implement suppression results without external calls at the ceiling.
- [ ] Implement one-response-at-a-time Bronze envelope and gzip flow.
- [ ] Implement unique conditional-create S3 keys.
- [ ] Separate API retry from S3 SDK retry and hold successful response bytes in memory.
- [ ] Implement all scheduled jobs and manual-only backfill routing.
- [ ] Implement sequential scoped requests for metadata/OHLC/backfill.
- [ ] Add Lambda handler tests and moto S3/DynamoDB tests.
- [ ] Prove an S3 failure after HTTP 200 causes zero additional HTTP calls.
- [ ] Prove unit/contract tests consume zero live API credits.
- [ ] Run the complete Phase 3 check suite.
- [ ] Update README/TASKS and report Phase 3.

## Phase 4 — Terraform collection platform

- [ ] Add Terraform provider/version constraints and dev environment composition.
- [ ] Implement storage module with public-access block, TLS-only, encryption, versioning, and lifecycle.
- [ ] Implement secret metadata only; do not create secret value/version in Terraform.
- [ ] Implement on-demand usage-counter table with TTL and encryption.
- [ ] Build reproducible Lambda zip artifact outside Terraform state.
- [ ] Implement Lambda, log group, zero async retry, and SQS failure handling.
- [ ] Implement all requested EventBridge Scheduler resources and manual-only omission for backfill.
- [ ] Implement SQS standard DLQ, queue policy, encryption, retention, and alarms.
- [ ] Implement least-privilege IAM and required tags.
- [ ] Add outputs that contain no secrets.
- [ ] Add `terraform.tfvars.example` with non-secret values only.
- [ ] Run Terraform fmt/validate, TFLint, Checkov, and Trivy where applicable.
- [ ] Inspect plan for prohibited services, public access, wildcard privileges, and secret values.
- [ ] Update README/TASKS and report Phase 4.

## Phase 5 — Silver and data quality

- [ ] Add reusable explicit Spark schemas for every Bronze response and Silver table.
- [ ] Implement envelope validation and safe UTC/decimal conversion helpers.
- [ ] Implement observed-vs-expected schema fingerprint/drift manifests.
- [ ] Implement reusable row/batch quality result model.
- [ ] Implement generic quarantine writer with all failure reasons.
- [ ] Implement `silver_market_snapshots`.
- [ ] Implement `silver_global_market`.
- [ ] Implement `silver_trending_assets`.
- [ ] Implement `silver_categories`.
- [ ] Implement `silver_exchanges`.
- [ ] Implement `silver_coin_metadata`.
- [ ] Implement `silver_coin_ohlc`.
- [ ] Implement `silver_historical_market`.
- [ ] Implement deterministic business-key deduplication.
- [ ] Implement missing-window, stale-source, scoped-completeness, and count-reconciliation checks.
- [ ] Implement run-scoped Parquet writes and validated Catalog partition-location updates.
- [ ] Add Spark unit, boundary, dedup, quarantine, drift, and contract tests.
- [ ] Add Terraform processing module, Glue roles/jobs, and explicit Catalog schemas.
- [ ] Run Python/Spark tests and Terraform/static checks.
- [ ] Update README/TASKS and report Phase 5.

## Phase 6 — Gold analytics

- [ ] Implement `gold_market_overview_hourly`.
- [ ] Implement `gold_daily_coin_performance`.
- [ ] Implement `gold_market_rank_movements`.
- [ ] Implement `gold_category_performance`.
- [ ] Implement `gold_trending_followthrough` with nearest-observation tolerance.
- [ ] Implement `gold_exchange_rankings`.
- [ ] Implement `gold_market_dominance`.
- [ ] Implement `gold_data_quality_summary`.
- [ ] Add stable aggregate fixtures and Bronze/Silver/Gold reconciliation tests.
- [ ] Add Silver-success-only Gold trigger.
- [ ] Run the complete Phase 6 check suite.
- [ ] Update README/TASKS and report Phase 6.

## Phase 7 — Athena and local Streamlit dashboard

- [ ] Add Athena workgroup and encrypted/lifecycle-managed result prefix.
- [ ] Add data validation and portfolio analytics SQL queries.
- [ ] Add query examples for all Gold tables.
- [ ] Implement local read-only Streamlit Athena client with testable injection.
- [ ] Add market overview, performance, ranks, categories, trending, exchanges, dominance, and quality views.
- [ ] Display last-updated/data-freshness status.
- [ ] Display `Data provided by CoinGecko` with direct API link.
- [ ] Display educational/non-commercial/non-investment disclaimer.
- [ ] Prove no CoinGecko key is required or exposed by the dashboard.
- [ ] Run SQL smoke checks, dashboard unit tests, and startup smoke test.
- [ ] Update README/TASKS and report Phase 7.

## Phase 8 — CI/CD and operations

- [ ] Add PR workflow: Ruff, MyPy, Pytest/coverage, Terraform fmt/validate, TFLint, Checkov, Trivy, secret scanning.
- [ ] Add deterministic Lambda artifact build and checksum.
- [ ] Add main workflow: artifact, Terraform plan, protected environment approval, apply, smoke tests.
- [ ] Use GitHub OIDC; do not store long-lived AWS keys.
- [ ] Resolve D-020 remote-state backend and deployment roles.
- [ ] Add `docs/runbook.md` for alerts, DLQ, replay, usage ceiling, schema drift, Glue failures, and credential rotation.
- [ ] Add `docs/cost-analysis.md` with assumptions and measured controls.
- [ ] Add `docs/cleanup.md` with ordered Terraform/AWS cleanup commands and recovery warnings.
- [ ] Document AWS Budget resource/console setup and notification ownership.
- [ ] Add dependency/security update policy.
- [ ] Lint workflows and run the complete Phase 8 check suite.
- [ ] Update README/TASKS and report Phase 8.

## Phase 9 — Integration and portfolio hardening

- [ ] Add opt-in moto/local integration suite behind `CRYPTOPULSE_RUN_INTEGRATION=1`.
- [ ] Add separately authorized one-request live Demo smoke test behind `CRYPTOPULSE_ALLOW_LIVE_API=1`.
- [ ] Deploy dev/demo infrastructure through approved workflow.
- [ ] Populate the secret value outside Terraform from a protected source.
- [ ] Validate every schedule, Lambda metric/log, counter threshold simulation, S3 contract, and DLQ path.
- [ ] Run Glue fixtures, verify Catalog partitions, and execute Athena smoke/reconciliation queries.
- [ ] Validate dashboard attribution, disclaimers, freshness, and read-only IAM.
- [ ] Validate cleanup in a disposable environment.
- [ ] Add architecture evidence/screenshots with no account IDs or secrets.
- [ ] Resolve D-021 repository license decision.
- [ ] Complete final security/cost review and update all documentation.
- [ ] Report final commands, results, residual risks, and portfolio usage instructions.

## Persistent acceptance criteria

- [ ] No committed, printed, logged, planned, or state-stored API key.
- [ ] No unit/contract CI job can reach CoinGecko.
- [ ] No unverified CoinGecko endpoint or parameter.
- [ ] No successful response refetched because an S3 write failed.
- [ ] Estimated outbound attempt 9,001 is atomically blocked.
- [ ] Bronze payload remains exact and original versions are preserved.
- [ ] Invalid Silver rows are quarantined with reasons.
- [ ] No `coin_id` partitioning.
- [ ] Every taggable AWS resource has all four required tags.
- [ ] No prohibited service appears in Terraform or architecture.
- [ ] Every phase stops on a failed required check.
