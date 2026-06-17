# API/admin mode

> Status: **Internal/admin**. Token-authenticated self-managed maintenance tooling; not a public SaaS product, not multi-user RBAC, and not a broker interface.

Finwall includes a **minimal internal** FastAPI app and server-rendered admin pages. This is operational tooling, not a public SaaS dashboard.

## Run locally with Uvicorn

Use loopback host by default and set a strong token:

```bash
FINWALL_API_TOKEN=change-me-long-random-token \
poetry run uvicorn "finwall.api:create_app" --factory --host 127.0.0.1 --port 8000
```

If launching through CLI/API-enabled paths, also ensure `FINWALL_API_ENABLED=true` where applicable.

## Authentication

- API endpoints use `Authorization: Bearer <FINWALL_API_TOKEN>`.
- Admin web login uses the same token and stores an HTTP-only cookie.

## Key routes

- Health: `GET /health`
- Admin login/home: `/admin/login`, `/admin`
- Portfolio read: `GET /api/v1/portfolio`
- Portfolio audit list: `GET /api/v1/portfolio/audit`

## What API/admin can update

Implemented API update routes cover portfolio state operations such as:

- cash add/withdraw
- holdings
- trades (buy/sell)
- active orders
- watchlist
- goal/timeline/risk updates

The admin interface provides minimal Jinja2-rendered forms/navigation for the same internal portfolio-management workflows, including audit views. The FastAPI app serves its own lightweight CSS/static assets under `/admin/static`; there is no frontend build step.

## What it cannot do

- No broker integration.
- No automatic order execution.
- No multi-user SaaS auth model.
- No React, Next.js, Tailwind, npm, Vite, or frontend build system.
- No charts, dashboard analytics, recommendations UI, broker integration, or automatic trading.

## Security guidance

This mode is intended for internal/self-managed operation. Do not treat it as enterprise-hardened or internet-public SaaS without additional host/network/deployment controls.


- Prefer `127.0.0.1` host unless deliberate network exposure is protected.
- Use a strong random API token and rotate it if exposed.
- Treat this as internal tooling and combine token auth with host/network controls.
- See [docs/security.md](security.md) for broader secret/privacy guidance.
