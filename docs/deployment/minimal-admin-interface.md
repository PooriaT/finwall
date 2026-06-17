# Minimal Admin Interface

> Status: **Internal/admin**. Minimal self-managed interface for maintenance tasks, not a public SaaS dashboard.

Finwall includes a minimal internal admin UI at `/admin` in the API app. It is server-rendered with FastAPI/Jinja2 templates and uses one small CSS file served by the app under `/admin/static`.

## Setup

- Set `FINWALL_API_TOKEN` to a strong secret token.
- Run the FastAPI app (for example with `uvicorn finwall.api:app --reload`).
- Open `/admin/login` and sign in with the token.
- No frontend build step is required; there is no React, Next.js, Tailwind, npm, Vite pipeline, or CDN chart dependency.

## Dashboard charts

The `/admin` dashboard includes first read-only charts for allocation by holding, cash vs invested, unrealized gain/loss by holding, and risk warnings by severity. They are server-rendered with HTML/CSS from the existing portfolio analysis chart-data layer, so the browser does not need bearer-token API calls. Chart values are decision-support only and may be partial when market prices are missing; missing data is shown with visible status text and fallback table/list content. Charts do not add broker integration, automatic trading, new analytics logic, or auth changes.

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
- No multi-user accounts, role-based access control, recommendations UI, broker integration, automatic trading, complex interactive charting, or public SaaS hardening.
