# Finwall

## Overview

Finwall is a **local/self-managed portfolio decision-support application**. It helps you maintain portfolio state, generate deterministic reports, review risk context, and use an internal FastAPI + React dashboard while keeping final investment decisions outside the tool.

The FastAPI backend is the source of truth for portfolio state, calculations, API contracts, and read/write rules. The browser UI is the Vite + React + TypeScript app in `apps/web`. CLI workflows remain a supported primary way to maintain portfolios and generate reports.

## Safety and non-goals

Finwall is **not financial advice** and does not guarantee outcomes.

Finwall does **not**:

- connect to brokers;
- execute orders;
- perform automatic trading;
- provide public SaaS-grade multi-user auth/RBAC;
- replace independent judgment, professional advice, or broker-grade market data.

See [Safety limits](docs/safety-limits.md) for the full boundary statement.

## Features at a glance

| Area | Current status | High-level purpose | Details |
| --- | --- | --- | --- |
| CLI portfolio maintenance | Supported primary | Maintain cash, holdings, trades, orders, watchlist, goals, timeline, and risk profile. | [CLI workflows](docs/cli-workflows.md) |
| Deterministic reports | Supported primary | Produce snapshots, risk checks, recommendations, and report output from portfolio state and inputs. | [CLI workflows](docs/cli-workflows.md) |
| React dashboard | Internal/self-managed | Browser dashboard for authenticated portfolio reads and chart-ready analysis. | [Frontend runbook](docs/frontend.md) |
| API/session auth | Internal/self-managed | FastAPI bearer-token API plus HTTP-only session-cookie auth for frontend read endpoints. | [API and browser session mode](docs/api-admin.md) |
| Live market data | Supported secondary / provider-limited | Use default `yfinance` market data for local live-price workflows, with explicit override/debug providers. | [Configuration: market data](docs/configuration.md#market-data) |
| Fundamentals/news | Experimental / optional | Add partial provider-dependent decision-support context; not authoritative recommendation drivers by default. | [Configuration](docs/configuration.md#fundamentals) |
| Scheduled reports/email | Supported secondary | Run self-managed scheduled reports and optional SMTP notifications. | [Scheduled reports](docs/deployment/scheduled-reports.md) |
| Optional narrative provider | Experimental / optional explanation | Rewrite deterministic evidence into constrained plain-language explanation when enabled. | [Configuration: narrative](docs/configuration.md#narrative) |

## Quick start

```bash
poetry install
cp .env.example .env
poetry run finwall --database finwall.db add-cash USD 1000
poetry run finwall --database finwall.db add-holding NVDA 2 100 --sector Technology
poetry run finwall --database finwall.db set-risk moderate --notes "Example only"
poetry run finwall --database finwall.db report --price NVDA=120
```

Use fake/test data while validating setup. For a fuller walkthrough, see [Local setup](docs/local-setup.md).

## Run the app locally

Run the backend API and frontend dev server in separate terminals.

Backend:

```bash
FINWALL_API_TOKEN=change-me-long-random-token \
poetry run uvicorn "finwall.api:create_app" --factory --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`. In local development, Vite proxies relative `/api` requests to the FastAPI backend on `http://127.0.0.1:8000`. See [Frontend runbook](docs/frontend.md).

## CLI overview

The CLI is the primary local workflow for portfolio maintenance and deterministic reports. Prefer `poetry run finwall <command> --help`, the [CLI reference](docs/cli-reference.md), and [CLI workflows](docs/cli-workflows.md) for detailed command options instead of treating this README as a command reference.

Common entry points:

```bash
poetry run finwall --database finwall.db snapshot --price NVDA=120
poetry run finwall --database finwall.db report --price NVDA=120
poetry run finwall --database finwall.db report --live-prices --save-run
```

## API overview

Finwall includes an internal/self-managed FastAPI backend. Programmatic clients use bearer-token auth. The React frontend uses `POST /api/v1/auth/login` to exchange the configured local token for an HTTP-only `finwall_web_session` cookie used by frontend read endpoints.

Portfolio mutation endpoints remain bearer-token protected. The removed server-rendered Jinja `/admin` UI is not a supported browser surface; use the React frontend instead. See [API and browser session mode](docs/api-admin.md), the [API reference](docs/api-reference.md), and [ADR 0002](docs/adr/0002-modern-frontend-scaffold.md).

## Frontend overview

The browser UI lives in `apps/web` and is built with Vite, React, TypeScript, TanStack Query, and Recharts. It consumes FastAPI endpoints and generated OpenAPI types; deterministic finance logic remains in the backend.

Current frontend scope is dashboard/read-oriented. Portfolio mutation forms are not implemented yet. See [Frontend runbook](docs/frontend.md).

## Live data behavior

Finwall defaults to `yfinance` for market data, fundamentals, and news where implemented. Static/manual providers remain available for tests, demos, explicit manual overrides, and safe fallback paths. Manual `--price TICKER=PRICE` values can still be used for deterministic examples and override fetched prices in supported CLI flows.

Live/free provider data may be unavailable, delayed, stale, partial, malformed, rate-limited, or blocked. It is decision-support context only, not broker-grade data and not an execution signal. See [Configuration](docs/configuration.md), [Safety limits](docs/safety-limits.md), and the [yfinance market-data spike](docs/market-data/yfinance-spike.md).

## Documentation map

- Local setup: [docs/local-setup.md](docs/local-setup.md)
- CLI workflows: [docs/cli-workflows.md](docs/cli-workflows.md)
- CLI reference: [docs/cli-reference.md](docs/cli-reference.md) plus `poetry run finwall --help` or `poetry run finwall <command> --help`
- API reference: [docs/api-reference.md](docs/api-reference.md); FastAPI OpenAPI is exported by `cd apps/web && npm run openapi:export`; see also [API and browser session mode](docs/api-admin.md)
- Frontend runbook: [docs/frontend.md](docs/frontend.md)
- Live-data provider reference: [Configuration market-data/fundamentals/news sections](docs/configuration.md#market-data) and [yfinance spike](docs/market-data/yfinance-spike.md)
- Configuration: [docs/configuration.md](docs/configuration.md)
- Safety limits: [docs/safety-limits.md](docs/safety-limits.md)
- Security: [docs/security.md](docs/security.md)
- Product modes: [docs/product-modes.md](docs/product-modes.md)
- Architecture: [docs/architecture/overview.md](docs/architecture/overview.md)
- ADRs: [docs/adr/](docs/adr/)
- Scheduled reports: [docs/deployment/scheduled-reports.md](docs/deployment/scheduled-reports.md)
- Email notifications: [docs/email-notifications.md](docs/email-notifications.md)

## Development

Backend checks:

```bash
poetry run ruff check .
poetry run ruff format --check --line-length 88 .
poetry run pytest
```

Frontend checks:

```bash
cd apps/web
npm run typecheck
npm test
npm run build
```
