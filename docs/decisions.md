# Architecture and engineering decisions

This is a lightweight decision log. `Accepted` decisions govern implementation until superseded by a later entry; `Open` decisions must be resolved before the phase named in their consequence.

## D-001 — Use only the CoinGecko Demo REST surface

- Status: Accepted
- Decision: Use `https://api.coingecko.com/api/v3`, the `x-cg-demo-api-key` request header, and only routes present in the official Demo endpoint overview. Do not use WebSocket, Webhook, Pro-only, Analyst, or Enterprise-only behavior.
- Rationale: This is the explicit project and budget boundary.
- Consequence: Endpoint configuration is an allow-list. Any API expansion requires official Demo documentation verification and an updated call-budget calculation.

## D-002 — One routed collector Lambda

- Status: Accepted
- Decision: Deploy one Python 3.12 Lambda handler and route validated `job_name` events to static job definitions.
- Rationale: The jobs share authentication, HTTP policy, logging, Bronze writing, and usage control. Separate functions would duplicate packaging and operational configuration without isolation value at this scale.
- Consequence: Job-specific behavior must remain data-driven and bounded; events cannot supply arbitrary URLs or query parameters.

## D-003 — Use synchronous httpx with dependency injection

- Status: Accepted
- Decision: Use one reusable `httpx.Client` wrapper with an injected transport/client, clock, sleep function, random source, logger, and budget gate where testing needs control.
- Rationale: Lambda invokes small sequential batches, so async concurrency adds complexity and rate-limit risk. Injection makes every retry and redaction path deterministic in tests.
- Consequence: Scoped metadata/OHLC requests run sequentially and remain below the Demo rate limit.

## D-004 — Separate HTTP retry scope from S3 write retry scope

- Status: Accepted
- Decision: After an HTTP 200, retain the serialized/gzipped envelope in memory and retry only S3. Configure zero Lambda asynchronous function retries; exhausted failures go to SQS.
- Rationale: A storage failure must not trigger another successful paid API request. The API client already owns bounded transport/server retry behavior.
- Consequence: An exhausted failure requires operator diagnosis. Replay checks Bronze first and deliberately chooses processing-only or collection replay.

## D-005 — Add DynamoDB solely for the atomic API-attempt ceiling

- Status: Accepted
- Decision: Use one on-demand DynamoDB table with conditional atomic monthly counters and warning markers.
- Rationale: Concurrent Lambda invocations cannot reliably gate at 9,000 using CloudWatch logs, metrics, or a mutable S3 object. DynamoDB provides the smallest serverless atomic primitive for this requirement.
- Consequence: This is an intentional addition to the supplied core diagram. It must not become a general application database.

## D-006 — Count all attempts and hard-stop before attempt 9,001

- Status: Accepted
- Decision: Reserve budget before each network attempt, including retries. Warn once at 7,000 and 8,500; suppress all new API calls at 9,000 by default.
- Rationale: CoinGecko documents that all attempts affect per-minute rate limiting even though only HTTP 200 currently deducts monthly credit. Conservative accounting protects the 10,000-call Demo allowance.
- Consequence: External calls made with the same key are not visible internally, so dashboard reconciliation and account alerts remain required.

## D-007 — One data-lake bucket with prefix isolation

- Status: Accepted
- Decision: Use one private, encrypted, versioned bucket per environment with Bronze, Silver, Gold, Quarantine, and Athena-result prefixes.
- Rationale: Separate buckets add policies and naming without improving the educational workload enough to justify them. Prefix-specific IAM preserves workload separation.
- Consequence: Bucket policy and IAM tests must prove that each role has access only to required prefixes.

## D-008 — Application-level Bronze immutability, no default Object Lock

- Status: Accepted
- Decision: Use unique conditional-create keys, S3 versioning, no collector delete permission, and no transform write permission to Bronze. Do not enable Object Lock in dev/demo by default.
- Rationale: The project is not a regulated WORM archive. Object Lock makes teardown and lifecycle behavior harder, while versioning preserves original object versions and workload roles cannot mutate them.
- Consequence: A privileged account administrator could still delete versions. If regulatory-grade retention becomes a requirement, use a new Object-Lock-enabled Bronze bucket and explicit retention policy.

## D-009 — SSE-S3 for the default data-lake encryption

- Status: Accepted
- Decision: Use S3-managed encryption keys (`AES256`) for the data lake and service-managed encryption for SQS/DynamoDB unless a later security requirement demands customer-managed KMS keys.
- Rationale: Encryption at rest is mandatory; customer-managed keys add policy, rotation, request cost, and deletion risk without a stated compliance need.
- Consequence: Checkov exceptions, if any tool demands customer-managed keys, must cite this decision and be narrow rather than disabling encryption checks broadly.

## D-010 — Explicit schemas and Catalog partitions, no crawlers

- Status: Accepted
- Decision: Terraform defines databases/table shells and version-controlled columns. Glue validates schemas and publishes successful partition locations. No Glue crawler determines table structure.
- Rationale: Explicit contracts make schema drift visible and testable; crawlers can silently infer undesirable types.
- Consequence: Every accepted schema change updates code, Catalog definitions, fixtures, documentation, and contract tests together.

## D-011 — Publish immutable run-scoped Parquet through partition-location swaps

- Status: Accepted
- Decision: Rebuild affected `snapshot_date` data into a new run-scoped prefix, validate it, then update that Catalog partition's location.
- Rationale: Appending to plain Parquet makes retries duplicate data, while deleting/replacing live prefixes can expose partial results. Run-scoped output preserves rollback without adding Iceberg/Hudi/Delta.
- Consequence: Old run prefixes need lifecycle cleanup, and readers must query through Glue Catalog rather than hard-coded S3 glob paths.

## D-012 — Daily transforms by default

- Status: Accepted
- Decision: Keep requested collection frequencies but run Bronze-to-Silver once daily, with Silver-to-Gold triggered only after success.
- Rationale: Glue startup/runtime cost dominates this small portfolio workload. Gold tables can still retain hourly grain when computed daily.
- Consequence: The dashboard may be up to one day behind and must display freshness. A higher cadence requires measured demand and a revised cost estimate.

## D-013 — Python 3.12 application with Glue 5.1 compatibility boundary

- Status: Accepted
- Decision: Use Python 3.12 for local development, Lambda, typing, and normal tests. Use managed Glue 5.1, currently Spark 3.5.6/Python 3.11, and keep Glue scripts compatible with Python 3.11. Use AWS's official Glue 5.0/Spark 3.5.4 local image as compatibility coverage until AWS publishes a 5.1 image.
- Rationale: Lambda supports Python 3.12, while the managed Glue Spark runtime does not. The official local image currently trails the managed runtime, and owning a custom Glue runtime solely to erase that minor test gap would add unnecessary platform work.
- Consequence: CI needs the Glue 5.0 compatibility test in addition to Python 3.12 checks; exact Glue 5.1 behavior remains an opt-in AWS integration test before deployment.

## D-014 — Secrets Manager metadata in Terraform, value outside Terraform

- Status: Accepted
- Decision: Terraform creates the secret resource only. Local live commands default to `COINGECKO_API_KEY`; Lambda retrieves the secret at runtime by ARN and injects it into the client.
- Rationale: Passing the value through a Terraform variable or Lambda environment declaration would place it in state. Direct runtime retrieval avoids that exposure.
- Consequence: The Lambda role gets `secretsmanager:GetSecretValue` only for the one ARN. Tests use dummy injected values and mock HTTP transports.

## D-015 — Decimal fixed point for financial fields

- Status: Accepted
- Decision: Use `decimal(38,18)` for currency/quantity fields and `decimal(20,10)` for percentages/ratios.
- Rationale: Crypto prices span very small fractions and large market totals; binary floats introduce avoidable comparison and aggregation error.
- Consequence: Overflow or incompatible values are quarantined. Transform tests cover maximum integer/fraction boundaries.

## D-016 — Keep `/coins/list` in Bronze only

- Status: Accepted
- Decision: Collect `/coins/list` daily and retain it as an identifier audit, but do not create an unrequested `silver_coin_list` table.
- Rationale: The specified Silver contract lists eight tables and excludes coin list. No current Gold consumer needs a separate ID dimension.
- Consequence: Add the dimension only through a reviewed data-model change with a concrete consumer.

## D-017 — Normalize all trending asset types in Silver

- Status: Accepted
- Decision: Store coins, NFTs, and categories from `/search/trending` in `silver_trending_assets` with an `asset_type` discriminator. Gold follow-through uses only coin rows.
- Rationale: The Demo response contains all three collections and Bronze should not be the only place to query them; one sparse normalized table avoids three tiny tables.
- Consequence: Type-specific fields are nullable and quality rules vary by `asset_type`.

## D-018 — Manual backfill is one request per configured coin

- Status: Accepted
- Decision: Call `/coins/{id}/market_chart` with `days=365&interval=daily&vs_currency=usd` once for each of the ten supplied IDs, only through an explicit manual command.
- Rationale: CoinGecko documents daily interval and a 365-day Demo limit. Ten requests are simpler and cheaper than range chunking.
- Consequence: There is no Scheduler resource. The command shows estimated call impact and requires budget-gate approval before execution.

## D-019 — Resolve the remaining metadata coin IDs before Phase 2

- Status: Accepted
- Decision: Extend the supplied OHLC/backfill top ten with `tron`, `chainlink`, `polkadot`, `bitcoin-cash`, `stellar`, `shiba-inu`, `litecoin`, `wrapped-bitcoin`, `sui`, and `near` for the weekly metadata job.
- Rationale: These are explicit, stable CoinGecko IDs rather than a claim about a time-sensitive live top-20 ranking. Keeping the ordered list in reviewed configuration makes collection reproducible while the daily coin-list job provides a future source for deployment-time existence checks.
- Consequence: Contract tests require the metadata list to begin with the authoritative top ten, contain exactly twenty unique safe IDs, and match a sanitized `/coins/list` fixture. Changing membership requires configuration and fixture review; it does not happen dynamically from market rank.

## D-020 — Remote Terraform state and deployment identity

- Status: Open
- Decision needed: Choose or supply the S3/DynamoDB remote-state backend and GitHub OIDC roles/account IDs for dev/demo.
- Rationale: These values are account-specific and cannot be inferred safely from an empty repository.
- Consequence: Local validation can proceed, but no shared plan/apply workflow or deployment occurs until resolved.

## D-021 — Repository license

- Status: Open
- Decision needed: Select a license or intentionally keep the repository unlicensed.
- Rationale: Licensing is an owner/legal choice, not an implementation default.
- Consequence: Phase 0 does not create a `LICENSE` file.

## D-022 — Deliver the platform local-first through ports

- Status: Accepted
- Decision: Implement Local Phases 3–7 with a `JobRunner` that depends on narrow secret, Bronze storage, checkpoint, metrics, clock, and request ports. Use `EnvironmentSecretProvider`, `LocalBronzeStore`, `LocalCheckpointStore`, and `LocalMetricsSink` as the first adapters; replace them later through dependency injection.
- Rationale: The AWS account is locked, but the collection and data contracts can be implemented and validated locally without coupling the application core to AWS services.
- Consequence: The existing AWS architecture remains the deferred target rather than being discarded. AWS adapters and a thin Lambda composition adapter belong to Deferred Local Phase 8, and no AWS feature is considered deployed until an approved deployment and AWS validation succeed.

## D-023 — Keep local runtime data outside Git

- Status: Accepted
- Decision: Store local runtime artifacts only under ignored `data/bronze/`, `data/silver/`, `data/gold/`, `data/quarantine/`, and `data/checkpoints/` roots. Preserve existing logical partitions and run-scoped output contracts.
- Rationale: Local data can be large and may contain operational context that does not belong in source control. Fixed roots make ignore and secret-scanning policy enforceable.
- Consequence: `LocalBronzeStore` uses exclusive create semantics for immutable gzip JSON. Checkpoints may use atomic metadata replacement, while Silver, Gold, quarantine, and quality output remains run-scoped. None of these roots may be committed.

## D-024 — Keep local scheduling optional and disabled

- Status: Accepted
- Decision: The CLI is the active trigger through Local Phase 7. Any local scheduler must be proposed in a separate PR, remain disabled by default, and call the same `JobRunner` boundary.
- Rationale: Background scheduling adds lifecycle and accidental-live-call risk before it is needed for local validation.
- Consequence: Installing the project starts no scheduler. Historical backfill remains manual-only, and live CoinGecko use still requires explicit opt-in.

## D-025 — Separate connectivity evidence from deployment evidence

- Status: Accepted
- Decision: Record the approved one-request CoinGecko `/ping` smoke as passed without retaining sensitive output. Keep normal tests and CI offline. Treat all AWS deployment, Glue/Athena execution, and operational validation as blocked while the account is locked.
- Rationale: A successful API ping proves only local client and credential connectivity; source code, mocks, containers, and static checks do not prove managed AWS behavior.
- Consequence: `.env` remains local and untracked. Athena SQL is explicitly AWS-unvalidated. Documentation must not describe any AWS feature as deployed until an approved deployment and validation occur.
