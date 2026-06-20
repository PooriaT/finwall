# Frontend Development

Finwall's modern frontend scaffold lives in `apps/web`. It is a Vite + React +
TypeScript app that runs separately from the FastAPI backend during local
development.

The React frontend is the browser UI direction for Finwall. The old
server-rendered Jinja `/admin` pages have been removed; browser users should use
the React app against the FastAPI API.

## Install dependencies

```bash
cd apps/web
npm install
```

## Run the frontend

```bash
cd apps/web
npm run dev
```

Vite prints the local development URL, typically `http://localhost:5173`.

## Run the backend separately

In another terminal, run the existing FastAPI app with Poetry:

```bash
poetry run uvicorn finwall.api:app --reload
```

The frontend API client defaults to calling the backend at relative `/api`. In
local development, Vite proxies `/api` to the FastAPI backend at
`http://127.0.0.1:8000`, so browser requests stay same-origin and do not require
CORS middleware.

For development against a different backend origin, configure:

```bash
VITE_FINWALL_API_BASE_URL=http://127.0.0.1:8000/api
```

Only use a full URL when that backend origin is configured to allow browser CORS
requests.

## Generate API types

FastAPI is the source of truth for the browser API contract. Do not hand-write
duplicate TypeScript API model types.

Export the OpenAPI schema from the backend without starting a server:

```bash
cd apps/web
npm run openapi:export
```

Generate TypeScript types from the exported schema:

```bash
cd apps/web
npm run openapi:generate
```

Run both steps and fail if generated files are stale:

```bash
cd apps/web
npm run openapi:check
```

Generated files live in:

- `apps/web/openapi/finwall-openapi.json`
- `apps/web/src/api/generated/schema.ts`

The small hand-written wrapper lives in `apps/web/src/api/client.ts`, with
operation-derived aliases in `apps/web/src/api/types.ts`.

## Dashboard charts

The dashboard uses Recharts as its only charting library. The first read-only
chart components live in `apps/web/src/features/charts` and render these
backend chart-ready series from `GET /api/v1/portfolio/analysis/charts`:

- `allocation_by_holding`
- `cash_vs_invested`
- `unrealized_gain_loss_by_holding`
- `risk_warnings_by_severity`

The backend remains the source of truth for chart semantics and financial
calculations. Frontend chart adapters only parse backend string values into
numbers for display, while preserving the original string values for visible
labels, tooltips, and fallback tables.

Missing, invalid, or `null` chart values are displayed as unavailable instead of
being silently removed. Series warnings, incomplete valuation status, and partial
price-completeness status are shown visibly in chart cards. Every chart includes
a title, short summary, visible numeric labels, and an HTML fallback table for
accessible non-SVG content.

Browser authentication uses the frontend session endpoints:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/session`

The login page submits the local app token directly to the backend. On success,
the backend sets an HTTP-only `finwall_web_session` cookie with `SameSite=Lax`,
`Path=/`, and `Secure` when `FINWALL_ENV=production`. The token is not returned
in JSON and must not be stored in `localStorage`, `sessionStorage`, URLs, logs,
or generated client configuration.

Frontend API requests must use `credentials: "include"` so the browser sends the
session cookie. Bearer token auth remains available for non-browser API clients,
and API mutation endpoints remain bearer-only. The frontend session cookie is
accepted only for session checks and read-only frontend-needed API endpoints.
`GET /api/v1/auth/session` returns `401` for missing or invalid sessions; the
frontend treats that as unauthenticated state and shows the login route.

## Current status

The scaffold currently includes:

- a layout shell with Finwall branding
- protected dashboard, login, and not-found routes
- a visible safety note
- generated OpenAPI TypeScript schema workflow
- typed wrappers for portfolio, analysis chart, and audit reads
- typed wrappers for session login, logout, and session checks
- reusable Recharts dashboard components for allocation, cash/invested,
  unrealized gain/loss, and risk-warning severity series
- local CSS
- frontend typecheck, test, build, and preview scripts

Not implemented yet:

- portfolio mutation forms

## Safety and non-goals

Finwall remains a local/self-managed decision-support tool. The frontend must not
own deterministic finance logic, expose API tokens to browser JavaScript, connect
to brokers, execute orders, or perform automatic trading.

Browser API calls must use session-cookie-friendly requests for read endpoints.
Do not store raw API tokens in frontend code or browser-accessible storage. OAuth,
user registration, password reset, RBAC, and multi-user account management are
out of scope.
