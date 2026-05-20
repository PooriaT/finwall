# Finwall

Finwall is a local-first portfolio decision-support application.

The project focuses on correctness, testability, and safe local persistence before adding external integrations. It currently provides typed portfolio domain models, SQLite-backed local storage, a CLI for maintaining portfolio state, and local portfolio snapshot generation.

## Safety disclaimer

Finwall is a decision-support tool only. It does not guarantee outcomes, execute trades, or replace independent financial judgment.

## Current scope

Included:

- Typed portfolio domain models
- Validation for holdings, active orders, timelines, and risk profiles
- SQLite local storage for portfolio state
- Separate storage for trade history and cash history
- CLI portfolio update commands
- Local portfolio snapshot generation
- Market-data fetching via optional provider layer (`--live-prices`)
- JSON snapshot export
- Poetry-based dependency management
- Pytest test coverage
- Ruff linting and formatting configuration

Not included:

- Broker integrations
- Automatic trading logic
- LLM-generated recommendations
- User accounts, authentication, or web APIs
- Frontend or UI frameworks

## Requirements

- Python 3.13
- Poetry

## Project structure

```text
finwall/
├── src/
│   └── finwall/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── market_data.py
│       ├── models.py
│       ├── risk.py
│       ├── snapshot.py
│       └── storage.py
├── tests/
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_market_data.py
│   ├── test_models.py
│   ├── test_snapshot.py
│   ├── test_risk.py
│   └── test_storage.py
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## Installation

Clone the repository:

```bash
git clone https://github.com/PooriaT/finwall.git
cd finwall
```

Install dependencies:

```bash
poetry install
```

Copy the example environment file if you want local overrides:

```bash
cp .env.example .env
```

## CLI usage

Initialize and update a local portfolio database:

```bash
poetry run finwall --database finwall.db add-cash USD 1000
```

Record a buy transaction:

```bash
poetry run finwall --database finwall.db record-buy NVDA 2 100 --currency USD
```

Record a sell transaction:

```bash
poetry run finwall --database finwall.db record-sell NVDA 1 120 --currency USD
```

Add or update an active order:

```bash
poetry run finwall --database finwall.db add-order PLTR buy limit 2 --limit-price 120
```

Set a portfolio risk profile:

```bash
poetry run finwall --database finwall.db set-risk moderate --notes "Long-term growth"
```

Generate a local portfolio snapshot:

```bash
poetry run finwall --database finwall.db snapshot
```

Generate a snapshot with manual prices:

```bash
poetry run finwall --database finwall.db snapshot --price NVDA=120 --price PLTR=90
```

Export a snapshot as JSON:

```bash
poetry run finwall --database finwall.db snapshot --json
```

Generate a snapshot with live prices for holdings:

```bash
poetry run finwall --database finwall.db snapshot --live-prices
```

Manual prices override live prices for matching tickers:

```bash
poetry run finwall --database finwall.db snapshot --live-prices --price NVDA=120
```


Risk assessment output (deterministic warnings only):

```bash
poetry run finwall --database finwall.db snapshot --price NVDA=120 --risk
```

Risk assessment JSON output:

```bash
poetry run finwall --database finwall.db snapshot --live-prices --risk --json
```

Fetch market index quote (currently supports `SP500` and `NASDAQ`):

```bash
poetry run finwall --database finwall.db market-index SP500
```


## Python usage example

```python
from decimal import Decimal

from finwall.models import CashBalance, Holding, Portfolio
from finwall.storage import SQLitePortfolioStore

store = SQLitePortfolioStore("finwall.db")
store.initialize()

portfolio = Portfolio(
    name="Primary",
    cash_balances=(CashBalance(currency="USD", amount=Decimal("1000")),),
    holdings=(
        Holding(
            ticker="AAPL",
            share_count=Decimal("2"),
            average_purchase_price=Decimal("180"),
            sector="Technology",
        ),
    ),
)

store.save_portfolio(portfolio)
loaded = store.get_portfolio("Primary")
```


## Snapshot output details

The `snapshot` command now includes richer valuation metadata for decision reports:

- Holding-level allocation percentages:
  - allocation within invested value
  - allocation within total portfolio value (when total valuation is available)
- Portfolio-level unrealized gain/loss totals and percent.
- Structured active orders in JSON output with:
  - `ticker`, `side`, `order_type`, `share_count`
  - `limit_price`, `stop_price`
  - human-readable `description`
- Clear missing-price handling per holding:
  - `price_available=false`
  - `price_status="missing"`
  - `missing_price_message`
- Explicit valuation status fields:
  - `multi_currency_cash`
  - `valuation_currency`
  - `valuation_status`

Current limitation: if cash balances contain multiple currencies, Finwall does **not** sum them into a single total portfolio value because FX conversion is not implemented yet. In this case, total valuation and allocation are reported as unavailable with `valuation_status="multi_currency_cash_unsupported"`.

Stale quote detection is not implemented yet. The market-data provider layer currently does not return quote timestamps, so freshness checks are intentionally deferred until provider timestamp metadata is available.



## Deterministic risk engine

When `snapshot --risk` is enabled, Finwall evaluates portfolio state against configurable risk rules tied to the saved risk profile (`conservative`, `moderate`, `aggressive`). If no saved profile exists, Finwall defaults to `moderate` and reports that fallback in warnings.

Checks currently include:

- single-position concentration limits
- cash deployment and minimum cash reserve limits
- missing price / incomplete valuation constraints
- multi-currency cash valuation limitation (FX conversion intentionally out of scope)
- portfolio-level and holding-level unrealized loss thresholds
- missing or non-protective stop-loss / stop-limit orders for large positions

The risk engine is deterministic and guardrail-oriented. It does **not** generate buy/sell/hold recommendations, position sizing, technical analysis, fundamental analysis, scheduling, deployment workflows, or email notifications.

## Market data configuration

Finwall supports an optional market-data provider layer for raw latest prices and basic index quotes.

Environment variables:

- `FINWALL_MARKET_DATA_PROVIDER` (default: `static`)
  - `static`: safe local default with no network calls
  - `yahoo`: public no-key Yahoo Finance quote endpoint
- `FINWALL_MARKET_DATA_TIMEOUT_SECONDS` (default: `5`)

Notes:

- Live market data can be delayed, missing, or temporarily unavailable.
- Snapshot generation remains resilient: missing ticker prices are warned and skipped.
- Manual `--price TICKER=PRICE` values always take precedence over fetched values.

## Development

Run tests:

```bash
poetry run pytest
```

Run linting:

```bash
poetry run ruff check .
```

Run formatting check:

```bash
poetry run ruff format --check --line-length 88 .
```

Format code locally:

```bash
poetry run ruff format .
```

## Continuous integration

GitHub Actions runs the test suite automatically when a pull request targets `main`.

## Evaluate proposed orders

Use `evaluate-order` to evaluate a trade idea against cash, risk profile limits, and basic goal-awareness. This command evaluates the provided order only; it does not generate buy/sell/hold recommendations.

Example buy evaluation:

```bash
poetry run finwall --database finwall.db evaluate-order NVDA buy limit \
  --entry-price 100 --shares 2 --limit-price 100 --stop-price 90 --target-price 120 \
  --price NVDA=100
```

Example sell evaluation:

```bash
poetry run finwall --database finwall.db evaluate-order NVDA sell stop_limit \
  --entry-price 100 --shares 1 --stop-price 95 --limit-price 94
```

The output reports affordability, reserve-aware sizing, risk-based sizing, expected downside/upside, and risk/reward when stop/target are provided. It may warn when goals are missing, goal target is missing, or valuation is unavailable due to missing prices or multi-currency cash.


## Deterministic recommendations (rule-based, no LLM)

Use `recommendations` to generate structured deterministic recommendation candidates from current holdings, snapshot valuation data, and deterministic risk warnings.

Manual-price example:

```bash
poetry run finwall --database finwall.db recommendations --price NVDA=120
```

Live-price example:

```bash
poetry run finwall --database finwall.db recommendations --live-prices
```

JSON output example:

```bash
poetry run finwall --database finwall.db recommendations --price NVDA=120 --json
```

Behavior notes:

- Recommendations are deterministic and rule-based.
- This command does **not** call any LLM.
- Technical, fundamental, and news/sentiment inputs are not implemented yet.
- Missing prices, partial valuation, and missing profile/goal context lower confidence.
- Output is decision-support only and does not execute trades.
- No scheduling, deployment, email, broker integration, or automatic trading is performed.

## Decision-support report command

Generate a structured decision-support report that composes existing snapshot, risk, and deterministic recommendation outputs:

```bash
poetry run finwall --database finwall.db report
```

Output formats:

- Default output: Markdown
- Explicit Markdown output: `--markdown`
- Structured JSON output: `--json`

Examples:

```bash
poetry run finwall --database finwall.db report --price NVDA=120 --price PLTR=90
poetry run finwall --database finwall.db report --live-prices --market-index SP500
poetry run finwall --database finwall.db report --price NVDA=120 --json
```

The report includes:

- Portfolio snapshot metrics (cash, invested value, total value, allocation, valuation status)
- Market condition section with optional raw index quote input
- Holding recommendations from deterministic recommendation output
- Cash allocation plan from deterministic recommendation output
- Suggested orders section containing existing active orders only
- Strategy assessment derived from valuation completeness, risk warnings, and cash deployment status
- Risks/warnings roll-up and final action plan

Important limitations and exclusions:

- Decision-support only; not financial advice and not guaranteed outcomes
- No LLM rewriting or generative analysis
- No scheduling, email, deployment automation, broker integration, or automatic trading
- No technical-analysis, fundamental-analysis, or news/sentiment modules
- No market-condition classification (only optional raw index quote inclusion)
- No new order generation in this report

Manual prices override live prices for matching tickers, consistent with snapshot and recommendation behavior.

## Technical indicators command

Use the `technicals` command to generate deterministic technical indicator snapshots for current holdings and watchlist tickers from historical prices.

```bash
poetry run finwall --database finwall.db technicals
```

```bash
poetry run finwall --database finwall.db technicals --days 250 --json
```

Supported options:

- `--days` (default `250`): number of calendar days of historical bars requested from provider
- `--json`: emits structured JSON output for downstream consumers
- `--holdings-only`: output holdings snapshots only
- `--watchlist-only`: output watchlist snapshots only

Current indicator set:

- SMA 20, SMA 50, SMA 200
- RSI 14
- Recent high and recent low
- Volume trend using recent vs previous average volume (when available)

Handling of missing or short history:

- Missing historical bars produce `data_status="missing_data"` with warnings
- Short history produces `partial` or `insufficient_data` without crashing
- Indicators with insufficient input remain `null` in JSON / `n/a` in text output

Important: technical indicators are deterministic decision-support inputs only. They are **not** buy/sell/hold/reduce/watch recommendations and are not integrated into recommendation logic yet.

## Market condition classification

Use the `market-condition` command to classify broader market conditions deterministically from historical index trends.

```bash
poetry run finwall --database finwall.db market-condition
```

Optional Nasdaq confirmation and JSON output:

```bash
poetry run finwall --database finwall.db market-condition --include-nasdaq --json
```

Report integration with index classification:

```bash
poetry run finwall --database finwall.db report --market-index SP500
```

How it works (high level):

- Default primary index is S&P 500 (`SP500` -> `^GSPC`).
- Optional Nasdaq confirmation (`NASDAQ` -> `^IXIC`) can be included.
- Classification uses deterministic moving-average and trend checks with existing technical indicator calculations.
- Status is one of: `favorable`, `neutral`, `risky`, `insufficient_data`.
- A lightweight volatility proxy is computed from recent close-to-close moves when enough data exists.
- Missing or short historical data produces warnings and `insufficient_data` instead of crashing.

Limitations and scope:

- Decision-support only; not financial advice and not guaranteed outcomes.
- Uses historical index prices only; no fundamentals or news analysis.
- Does not generate or modify individual stock recommendations.
- No LLM reasoning, broker integration, automatic trading, scheduling, deployment, or email notifications.
