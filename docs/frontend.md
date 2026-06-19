# Frontend Development

Finwall's modern frontend scaffold lives in `apps/web`. It is a Vite + React +
TypeScript app that runs separately from the FastAPI backend during local
development.

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

The frontend API client defaults to calling the backend at relative `/api`. For
local development against a separately hosted API, configure:

```bash
VITE_FINWALL_API_BASE_URL=http://127.0.0.1:8000/api
```

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

The initial wrappers call read-only API endpoints and rely on the HTTP-only
`finwall_admin_token` cookie set by the existing admin login flow. Bearer token
auth remains available for non-browser API clients, and API mutation endpoints
remain bearer-only.

## Current status

The scaffold currently includes:

- a layout shell with Finwall branding
- dashboard, login, and not-found placeholder routes
- a visible safety note
- generated OpenAPI TypeScript schema workflow
- typed wrappers for portfolio, analysis chart, and audit reads
- local CSS
- frontend typecheck, test, build, and preview scripts

Not implemented yet:

- real browser session auth
- live dashboard data
- charts
- portfolio mutation forms
- backend API integration

## Safety and non-goals

Finwall remains a local/self-managed decision-support tool. The frontend must not
own deterministic finance logic, expose API tokens to browser JavaScript, connect
to brokers, execute orders, or perform automatic trading.

Browser API calls must use session-cookie-friendly requests for read endpoints.
Do not store or send raw API tokens from frontend code.
