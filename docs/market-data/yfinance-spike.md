# yfinance market data provider decision

## Current decision

Finwall uses `yfinance` as the default market-data provider for local/self-managed live-price workflows.

`FINWALL_MARKET_DATA_PROVIDER` remains an override/debug setting:

- `yfinance` uses the normal runtime `YFinanceMarketDataProvider`.
- `yahoo` uses Finwall's direct Yahoo public-endpoint provider.
- `static` uses manually supplied prices and explicit test/demo fixtures.

Manual CLI `--price TICKER=PRICE` values remain available and override fetched live prices where existing workflows merge both sources.

## Source caveat

The `yfinance` project describes itself on PyPI as a Pythonic way to fetch market data from Yahoo Finance and states that it is not affiliated, endorsed, or vetted by Yahoo. The project page also points users to Yahoo terms for rights to use downloaded data and describes Yahoo Finance API usage as personal-use oriented.

This means `yfinance` is not a guaranteed production data source. Finwall must not present it as broker-grade, real-time, institutional, or suitable for automated trading. Free providers may be unavailable, delayed, stale, partial, malformed, rate-limited, or blocked.

## Comparison

| Area | Direct Yahoo public-endpoint provider | Default yfinance provider | Current result |
|---|---|---|---|
| Dependency model | Uses Python standard library networking. | Normal runtime dependency with transitive dataframe/networking packages. | Accepted for live-data-first behavior. |
| Provider selection | `FINWALL_MARKET_DATA_PROVIDER=yahoo`. | Default; can also be selected explicitly with `FINWALL_MARKET_DATA_PROVIDER=yfinance`. | Users do not need env configuration for normal live prices. |
| Quote support | Uses Yahoo quote endpoint and maps `regularMarketPrice` plus currency into `MarketPrice`. | Uses timeout-aware `Ticker(...).history(period="5d", interval="1d", timeout=...)` and maps the latest close into `MarketPrice`. | Both remain decision-support providers. |
| Historical price support | Uses Yahoo chart endpoint and maps closes/volumes into `HistoricalPriceBar`. | Uses `Ticker(...).history(period=..., interval="1d")` and maps rows into `HistoricalPriceBar`. | Supports technical-analysis style decision-support inputs. |
| Index quote support | Uses Finwall's existing `INDEX_SYMBOL_MAP`, such as `SP500` to `^GSPC`. | Reuses the same `INDEX_SYMBOL_MAP` and returns `IndexQuote`. | Keeps index behavior consistent. |
| Failure behavior | Catches network, HTTP, timeout, and payload failures and returns unavailable objects or empty history. | Catches import failures, provider exceptions, empty history, malformed rows, missing prices, and invalid numeric values. | Safe unavailable results are preferred over raw provider tracebacks. |
| Rate-limit/blocking risk | Public Yahoo endpoints may be delayed, blocked, rate-limited, or changed. | Same upstream Yahoo fragility, plus dependency behavior changes outside Finwall's control. | No production reliability claim. |
| Testability without network access | Tests monkeypatch fetch behavior and do not use the network. | Tests monkeypatch fake providers or fake `yfinance` modules and do not call the real service. | Meets no-network test requirement. |

## Implementation notes

- Adapter module: `src/finwall/market_data_yfinance.py`.
- Provider selector: `FINWALL_MARKET_DATA_PROVIDER`.
- Dependency handling: `yfinance` is declared as a normal Poetry runtime dependency.
- Default behavior: `yfinance` is the default; `static` is explicit for tests, demos, and manual override workflows.
- Existing Yahoo behavior: `yahoo` still uses Finwall's standard-library Yahoo public-endpoint provider.
- Diagnostics: `market-data-check` reports configured provider, effective provider, yfinance availability where practical, latest quote status, and historical-price status.

## Non-goals

- Provider fallback chain.
- Broker integration, automatic trading, or order execution.
- Real-time or streaming market data.
- Guaranteed production, institutional, or broker-grade market data.
