# CLI reference

Finwall's CLI is a local/self-managed portfolio maintenance and decision-support interface. It reads and writes the configured Finwall portfolio store; it does **not** connect to brokers, place orders, execute trades, or automate investing decisions.

For task-oriented walkthroughs, see [CLI workflows](cli-workflows.md). For setup and storage configuration, see [Local setup](local-setup.md) and [Configuration](configuration.md).

## Status and safety

- Portfolio mutation commands update only Finwall's local/self-managed portfolio state.
- `add-order` and `update-order` record planned or active orders in local state only. They do not submit broker orders.
- Analysis commands are deterministic decision-support surfaces unless an explicitly configured optional provider supplies market, fundamentals, news, or narrative data.
- Live/free provider data may be unavailable, delayed, stale, partial, malformed, rate-limited, blocked, or different from broker data.
- JSON and Markdown output are reporting formats, not API stability guarantees unless documented elsewhere.
- Finwall is not financial advice and is not an execution system. See [Safety limits](safety-limits.md) and [Product modes](product-modes.md).

## Global options

Global options appear before the command name:

```bash
poetry run finwall [GLOBAL_OPTIONS] <command> [COMMAND_OPTIONS]
```

| Option | Default | Purpose |
| --- | --- | --- |
| `--database DATABASE` | `finwall.db` | SQLite database path used by CLI commands when the configured storage backend is SQLite. This is local/self-managed state. |
| `--portfolio PORTFOLIO` | `Primary` | Portfolio name to load or create in the selected store. |
| `-h`, `--help` | n/a | Show top-level or command-specific help. |

Examples:

```bash
poetry run finwall --database finwall.db --portfolio Primary snapshot --price AAPL=190
poetry run finwall report --help
```

The CLI also respects configured storage and provider environment variables. See [Configuration](configuration.md) for `FINWALL_STORAGE_BACKEND`, `FINWALL_DATABASE_URL`, `FINWALL_MARKET_DATA_PROVIDER`, `FINWALL_FUNDAMENTAL_DATA_PROVIDER`, and `FINWALL_NEWS_PROVIDER`.

## Command summary

| Command | Reads portfolio | Mutates portfolio | Live/provider data | JSON output |
| --- | --- | --- | --- | --- |
| `add-cash` | Yes | Yes | No | No |
| `withdraw-cash` | Yes | Yes | No | No |
| `add-holding` | Yes | Yes | No | No |
| `record-buy` | Yes | Yes | No | No |
| `record-sell` | Yes | Yes | No | No |
| `add-order` | Yes | Yes | No | No |
| `update-order` | Yes | Yes | No | No |
| `remove-order` | Yes | Yes | No | No |
| `add-watchlist` | Yes | Yes | No | No |
| `remove-watchlist` | Yes | Yes | No | No |
| `set-goal` | Yes | Yes | No | No |
| `set-timeline` | Yes | Yes | No | No |
| `set-risk` | Yes | Yes | No | No |
| `snapshot` | Yes | No | Optional with `--live-prices` | Yes |
| `recommendations` | Yes | No | Optional with `--live-prices` | Yes |
| `evaluate-order` | Yes | No | Optional with `--live-prices` | Yes |
| `market-index` | No portfolio dependency after store init | No | Yes | No |
| `technicals` | Yes | No | Yes | Yes |
| `market-condition` | No portfolio dependency after store init | No | Yes | Yes |
| `fundamentals` | Yes | No | Yes, provider-dependent | Yes |
| `fundamentals-summary` | Yes | No | Yes, provider-dependent | Yes |
| `news` | Yes | No | Yes, provider-dependent | Yes |
| `news-summary` | Yes | No | Yes, provider-dependent | Yes |
| `report` | Yes | Optional history write with `--save-run` | Optional with `--live-prices`; optional narrative provider with `--narrative` | Yes |
| `run-scheduled-report` | Yes | Yes, scheduled-run metadata and optional report history | Optional with `--live-prices`; optional email provider | Yes |
| `scheduled-runs` | Yes | No | No | Yes |
| `market-data-check` | No | No | Yes | Yes |
| `security-check` | No | No | No | Yes |

## Portfolio maintenance commands

All commands in this section mutate only Finwall's local portfolio store. They do not place broker orders, move money, or execute trades.

| Command | Purpose | Required arguments | Optional flags | Example |
| --- | --- | --- | --- | --- |
| `add-cash` | Increase a cash balance. | `currency`, `amount` | None | `poetry run finwall add-cash USD 1000` |
| `withdraw-cash` | Decrease a cash balance. | `currency`, `amount` | None | `poetry run finwall withdraw-cash USD 250` |
| `add-holding` | Add or update a holding with share count and average purchase price. | `ticker`, `shares`, `average_price` | `--sector SECTOR` | `poetry run finwall add-holding NVDA 2 100 --sector Technology` |
| `record-buy` | Record a completed buy transaction and update local state. | `ticker`, `shares`, `price` | `--currency CURRENCY` (default `USD`), `--date YYYY-MM-DD` (default today) | `poetry run finwall record-buy AAPL 1 182 --currency USD --date 2026-05-20` |
| `record-sell` | Record a completed sell transaction and update local state. | `ticker`, `shares`, `price` | `--currency CURRENCY` (default `USD`), `--date YYYY-MM-DD` (default today) | `poetry run finwall record-sell AAPL 1 190 --date 2026-05-21` |
| `add-order` | Add a local active/planned order record. | `ticker`, `side`, `order_type`, `shares` | `--limit-price PRICE`, `--stop-price PRICE` | `poetry run finwall add-order NVDA buy limit 2 --limit-price 118` |
| `update-order` | Upsert an existing local active/planned order record. | `ticker`, `side`, `order_type`, `shares` | `--limit-price PRICE`, `--stop-price PRICE` | `poetry run finwall update-order NVDA buy stop_limit 2 --limit-price 118 --stop-price 120` |
| `remove-order` | Remove a local active/planned order record. | `ticker` | None | `poetry run finwall remove-order NVDA` |
| `add-watchlist` | Add a ticker to the local watchlist. | `ticker` | `--note NOTE` | `poetry run finwall add-watchlist MSFT --note "Earnings follow-up"` |
| `remove-watchlist` | Remove a ticker from the local watchlist. | `ticker` | None | `poetry run finwall remove-watchlist MSFT` |
| `set-goal` | Set portfolio goal metadata. | `name` | `--target-amount AMOUNT` | `poetry run finwall set-goal "Home down payment" --target-amount 80000` |
| `set-timeline` | Set portfolio start and optional target dates. | `start_date` | `--target-date YYYY-MM-DD` | `poetry run finwall set-timeline 2026-01-01 --target-date 2030-01-01` |
| `set-risk` | Set the local risk profile. | `level` (`conservative`, `moderate`, or `aggressive`) | `--notes NOTES` | `poetry run finwall set-risk moderate --notes "Example profile"` |

Order `side` choices are `buy` and `sell`. Order `order_type` choices are `limit`, `stop_loss`, and `stop_limit`.

## Analysis and reporting commands

### `snapshot`

Generates a portfolio valuation snapshot from local portfolio state and supplied or fetched prices.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--price TICKER=PRICE` (repeatable), `--live-prices`, `--risk`, `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Only with `--live-prices` |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall snapshot --price NVDA=120 --risk` |

`--price` values are manual valuation inputs. If `--live-prices` is also supplied, fetched holding prices are loaded first and manual prices override matching tickers.

### `recommendations`

Builds deterministic recommendation context from the portfolio snapshot and risk assessment.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--price TICKER=PRICE` (repeatable), `--live-prices`, `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Only with `--live-prices` |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall recommendations --live-prices --json` |

### `evaluate-order`

Evaluates a hypothetical proposed order against portfolio cash, holdings, risk, and price context. It does not record or place the order.

| Field | Details |
| --- | --- |
| Required arguments | `ticker`, `side` (`buy` or `sell`), `order_type` (`limit`, `stop_loss`, or `stop_limit`), `--entry-price PRICE` |
| Optional flags | `--shares SHARES`, `--limit-price PRICE`, `--stop-price PRICE`, `--target-price PRICE`, `--currency CURRENCY` (default `USD`), `--price TICKER=PRICE` (repeatable), `--live-prices`, `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Only with `--live-prices` |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall evaluate-order NVDA buy limit --entry-price 120 --limit-price 118 --shares 2 --price NVDA=120` |

### `report`

Builds the deterministic report bundle. Text output is Markdown by default; `--json` returns a structured payload. `--markdown` is accepted for parity with scheduled reports but the non-JSON report path already prints Markdown.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--price TICKER=PRICE` (repeatable), `--live-prices`, `--market-index SP500|NASDAQ`, `--include-nasdaq`, `--market-condition-days DAYS` (default `400`), `--json`, `--markdown`, `--narrative`, `--save-run`, `--compare` |
| Reads portfolio | Yes |
| Mutates portfolio | Only when `--save-run` stores report history |
| Reads live provider data | With `--live-prices`; market condition/index context uses provider-backed market data when requested by report pipeline options; `--narrative` uses the configured narrative provider |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall report --live-prices --market-index SP500 --save-run --compare` |

## Live-data and provider diagnostics

Provider defaults come from code/configuration:

- `FINWALL_MARKET_DATA_PROVIDER` defaults to `yfinance`. In code, `yfinance` builds a yfinance provider with a Yahoo public quote fallback; `yahoo` selects the Yahoo public quote/chart provider directly; `static` selects a static provider; unknown market-data provider names fall back to static with a configuration warning.
- `FINWALL_FUNDAMENTAL_DATA_PROVIDER` defaults to `yfinance`; any non-`yfinance` value uses the static fundamentals provider.
- `FINWALL_NEWS_PROVIDER` defaults to `yfinance`; `static` uses the static news provider; unsupported news provider names use static fallback and CLI output adds a warning.
- Provider timeout defaults are 5 seconds for market data, fundamentals, and news.

Manual price overrides apply only to commands with `--price TICKER=PRICE`: `snapshot`, `recommendations`, `evaluate-order`, `report`, and `run-scheduled-report`. Manual prices are merged after fetched live prices, so they override fetched values for matching tickers. Missing provider prices are reported as warnings where supported, and valuation/recommendation output continues with partial or missing price coverage rather than placing trades.

### `market-index`

Fetches one configured market index quote.

| Field | Details |
| --- | --- |
| Required arguments | `symbol` (`SP500` or `NASDAQ`) |
| Optional flags | None |
| Reads portfolio | No portfolio dependency after store initialization |
| Mutates portfolio | No |
| Reads live provider data | Yes, through the configured market-data provider |
| JSON output | No |
| Example | `poetry run finwall market-index SP500` |

### `technicals`

Builds technical-analysis context for holdings and watchlist tickers using historical market data.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--days DAYS` (default `250`), `--holdings-only`, `--watchlist-only`, `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Yes, historical prices through the configured market-data provider |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall technicals --holdings-only --days 250` |

### `market-condition`

Classifies market-condition context from index historical data.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--primary-index SP500|NASDAQ` (default `SP500`), `--include-nasdaq`, `--days DAYS` (default `250`), `--json` |
| Reads portfolio | No portfolio dependency after store initialization |
| Mutates portfolio | No |
| Reads live provider data | Yes, historical prices through the configured market-data provider |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall market-condition --primary-index SP500 --include-nasdaq --json` |

### `fundamentals`

Builds fundamentals context for holdings and watchlist tickers.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--holdings-only`, `--watchlist-only`, `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Yes when the fundamentals provider is `yfinance`; otherwise static/unavailable provider data |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall fundamentals --watchlist-only` |

### `fundamentals-summary`

Summarizes fundamentals context for holdings and watchlist tickers.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Yes when the fundamentals provider is `yfinance`; otherwise static/unavailable provider data |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall fundamentals-summary --json` |

### `news`

Fetches or reports news context for holdings, watchlist, and optionally broad market/sector topics.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--holdings-only`, `--watchlist-only`, `--include-market`, `--include-sectors`, `--limit-per-topic LIMIT`, `--max-age-hours HOURS`, `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Yes when the news provider is `yfinance`; otherwise static/unavailable provider data |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall news --include-market --include-sectors --limit-per-topic 3` |

If `--limit-per-topic` or `--max-age-hours` is omitted, the command uses configured defaults (`FINWALL_NEWS_MAX_ARTICLES_PER_TOPIC`, default `5`; `FINWALL_NEWS_MAX_AGE_HOURS`, default `72`). Source quality and recency are heuristic context only.

### `news-summary`

Summarizes news context into confirmed facts, possible interpretations, uncertainties, and speculative claims.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--holdings-only`, `--watchlist-only`, `--include-market`, `--include-sectors`, `--limit-per-topic LIMIT`, `--max-age-hours HOURS`, `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live provider data | Yes when the news provider is `yfinance`; otherwise static/unavailable provider data |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall news-summary --include-market --include-sectors --json` |

### `market-data-check`

Runs market-data provider diagnostics without requiring portfolio state.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--ticker TICKER` (default `AAPL`), `--historical-days DAYS` (default `30`, must be positive), `--json` |
| Reads portfolio | No |
| Mutates portfolio | No |
| Reads live provider data | Yes, checks configured/default provider behavior |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall market-data-check --ticker AAPL --historical-days 30 --json` |

## Automation and scheduled reports

### `run-scheduled-report`

Runs a scheduled-report workflow for a calendar date and context. It records scheduled-run metadata, suppresses duplicate scheduled runs for the same context/date, skips non-trading days unless forced, can save report history, and can optionally send email notifications through the configured email provider.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--run-context morning|after_close|manual` (default `manual`), `--run-date YYYY-MM-DD`, `--force`, `--price TICKER=PRICE` (repeatable), `--live-prices`, `--market-index SP500|NASDAQ`, `--include-nasdaq`, `--market-condition-days DAYS` (default `400`), `--json`, `--markdown`, `--save-run`, `--compare`, `--email`, `--email-on-failure`, `--email-to ADDRESS[,ADDRESS...]` |
| Reads portfolio | Yes |
| Mutates portfolio | Yes, scheduled-run metadata; report history when `--save-run` is used |
| Reads live/provider data | Optional market data with `--live-prices`; optional email provider with email flags |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall run-scheduled-report --run-context morning --save-run --compare --json` |


### `scheduled-runs`

Lists scheduled-run records for the selected portfolio.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--limit LIMIT` (default `10`), `--json` |
| Reads portfolio | Yes |
| Mutates portfolio | No |
| Reads live/provider data | No |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall scheduled-runs --limit 10 --json` |

## Security diagnostics

### `security-check`

Validates runtime security settings and exits non-zero if warnings are found.

| Field | Details |
| --- | --- |
| Required arguments | None |
| Optional flags | `--json` |
| Reads portfolio | No |
| Mutates portfolio | No |
| Reads live/provider data | No |
| JSON output | Yes, with `--json` |
| Example | `poetry run finwall security-check --json` |

## JSON output conventions

Commands that support `--json` print indented JSON to standard output. Commands without `--json` print human-readable text or Markdown. Some diagnostics return a non-zero exit code when checks fail even if JSON is emitted:

- `security-check` returns `1` when security warnings are present.
- `market-data-check` returns `1` when provider diagnostics fail.
- `market-index` returns `1` when the requested index quote is unavailable.
- `run-scheduled-report` returns `1` if report generation fails unexpectedly.

Warnings may appear in structured JSON fields, Markdown/text output, or standard output before a report depending on the command path. Treat JSON output as local CLI output for automation in this repository rather than as a public compatibility contract.

## Common examples

```bash
# Maintain local state.
poetry run finwall --database finwall.db add-cash USD 2000
poetry run finwall --database finwall.db add-holding AAPL 3 180 --sector Technology
poetry run finwall --database finwall.db set-risk moderate --notes "Example profile"

# Use manual prices for deterministic valuation.
poetry run finwall --database finwall.db snapshot --price AAPL=190 --risk
poetry run finwall --database finwall.db report --price AAPL=190

# Use configured live providers with conservative caveats.
poetry run finwall --database finwall.db snapshot --live-prices --json
poetry run finwall --database finwall.db technicals --holdings-only
poetry run finwall --database finwall.db fundamentals-summary --json
poetry run finwall --database finwall.db news-summary --include-market --include-sectors

# Run diagnostics and scheduled/report history workflows.
poetry run finwall market-data-check --ticker AAPL --historical-days 30
poetry run finwall --database finwall.db report --save-run --compare
poetry run finwall --database finwall.db scheduled-runs --limit 10 --json
```
