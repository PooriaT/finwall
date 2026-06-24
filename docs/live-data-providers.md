# Live-data provider reference

This page is the central reference for Finwall live-data providers. It documents current code behavior only; it does not change provider defaults, fallbacks, payloads, CLI flags, frontend behavior, or report logic.

## Status and safety

Finwall provider data is decision-support context only. It is not financial advice, broker-grade market data, an execution signal, broker integration, automatic trading, or order execution.

Free/public providers can be unavailable, delayed, stale, partial, malformed, rate-limited, blocked, or missing fields. Frontend views, API payloads, CLI output, and reports should display provider status and warnings instead of presenting provider output as guaranteed complete or real time.

## Default provider behavior

Normal users do **not** need to configure live-data provider environment variables for the default live-data-first behavior implemented today.

| Setting | Current default | Normal-user requirement | Override/debug role |
| --- | --- | --- | --- |
| `FINWALL_MARKET_DATA_PROVIDER` | `yfinance` | Not required for normal `--live-prices`, `market-index`, `technicals`, or market-condition workflows. | Set to `yfinance`, `yahoo`, or `static` to debug provider selection or force a provider path. Unknown values use safe static provider behavior with a configuration warning. |
| `FINWALL_FUNDAMENTAL_DATA_PROVIDER` | `yfinance` | Not required for normal fundamentals workflows. | Set to `static` for fixtures/unavailable static behavior. Any non-`yfinance` value currently uses the static fundamentals provider. |
| `FINWALL_NEWS_PROVIDER` | `yfinance` | Not required for normal news workflows. | Set to `static` for fixtures/unavailable static behavior. Unsupported values use static fallback behavior. |

Timeout settings are separate from provider selection: `FINWALL_MARKET_DATA_TIMEOUT_SECONDS`, `FINWALL_FUNDAMENTAL_DATA_TIMEOUT_SECONDS`, and `FINWALL_NEWS_TIMEOUT_SECONDS` default to 5 seconds.

## Provider matrix

| Provider | Purpose | Default/override/manual role | Supported surfaces | Latest prices | Historical prices | Index quotes | Fundamentals | News | Known limitations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `yfinance` | Default free/public live-data provider where implemented. | Default for market data, fundamentals, and news. Market data uses yfinance as primary with Yahoo direct fallback. | Portfolio live prices, market indexes, historical prices, technicals, market condition, fundamentals, ticker/company news. | Yes, through yfinance history-derived latest close. | Yes, through yfinance history. | Yes, via mapped symbols such as `SP500` -> `^GSPC` and `NASDAQ` -> `^IXIC`. | Yes, limited company profile and selected metrics when available. | Yes for ticker/company news when available; market-wide and sector topics are safely unavailable for the current yfinance news provider. | Unofficial library, not affiliated with or endorsed by Yahoo; may be stale, delayed, partial, malformed, blocked, rate-limited, unavailable, or not real time. Not broker-grade. |
| `yahoo` | Direct Yahoo public endpoint market-data provider. | Market-data override and fallback under default `yfinance` market data. | Latest prices, index quotes, historical prices, technicals, market condition. | Yes, via Yahoo public quote endpoint. | Yes, via Yahoo public chart endpoint. | Yes, via same symbol mapping. | No. | No. | Public endpoints can fail, change, throttle, block, omit fields, or return stale/partial/unavailable data. Decision-support only. |
| `static` | Deterministic configured/unavailable data path. | Explicit tests, demos, fixtures, and manual workflows; also safe fallback for unknown provider names. | Static market-data provider objects, static fundamentals, static news, and manual CLI prices where supported. | Only if explicitly configured in code/tests; otherwise unavailable. | Only if explicitly configured in code/tests; otherwise empty. | Only if explicitly configured in code/tests; otherwise unavailable. | Static snapshots only; otherwise unavailable. | Static articles only; otherwise unavailable. | Static/manual values are not live and must not be presented as live provider data. |

## Market prices

Market-price fetching is used by CLI flows such as `snapshot --live-prices`, `recommendations --live-prices`, `evaluate-order --live-prices`, `report --live-prices`, and `run-scheduled-report --live-prices`, plus API/report code paths that request latest prices.

With the default market-data provider, Finwall builds a yfinance primary provider and a direct Yahoo public endpoint fallback. Per ticker, Finwall uses a primary price when available and attempts fallback for missing/unavailable primary results. If neither provider returns an available price, the ticker remains unavailable and a safe warning/error message is surfaced.

Manual CLI prices are supplied as `--price TICKER=PRICE`. In supported flows, manual prices are merged after fetched live prices, so a manual value overrides a fetched value for the same ticker. Manual values are user-provided and should be labeled as manual, not live, where the surface can distinguish per-ticker provenance. Current mixed `--live-prices --price` report flows may expose an overall market-price live-data status with the configured provider/source (for example `yfinance`/`live`) even when one or more ticker prices were manually overridden; that status describes the provider attempt for the workflow, not guaranteed per-ticker provenance.

## Historical prices and technicals

Historical prices support technical indicators and market-condition inputs. The default `yfinance` market provider requests daily history from yfinance. The direct `yahoo` provider requests daily chart data from Yahoo public endpoints. Static historical bars exist only when explicitly configured in tests/fixtures.

Historical data can be empty even when latest quotes are available. Empty or malformed history is treated as unavailable/partial data instead of a provider guarantee failure.

## Market indexes and market condition

Finwall maps supported index names to provider symbols before quote/history lookup. Current market indexes include `SP500` mapped to `^GSPC` and `NASDAQ` mapped to `^IXIC`. Market-condition reports depend on the same market-data provider behavior and inherit the same availability limitations.

## Fundamentals

`FINWALL_FUNDAMENTAL_DATA_PROVIDER` defaults to `yfinance`. The yfinance fundamentals provider returns company profile data and selected revenue growth, earnings growth, profitability, debt/liquidity, and valuation metrics when the provider exposes them. Missing or unparseable fields become unavailable metrics and can result in `partial` or missing-data report status.

The static fundamentals provider returns configured snapshots when provided by tests/fixtures; otherwise it returns unavailable snapshots. Fundamentals are raw decision-support inputs and are not automatically financial advice or trading instructions.

## News

`FINWALL_NEWS_PROVIDER` defaults to `yfinance`. The yfinance news provider supports ticker/company news when available. Current market-wide and sector news requests return safe unavailable results rather than synthesizing unsupported news.

News enrichment classifies source quality and recency heuristically, deduplicates articles, and preserves safe warnings. News is not sentiment analysis, not broker action, and not an automatic recommendation input unless a separate rule explicitly implements that behavior.

## Static/manual overrides

Use `static` for tests, demos, explicit fixtures, offline examples, and deterministic manual workflows. Static provider outputs may intentionally be unavailable unless a test or fixture supplies values.

Use manual `--price TICKER=PRICE` values when you need deterministic CLI valuation inputs. Manual prices override fetched prices in supported CLI flows when both are provided for the same ticker. Static and manual values should be displayed as static/manual, never as live provider data, when the consuming surface has that provenance available. Current report JSON does not expose per-ticker manual-vs-provider provenance for mixed `--live-prices --price` runs, so consumers should not infer that every price came from the provider solely from the aggregate status.

## Provider fallback behavior

Market data has an implemented fallback chain only for the default `yfinance` market-data provider: yfinance primary, Yahoo direct fallback. The fallback applies to latest prices, index quotes, and historical prices. Fallback status records requested symbols, which symbols were fulfilled by primary or fallback, unavailable symbols, whether fallback was attempted, and safe error text.

Fundamentals and news do not implement a yfinance-to-Yahoo direct fallback chain. Non-yfinance/unsupported values use static behavior instead.

## Live-data status contract

Finwall has a public live-data status shape for diagnostics and report/frontend payloads. Not every endpoint exposes every status today, so treat these meanings as the public contract when status is present.

| Status | Meaning | Typical cause | Display guidance | User next step |
| --- | --- | --- | --- | --- |
| `live` | Requested live provider data was available for the checked domain/items. | Provider returned usable data for all required items in that status calculation. | Show as live/provider data, with provider/source and timestamp; avoid promising real time. | Continue, while reviewing provider caveats. |
| `partial` | Some, but not all, requested data was available. | Missing tickers, partial fundamentals, empty historical bars for some items, provider omissions. | Show a warning badge and identify missing/partial items. | Retry later, check ticker symbols, run diagnostics, or provide manual/static values where appropriate. |
| `unavailable` | Requested live data was attempted but no usable data was available. | Network failure, dependency unavailable, provider error, blocked/rate-limited response, malformed/empty response. | Show unavailable status, safe error messages, and avoid using values as live. | Run diagnostics, verify network/dependencies, retry later, switch provider override, or use explicit manual/static data. |
| `static` | Data came from the static provider path. | `static` provider selected explicitly, unknown provider fell back to static, or configured fixture path. | Label as static/test/fixture data, not live. | Use for tests/demos or switch back to default provider for live data. |
| `manual` | Data came from user-provided manual input, or the workflow was run without live fetching and used supplied prices. | CLI `--price TICKER=PRICE` values in supported flows. Mixed live/manual report flows may still report an aggregate provider status rather than per-ticker `manual`. | Label as manual/user supplied when known; do not assume aggregate `live` proves every ticker value came from the provider. | Verify the value externally; remove manual override to use provider data. |
| `unknown` | Status cannot determine availability. | No holdings/items, configured-only status, endpoint did not run a provider check. | Show neutral/unknown status and avoid implying success or failure. | Run a provider-backed workflow or diagnostics if live data is needed. |

## Diagnostics

Run market-data diagnostics without initializing portfolio storage:

```bash
poetry run finwall market-data-check --ticker AAPL --historical-days 30
poetry run finwall market-data-check --json
```

Diagnostics check provider selection, effective provider, timeout, yfinance dependency availability where relevant, latest quote availability for the sample ticker, historical price availability for the requested day count, and fallback status where the market-data provider exposes it. JSON output also includes a `live_data_status` object.

Interpret failures conservatively. A failure can mean dependency problems, local network issues, unavailable provider data, public endpoint changes, throttling/blocking, invalid symbols, empty historical results, or unsupported/unknown provider configuration. Diagnostic examples are network-dependent and should not be required to pass in CI.

## Failure modes

Common failure modes include missing optional dependencies, DNS/network failures, timeouts, HTTP errors, rate limits, provider blocks, ticker not found, stale quotes, missing currency/price fields, malformed JSON, empty history, unsupported market/sector news topics, and unknown provider names.

Finwall aims to surface safe errors and availability status instead of raw third-party tracebacks. Missing provider data should reduce confidence, not cause users to treat stale/manual/static values as live.

## Examples

Use default live market diagnostics:

```bash
poetry run finwall market-data-check --ticker AAPL --historical-days 30
```

Inspect structured provider status:

```bash
poetry run finwall market-data-check --json
```

Force direct Yahoo market-data override for local debugging:

```bash
FINWALL_MARKET_DATA_PROVIDER=yahoo poetry run finwall market-data-check --json
```

Use deterministic manual prices in a supported CLI workflow:

```bash
poetry run finwall snapshot --price AAPL=190 --price MSFT=420
```

Fetch live prices and override one ticker manually. In current report JSON, this mixed run can still show an aggregate market-price provider status such as `yfinance`/`live`; consumers should treat that as workflow/provider status, not per-ticker provenance:

```bash
poetry run finwall report --live-prices --price AAPL=190
```

## Out of scope

This reference does not implement new providers, fallback chains, caching, paid data integrations, broker integrations, automatic trading, order execution, diagnostics changes, CLI flag changes, API payload changes, frontend behavior changes, or provider default changes.
