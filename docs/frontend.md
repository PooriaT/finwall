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

The frontend scaffold does not call backend endpoints yet. A later issue may add
a development proxy and generated API client workflow.

## Current status

The scaffold currently includes:

- a layout shell with Finwall branding
- dashboard, login, and not-found placeholder routes
- a visible safety note
- local CSS
- frontend typecheck, test, build, and preview scripts

Not implemented yet:

- real browser session auth
- generated API client
- live dashboard data
- charts
- portfolio mutation forms
- backend API integration

## Safety and non-goals

Finwall remains a local/self-managed decision-support tool. The frontend must not
own deterministic finance logic, expose API tokens to browser JavaScript, connect
to brokers, execute orders, or perform automatic trading.
