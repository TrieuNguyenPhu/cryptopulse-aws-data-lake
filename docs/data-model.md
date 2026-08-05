# Data model

## Bronze envelope

Each HTTP 200 response is stored as gzip JSON with collection metadata and the untouched parsed
payload.

```json
{
  "metadata": {
    "source": "coingecko",
    "endpoint": "/coins/markets",
    "job_name": "market_snapshot",
    "run_id": "uuid",
    "requested_at": "UTC timestamp",
    "received_at": "UTC timestamp",
    "http_status": 200,
    "latency_ms": 125,
    "record_count": 250,
    "parameters": {"vs_currency": "usd"}
  },
  "payload": []
}
```

The object path contains entity, UTC collection partitions, job name, run ID, and request ID.
Create-only writes make a collision fail instead of replacing source data.

## Silver

`market_snapshot.parquet` contains one row per coin per collection:

```text
collected_at, run_id, source_updated_at, coin_id, symbol, name, image,
current_price, change_1h, change_24h, change_7d, market_cap,
market_cap_rank, total_volume, circulating_supply, ath, atl
```

`global_market.parquet` contains one row per global collection:

```text
collected_at, run_id, source_updated_at, active_cryptocurrencies,
total_market_cap_usd, total_volume_usd, btc_dominance, eth_dominance,
market_cap_change_24h
```

Source timestamps are normalized to timezone-aware UTC. Missing optional market numbers remain
null; invalid object shapes, identifiers, or timestamps stop the build with a clear error. Bronze
remains available for correction and replay.

## Gold

`market_overview.parquet` contains the latest global snapshot joined with breadth computed from the
latest market snapshot:

```text
collected_at, source_updated_at, active_cryptocurrencies,
total_market_cap_usd, total_volume_usd, btc_dominance, eth_dominance,
market_cap_change_24h, volume_to_market_cap, gainers, losers, unchanged,
tracked_coins, market_breadth
```

`market_breadth = gainers / tracked_coins`. A null 24-hour change counts as unchanged. The
dashboard reads this Gold row for summary metrics and queries Silver for top-coin tables, history,
and screener results.
