# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python 3.14 application with a Streamlit interface, DuckDB analytics, Parquet datasets, and local filesystem storage. The attached brief explicitly delegates this stack and keeps AWS as a later deployment target.

## Users

The primary user is the project owner: a data-engineering practitioner who runs CryptoPulse locally to inspect cryptocurrency market structure and demonstrate an understandable, production-minded data pipeline in a portfolio.

## Product Purpose

CryptoPulse turns reviewed CoinGecko Demo REST responses into inspectable Bronze, Silver, and Gold datasets, then presents market context and screening tools without trading automation or predictive claims. The first release succeeds when one manual refresh produces durable data and a useful Market Overview and Coin Screener.

## Positioning

Unlike a price-board clone, CryptoPulse exposes both the market view and the local data lineage behind it. Every dashboard value can be traced to a timestamped Bronze response and a reproducible local transform.

## Operating Context

- The application runs on a developer workstation and is started manually from PowerShell.
- Collection is explicit polling; no scheduler, WebSocket, webhook, or background service runs during development.
- The dashboard reads local Gold and Silver data and never receives the CoinGecko API key.
- AWS Lambda, S3, Glue, Athena, and deployment remain future adapters, not current capabilities.

## Capabilities and Constraints

- Current scope: `/coins/markets` and `/global`, local Bronze JSON.gz, Silver Parquet, Gold metrics, Market Overview, and Coin Screener.
- Coin screener data includes rank, price, 1h/24h/7d change, market cap, volume, supply, ATH, ATL, and source freshness.
- Collection must respect the reviewed endpoint allow-list, bounded retries, secret redaction, and explicit manual execution.
- Data and secrets remain local and ignored by Git.
- Coin Detail, Trending, Category Analytics, portfolio tracking, alerts, cloud deployment, authentication, AI/ML, and trading are outside this release.

## Brand Commitments

The product name is CryptoPulse. Copy should be factual, calm, and suitable for a data-engineering portfolio. The interface must display “Data provided by CoinGecko” with a direct API link and must not imply real-time prices or investment advice.

## Evidence on Hand

Sanitized CoinGecko fixtures exist under `tests/fixtures/`, and the collector, retry policy, Bronze envelope, structured logging, and contract tests are already implemented. No customer claims, deployment evidence, or live production metrics exist and none may be fabricated.

## Product Principles

- Show lineage, freshness, and data state instead of hiding the pipeline.
- Prefer one explicit manual workflow over background automation.
- Keep the Python package flat until real module clusters appear.
- Derive useful analytics locally before spending more API credits.
- Present market information as analysis, never as financial advice.

## Accessibility & Inclusion

The web interface must remain keyboard-operable, responsive, readable at common zoom levels, and must not rely on color alone to communicate gains, losses, loading, empty, or error states.
