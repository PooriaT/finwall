# Minimal Admin Interface

Finwall includes a minimal internal admin UI at `/admin` in the API app.

## Setup

- Set `FINWALL_API_TOKEN` to a strong secret token.
- Run the FastAPI app (for example with `uvicorn finwall.api:app --reload`).
- Open `/admin/login` and sign in with the token.

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
- No multi-user accounts, role-based access control, charts, recommendations UI, or broker integration.
