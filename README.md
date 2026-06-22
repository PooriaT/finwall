# Finwall

## What Finwall is

Finwall is a **local/self-managed portfolio decision-support workflow**.

Its core path is to maintain portfolio state, generate deterministic analysis, and help you review risk and recommendation context before making your own decisions outside the tool.

## Safety and non-goals

Finwall is **not** financial advice.

- It does **not** connect to brokers.
- It does **not** execute orders.
- It does **not** perform automatic trading.
- It does **not** guarantee outcomes.
- Final decisions remain with you.

Finwall provides decision-support inputs (including deterministic analysis and optional narratives), not execution or guaranteed predictions.

See [docs/safety-limits.md](docs/safety-limits.md) for full limitations.

## Who Finwall is for

Finwall is for people who want to:

- Keep portfolio state local or self-managed.
- Generate deterministic decision-support reports.
- Review transparent risk signals and recommendation reasoning.
- Operate without broker execution or automatic trading.
- Avoid opaque AI-first advice engines as the primary decision source.

## Product modes at a glance

See [docs/product-modes.md](docs/product-modes.md) for the canonical capability-maturity reference.

| Mode | Maturity | Typical user action |
| --- | --- | --- |
| CLI portfolio maintenance | Supported primary | Update cash, holdings, trades/orders, watchlist, goals, and risk profile |
| Deterministic reports | Supported primary | Generate snapshot/risk/recommendation/report outputs |
| Scheduled reports | Supported secondary | Run reports on a schedule with app-level guardrails |
| Email notifications | Supported secondary | Receive scheduled-run success/failure summaries |
| API + modern frontend | Internal/self-managed | Use the React browser UI for dashboard reads and authenticated API endpoints for internal automation |
| Narrative provider | Experimental / optional explanation | Rewrite deterministic evidence into plain-language explanation |

## Primary workflow

1. Maintain local portfolio state (cash, holdings, orders, watchlist, goals, risk profile).
2. Generate deterministic reports.
3. Review risk warnings, recommendation status, and supporting inputs.
4. Make independent decisions outside Finwall.
5. Optionally add narrative explanation and scheduled automation.

Example (fake/test data):

```bash
poetry run finwall --database finwall.db add-cash USD 1000
poetry run finwall --database finwall.db add-holding NVDA 2 100 --sector Technology
poetry run finwall --database finwall.db set-risk moderate --notes "Example only"
poetry run finwall --database finwall.db report --price NVDA=120
```

## Quick start

```bash
poetry install
cp .env.example .env
poetry run finwall --database finwall.db add-cash USD 1000
poetry run finwall --database finwall.db add-holding NVDA 2 100 --sector Technology
poetry run finwall --database finwall.db report --price NVDA=120
```

For fuller local setup and command walkthroughs, see [docs/local-setup.md](docs/local-setup.md) and [docs/cli-workflows.md](docs/cli-workflows.md).

For the React frontend, see [docs/frontend.md](docs/frontend.md).

## Run the web app locally

Run the backend API and frontend dev server in separate terminals.

Backend:

```bash
FINWALL_API_TOKEN=change-me-long-random-token \
poetry run uvicorn finwall.api:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`. The frontend calls relative
`/api/v1/...` URLs, and Vite proxies `/api` to the FastAPI backend on
`http://127.0.0.1:8000`, so local browser requests do not require CORS.

## Common workflows

### Portfolio maintenance

Use CLI commands to maintain:

- cash balances
- holdings and sector metadata
- orders and watchlist entries
- goals and timeline inputs
- risk profile and related notes

See: [docs/local-setup.md](docs/local-setup.md), [docs/cli-workflows.md](docs/cli-workflows.md).

### Deterministic analysis and reports

> Status: **Supported primary** for snapshots/risk/recommendations/report structure. Technical/fundamental/news/market-condition outputs are **experimental/optional decision-support inputs** and may be incomplete or provider-limited. Fundamentals default to partial live `yfinance` inputs when available; static fundamentals remain for tests/manual overrides. Deterministic recommendations remain conservative and primarily snapshot/risk driven unless a rule set explicitly consumes additional inputs. These outputs are not financial advice or broker-grade guarantees.


Use deterministic commands for snapshots and decision-support analysis, including:

- snapshots and full reports
- risk assessment
- order evaluation
- recommendation status with supporting context

See: [docs/cli-workflows.md](docs/cli-workflows.md).

Finwall defaults to `yfinance` for local/self-managed live market data in commands such as `snapshot --live-prices`, `report --live-prices`, `technicals`, and `market-index SP500`. `FINWALL_MARKET_DATA_PROVIDER` is available as an override/debug setting for `yfinance`, `yahoo`, or explicit `static` workflows. Free providers may be unavailable, delayed, stale, partial, rate-limited, or blocked; they are not broker-grade market data and Finwall remains decision-support only. Run `poetry run finwall market-data-check --json` to check default or overridden provider availability before relying on live-price reports. See [docs/configuration.md](docs/configuration.md#market-data).

### Optional explanation

> Status: **Experimental / optional explanation**. Narrative output is downstream from deterministic evidence and cannot override deterministic report fields.


Narrative output is optional and downstream from deterministic evidence.

- Deterministic report fields remain authoritative.
- Invalid or unsafe narrative output falls back to a safe deterministic warning.
- Narrative output is not financial advice.

For configuration details, see [docs/configuration.md](docs/configuration.md).

## Optional automation and notifications

> Status: **Supported secondary**. Implemented for self-managed automation, but not the primary local usage path.


Automation is an optional layer, not the default usage path.

- Scheduled reports: [docs/deployment/scheduled-reports.md](docs/deployment/scheduled-reports.md)
- GitHub Actions scheduled runs: [docs/deployment/github-actions-scheduled-report.md](docs/deployment/github-actions-scheduled-report.md)
- SMTP email notifications: [docs/email-notifications.md](docs/email-notifications.md)

## Optional API and frontend surface

> Status: **Internal/self-managed**. Local browser UI and authenticated API only; not a public SaaS dashboard.

Finwall includes a Vite + React + TypeScript frontend under `apps/web` and a FastAPI backend API.

- Not a public SaaS dashboard.
- Not a broker interface.
- Intended for controlled internal use.
- Browser login uses HTTP-only session-cookie endpoints for read-only dashboard data.
- Programmatic/internal clients can use bearer-token API auth.
- The old server-rendered Jinja `/admin` UI has been removed; see [ADR 0002](docs/adr/0002-modern-frontend-scaffold.md).

See [docs/frontend.md](docs/frontend.md) and [docs/api-admin.md](docs/api-admin.md).

## Documentation map

### Getting started

- Local setup: `docs/local-setup.md`
- Configuration: `docs/configuration.md`
- Frontend development: `docs/frontend.md`

### Usage workflows

- CLI workflows: `docs/cli-workflows.md`

### Automation and deployment

- Scheduled reports: `docs/deployment/scheduled-reports.md`
- GitHub Actions scheduled report: `docs/deployment/github-actions-scheduled-report.md`
- Email notifications: `docs/email-notifications.md`
- Deployment ADR: `docs/adr/0001-finwall-scheduled-report-deployment.md`

### API and frontend

- Frontend development: `docs/frontend.md`
- API and browser session mode: `docs/api-admin.md`

### Safety, security, architecture

- Safety limits: `docs/safety-limits.md`
- Security and privacy: `docs/security.md`
- Architecture overview: `docs/architecture/overview.md`
- Frontend architecture ADR: `docs/adr/0002-modern-frontend-scaffold.md`

## Development

```bash
poetry run ruff check .
poetry run ruff format --check --line-length 88 .
poetry run pytest
```
