# Frontend runbook

## What the frontend is

Finwall's browser UI lives in `apps/web`. It is a Vite + React + TypeScript
app that runs separately from the FastAPI backend during local development.
It uses TanStack Query for API reads, generated OpenAPI TypeScript types for the
backend contract, and Recharts for dashboard charts.

The React app is the supported browser surface. The old server-rendered Jinja
`/admin` pages have been removed. CLI workflows remain supported for portfolio
maintenance and reports, while the current browser scope is read-oriented
dashboard access.

## Prerequisites

- Install the Python/Poetry environment from the repository root.
- Install Node.js/npm for the Vite app.
- Configure a local API token before using the backend or login form.
- Use fake/test portfolio data while validating setup.

Frontend-relevant backend variables:

- `FINWALL_API_TOKEN`: required for API mode and for browser login. Use a long,
  random local token.
- `FINWALL_API_HOST` and `FINWALL_API_PORT`: used by Finwall API configuration
  helpers and deployment scripts; the runbook command below pins uvicorn to
  `127.0.0.1:8000` explicitly.
- `FINWALL_ENV`: set to `production` only when the frontend/backend are served
  over HTTPS; in production the session cookie is marked `Secure`.
- Provider variables such as market-data, fundamentals, and news providers are
  backend concerns. See [Configuration](configuration.md) and the
  [market-data section](configuration.md#market-data) instead of duplicating the
  provider reference here.

Frontend variable:

- `VITE_FINWALL_API_BASE_URL`: optional. Leave unset for normal local
  development so the app calls relative `/api` and uses the Vite proxy. Set it
  only when the browser must call a different backend base URL, for example
  `http://127.0.0.1:8000/api`; full cross-origin URLs require CORS and
  session-cookie settings that work for browser credentialed requests.

Do not add new frontend environment variables for this workflow.

## Run backend locally

Run the backend from the repository root in one terminal:

```bash
FINWALL_API_TOKEN=change-me-long-random-token \
poetry run uvicorn "finwall.api:create_app" --factory --host 127.0.0.1 --port 8000
```

Use the same token in the browser login form. If you also maintain portfolio
state from the CLI, keep using the existing CLI commands and database settings
for your local setup.

## Run frontend locally

Run the Vite app in a second terminal:

```bash
cd apps/web
npm install
npm run dev
```

Vite prints the local development URL, typically `http://localhost:5173`. Open
that URL in the browser. During normal local development, browser API calls use
relative `/api` URLs and Vite proxies those requests to
`http://127.0.0.1:8000`.

## Login flow

Browser authentication uses these session endpoints:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/session`

The user enters the local app token in the React login form. The frontend sends
that token to `/api/v1/auth/login`; the backend validates it against
`FINWALL_API_TOKEN` and, on success, sets an HTTP-only `finwall_web_session`
cookie. The frontend does not receive the raw token in JSON and must not store
it in `localStorage`, `sessionStorage`, URLs, logs, generated client
configuration, or checked-in files.

Session state is checked with `GET /api/v1/auth/session`. A missing, expired, or
invalid session returns `401`, which the app treats as unauthenticated state and
shows the login page. Logout calls `POST /api/v1/auth/logout`, which clears the
cookie and removes cached dashboard reads.

Frontend requests include `credentials: "include"` so the browser sends the
session cookie. Bearer-token auth remains available for programmatic/internal
API clients and portfolio mutation endpoints remain bearer-token protected.

## API base URL and Vite proxy

The hand-written API wrapper in `apps/web/src/api/client.ts` defaults to
`/api`. It builds endpoint paths such as `/api/v1/portfolio` and always sends
browser credentials.

`apps/web/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000` with
`changeOrigin: true` during `npm run dev`. This keeps local development
same-origin from the browser's point of view and avoids needing CORS middleware
for the default two-terminal setup.

Use `VITE_FINWALL_API_BASE_URL` only when the frontend must talk to a backend
outside the Vite proxy. Prefer a base URL that includes `/api`, for example:

```bash
VITE_FINWALL_API_BASE_URL=http://127.0.0.1:8000/api npm run dev
```

A full backend URL can make requests cross-origin. In that mode the backend must
permit credentialed browser requests, and the cookie attributes must be valid
for the origin and protocol. For local development, the relative `/api` default
is the safer path.

## Generated API client workflow

FastAPI is the source of truth for the browser API contract. Do not hand-write
duplicate TypeScript model types for API payloads.

From `apps/web`, use:

```bash
cd apps/web
npm run openapi:export
npm run openapi:generate
npm run openapi:check
```

The scripts do the following:

- `openapi:export`: runs the backend schema exporter and writes
  `apps/web/openapi/finwall-openapi.json`.
- `openapi:generate`: runs `openapi-typescript` and writes
  `apps/web/src/api/generated/schema.ts`.
- `openapi:check`: exports, regenerates, then fails if either generated file has
  an uncommitted diff.

The small fetch wrapper lives in `apps/web/src/api/client.ts`, and
operation-derived aliases live in `apps/web/src/api/types.ts`.

## Dashboard data flow

The dashboard combines three backend reads through TanStack Query:

- `GET /api/v1/portfolio` for holdings, cash balances, active orders,
  watchlist, goals, risk profile, and summary tables.
- `GET /api/v1/portfolio/analysis/charts` for backend analysis metadata,
  chart-ready series, live-data status, and latest report metadata.
- `GET /api/v1/portfolio/audit?limit=5` for the recent audit preview.

TanStack Query is configured with retries disabled and no refetch-on-window-focus
for predictable local behavior. The dashboard shows explicit loading and error
states: if the portfolio read fails, the dashboard does not show partial
portfolio tables; if analysis or audit reads fail, the portfolio tables remain
visible with targeted error messages for those sections.

Missing or partial live data is displayed as status and warnings in the UI. The
backend remains the source of deterministic portfolio state, finance logic,
risk checks, and market-data/provider decisions.

## Chart data flow

Recharts components render backend chart-ready data from
`GET /api/v1/portfolio/analysis/charts`. Current dashboard chart sections use:

- `allocation_by_holding`
- `cash_vs_invested`
- `unrealized_gain_loss_by_holding`
- `risk_warnings_by_severity`

The backend also exposes related analysis endpoints for API clients, but the
frontend dashboard reads the aggregate charts endpoint. Frontend chart adapters
parse backend string values into numbers for display and preserve original
strings for labels, tooltips, and fallback tables.

Empty, missing, invalid, or `null` chart values are shown as unavailable or empty
states instead of being silently removed. Incomplete valuation, partial
price-completeness, and provider warnings are decision-support metadata only;
they are not broker-grade data or trading signals.

## Troubleshooting

- **Frontend cannot reach backend**: make sure the backend command is running on
  `127.0.0.1:8000`, the frontend is running from `apps/web`, and
  `VITE_FINWALL_API_BASE_URL` is unset for the default proxy path. Check the
  browser network tab for `/api/v1/...` requests.
- **Login returns 401**: confirm `FINWALL_API_TOKEN` is set before backend start,
  enter that exact token in the login form, and restart the backend if the token
  changed. A missing token also makes authentication fail.
- **Dashboard stuck loading**: check whether `/api/v1/auth/session` or
  `/api/v1/portfolio` is pending or blocked in the network tab. Restart the
  backend/frontend dev servers and confirm the Vite proxy target is reachable.
- **Missing live data**: provider data can be unavailable, delayed, partial,
  malformed, rate-limited, or blocked. Review the live-data status displayed in
  the dashboard and see [Configuration](configuration.md#market-data) for
  provider settings and diagnostics.
- **Stale OpenAPI client**: run `cd apps/web && npm run openapi:check`. If it
  reports diffs, commit the regenerated schema and TypeScript files with the
  backend API change.
- **Empty chart sections**: confirm the portfolio has holdings/cash/risk data
  relevant to the chart, then inspect the `analysis/charts` response for empty
  series, warnings, or unavailable values.
- **CORS or session-cookie problems with a full backend URL**: prefer relative
  `/api` locally. If using `VITE_FINWALL_API_BASE_URL` with another origin,
  browser credentialed requests require backend CORS support and cookie
  attributes compatible with that origin, HTTPS, and `FINWALL_ENV`.
- **Test, typecheck, or build failures**: run the exact command from `apps/web`,
  install dependencies with `npm install`, and regenerate OpenAPI files if errors
  reference generated API types.

## Safety and non-goals

Finwall remains a local/self-managed decision-support tool. The frontend must
not own deterministic finance logic, expose API tokens to browser JavaScript,
connect to brokers, execute orders, or perform automatic trading.

Browser API calls must use session-cookie-friendly requests for read endpoints.
Do not store raw API tokens in frontend code or browser-accessible storage.
OAuth, user registration, password reset, RBAC, public SaaS multi-user account
management, broker integration, automatic trading, portfolio mutation forms, and
new charts are out of scope for this runbook update.
