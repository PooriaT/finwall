# API reference

> Status: **internal/self-managed API reference**. FastAPI is the source of
> truth for endpoint behavior and OpenAPI contracts; this document is a readable
> companion, not a replacement for generated schemas.

## Status and safety

Finwall's API is intended for local or otherwise tightly controlled
self-managed deployments. It is decision-support software only: it does not
connect to brokers, execute orders, automate trading, or provide financial
advice.

Keep deployments private unless you add separate host, network, and operational
controls. OAuth, RBAC, public SaaS hardening, registration, password reset, and
multi-user account management are out of scope.

## Authentication model

Finwall has two authentication paths backed by the same configured
`FINWALL_API_TOKEN` value:

- **Bearer-token auth** for programmatic/internal clients:
  `Authorization: Bearer <FINWALL_API_TOKEN>`.
- **Browser session-cookie auth** for the React frontend read experience:
  `POST /api/v1/auth/login` accepts the local token and sets an HTTP-only
  `finwall_web_session` cookie.

The session cookie is set with `HttpOnly`, `SameSite=Lax`, `Path=/`, and
`Secure` when `FINWALL_ENV=production`. Browser API requests must use
`credentials: "include"` so the cookie is sent. The raw API token is not returned
by login responses and must not be stored in `localStorage`, `sessionStorage`,
URLs, logs, generated frontend configuration, or other browser-accessible
storage.

Read endpoints needed by the React frontend accept either bearer auth or the
browser session cookie. Portfolio mutation endpoints remain **bearer-token only**
and do not accept the frontend session cookie.

## Response and error conventions

- JSON is the normal response format.
- Authentication failures return `401` with a safe `detail` message.
- FastAPI/Pydantic validation failures return `422` for malformed request bodies
  or invalid typed parameters.
- Some domain validation failures return `400` with a safe error message.
- Decimal-like request values are accepted as strings to avoid browser and JSON
  floating-point ambiguity.
- Mutation endpoints return the updated portfolio snapshot rather than a narrow
  mutation result object.

## Health

| Method | Path | Purpose | Auth accepted | Request body | Query params | Response summary | Mutates state? | Frontend-used? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/health` | Liveness check for the API process. | None. | None. | None. | `{ "status": "ok" }`. | No | No |

## Browser session endpoints

| Method | Path | Purpose | Auth accepted | Request body | Query params | Response summary | Mutates state? | Frontend-used? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | Exchange the configured local API token for an HTTP-only browser session cookie. | Submitted token in JSON body. | `{ "token": "..." }`. | None. | `{ "authenticated": true }` and `Set-Cookie: finwall_web_session=...` on success. | Yes, browser cookie only | Yes |
| `POST` | `/api/v1/auth/logout` | Clear the browser session cookie. | None required. | None. | None. | `{ "authenticated": false }` and an expired session cookie. | Yes, browser cookie only | Yes |
| `GET` | `/api/v1/auth/session` | Check whether the browser session cookie is currently valid. | Valid `finwall_web_session` cookie only. | None. | None. | `{ "authenticated": true }`; missing/invalid sessions return `401`. | No | Yes |

## Portfolio read endpoints

| Method | Path | Purpose | Auth accepted | Request body | Query params | Response summary | Mutates state? | Frontend-used? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/portfolio` | Read the default portfolio snapshot. | Bearer token or browser session cookie. | None. | None. | Portfolio object with name, cash balances, holdings, transactions, active orders, watchlist, goals, risk profile, and recommendations. | No | Yes |
| `GET` | `/api/v1/live-data/status` | Read configured live-data provider status metadata for prices, fundamentals, news, and market condition. | Bearer token or browser session cookie. | None. | None. | `{ "statuses": [...] }` with domain, provider, source, availability, fallback, warning, safe-error, and metadata fields. | No | No |

## Analysis/chart-data endpoints

All analysis endpoints are read-only and accept either bearer auth or the browser
session cookie. They may include partial/unavailable status metadata when live
prices or report-history inputs are incomplete. `report_history_limit` defaults
to `10` and is bounded by the backend to the range `0..50`.

| Method | Path | Purpose | Auth accepted | Request body | Query params | Response summary | Mutates state? | Frontend-used? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/portfolio/analysis/charts` | Read all dashboard chart-ready analysis series at once. | Bearer token or browser session cookie. | None. | `report_history_limit` integer, optional. | Portfolio name, valuation/price completeness status, data warnings, live-data status list, and a `charts` object containing all series. | No | Yes |
| `GET` | `/api/v1/portfolio/analysis/allocation/holdings` | Read allocation by holding. | Bearer token or browser session cookie. | None. | `report_history_limit` integer, optional. | Chart series with key, title, points, warnings, and per-point value/percent/status/metadata. | No | No |
| `GET` | `/api/v1/portfolio/analysis/allocation/sectors` | Read allocation by sector. | Bearer token or browser session cookie. | None. | `report_history_limit` integer, optional. | Chart series with sector allocation points. | No | No |
| `GET` | `/api/v1/portfolio/analysis/cash-vs-invested` | Read cash compared with invested value. | Bearer token or browser session cookie. | None. | `report_history_limit` integer, optional. | Chart series with cash/invested points. | No | No |
| `GET` | `/api/v1/portfolio/analysis/unrealized-gain-loss` | Read unrealized gain/loss by holding. | Bearer token or browser session cookie. | None. | `report_history_limit` integer, optional. | Chart series with gain/loss points and availability metadata. | No | No |
| `GET` | `/api/v1/portfolio/analysis/risk-warnings` | Read risk-warning counts by severity. | Bearer token or browser session cookie. | None. | `report_history_limit` integer, optional. | Chart series with risk-warning severity points. | No | No |
| `GET` | `/api/v1/portfolio/analysis/report-history` | Read saved report-history summary data. | Bearer token or browser session cookie. | None. | `report_history_limit` integer, optional. | Chart series summarizing recent saved report runs. | No | No |

## Audit endpoints

| Method | Path | Purpose | Auth accepted | Request body | Query params | Response summary | Mutates state? | Frontend-used? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/portfolio/audit` | Read portfolio mutation audit events for the default portfolio. | Bearer token or browser session cookie. | None. | `limit` integer, optional; defaults to `50`. | `{ "events": [...] }` containing safe audit event data such as action, entity, status, summary, before/after JSON snapshots, and safe error messages where available. | No | Yes |

## Portfolio mutation endpoints

Mutation endpoints require bearer-token auth and do not accept the browser
session cookie. They update the default portfolio and record audit events where
implemented. Request body decimal fields are strings.

| Method | Path | Purpose | Auth accepted | Request body | Query params/path params | Response summary | Mutates state? | Frontend-used? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/portfolio/cash/add` | Add to or create a cash balance. | Bearer token only. | `currency`, `amount`. | None. | Updated portfolio snapshot. | Yes | No |
| `POST` | `/api/v1/portfolio/cash/withdraw` | Withdraw from a cash balance. | Bearer token only. | `currency`, `amount`. | None. | Updated portfolio snapshot; domain failures can return `400`. | Yes | No |
| `POST` | `/api/v1/portfolio/holdings` | Add or update a holding. | Bearer token only. | `ticker`, `shares`, `average_price`, optional `sector`. | None. | Updated portfolio snapshot. | Yes | No |
| `DELETE` | `/api/v1/portfolio/holdings/{ticker}` | Remove a holding by ticker. | Bearer token only. | None. | `ticker` path parameter. | Updated portfolio snapshot. | Yes | No |
| `POST` | `/api/v1/portfolio/trades/buy` | Record a buy trade and update cash/holdings. | Bearer token only. | `ticker`, `shares`, `price`, `currency`, optional `trade_date`. | None. | Updated portfolio snapshot; insufficient cash/domain failures can return `400`. | Yes | No |
| `POST` | `/api/v1/portfolio/trades/sell` | Record a sell trade and update cash/holdings. | Bearer token only. | `ticker`, `shares`, `price`, `currency`, optional `trade_date`. | None. | Updated portfolio snapshot; insufficient holdings/domain failures can return `400`. | Yes | No |
| `POST` | `/api/v1/portfolio/orders` | Add or update an active order record. | Bearer token only. | `ticker`, `side`, `order_type`, `shares`, optional `limit_price`, optional `stop_price`. | None. | Updated portfolio snapshot. | Yes | No |
| `DELETE` | `/api/v1/portfolio/orders/{ticker}` | Remove an active order by ticker. | Bearer token only. | None. | `ticker` path parameter. | Updated portfolio snapshot. | Yes | No |
| `POST` | `/api/v1/portfolio/watchlist` | Add or update a watchlist item. | Bearer token only. | `ticker`, optional `note`. | None. | Updated portfolio snapshot. | Yes | No |
| `DELETE` | `/api/v1/portfolio/watchlist/{ticker}` | Remove a watchlist item by ticker. | Bearer token only. | None. | `ticker` path parameter. | Updated portfolio snapshot. | Yes | No |
| `PUT` | `/api/v1/portfolio/goal` | Set the portfolio goal. | Bearer token only. | `name`, optional `target_amount`. | None. | Updated portfolio snapshot. | Yes | No |
| `PUT` | `/api/v1/portfolio/timeline` | Set the investment timeline. | Bearer token only. | `start_date`, optional `target_date`. | None. | Updated portfolio snapshot; invalid timeline can return `422`. | Yes | No |
| `PUT` | `/api/v1/portfolio/risk-profile` | Set the risk profile. | Bearer token only. | `level`, optional `notes`. | None. | Updated portfolio snapshot. | Yes | No |

## OpenAPI and generated frontend client

FastAPI route and Pydantic model declarations are the source of truth. Keep this
human reference concise and use generated contracts for exact nested schemas.

OpenAPI workflow files:

- Export script: [`scripts/export_openapi.py`](../scripts/export_openapi.py)
- Exported schema: [`apps/web/openapi/finwall-openapi.json`](../apps/web/openapi/finwall-openapi.json)
- Generated TypeScript schema: [`apps/web/src/api/generated/schema.ts`](../apps/web/src/api/generated/schema.ts)
- Frontend API wrapper: [`apps/web/src/api/client.ts`](../apps/web/src/api/client.ts)
- npm scripts: [`apps/web/package.json`](../apps/web/package.json)
  - `npm run openapi:export`
  - `npm run openapi:generate`
  - `npm run openapi:check`

`npm run openapi:check` exports the current FastAPI schema, regenerates
TypeScript types, and fails if the committed OpenAPI JSON or generated
TypeScript schema is stale.

## Curl examples

Set a base URL first:

```bash
API_BASE=http://127.0.0.1:8000
TOKEN=replace-with-your-local-finwall-token
```

Health check:

```bash
curl "$API_BASE/health"
```

Browser-session login, session check, and logout with a temporary cookie jar:

```bash
curl -c /tmp/finwall-cookies.txt \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$TOKEN\"}" \
  "$API_BASE/api/v1/auth/login"

curl -b /tmp/finwall-cookies.txt \
  "$API_BASE/api/v1/auth/session"

curl -b /tmp/finwall-cookies.txt -c /tmp/finwall-cookies.txt \
  -X POST \
  "$API_BASE/api/v1/auth/logout"
```

Bearer-token portfolio read:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$API_BASE/api/v1/portfolio"
```

Analysis chart data:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$API_BASE/api/v1/portfolio/analysis/charts?report_history_limit=10"
```

Audit list:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$API_BASE/api/v1/portfolio/audit?limit=25"
```

Representative mutation endpoint, using bearer-token auth only:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"currency":"USD","amount":"100.00"}' \
  "$API_BASE/api/v1/portfolio/cash/add"
```
