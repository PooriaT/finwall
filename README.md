# Finwall

Finwall is a local-first portfolio decision-support application.

The project starts intentionally small and focuses on correctness, testability, and maintainability.

## Safety disclaimer

Finwall is a decision-support tool only. It does not guarantee outcomes, execute trades, or replace independent financial judgment.

## Current scope

Included:

- Minimal Python package structure
- Poetry-based dependency management
- Pytest test setup
- Ruff linting and formatting
- Example environment configuration

Not included:

- Broker integrations
- Automatic trading logic
- LLM-generated recommendations
- Frontend or UI frameworks

## Project structure

```text
finwall/
├── src/
│   └── finwall/
│       ├── __init__.py
│       └── config.py
├── tests/
│   └── test_config.py
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## Local setup

Install dependencies:

```bash
poetry install
```

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
