# Safety limits and known limitations

Finwall is a decision-support tool, not an execution platform.

## Plain-language boundaries

- Not financial advice.
- No guaranteed outcomes.
- No broker integration.
- No automatic trading.
- No order execution.
- Final decisions remain with the user.

## Data and analysis limitations

- Market data can be missing, delayed, stale, or unavailable.
- Fundamentals and news coverage can be incomplete.
- Deterministic checks are guardrails, not predictions.
- Narrative/LLM-style outputs (if enabled) are optional context and must not override deterministic evidence.

## Operational limitations

- Multi-currency cash valuation has FX-conversion limitations; full cross-currency aggregation is constrained.
- Production security and deployment hardening remain the deployer's responsibility.
- API/admin mode is minimal internal tooling and should not be exposed as a public service without additional controls.

For security and secret-handling practices, see [docs/security.md](security.md).
