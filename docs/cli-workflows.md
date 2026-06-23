# CLI workflows

> Status: **Supported primary** for CLI portfolio maintenance and deterministic report generation. Technical/fundamental/news/market-condition commands are **experimental/optional decision-support inputs** and should not be treated as prediction certainty or execution signals.

This guide remains workflow-focused and shows common command patterns. For full command arguments, flags, output modes, and live-data behavior, see the [CLI reference](cli-reference.md) or run `poetry run finwall <command> --help`.

## Portfolio maintenance

### Cash and holdings

```bash
poetry run finwall --database finwall.db add-cash USD 2000
poetry run finwall --database finwall.db withdraw-cash USD 200
poetry run finwall --database finwall.db add-holding AAPL 3 180 --sector Technology
```

### Record buys/sells

```bash
poetry run finwall --database finwall.db record-buy AAPL 1 182 --currency USD --date 2026-05-20
poetry run finwall --database finwall.db record-sell AAPL 1 190 --currency USD --date 2026-05-21
```

### Orders and watchlist

```bash
poetry run finwall --database finwall.db add-order NVDA buy limit 2 --limit-price 118
poetry run finwall --database finwall.db update-order NVDA buy stop_limit 2 --limit-price 118 --stop-price 120
poetry run finwall --database finwall.db remove-order NVDA
poetry run finwall --database finwall.db add-watchlist MSFT --note "Earnings follow-up"
poetry run finwall --database finwall.db remove-watchlist MSFT
```

### Goal, timeline, risk

```bash
poetry run finwall --database finwall.db set-goal "Home down payment" --target-amount 80000
poetry run finwall --database finwall.db set-timeline 2026-01-01 --target-date 2030-01-01
poetry run finwall --database finwall.db set-risk moderate --notes "Example profile"
```

## Analysis and reporting

Live-price workflows use the default `yfinance` market-data provider unless `FINWALL_MARKET_DATA_PROVIDER` is set to `yahoo` or explicit `static`. Manual `--price TICKER=PRICE` values remain available and override fetched live prices where both are supplied.

```bash
poetry run finwall --database finwall.db snapshot --price NVDA=120
poetry run finwall --database finwall.db snapshot --live-prices --risk --json
poetry run finwall --database finwall.db evaluate-order NVDA buy limit --entry-price 120 --limit-price 118 --shares 2 --price NVDA=120
poetry run finwall --database finwall.db recommendations --live-prices --json
poetry run finwall --database finwall.db report --live-prices --market-index SP500 --compare --save-run
```

Fundamentals commands use the default `yfinance` fundamentals provider unless `FINWALL_FUNDAMENTAL_DATA_PROVIDER=static` is set. Live fundamentals are partial decision-support context only; they may be incomplete, stale, unavailable, or provider-dependent, and they do not change recommendation scoring unless integrated by a separate rule set.

News commands use the default `yfinance` news provider unless `FINWALL_NEWS_PROVIDER=static` is set. `yfinance` supports ticker/company news when available; market and sector topics are safely reported as unavailable and commands continue. News source quality and recency are heuristic context only, not sentiment analysis, recommendation inputs, broker actions, or trading signals.

Additional command examples:

```bash
poetry run finwall --database finwall.db technicals --holdings-only
poetry run finwall --database finwall.db market-condition --primary-index SP500 --include-nasdaq
poetry run finwall --database finwall.db fundamentals-summary --json
poetry run finwall --database finwall.db news-summary --include-market --include-sectors
poetry run finwall market-data-check --ticker AAPL --historical-days 30
poetry run finwall --database finwall.db security-check --json
```

## Persistence and run history

```bash
poetry run finwall --database finwall.db report --save-run --compare
poetry run finwall --database finwall.db run-scheduled-report --run-context morning --save-run --compare
poetry run finwall --database finwall.db scheduled-runs --limit 10 --json
```

If API mode is enabled, audit events are available via API (`/api/v1/portfolio/audit`) and through the React frontend dashboard.


## Live-data status contract

Finwall exposes a shared `live_data_status` contract for frontend, API, CLI diagnostics, and report payloads. Status values are:

- `live`: the evaluated data source returned the requested data for that surface.
- `partial`: some requested items were available and some were missing.
- `unavailable`: the evaluated source could not provide usable data.
- `static`: the configured source is static/sample/manual fallback data rather than a live provider.
- `manual`: user-supplied values were used instead of provider fetches.
- `unknown`: only configuration is known or the domain has not been evaluated.

Provider status is decision-support metadata only. It is not a guarantee that data is real-time, complete, broker-grade, or suitable for trading automation. The contract does not add caching, new providers, broker integration, or automatic trading.
