# Product modes and capability maturity

This document is the canonical capability-maturity reference for Finwall.

Finwall is a self-managed decision-support tool. It is not a broker, not an execution engine, and not a guarantee/prediction system.

## Maturity taxonomy

- **Supported primary**: Core workflows Finwall presents as the main usage path.
- **Supported secondary**: Implemented and usable automation/supporting workflows, but not the primary local path.
- **Internal/admin**: Implemented self-managed maintenance surfaces, not a public SaaS product.
- **Experimental / optional**: Optional or constrained analysis/explanation inputs that support decisions but are not deterministic ground truth.
- **Incomplete / constrained**: Known limits that affect deployment, data quality, scope, or hardening.
- **Future / planned / out of scope**: Explicit non-goals and not-currently-implemented capabilities.

## Supported primary

- CLI portfolio maintenance (cash, holdings, trades, orders, watchlist, goals, timeline, risk profile).
- Local/self-managed SQLite portfolio state.
- Deterministic snapshots/reports/risk/recommendation outputs.
- Safety and non-goal boundaries (no broker integration, no order execution, no guaranteed outcomes).

## Supported secondary

- `run-scheduled-report` command for self-managed automation.
- Report history/save/compare workflows.
- Scheduled-run logging and duplicate suppression.
- SMTP email notifications for scheduled report outcomes.
- GitHub Actions scheduled-report workflow as a repo automation option.
- Yahoo public-endpoint market data via `FINWALL_MARKET_DATA_PROVIDER=yahoo` for local/self-managed live-price, index, technical, and market-condition workflows.

## Internal/admin

- FastAPI API endpoints for authenticated portfolio maintenance.
- Minimal server-rendered admin forms.
- Portfolio audit history surfaces.

These are internal/self-managed tooling surfaces and are not public SaaS-grade product interfaces.

## Experimental / optional

- Optional narrative provider (for example Ollama) as an explanation layer.
- Narrative output as downstream context only.
- Technical indicators.
- Market-condition classification.
- Fundamentals inputs/summaries.
- News inputs/summaries.

These capabilities are decision-support inputs and may be provider-limited or incomplete. Deterministic report/risk/recommendation fields remain the authoritative structured outputs.

## Incomplete / constrained

- Postgres backend selection is not implemented at runtime; SQLite is the usable backend today.
- Multi-currency aggregation has FX-conversion limitations.
- Market/fundamentals/news freshness and coverage depend on provider constraints. Yahoo public market data may be unavailable, delayed, stale, partial, or rate-limited and is not broker-grade or guaranteed institutional market data.
- API/admin mode is token-authenticated internal tooling, not public SaaS-grade multi-user RBAC.
- Security posture is application-level/self-managed and not enterprise compliance certification.

## Future / planned / out of scope

The following must not be implied as currently available:

- Broker integration.
- Automatic trading.
- Order execution.
- `yfinance` dependency support.
- Public SaaS multi-tenant auth/RBAC product model.
- Enterprise compliance/security certification guarantees.
- Guaranteed predictions or investment returns.
