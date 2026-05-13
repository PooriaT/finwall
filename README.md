# Finwall

Finwall is a local-first portfolio decision-support application.

The project focuses on correctness, testability, and safe local persistence before adding external integrations. It currently provides typed portfolio domain models and SQLite-backed local storage for portfolio state and history.

## Safety disclaimer

Finwall is a decision-support tool only. It does not guarantee outcomes, execute trades, or replace independent financial judgment.

## Current scope

Included:

- Typed portfolio domain models
- Validation for holdings, active orders, timelines, and risk profiles
- SQLite local storage for portfolio state
- Separate storage for trade history and cash history
- Poetry-based dependency management
- Pytest test coverage
- Ruff linting and formatting configuration

Not included:

- Broker integrations
- Automatic trading logic
- Market-data fetching
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
│       ├── config.py
│       ├── models.py
│       └── storage.py
├── tests/
│   ├── test_config.py
│   ├── test_models.py
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

## Usage example

The current project is a Python library. There is no CLI or web interface yet.

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
poetry run ruff format --check .
```

Format code locally:

```bash
poetry run ruff format .
```

## Continuous integration

GitHub Actions runs the test suite automatically when a pull request targets `main`.
