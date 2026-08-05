# Data model

## Modeling principles

- Bronze preserves the exact successful API payload and collection context. It is never corrected in place.
- Silver is typed, flattened where useful, deduplicated, quality-checked, and suitable for reuse.
- Gold contains portfolio analytics derived only from accepted Silver rows.
- All timestamps are UTC. Millisecond Unix timestamps are converted without passing through local time.
- Financial values use fixed-point decimals rather than binary floating point.
- `snapshot_date` is the only required partition key. `coin_id` is never a partition key.
- Column names use `snake_case`. Source field meaning is preserved; derived columns are documented.
- Data Catalog schemas are explicit and version-controlled. Crawlers do not define production schemas.

## Type conventions

| Logical type | Glue/Athena type | Use |
|---|---|---|
| Identifier/text | `string` | IDs, names, symbols, URLs |
| Currency/quantity | `decimal(38,18)` | prices, market caps, volume, supply, OHLC |
| Percentage/ratio | `decimal(20,10)` | changes, dominance, rates |
| Rank/count | `int` or `bigint` | ranks and counts |
| Event time | `timestamp` | UTC instant |
| Calendar day | `date` | `snapshot_date` partition |
| Flexible source map | `map<string,string>` or typed map | low-value dynamic source keys |
| Repeated primitive | `array<string>` | categories, sites, top coin IDs |

`decimal(38,18)` leaves twenty integer digits. Any value that cannot be safely cast is quarantined rather than silently rounded or converted to double.

## Local storage mapping

The logical Bronze, Silver, Gold, quarantine, partition, and business-key contracts in this document are unchanged. Local adapters map them under these repository-relative runtime roots:

| Layer/state | Local root | Physical format |
|---|---|---|
| Bronze | `data/bronze/` | one immutable gzip JSON envelope per successful response |
| Silver | `data/silver/` | Snappy Parquet in `snapshot_date` and run-scoped paths |
| Gold | `data/gold/` | Snappy Parquet in `snapshot_date` and run-scoped paths |
| Quarantine/reports | `data/quarantine/` | gzip JSON records, schema-drift manifests, and quality reports |
| Checkpoints | `data/checkpoints/` | adapter-owned atomic checkpoint metadata; never source data |

All five roots are local-only and must remain ignored and untracked. `snapshot_date` remains the only required data partition key, `coin_id` is never a partition key, and each transform run writes to a unique `run_id` path. Deferred S3 adapters remove the leading `data/` root while preserving the remaining logical layout and contracts.

## Bronze contract

### Envelope

Every successful response is stored as one gzip-compressed JSON document with these required fields:

```json
{
  "metadata": {
    "source": "coingecko",
    "endpoint": "/coins/markets",
    "job_name": "market_snapshot",
    "run_id": "00000000-0000-0000-0000-000000000000",
    "requested_at": "2026-08-04T00:00:00.000000Z",
    "received_at": "2026-08-04T00:00:00.250000Z",
    "http_status": 200,
    "latency_ms": 250,
    "record_count": 250,
    "parameters": {
      "vs_currency": "usd"
    }
  },
  "payload": []
}
```

`payload` is the API response exactly as parsed JSON: an array for array endpoints and an object for object endpoints. It is not normalized, sorted, filtered, rounded, or decorated. `parameters` contains all effective allow-listed query parameters, including supported defaults deliberately set by CryptoPulse, and cannot contain an API key. Response headers are not persisted.

Request IDs are recorded in structured logs and the object filename, while `run_id` remains the envelope-level correlation key required by the contract.

### Object key

```text
bronze/coingecko/
  entity=market_snapshot/
  year=2026/month=08/day=04/hour=00/
  market_snapshot_20260804T000000Z_<run_id>_<request_id>.json.gz
```

Scoped jobs add the safe CoinGecko ID before the IDs, for example `coin_ohlc_bitcoin_...json.gz`. The key is unique and created conditionally. A repeated job never overwrites an existing object.

### Bronze entities and counts

| Entity | Payload shape | `record_count` |
|---|---|---:|
| `market_snapshot` | array of coins | array length |
| `global_market` | object containing `data` | 1 |
| `trending` | object containing three arrays | sum of `coins`, `nfts`, `categories` lengths |
| `categories` | array of categories | array length |
| `exchanges` | array of exchanges | array length |
| `coin_list` | array of coin identifiers | array length |
| `coin_metadata` | one coin object per request | 1 |
| `coin_ohlc` | array of five-value candles | array length |
| `historical_market` | object containing three time series | count of distinct timestamps across all series |

## Silver common columns

Every Silver table includes these lineage fields unless a table definition below gives a more specific name:

| Column | Type | Null | Meaning |
|---|---|---:|---|
| `run_id` | `string` | no | originating collection run |
| `received_at` | `timestamp` | no | successful response receipt time in UTC |
| `source_endpoint` | `string` | no | path without host or credentials |
| `snapshot_date` | `date` | no | low-cardinality partition date |

When duplicate business keys occur, the deterministic default tie-breaker is descending `received_at`, then descending `run_id`. Endpoint-specific source timestamps take precedence where stated.

## Silver tables

### `silver_market_snapshots`

One row per coin and CoinGecko source update.

| Column | Type | Null |
|---|---|---:|
| `coin_id` | `string` | no |
| `symbol` | `string` | no |
| `name` | `string` | no |
| `image_url` | `string` | yes |
| `current_price` | `decimal(38,18)` | yes |
| `market_cap` | `decimal(38,18)` | yes |
| `market_cap_rank` | `int` | yes |
| `fully_diluted_valuation` | `decimal(38,18)` | yes |
| `total_volume` | `decimal(38,18)` | yes |
| `high_24h` | `decimal(38,18)` | yes |
| `low_24h` | `decimal(38,18)` | yes |
| `price_change_24h` | `decimal(38,18)` | yes |
| `price_change_percentage_1h` | `decimal(20,10)` | yes |
| `price_change_percentage_24h` | `decimal(20,10)` | yes |
| `price_change_percentage_7d` | `decimal(20,10)` | yes |
| `market_cap_change_24h` | `decimal(38,18)` | yes |
| `market_cap_change_percentage_24h` | `decimal(20,10)` | yes |
| `circulating_supply` | `decimal(38,18)` | yes |
| `total_supply` | `decimal(38,18)` | yes |
| `max_supply` | `decimal(38,18)` | yes |
| `ath` | `decimal(38,18)` | yes |
| `ath_date` | `timestamp` | yes |
| `atl` | `decimal(38,18)` | yes |
| `atl_date` | `timestamp` | yes |
| `source_updated_at` | `timestamp` | no |
| common lineage columns |  |  |

- Business key: `(coin_id, source_updated_at)`.
- Partition: date of `source_updated_at`, falling back to `received_at` only for quarantine routing when invalid.
- Batch expectation: at least 200 accepted rows per scheduled collection window; lower counts create a quality warning.

### `silver_global_market`

One row per CoinGecko global update. Source currency maps remain available in Bronze; Silver promotes the USD and dominance fields used by analytics.

| Column | Type | Null |
|---|---|---:|
| `active_cryptocurrencies` | `bigint` | yes |
| `markets` | `bigint` | yes |
| `total_market_cap_usd` | `decimal(38,18)` | yes |
| `total_volume_usd` | `decimal(38,18)` | yes |
| `market_cap_percentage` | `map<string,decimal(20,10)>` | yes |
| `btc_dominance_percentage` | `decimal(20,10)` | yes |
| `eth_dominance_percentage` | `decimal(20,10)` | yes |
| `market_cap_change_percentage_24h_usd` | `decimal(20,10)` | yes |
| `volume_change_percentage_24h_usd` | `decimal(20,10)` | yes |
| `source_updated_at` | `timestamp` | no |
| common lineage columns |  |  |

- Business key: `source_updated_at`.
- Partition: date of `source_updated_at`.

### `silver_trending_assets`

One normalized row for each trending coin, NFT, or category. Fields that do not apply to an asset type are nullable.

| Column | Type | Null |
|---|---|---:|
| `snapshot_hour` | `timestamp` | no |
| `asset_type` | `string` | no |
| `asset_id` | `string` | no |
| `trending_rank` | `int` | no |
| `name` | `string` | no |
| `symbol` | `string` | yes |
| `slug` | `string` | yes |
| `market_cap_rank` | `int` | yes |
| `price_btc` | `decimal(38,18)` | yes |
| `price_usd` | `decimal(38,18)` | yes |
| `price_change_percentage_24h_usd` | `decimal(20,10)` | yes |
| `floor_price_native` | `decimal(38,18)` | yes |
| `floor_price_change_percentage_24h` | `decimal(20,10)` | yes |
| `coins_count` | `bigint` | yes |
| common lineage columns |  |  |

- `asset_type` is one of `coin`, `nft`, or `category`.
- `snapshot_hour` is `requested_at` truncated to the UTC hour because the source response has no snapshot timestamp.
- `trending_rank` is the zero-based source array order within each asset type.
- Business key: `(snapshot_hour, asset_type, asset_id)`.
- Partition: date of `snapshot_hour`.

### `silver_categories`

| Column | Type | Null |
|---|---|---:|
| `category_id` | `string` | no |
| `name` | `string` | no |
| `content` | `string` | yes |
| `market_cap` | `decimal(38,18)` | yes |
| `market_cap_change_percentage_24h` | `decimal(20,10)` | yes |
| `volume_24h` | `decimal(38,18)` | yes |
| `top_3_coin_ids` | `array<string>` | yes |
| `source_updated_at` | `timestamp` | no |
| common lineage columns |  |  |

- Business key: `(category_id, source_updated_at)`.
- Partition: date of `source_updated_at`.

### `silver_exchanges`

| Column | Type | Null |
|---|---|---:|
| `snapshot_at` | `timestamp` | no |
| `exchange_id` | `string` | no |
| `name` | `string` | no |
| `year_established` | `int` | yes |
| `country` | `string` | yes |
| `url` | `string` | yes |
| `image_url` | `string` | yes |
| `has_trading_incentive` | `boolean` | yes |
| `trust_score` | `int` | yes |
| `trust_score_rank` | `int` | yes |
| `trade_volume_24h_btc` | `decimal(38,18)` | yes |
| common lineage columns |  |  |

- `snapshot_at` is `requested_at` truncated to the UTC day because this response has no update timestamp.
- Business key: `(snapshot_at, exchange_id)`.
- Partition: date of `snapshot_at`.

### `silver_coin_metadata`

Market/community/developer/ticker sections are disabled at collection, so this table contains slowly changing descriptive data only.

| Column | Type | Null |
|---|---|---:|
| `snapshot_week` | `date` | no |
| `coin_id` | `string` | no |
| `symbol` | `string` | no |
| `name` | `string` | no |
| `asset_platform_id` | `string` | yes |
| `platforms` | `map<string,string>` | yes |
| `categories` | `array<string>` | yes |
| `description_en` | `string` | yes |
| `homepage_url` | `string` | yes |
| `blockchain_sites` | `array<string>` | yes |
| `image_url` | `string` | yes |
| `country_origin` | `string` | yes |
| `genesis_date` | `date` | yes |
| `hashing_algorithm` | `string` | yes |
| `block_time_minutes` | `decimal(20,10)` | yes |
| `market_cap_rank` | `int` | yes |
| `source_updated_at` | `timestamp` | yes |
| common lineage columns |  |  |

- `snapshot_week` is the Monday UTC date for the collection week.
- Business key: `(snapshot_week, coin_id)`.
- Partition: collection `snapshot_date`.

### `silver_coin_ohlc`

| Column | Type | Null |
|---|---|---:|
| `coin_id` | `string` | no |
| `vs_currency` | `string` | no |
| `candle_close_at` | `timestamp` | no |
| `open_price` | `decimal(38,18)` | no |
| `high_price` | `decimal(38,18)` | no |
| `low_price` | `decimal(38,18)` | no |
| `close_price` | `decimal(38,18)` | no |
| common lineage columns |  |  |

- Source array order is `[close_timestamp_ms, open, high, low, close]`; CoinGecko documents the timestamp as candle close time.
- Business key: `(coin_id, vs_currency, candle_close_at)`.
- Partition: date of `candle_close_at`.

### `silver_historical_market`

The three source arrays are full-outer-joined on timestamp so missing metrics remain observable rather than being silently discarded.

| Column | Type | Null |
|---|---|---:|
| `coin_id` | `string` | no |
| `vs_currency` | `string` | no |
| `observed_at` | `timestamp` | no |
| `price` | `decimal(38,18)` | yes |
| `market_cap` | `decimal(38,18)` | yes |
| `total_volume` | `decimal(38,18)` | yes |
| common lineage columns |  |  |

- Business key: `(coin_id, vs_currency, observed_at)`.
- Partition: date of `observed_at`, not backfill execution date.
- `historical_backfill` is the only producer and remains manual-only.

### Deliberate omission: Silver coin list

The required Silver table list does not include `silver_coin_list`. `/coins/list` is therefore retained in Bronze as a daily identifier audit and used to validate configured CoinGecko IDs. Adding a Silver ID dimension is deferred until a concrete consumer requires it.

## Gold tables

Gold schemas may add quality/freshness flags during implementation, but these are the minimum contracts.

### `gold_market_overview_hourly`

Hourly nearest-valid global and market-snapshot overview.

| Column | Type |
|---|---|
| `hour_at` | `timestamp` |
| `total_market_cap_usd` | `decimal(38,18)` |
| `total_volume_usd` | `decimal(38,18)` |
| `btc_dominance_percentage` | `decimal(20,10)` |
| `eth_dominance_percentage` | `decimal(20,10)` |
| `active_cryptocurrencies` | `bigint` |
| `top_10_market_cap_usd` | `decimal(38,18)` |
| `top_10_market_share_percentage` | `decimal(20,10)` |
| `market_snapshot_record_count` | `int` |
| `is_complete` | `boolean` |
| `snapshot_date` | `date` partition |

Business key: `hour_at`.

### `gold_daily_coin_performance`

| Column | Type |
|---|---|
| `performance_date` | `date` |
| `coin_id` | `string` |
| `open_price` / `high_price` / `low_price` / `close_price` | `decimal(38,18)` |
| `daily_return_percentage` | `decimal(20,10)` |
| `close_market_cap` / `close_total_volume` | `decimal(38,18)` |
| `start_rank` / `end_rank` | `int` |
| `observation_count` | `int` |
| `snapshot_date` | `date` partition |

Business key: `(performance_date, coin_id)`. Open/close are the earliest/latest accepted market snapshots, not exchange trade candles.

### `gold_market_rank_movements`

| Column | Type |
|---|---|
| `movement_date` | `date` |
| `coin_id` | `string` |
| `start_rank` / `end_rank` / `best_rank` / `worst_rank` | `int` |
| `rank_change` | `int` |
| `observation_count` | `int` |
| `snapshot_date` | `date` partition |

`rank_change = start_rank - end_rank`, so a positive number means the coin moved toward rank 1. Business key: `(movement_date, coin_id)`.

### `gold_category_performance`

| Column | Type |
|---|---|
| `performance_date` | `date` |
| `category_id` / `category_name` | `string` |
| `start_market_cap` / `end_market_cap` / `end_volume_24h` | `decimal(38,18)` |
| `market_cap_change_percentage` | `decimal(20,10)` |
| `source_change_percentage_24h` | `decimal(20,10)` |
| `snapshot_date` | `date` partition |

Business key: `(performance_date, category_id)`.

### `gold_trending_followthrough`

Coin assets only; NFT and category trends remain queryable in Silver.

| Column | Type |
|---|---|
| `trending_at` | `timestamp` |
| `coin_id` | `string` |
| `trending_rank` | `int` |
| `price_at_trend` / `price_1h_after` / `price_24h_after` | `decimal(38,18)` |
| `return_1h_percentage` / `return_24h_percentage` | `decimal(20,10)` |
| `has_1h_observation` / `has_24h_observation` | `boolean` |
| `snapshot_date` | `date` partition |

Nearest later snapshot within a documented tolerance wins. Business key: `(trending_at, coin_id)`.

### `gold_exchange_rankings`

| Column | Type |
|---|---|
| `ranking_date` | `date` |
| `exchange_id` / `name` / `country` | `string` |
| `trust_score` / `trust_score_rank` | `int` |
| `trade_volume_24h_btc` | `decimal(38,18)` |
| `volume_rank` | `int` |
| `snapshot_date` | `date` partition |

Business key: `(ranking_date, exchange_id)`.

### `gold_market_dominance`

| Column | Type |
|---|---|
| `hour_at` | `timestamp` |
| `asset_symbol` | `string` |
| `dominance_percentage` | `decimal(20,10)` |
| `change_1h_percentage_points` / `change_24h_percentage_points` | `decimal(20,10)` |
| `snapshot_date` | `date` partition |

The source dominance map is exploded to one row per asset symbol. Business key: `(hour_at, asset_symbol)`.

### `gold_data_quality_summary`

| Column | Type |
|---|---|
| `quality_run_id` | `string` |
| `checked_at` | `timestamp` |
| `dataset_name` / `check_name` / `check_scope` | `string` |
| `status` | `string` |
| `severity` | `string` |
| `total_count` / `failed_count` | `bigint` |
| `failure_percentage` | `decimal(20,10)` |
| `details_json` | `string` |
| `snapshot_date` | `date` partition |

`status` is one of `pass`, `warn`, or `fail`; `severity` is `info`, `warning`, or `critical`. Business key: `(quality_run_id, dataset_name, check_name)`.

## Deterministic deduplication

| Table | Business key | Winner |
|---|---|---|
| market snapshots | `coin_id`, `source_updated_at` | latest `received_at`, then greatest `run_id` |
| global market | `source_updated_at` | latest `received_at`, then greatest `run_id` |
| trending assets | `snapshot_hour`, `asset_type`, `asset_id` | latest `received_at`, then lowest source rank |
| categories | `category_id`, `source_updated_at` | latest `received_at`, then greatest `run_id` |
| exchanges | `snapshot_at`, `exchange_id` | latest `received_at`, then greatest `run_id` |
| coin metadata | `snapshot_week`, `coin_id` | latest `received_at`, then greatest `run_id` |
| OHLC | `coin_id`, `vs_currency`, `candle_close_at` | latest `received_at`, then greatest `run_id` |
| historical market | `coin_id`, `vs_currency`, `observed_at` | latest `received_at`, then greatest `run_id` |

## Reusable data-quality checks

### Row checks

| Dataset | Check | Severity/action |
|---|---|---|
| all | required business-key fields are non-null/non-empty | fail; quarantine row |
| all | `received_at` parses as a UTC instant and is not implausibly future-dated | fail; quarantine row |
| market snapshot | `current_price >= 0` when present | fail; quarantine row |
| market snapshot | `market_cap >= 0` and `total_volume >= 0` when present | fail; quarantine row |
| market snapshot | `market_cap_rank > 0` or null | fail; quarantine row |
| categories | market cap and volume are non-negative when present | fail; quarantine row |
| exchanges | trust rank is positive or null; volume is non-negative | fail; quarantine row |
| OHLC | `high_price >= open_price` and `high_price >= close_price` | fail; quarantine row |
| OHLC | `low_price <= open_price` and `low_price <= close_price` | fail; quarantine row |
| OHLC | `low_price <= high_price` and all values are non-negative | fail; quarantine row |
| historical | present financial values are non-negative | fail; quarantine row |
| all | decimal cast succeeds without overflow | fail; quarantine row |
| all | no duplicate survives on the business key | critical batch failure |

### Batch and freshness checks

| Check | Expected behavior |
|---|---|
| market snapshot size | normally at least 200 accepted coins per ten-minute window; warn below 200, fail at zero |
| missing collection windows | compare observed Bronze envelopes with expected UTC windows per schedule and list each missing window |
| source timestamp freshness | market source update within 20 minutes of receipt; global within 2 hours; categories within 12 hours |
| scoped completeness | daily OHLC expects ten configured coin responses; weekly metadata expects twenty |
| response status | only HTTP 200 enters Bronze; any non-200 appears in operational metrics, not as a false Bronze success |
| count reconciliation | `bronze record_count = accepted Silver rows + quarantined rows + documented duplicate rows` for each run |
| dominance reasonableness | values are non-negative and their reported sum is within a documented tolerance of 100; warn rather than discard |
| historical series alignment | report timestamps missing price, market cap, or volume; price missing is a failed row |

Missing-window checks use the schedule configuration as data rather than hard-coded copies in each transform. Planned frequencies are 144 market, 24 global, 24 trending, 4 category, 1 exchange, and 1 coin-list window per complete UTC day; scoped counts are evaluated separately.

## Quarantine contract

Invalid records are written as gzip JSON to the Quarantine prefix with:

| Field | Type | Meaning |
|---|---|---|
| `dataset_name` | string | intended Silver table |
| `run_id` | string | originating collection run |
| `business_key_json` | string | safe serialized key fields |
| `source_endpoint` | string | safe endpoint path |
| `received_at` | timestamp | collection time |
| `quarantined_at` | timestamp | transform time |
| `failure_reasons` | array<string> | every failed check, not only the first |
| `record_json` | string | exact candidate row before destructive casting |
| `snapshot_date` | date | quarantine partition |

Schema-drift manifests are batch-level records containing expected/observed schema fingerprints, additive/missing/incompatible paths, entity, transform run, and detection time. They never contain credentials or HTTP headers.

## Partition publication and recovery

Each local transform writes a complete rebuilt `snapshot_date` partition to a new `run_id` path. After row, duplicate, and reconciliation checks pass, a local selected-run manifest may publish that run to DuckDB and Streamlit consumers. A failed run cannot replace the last validated selection, and previous run paths remain available for local rollback or deliberate cleanup.

In Deferred Local Phase 8, the same contract maps to an S3 run-scoped prefix followed by a Glue Data Catalog partition-location update. That AWS publication path and all Athena SQL remain AWS-unvalidated while the account is locked. Both adapters avoid in-place mutation and duplicate Parquet files without adding an open table format that the project did not request.

## Schema evolution policy

1. Additive nullable field: warn, retain raw, continue known-column transform, then review a contract update.
2. Missing optional field: accept null and record drift.
3. Missing required/business-key field: quarantine affected rows and fail the relevant completeness check.
4. Compatible numeric widening: require an explicit versioned schema change before publication.
5. Incompatible type or decimal overflow: quarantine; never coerce through a string/double round trip.
6. Renames/removals: treat as breaking until a reviewed mapping and fixture are committed.

Every schema change updates this document, the explicit Spark/Data Catalog schema, sanitized fixtures, contract tests, and `docs/decisions.md` when it changes a modeling decision.
