# Market data providers

## Purpose

Finwall can enrich reports and analytics with market data, but the market-data layer is intentionally best-effort. This document explains exactly what providers are available, which commands depend on them, what diagnostics are exposed, and what Finwall does **not** guarantee.

## Provider options

Finwall currently supports two market-data provider values via `FINWALL_MARKET_DATA_PROVIDER`:

- `static` (default)
- `yahoo`

Provider construction behavior is currently:

- `yahoo` selects `YahooMarketDataProvider`
- any other value falls back to `StaticMarketDataProvider`

This means unsupported provider names do not crash startup; they behave like `static`.

## Static provider

`static` is the safe deterministic provider:

- No network calls.
- Useful for tests and reproducible local runs.
- Returns only configured in-memory values.
- Missing quotes/indexes/historical bars are expected unless explicitly configured.

Because `static` is deterministic and local, it is the default in configuration.

## Yahoo provider

`yahoo` uses public Yahoo Finance endpoints (`query1.finance.yahoo.com`) without an API key.

Key characteristics:

- Uses unofficial/public endpoints rather than a contracted broker-grade feed.
- Supports latest quote retrieval for tickers.
- Supports index quote retrieval via Finwall index alias mapping.
- Supports historical daily bars used by technical and market-condition logic.
- May fail due to endpoint changes, rate limiting/throttling, network issues, malformed responses, or missing symbol/price data.

## Supported operations

| Operation | Static provider | Yahoo provider | Used by |
|---|---|---|---|
| Latest holding prices | Configured data only | Yes | `snapshot --live-prices`, `recommendations --live-prices`, `evaluate-order --live-prices`, `report --live-prices`, `run-scheduled-report --live-prices` |
| Index quotes | Configured data only | Yes (via symbol map) | `market-index`, `report --market-index`, scheduled report market-index options |
| Historical bars | Configured data only | Yes | `technicals`, `market-condition`, and report/scheduled report market-condition sections |

Current index aliases (`INDEX_SYMBOL_MAP`):

- `SP500` -> `^GSPC`
- `NASDAQ` -> `^IXIC`

## Diagnostics and error reporting

Finwall exposes structured market-data diagnostics through the `market-data-diagnostics` command.

Examples:

```bash
poetry run finwall market-data-diagnostics --ticker NVDA --index SP500 --historical-days 30
poetry run finwall market-data-diagnostics --ticker NVDA --index SP500 --json
```

Text mode prints simple status plus safe reason strings. JSON mode includes structured objects for:

- ticker latest quote status
- ticker historical result (`bars`, `available`, `error`, `error_code`, `diagnostics`)
- index quote status

Diagnostic object fields:

- `provider`
- `operation`
- `symbol`
- `code`
- `severity`
- `user_message`
- `debug_message`
- `http_status`
- `retryable`

Current diagnostic/error codes include:

- `invalid_input`
- `timeout`
- `http_error`
- `rate_limited`
- `network_error`
- `malformed_response`
- `missing_symbol`
- `missing_price`
- `missing_historical_data`
- `unsupported_provider`
- `unknown`

Illustrative JSON shape:

```json
{
  "tickers": {
    "NVDA": {
      "latest": {
        "available": false,
        "price": null,
        "error": "provider rate-limited request",
        "error_code": "rate_limited",
        "diagnostic": {
          "provider": "yahoo-finance-public",
          "operation": "latest_prices",
          "symbol": "NVDA",
          "code": "rate_limited",
          "severity": "warning",
          "user_message": "provider rate-limited request",
          "debug_message": "HTTP 429",
          "http_status": 429,
          "retryable": true
        }
      },
      "historical": {
        "ticker": "NVDA",
        "bars": [],
        "source": "yahoo-finance-public",
        "available": false,
        "error": "historical data unavailable",
        "error_code": "missing_historical_data",
        "diagnostics": []
      }
    }
  },
  "indexes": {
    "SP500": {
      "available": true,
      "price": "5300.12",
      "error": null,
      "error_code": null,
      "diagnostic": null
    }
  }
}
```

## Data freshness expectations

Finwall does **not** guarantee real-time quotes.

- Provider data can be delayed.
- Provider data can be stale or temporarily unavailable.
- Finwall is not a broker-grade quote terminal.
- Finwall does not currently provide a hard freshness guarantee for every returned quote.

Use market data as decision support, not as a source for execution-critical timing.

## Rate limits and availability

For the Yahoo provider in particular:

- Public endpoints may throttle or temporarily block requests.
- Rate limits are not contractually stable.
- Availability can change without notice.

If diagnostics show rate-limit style failures (`rate_limited`, HTTP 429, retryable warnings), treat this as a provider availability issue.

For scheduled runs, design operational expectations around occasional missing market data rather than assuming uninterrupted provider access.

## Unsupported guarantees

Finwall does **not** guarantee:

- real-time quotes
- complete quote coverage
- complete historical data
- uninterrupted provider availability
- provider schema stability
- broker-grade pricing accuracy
- execution-quality pricing
- that reports/recommendations reflect all market-moving information

Also:

- Finwall does not execute trades.
- Finwall is decision support only.
- Final decisions remain with the user.

## How provider limitations affect reports and analytics

- `snapshot --live-prices`, `recommendations --live-prices`, `report --live-prices`, and `run-scheduled-report --live-prices` tolerate missing quotes and continue with warnings/partial valuation.
- Missing latest prices can reduce confidence or make valuation/recommendation context incomplete.
- `technicals` and `market-condition` rely on historical bars; insufficient bars can make outputs unavailable/limited.
- Manual `--price TICKER=VALUE` inputs can override live-price gaps in commands that support manual prices.

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| Missing latest price | Symbol unavailable, malformed response, or provider omission | Retry later, run `market-data-diagnostics`, or use manual `--price` overrides where supported |
| Empty/insufficient technical output | Missing or too-short historical bar set | Increase historical day window where available, retry later, check diagnostics |
| `rate_limited`/HTTP 429 style diagnostics | Provider throttling | Retry later, reduce request frequency, avoid repeated manual polling |
| Static provider returns unavailable values | Fixture/config data not set for symbols | Configure static fixture data for tests, or provide manual prices |

## Safety notes

Market data in Finwall is best-effort decision-support input. Do not treat it as trade execution infrastructure or authoritative real-time pricing.
