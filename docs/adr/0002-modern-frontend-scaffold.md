# ADR 0002: Modern Frontend Scaffold and App Boundary

## Status

Accepted

## Context

Finwall currently exposes its interactive maintenance UI through the FastAPI/Jinja admin surface. That surface is useful for internal, self-managed administration, but it is not the right long-term product UI for richer portfolio review workflows, interactive loading/error states, client-side charting, or a clearer separation between presentation code and deterministic finance logic.

Finwall's core safety posture does not change: it is a local/self-managed decision-support tool, not a broker integration, automatic trading system, or financial advice engine. The backend remains the source of truth for portfolio state, deterministic analysis, provider orchestration, reports, and audit semantics.

## Decision

Build the next primary product UI as a separate **Vite + React + TypeScript** app under `apps/web`.

The frontend will run separately from the FastAPI backend during local development. Later implementation PRs may add a Vite development proxy to FastAPI, but this ADR does not add frontend tooling, scripts, dependencies, or scaffold files.

The frontend/backend contract direction is:

- Generate a TypeScript API client from the FastAPI OpenAPI schema.
- Use TanStack Query for server-state loading, caching, invalidation, and loading/error/empty states.
- Use Recharts for the first dashboard charts.
- Start with plain CSS, CSS modules, or a small component utility layer; do not commit to a large design system yet.

The existing Jinja admin remains a legacy/internal maintenance surface during migration and should continue to work until intentionally replaced.

## Frontend Boundary

The frontend may own:

- routes and views
- user interaction state
- loading, error, and empty states
- chart rendering
- presentation components
- calls to the generated API client

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

The intended web auth direction is:

- Add session-based web login in a later issue.
- Use HttpOnly cookies for the frontend web session.
- Do not expose the API token to browser JavaScript.
- Keep bearer-token API auth available for programmatic/internal API usage unless intentionally changed later.

OAuth, user registration, password reset, RBAC, multi-user accounts, and public SaaS auth are out of scope.

## Development and Build Shape

Backend development remains Python/Poetry based.

Frontend development will use Node package tooling isolated under `apps/web`. Local development can run the backend and frontend separately. A later PR may add a Vite-to-FastAPI dev proxy.

Production/deployment shape is not fully decided in this ADR. The intended direction is to keep FastAPI as the authoritative backend API and serve/build the frontend as a separate web app artifact or deployment concern, without moving deterministic finance logic into browser code.

## Alternatives Considered

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Continue Jinja-admin-first | Simple; no frontend toolchain | Poor fit for rich product UI, client-side charts, and modern interaction states | Keep only as legacy/internal during migration |
| Vite + React + TypeScript | Lightweight SPA tooling; strong typing; clear app boundary | Adds Node tooling and generated-client workflow | Chosen direction |
| Next.js/SSR | Full-stack framework and SSR options | More framework surface than needed; blurs backend ownership for this app | Exclude for now |
| Large design system | Faster visual consistency if already needed | Premature commitment and dependency weight | Defer |

## Consequences

Positive outcomes:

- Clear path from internal Jinja admin toward a proper product UI.
- Stronger frontend/backend boundary around deterministic finance logic.
- Typed API access through the generated OpenAPI client.
- Client-side state and charting choices are explicit before scaffold work begins.

Tradeoffs:

- Adds a future Node toolchain under `apps/web`.
- Requires OpenAPI client generation workflow in a later issue.
- Requires a later auth implementation for browser sessions.
- Keeps two UI surfaces during migration.

## Out of Scope for This ADR

This ADR accepts the frontend direction, but it does not implement it. The following work is deferred to later implementation PRs unless explicitly excluded elsewhere:

- Creating the `apps/web` scaffold.
- Adding Vite, React, TypeScript, Node dependencies, or package files.
- Adding OpenAPI generation scripts.
- Adding auth/session endpoints.
- Building dashboard pages or charts.
- Changing FastAPI, CLI, Jinja templates, or deterministic finance logic.
- Broker integration.
- Automatic trading.
- Next.js or SSR.
- OAuth, RBAC, public SaaS auth, or multi-user account management.
- Large design-system work.
