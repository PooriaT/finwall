# ADR 0002: Modern Frontend Scaffold and App Boundary

## Status

Accepted

## Context

Finwall now has a separate modern frontend scaffold under `apps/web` and no longer keeps the old FastAPI/Jinja `/admin` pages as a parallel browser UI.

Finwall's core safety posture does not change: it is a local/self-managed decision-support tool, not a broker integration, automatic trading system, or financial advice engine. The backend remains the source of truth for portfolio state, deterministic analysis, provider orchestration, reports, and audit semantics.

## Decision

Use the **Vite + React + TypeScript** app under `apps/web` as the primary product UI direction.

FastAPI remains the authoritative backend/API surface. The frontend consumes explicit API contracts and generated TypeScript types from the FastAPI OpenAPI schema. Browser login uses session-cookie endpoints:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/session`

The frontend/backend contract includes:

- OpenAPI-generated TypeScript schema/client workflow.
- TanStack Query for server-state loading, caching, and loading/error states.
- Recharts for the first dashboard charts.
- Plain CSS and local components until a larger design system is justified.

Bearer-token API auth remains available for programmatic/internal API usage. Browser session-cookie auth is accepted for frontend-needed read endpoints only. Portfolio mutation endpoints remain bearer-token protected unless intentionally changed by a later decision.

The old Jinja admin UI has been removed. Future portfolio mutation UI should be built in React against explicit backend API contracts.

## Frontend Boundary

The frontend may own:

- routes and views
- user interaction state
- loading, error, and empty states
- chart rendering
- presentation components
- calls to generated or typed API wrappers

The frontend must not own:

- portfolio valuation logic
- risk rules
- recommendation logic
- provider or fallback logic
- audit semantics
- report generation logic
- financial decision rules

## Backend Boundary

The backend continues to own:

- portfolio model and persistence
- API contract
- auth and session cookies
- market-data, fundamentals, and news provider calls
- chart-ready analysis data
- deterministic reports
- audit history

Backend modules remain the source of deterministic decision-support truth. Frontend code may present backend outputs, but it must not reimplement or fork finance decisions.

## Auth Direction

Finwall remains local/self-managed.

The web auth shape is:

- Use HttpOnly cookies for the frontend web session.
- Do not expose the API token to browser JavaScript.
- Keep bearer-token API auth available for programmatic/internal API usage.
- Keep browser session auth read-only unless a later ADR or issue intentionally changes that boundary.

OAuth, user registration, password reset, RBAC, multi-user accounts, and public SaaS auth are out of scope.

## Development and Build Shape

Backend development remains Python/Poetry based.

Frontend development uses Node package tooling isolated under `apps/web`. Local development can run the backend and frontend separately. Production/deployment shape remains a deployment concern, but deterministic finance logic must stay in backend Python modules rather than moving into browser code.

## Alternatives Considered

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Continue Jinja-admin-first | Simple backend-only UI | Poor fit for rich product UI, client-side charts, generated API typing, and modern interaction states | Removed as a parallel product surface |
| Vite + React + TypeScript | Lightweight SPA tooling; strong typing; clear app boundary | Adds Node tooling and generated-client workflow | Chosen direction |
| Next.js/SSR | Full-stack framework and SSR options | More framework surface than needed; blurs backend ownership for this app | Exclude for now |
| Large design system | Faster visual consistency if already needed | Premature commitment and dependency weight | Defer |

## Consequences

Positive outcomes:

- Clear primary browser UI direction in React.
- Stronger frontend/backend boundary around deterministic finance logic.
- Typed API access through the generated OpenAPI workflow.
- Client-side state and charting choices are explicit.
- The backend no longer carries a competing server-rendered UI surface.

Tradeoffs:

- Adds a Node toolchain under `apps/web`.
- Requires generated OpenAPI artifacts to stay current with backend API changes.
- Portfolio mutation UI must be implemented deliberately in React when needed.
- Local/self-managed browser auth remains token-derived and intentionally limited.

## Out of Scope

- Broker integration.
- Automatic trading.
- Next.js or SSR.
- OAuth, RBAC, public SaaS auth, or multi-user account management.
- Large design-system work.
- Moving valuation, risk, recommendation, provider fallback, report generation, or audit semantics into frontend code.
