# Local setup

## Prerequisites

- Python 3.13
- Poetry

## Install and initialize

```bash
git clone https://github.com/PooriaT/finwall.git
cd finwall
poetry install
cp .env.example .env
```

By default, Finwall uses local SQLite (`finwall.db`) unless storage settings override it.

## First portfolio initialization (example data)

```bash
poetry run finwall --database finwall.db add-cash USD 1000
poetry run finwall --database finwall.db add-holding NVDA 2 100 --sector Technology
poetry run finwall --database finwall.db set-risk moderate --notes "Long-term growth (example)"
```

Optional setup:

```bash
poetry run finwall --database finwall.db set-goal "Retirement" --target-amount 250000
poetry run finwall --database finwall.db set-timeline 2026-01-01 --target-date 2040-01-01
```

## Generate a snapshot and report

```bash
poetry run finwall --database finwall.db snapshot --price NVDA=120
poetry run finwall --database finwall.db report --price NVDA=120
```

## Run checks

```bash
poetry run ruff check .
poetry run ruff format --check --line-length 88 .
poetry run pytest
```

## Notes

- Keep `.env` local and never commit it.
- Use fake/test portfolio data while validating setup.
- For advanced workflows (scheduled reports, email, API, frontend), continue with the docs map in `README.md`.
