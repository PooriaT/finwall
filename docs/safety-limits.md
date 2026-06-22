# Safety limits and known limitations

> Status: Safety boundaries are **supported primary** product constraints and apply across CLI, scheduled runs, API/frontend, and optional narrative features.

Finwall is a decision-support tool, not an execution platform.

## Plain-language boundaries

- Not financial advice.
- No guaranteed outcomes.
- No broker integration.
- No automatic trading.
- No order execution.
- Final decisions remain with the user.

## Data and analysis limitations

- Market data defaults to `yfinance` but can still be missing, delayed, stale, partial, malformed, unavailable, rate-limited, or blocked. It is not broker-grade market data.
- Technical indicators, market-condition analysis, fundamentals, and news coverage can be optional, experimental, provider-dependent, or incomplete. Live fundamentals from free providers such as `yfinance` may be stale, partial, unavailable, or malformed and are not broker-grade or institutional fundamentals.
- Deterministic checks are guardrails, not predictions.
- Deterministic recommendations remain conservative and primarily snapshot/risk driven unless a rule set explicitly consumes additional inputs; live fundamentals are not authoritative recommendation drivers by default.
- Narrative/LLM-style outputs (if enabled) are optional context and must not override deterministic evidence.

## Operational limitations

- Multi-currency cash valuation has FX-conversion limitations; full cross-currency aggregation is constrained.
- Production security and deployment hardening remain the deployer's responsibility.
- API/frontend mode is internal self-managed tooling and should not be exposed as a public service without additional controls.

For security and secret-handling practices, see [docs/security.md](security.md).


## Explicitly out of scope

- Broker integration.
- Automatic trading.
- Order execution.
- Public SaaS multi-tenant authentication/authorization.
- Enterprise compliance/security certification guarantees.
- Guaranteed predictions or returns.
