# Finwall

## What Finwall is

Finwall is a **portfolio decision-support tool** for local and self-managed workflows. It helps you maintain portfolio state and generate deterministic reports using CLI, optional scheduled automation, and a minimal API/admin mode.

## Safety disclaimer

Finwall is **not** financial advice.

- It does **not** execute trades.
- It does **not** connect to a broker.
- It does **not** guarantee outcomes.
- Reports, recommendations, narratives, technicals, fundamentals, and news summaries are decision-support inputs only.
- Final decisions remain with you.

See [docs/safety-limits.md](docs/safety-limits.md) for full limitations.

## Current capabilities

- Python 3.13 + Poetry project with CLI entrypoint `finwall`.
- Local portfolio maintenance (cash, holdings, orders, watchlist, goals, timeline, risk).
- Snapshot, risk assessment, order evaluation, recommendations, and full decision-support report generation.
- Technical analysis, market condition, fundamentals, fundamentals summary, news, and news summary commands.
- Scheduled report runs with duplicate suppression and run history.
- Optional SMTP email notifications for scheduled runs.
- Optional FastAPI API plus minimal server-rendered admin interface with token auth.
- Runtime security check command and security-focused configuration patterns.

## Explicit non-goals

- Broker integration.
- Automatic trading or order execution.
- Guaranteed returns or prediction certainty.
- Public SaaS-style multi-tenant authentication/authorization model.

## Quick start

```bash
poetry install
cp .env.example .env
poetry run finwall --database finwall.db add-cash USD 1000
poetry run finwall --database finwall.db add-holding NVDA 2 100 --sector Technology
poetry run finwall --database finwall.db set-risk moderate --notes "Example only"
poetry run finwall --database finwall.db snapshot --price NVDA=120
poetry run finwall --database finwall.db report --price NVDA=120
```

Use fake/test data while learning.

## Common workflows

- Portfolio setup and daily CLI flows: [docs/local-setup.md](docs/local-setup.md)
- Expanded command examples: [docs/cli-workflows.md](docs/cli-workflows.md)
- Environment variable reference: [docs/configuration.md](docs/configuration.md)

## Scheduled automation

- App-level scheduling command: `run-scheduled-report`
- Deployment guidance: [docs/deployment/scheduled-reports.md](docs/deployment/scheduled-reports.md)
- GitHub Actions workflow details: [docs/deployment/github-actions-scheduled-report.md](docs/deployment/github-actions-scheduled-report.md)

## API/admin mode

Finwall includes a minimal internal API/admin mode (token-based, self-managed, not a public dashboard).

See [docs/api-admin.md](docs/api-admin.md).

## Documentation map

- Local setup: `docs/local-setup.md`
- CLI workflows: `docs/cli-workflows.md`
- Configuration: `docs/configuration.md`
- Scheduled reports: `docs/deployment/scheduled-reports.md`
- GitHub Actions scheduled report: `docs/deployment/github-actions-scheduled-report.md`
- API/admin mode: `docs/api-admin.md`
- Email notifications: `docs/email-notifications.md`
- Security and privacy: `docs/security.md`
- Safety limits: `docs/safety-limits.md`
- Deployment ADR: `docs/adr/0001-finwall-scheduled-report-deployment.md`
- Architecture overview: `docs/architecture/overview.md`
- Minimal admin interface details: `docs/deployment/minimal-admin-interface.md`

## Development

```bash
poetry run ruff check .
poetry run ruff format --check --line-length 88 .
poetry run pytest
```
