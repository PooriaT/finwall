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
- Technical indicators, market-condition analysis, fundamentals, and news coverage can be optional, experimental, provider-dependent, or incomplete. Live fundamentals and live ticker news from free providers such as `yfinance` may be stale, partial, unavailable, malformed, rate-limited, blocked, or provider-dependent and are not broker-grade or institutional data.
- Deterministic checks are guardrails, not predictions.
- Deterministic recommendations remain conservative and primarily snapshot/risk driven unless a rule set explicitly consumes additional inputs; live fundamentals and news are not authoritative recommendation drivers by default.
- News source quality and recency labels are heuristic classifications. News is not sentiment analysis, full article ingestion, paid API coverage, caching, broker integration, or automated trading.
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


## Live-data status contract

Finwall exposes a shared `live_data_status` contract for frontend, API, CLI diagnostics, and report payloads. Status values are:

- `live`: the evaluated data source returned the requested data for that surface.
- `partial`: some requested items were available and some were missing.
- `unavailable`: the evaluated source could not provide usable data.
- `static`: the configured source is static/sample/manual fallback data rather than a live provider.
- `manual`: user-supplied values were used instead of provider fetches.
- `unknown`: only configuration is known or the domain has not been evaluated.

Provider status is decision-support metadata only. It is not a guarantee that data is real-time, complete, broker-grade, or suitable for trading automation. The contract does not add caching, new providers, broker integration, or automatic trading.
