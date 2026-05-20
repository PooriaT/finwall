# ADR 0001: Scheduled Report Deployment and Production Storage

## Status

Accepted

## Context

Finwall is a local-first decision-support tool, and local SQLite remains useful for single-user development and manual CLI operation. Finwall now also supports non-interactive scheduled execution (`run-scheduled-report`) and application-level email notifications for scheduled report success/failure.

The next architecture decision is where automated scheduled jobs should run in production and where persistent state should live. Cloud scheduled runs need stable persistence for portfolio state, report history, recommendation status history, scheduled run status, and notification outcomes, along with secure runtime configuration for provider and email settings.

Relevant platform constraints:

- GitHub Actions scheduled workflows use `on.schedule` cron syntax and run on the latest commit on the default branch. GitHub documents UTC by default and supports timezone-aware scheduling with an IANA timezone string; shortest schedule interval is every 5 minutes.
- Render Cron Jobs are purpose-built periodic tasks with cron expressions and UTC day/time ranges.
- Render Cron Jobs can use environment variables/environment groups.
- Render Cron Jobs cannot access persistent disks.
- Render guarantees at most one active run per cron job at a time (overlaps are delayed or canceled based on trigger mode).
- Render persistent disks are for paid web/private/background services; filesystem changes are otherwise ephemeral, and Render recommends managed Postgres/Key Value when suitable.

References:

- GitHub Actions workflow syntax (`on.schedule`): https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule
- Render Cron Jobs: https://render.com/docs/cronjobs
- Render Persistent Disks: https://render.com/docs/disks

## Decision

For the MVP production deployment path:

1. Use **Render Cron Jobs** as the preferred scheduler for deployed scheduled report runs.
2. Use an **external managed database** as the production source of truth.
3. Keep **local SQLite** as the default for local development and manual CLI usage.
4. Use Finwall’s existing report command and email notification capabilities for product-level success/failure emails.
5. Do **not** use local files (including a local SQLite file on ephemeral runners) as cloud scheduled source-of-truth storage.

## Options Considered

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Local-only CLI | Simple, private, lowest cost | Not automated unless the user machine is always on | Keep for development/manual use |
| GitHub Actions scheduled workflow | Low cost, easy cron setup, built-in secrets | Repo-coupled runtime; private financial state less ideal; still requires external DB for persistence | Secondary/experimental |
| Render Cron Jobs | Purpose-built scheduler; env vars/groups; single active run guarantee | No persistent disks; paid floor; still needs external DB | Preferred MVP scheduler |
| Render background worker | Better for long-running/queue workloads | Overkill for twice-per-trading-day scheduled reports | Later only |
| External scheduler + managed DB | Flexible and portable | More moving parts and ops overhead | Later if Render/GitHub is insufficient |

### Option 1: Local-only CLI

Best for development, validation, and manual operation; not sufficient as a production automation path.

### Option 2: GitHub Actions scheduled workflow

Useful for low-cost proofs of concept and manual experimentation; not the preferred MVP when operational separation and persistent application state matter.

### Option 3: Render Cron Jobs

Best fit for first production scheduler because Finwall already provides a non-interactive scheduled command and app-level notifications.

### Option 4: Render background worker

Deferred until/if Finwall needs long-running processing, queues, continuous polling, or richer orchestration.

### Option 5: External scheduler plus managed database

Viable future fallback for portability and customization if MVP scheduler choices become limiting.

## Recommended MVP Path

- Keep local SQLite for local/manual workflows.
- Treat production scheduled runs as cloud automation that must use shared managed persistence.
- Run scheduled jobs on Render Cron Jobs first.
- Keep GitHub Actions schedules as a secondary experimentation option.
- Prioritize production persistence implementation as the next issue after this ADR.

## Production Storage Decision

Local SQLite remains valid for local development and manual runs, but it is not the cloud production source of truth.

Production scheduled runs should eventually persist at least:

- portfolio state
- cash balances
- holdings
- active orders
- goals
- risk profile
- generated report metadata
- saved report JSON
- recommendation status history
- scheduled run status
- notification delivery status

This ADR does not implement database support.

## Why Local SQLite Is Not Enough for Cloud Scheduled Runs

- Cloud scheduled runners are ephemeral.
- Render Cron Jobs cannot use persistent disks.
- GitHub Actions runner filesystems are temporary per workflow run.
- A local `.db` file in cloud automation risks lost or stale state and unreliable report-history comparisons.
- Production scheduling needs stable shared storage across runs.

## Secret Management

Store secrets in platform-managed secret systems only:

- Render environment variables/environment groups for Render Cron Jobs.
- GitHub Actions secrets for GitHub Actions-based runs.
- Local `.env` only for local development.

Likely secret/config categories:

- database URL
- market-data provider settings (as needed)
- fundamentals/news provider settings (if added)
- SMTP host, port, username, password
- email sender/recipient configuration
- narrative provider settings (if narrative mode is enabled)

Rules:

- Never commit `.env`.
- Never commit database URLs.
- Never commit SMTP credentials.
- Logs and notifications must not expose secrets.

## Email Notification Strategy

Finwall should remain responsible for product-level report emails because it owns report context and run outcomes.

- Use Finwall scheduled command options/provider configuration to send success/failure notifications.
- Treat platform notifications as infrastructure-level complements, not substitutes.
- Include safe summaries by default; include full report content only when it does not expose unnecessary sensitive data.
- Failure notifications should include safe error categories/messages, not raw traces containing secrets.

## Migration Path from Local to Deployed Usage

1. Continue local SQLite for manual testing.
2. Add production database support in a future issue.
3. Add safe export/import migration from local SQLite to production database in a future issue.
4. Configure scheduled command to read/write production storage.
5. Configure email-provider secrets in deployment platform secret stores.
6. Add Render Cron Job configuration in a future issue.
7. Run manual triggered cloud jobs before relying on schedule.
8. Enable twice-per-trading-day scheduled runs.

This ADR is documentation-only and does not execute these steps.

## Operational Notes

- Keep Finwall’s market-calendar guard inside the application; do not rely only on cron weekday filters.
- Use either two schedules or one parameterized invocation by run context, depending on platform setup.
- Maintain idempotency expectations and run-history tracking.
- Prefer non-interactive commands for scheduled execution.
- Validate with manual triggers before enabling routine schedules.
- Ensure failures return non-zero exit status where appropriate.
- Keep cloud logs concise and free of sensitive data.

## Consequences

Positive outcomes:

- Clear production automation path.
- Avoids dependence on ephemeral local files.
- Preserves simple local-first development workflow.
- Separates product report notifications from platform infrastructure alerts.

Tradeoffs:

- Requires future production database implementation.
- Adds cloud operations responsibility.
- Requires strict secret hygiene.
- Render Cron Jobs have cost and no persistent-disk support.

## Out of Scope

- Implementing a GitHub Actions scheduled workflow.
- Implementing Render Cron Job setup.
- Implementing production database support.
- Implementing SQLite-to-production migrations.
- Implementing new email providers.
- Implementing authentication.
- Implementing broker integration.
- Implementing automatic trading.
- Changing investment/risk/recommendation logic.
