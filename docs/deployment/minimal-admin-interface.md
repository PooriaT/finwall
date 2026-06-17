# Minimal Admin Interface

> Status: **Internal/admin**. Minimal self-managed interface for maintenance tasks, not a public SaaS dashboard.

Finwall includes a minimal internal admin UI at `/admin` in the API app. It is server-rendered with FastAPI/Jinja2 templates and uses one small CSS file served by the app under `/admin/static`.

## Setup

- Set `FINWALL_API_TOKEN` to a strong secret token.
- Run the FastAPI app (for example with `uvicorn finwall.api:app --reload`).
- Open `/admin/login` and sign in with the token.
- No frontend build step is required; there is no React, Next.js, Tailwind, npm, or Vite pipeline.

## What it can update

- cash balances
- holdings
- buy/sell trades
- active orders
- watchlist items
- goal, timeline, and risk profile settings

## Security and limitations

- This is a minimal internal interface, not a public dashboard.
- It uses single-token authentication and an HttpOnly cookie.
- Do not expose publicly without extra protection (private network, reverse proxy auth, platform-level access controls).
- No multi-user accounts, role-based access control, charts, dashboard analytics, recommendations UI, broker integration, automatic trading, or public SaaS hardening.
