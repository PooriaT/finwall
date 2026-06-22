# API and browser session mode

> Status: **Internal/self-managed API**. Token-authenticated backend API plus browser session endpoints for the React frontend; not a public SaaS product, not multi-user RBAC, and not a broker interface.

Finwall's FastAPI app is the authoritative backend/API surface. Browser users should use the React frontend in `apps/web`; the old server-rendered Jinja `/admin` pages have been removed.

## Run locally with Uvicorn

Use loopback host by default and set a strong token:

```bash
FINWALL_API_TOKEN=change-me-long-random-token \
poetry run uvicorn "finwall.api:create_app" --factory --host 127.0.0.1 --port 8000
```

If launching through CLI/API-enabled paths, also ensure `FINWALL_API_ENABLED=true` where applicable.

## Authentication

- Programmatic/internal API clients use `Authorization: Bearer <FINWALL_API_TOKEN>`.
- The React frontend uses `POST /api/v1/auth/login` to exchange the local token for an HTTP-only `finwall_web_session` cookie.
- Browser requests must use `credentials: include`; the token is not returned in JSON and must not be stored in browser-accessible storage.

This local/self-managed flow does not add OAuth, registration, password reset, RBAC, public SaaS auth, or multi-user accounts.

## Key routes

- Health: `GET /health`
- Frontend session auth: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/session`
- Portfolio read: `GET /api/v1/portfolio`
- Portfolio analysis charts: `GET /api/v1/portfolio/analysis/*`
- Portfolio audit list: `GET /api/v1/portfolio/audit`

`GET /api/v1/auth/session` returns `401` when the frontend session cookie is missing or invalid. Successful login/logout responses only return authenticated state and do not include the configured token.

## Read and mutation split

Read endpoints needed by the React frontend accept either bearer auth or the browser session cookie:

- `GET /api/v1/portfolio`
- `GET /api/v1/portfolio/analysis/charts`
- `GET /api/v1/portfolio/analysis/allocation/holdings`
- `GET /api/v1/portfolio/analysis/allocation/sectors`
- `GET /api/v1/portfolio/analysis/cash-vs-invested`
- `GET /api/v1/portfolio/analysis/unrealized-gain-loss`
- `GET /api/v1/portfolio/analysis/risk-warnings`
- `GET /api/v1/portfolio/analysis/report-history`
- `GET /api/v1/portfolio/audit`

Portfolio mutation endpoints remain bearer-token protected and do not accept the frontend session cookie:

- cash add/withdraw
- holdings changes
- trades
- orders
- watchlist
- goal, timeline, and risk profile updates

Future portfolio mutation UI should be built in React against explicit backend API contracts.

## Portfolio analysis chart-data endpoints

The analysis endpoints return deterministic JSON payloads used by the React dashboard charts and available to API clients. They do not mutate portfolios, place broker orders, add analytics rules, or change storage schema.

These endpoints reuse the existing portfolio snapshot, risk assessment, market-data provider selection, latest-price fetching, and report-history storage services. Values are decision-support data only. Finwall defaults to `yfinance` for live market prices, while `FINWALL_MARKET_DATA_PROVIDER` is only an override/debug selector for `yfinance`, `yahoo`, or explicit `static`. Payloads can be partial when prices are missing or a market data provider fails; missing prices are represented with status fields, `null` values where appropriate, warnings, and metadata instead of raw tracebacks.

Use the optional `report_history_limit` query parameter to bound report history in chart payloads. The API defaults to `10` and caps requests at `50`.

## Security guidance

This mode is intended for internal/self-managed operation. Do not treat it as enterprise-hardened or internet-public SaaS without additional host, network, and deployment controls.

- Prefer `127.0.0.1` host unless deliberate network exposure is protected.
- Use a strong random API token and rotate it if exposed.
- Treat this as internal tooling and combine token auth with host/network controls.
- See [docs/security.md](security.md) for broader secret/privacy guidance.

## What it cannot do

- No broker integration.
- No automatic order execution.
- No multi-user SaaS auth model.
- No public SaaS hardening.
- No guaranteed outcomes or financial advice.
