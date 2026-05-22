# Finwall

## What Finwall is

Finwall is a **local/self-managed portfolio decision-support workflow**.

Its core path is to maintain portfolio state, generate deterministic analysis, and help you review risk and recommendation context before making your own decisions outside the tool.

## Safety and non-goals

Finwall is **not** financial advice.

- It does **not** connect to brokers.
- It does **not** execute orders.
- It does **not** perform automatic trading.
- It does **not** guarantee outcomes.
- Final decisions remain with you.

Finwall provides decision-support inputs (including deterministic analysis and optional narratives), not execution or guaranteed predictions.

See [docs/safety-limits.md](docs/safety-limits.md) for full limitations.

## Who Finwall is for

Finwall is for people who want to:

- Keep portfolio state local or self-managed.
- Generate deterministic decision-support reports.
- Review transparent risk signals and recommendation reasoning.
- Operate without broker execution or automatic trading.
- Avoid opaque AI-first advice engines as the primary decision source.

## Product modes at a glance

See [docs/product-modes.md](docs/product-modes.md) for the canonical capability-maturity reference.

| Mode | Maturity | Typical user action |
| --- | --- | --- |
| CLI portfolio maintenance | Supported primary | Update cash, holdings, trades/orders, watchlist, goals, and risk profile |
| Deterministic reports | Supported primary | Generate snapshot/risk/recommendation/report outputs |
| Scheduled reports | Supported secondary | Run reports on a schedule with app-level guardrails |
| Email notifications | Supported secondary | Receive scheduled-run success/failure summaries |
| API/admin mode | Internal/admin | Update portfolio state through authenticated internal endpoints/forms |
| Narrative provider | Experimental / optional explanation | Rewrite deterministic evidence into plain-language explanation |

## Primary workflow

1. Maintain local portfolio state (cash, holdings, orders, watchlist, goals, risk profile).
2. Generate deterministic reports.
3. Review risk warnings, recommendation status, and supporting inputs.
4. Make independent decisions outside Finwall.
5. Optionally add narrative explanation and scheduled automation.

Example (fake/test data):

```bash
poetry run finwall --database finwall.db add-cash USD 1000
poetry run finwall --database finwall.db add-holding NVDA 2 100 --sector Technology
poetry run finwall --database finwall.db set-risk moderate --notes "Example only"
poetry run finwall --database finwall.db report --price NVDA=120
```

## Quick start

```bash
poetry install
cp .env.example .env
poetry run finwall --database finwall.db add-cash USD 1000
poetry run finwall --database finwall.db add-holding NVDA 2 100 --sector Technology
poetry run finwall --database finwall.db report --price NVDA=120
```

For fuller local setup and command walkthroughs, see [docs/local-setup.md](docs/local-setup.md) and [docs/cli-workflows.md](docs/cli-workflows.md).

## Common workflows

### Portfolio maintenance

Use CLI commands to maintain:

- cash balances
- holdings and sector metadata
- orders and watchlist entries
- goals and timeline inputs
- risk profile and related notes

See: [docs/local-setup.md](docs/local-setup.md), [docs/cli-workflows.md](docs/cli-workflows.md).

### Deterministic analysis and reports

> Status: **Supported primary** for snapshots/risk/recommendations/report structure. Technical/fundamental/news/market-condition outputs are **experimental/optional decision-support inputs** and may be incomplete or provider-limited.


Use deterministic commands for snapshots and decision-support analysis, including:

- snapshots and full reports
- risk assessment
- order evaluation
- recommendation status with supporting context

See: [docs/cli-workflows.md](docs/cli-workflows.md).

### Optional explanation

> Status: **Experimental / optional explanation**. Narrative output is downstream from deterministic evidence and cannot override deterministic report fields.


Narrative output is optional and downstream from deterministic evidence.

- Deterministic report fields remain authoritative.
- Invalid or unsafe narrative output falls back to a safe deterministic warning.
- Narrative output is not financial advice.

For configuration details, see [docs/configuration.md](docs/configuration.md).

## Optional automation and notifications

> Status: **Supported secondary**. Implemented for self-managed automation, but not the primary local usage path.


Automation is an optional layer, not the default usage path.

- Scheduled reports: [docs/deployment/scheduled-reports.md](docs/deployment/scheduled-reports.md)
- GitHub Actions scheduled runs: [docs/deployment/github-actions-scheduled-report.md](docs/deployment/github-actions-scheduled-report.md)
- SMTP email notifications: [docs/email-notifications.md](docs/email-notifications.md)

## Optional API/admin maintenance surface

> Status: **Internal/admin**. Self-managed maintenance tooling only; not a public SaaS dashboard.


API/admin mode is a minimal, token-authenticated, internal/self-managed maintenance surface.

- Not a public SaaS dashboard.
- Not a broker interface.
- Intended for controlled internal use.

See [docs/api-admin.md](docs/api-admin.md) and [docs/deployment/minimal-admin-interface.md](docs/deployment/minimal-admin-interface.md).

## Documentation map

### Getting started

- Local setup: `docs/local-setup.md`
- Configuration: `docs/configuration.md`

### Usage workflows

- CLI workflows: `docs/cli-workflows.md`

### Automation and deployment

- Scheduled reports: `docs/deployment/scheduled-reports.md`
- GitHub Actions scheduled report: `docs/deployment/github-actions-scheduled-report.md`
- Email notifications: `docs/email-notifications.md`
- Deployment ADR: `docs/adr/0001-finwall-scheduled-report-deployment.md`

### API/admin

- API/admin mode: `docs/api-admin.md`
- Minimal admin interface details: `docs/deployment/minimal-admin-interface.md`

### Safety, security, architecture

- Safety limits: `docs/safety-limits.md`
- Security and privacy: `docs/security.md`
- Architecture overview: `docs/architecture/overview.md`

## Development

```bash
poetry run ruff check .
poetry run ruff format --check --line-length 88 .
poetry run pytest
```
