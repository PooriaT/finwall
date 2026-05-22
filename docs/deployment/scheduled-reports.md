# Scheduled reports

> Status: **Supported secondary**. Scheduled reports are implemented for self-managed automation, but they are not the primary local workflow.

This guide explains Finwall's app-level scheduled command and deployment-oriented usage.

## App-level command

The core command is:

```bash
poetry run finwall --database finwall.db run-scheduled-report --run-context morning --json
```

Contexts:

- `morning`
- `after_close`
- `manual` (default)

Useful options:

- `--run-date YYYY-MM-DD`
- `--force`
- `--save-run`
- `--compare`
- `--email`
- `--email-on-failure`
- `--email-to`

## Behavior guarantees in app logic

`run-scheduled-report` includes app-managed behavior independent of external cron:

- US market-calendar guard.
- Non-trading-day skip behavior.
- Duplicate suppression for scheduled contexts.
- Scheduled-run logging and history for review.

Use history command:

```bash
poetry run finwall --database finwall.db scheduled-runs --limit 20 --json
```

## GitHub Actions option

Repository workflow: `.github/workflows/scheduled-report.yml`

- Runs weekday schedules for `morning` and `after_close` contexts.
- Supports manual `workflow_dispatch` testing.
- Uses app command behavior for market calendar, skips, and duplicate suppression.

Detailed setup and secrets are documented in:

- [docs/deployment/github-actions-scheduled-report.md](github-actions-scheduled-report.md)

## Manual dispatch testing checklist

1. Trigger workflow with `run_context=morning`.
2. Optionally set `run_date` for deterministic replay.
3. Use `force=true` only for non-trading-day testing.
4. Confirm logs, run history, and email behavior.

## Email success/failure behavior

- `--email`: send success notification when a scheduled report is generated.
- `--email-on-failure`: send failure notification for unexpected scheduled-run failures.

See [docs/email-notifications.md](../email-notifications.md).

## Persistence caveat for cloud runs

- Local SQLite (`FINWALL_DATABASE_PATH`) works for smoke tests.
- GitHub-hosted runners are ephemeral.
- Durable scheduled-run history/comparison in cloud automation requires durable backend configuration (for example `FINWALL_STORAGE_BACKEND` + `FINWALL_DATABASE_URL`).

## Deployment conservatism

- Treat production scheduling/storage as self-managed deployment work.
- For architecture background, see ADR: [docs/adr/0001-finwall-scheduled-report-deployment.md](../adr/0001-finwall-scheduled-report-deployment.md).
