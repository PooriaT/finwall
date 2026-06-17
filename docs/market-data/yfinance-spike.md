# yfinance market data provider spike

## Decision

Finwall will include a small optional `yfinance` adapter behind the existing `MarketDataProvider` interface.

`yfinance` remains disabled by default. The default provider is still `static`, and the existing `YahooMarketDataProvider` remains the supported Yahoo public-endpoint implementation. The `yfinance` adapter is an experimental opt-in provider for local/self-managed decision-support workflows only.

## Source caveat

The `yfinance` project describes itself on [PyPI](https://pypi.org/project/yfinance/) as a Pythonic way to fetch market data from Yahoo Finance and states that it is not affiliated, endorsed, or vetted by Yahoo. The project page also points users to Yahoo terms for rights to use downloaded data and describes Yahoo Finance API usage as personal-use oriented.

This means `yfinance` is not a guaranteed production data source. Finwall must not present it as broker-grade, real-time, institutional, or suitable for automated trading.

## Comparison

| Area | Current Yahoo public-endpoint provider | Optional yfinance adapter | Spike result |
|---|---|---|---|
| Dependency weight and transitive dependencies | Uses Python standard library only. No extra install footprint. | Pulls in `yfinance` and its data stack transitively, including heavier runtime dependencies such as dataframe/networking packages. | Acceptable only as an optional extra; not acceptable as a default dependency. |
| Install/runtime impact | Works in the default install. | Requires installing the optional `yfinance` extra. Normal Finwall imports still work because the adapter lazy-imports `yfinance`. | Implemented behind explicit provider selection. |
| Quote support | Uses Yahoo quote endpoint and maps `regularMarketPrice` plus currency into `MarketPrice`. | Uses `Ticker(...).fast_info` first, with a small fallback to `info`, then maps into `MarketPrice`. | Sufficient for a small experimental adapter. |
| Historical price support | Uses Yahoo chart endpoint and maps closes/volumes into `HistoricalPriceBar`. | Uses `Ticker(...).history(period=..., interval="1d")` and maps rows into `HistoricalPriceBar`. | Sufficient for technical-analysis style decision-support inputs. |
| Index quote support | Uses Finwall's existing `INDEX_SYMBOL_MAP`, such as `SP500` to `^GSPC`. | Reuses the same `INDEX_SYMBOL_MAP` and returns `IndexQuote`. | Keeps index behavior consistent. |
| Failure behavior | Catches network, HTTP, timeout, and payload failures and returns unavailable objects or empty history. | Catches import failures, provider exceptions, empty history, malformed rows, missing prices, and invalid numeric values. | Safe behavior matches Finwall's provider pattern. |
| Stale/missing data behavior | Detects stale latest quotes when Yahoo provides a market timestamp. Missing prices/currency are unavailable. | Does not add independent stale quote detection because `yfinance` does not expose the same timestamp path consistently through the adapter. Missing/invalid prices are unavailable. | Acceptable for experimental status; current Yahoo provider remains stronger for stale quote detection. |
| Rate-limit/blocking risk | Public Yahoo endpoints may be delayed, blocked, rate-limited, or changed. | Same upstream Yahoo fragility, plus dependency behavior changes outside Finwall's control. | No production reliability claim. |
| Testability without network access | Existing tests monkeypatch fetch behavior and do not use the network. | New tests monkeypatch a fake `yfinance` module and do not install or call the real service. | Meets no-network test requirement. |
| Legal/usage caveats | Yahoo public endpoint usage must remain self-managed and decision-support only. | `yfinance` is unofficial and its project directs users to Yahoo terms for usage rights. | Documentation must keep the caveat visible. |
| Fit for Finwall positioning | Fits as optional decision-support enrichment, not guaranteed data. | Fits only as experimental opt-in enrichment. | Adapter is included, but remains disabled by default. |

## Implementation notes

- Adapter module: `src/finwall/market_data_yfinance.py`.
- Provider selector: `FINWALL_MARKET_DATA_PROVIDER=yfinance`.
- Dependency handling: `yfinance` is declared as an optional Poetry dependency and extra.
- Default behavior: unchanged; `static` remains the default and unknown providers still fall back to `static`.
- Existing Yahoo behavior: unchanged; `yahoo` still uses Finwall's standard-library Yahoo public endpoint provider.
- Test strategy: fake `yfinance` module via monkeypatching, with no live network calls.

## Non-goals

- Replacing the current Yahoo public-endpoint provider.
- Making `yfinance` the default.
- Broker integration, automatic trading, or order execution.
- Real-time or streaming market data.
- Guaranteed production, institutional, or broker-grade market data.
