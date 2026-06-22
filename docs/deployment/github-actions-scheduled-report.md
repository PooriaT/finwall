# GitHub Actions scheduled report automation

> Status: **Supported secondary** self-managed automation. This workflow is not a managed SaaS scheduler and still depends on your storage/security/deployment posture.

This repository provides a GitHub Actions workflow at `.github/workflows/scheduled-report.yml` that runs Finwall's existing `run-scheduled-report` CLI command twice on weekdays and also supports manual triggering for deterministic testing/backfill.

## What this workflow does

- Runs on a weekday morning schedule and a weekday after-close schedule.
- Supports `workflow_dispatch` inputs for `run_context`, optional `run_date`, and optional toggle flags.
- Calls the existing CLI command only:
  - `poetry run finwall --database "$FINWALL_DATABASE_PATH" run-scheduled-report ...`
- Passes automation-focused flags (`--json`, `--save-run`, `--compare`, `--email`, `--email-on-failure`) by default for scheduled runs.
- Keeps market-day and holiday skip behavior in app logic, not workflow logic.

## Why market-calendar guard still matters

The cron schedule controls *when* automation attempts to run. The app's internal US market-calendar guard controls *whether* the run should generate a report on that date/context.

That means:
- Weekends and supported market holidays are skipped by app logic.
- Skipped non-trading-day runs still complete successfully.
- `--force` can be used for manual deterministic testing/backfill.

## Schedule and run contexts

The workflow uses UTC cron expressions for compatibility:

- `30 14 * * 1-5` → `morning` context (roughly 10:30 ET during standard market hours).
- `15 20 * * 1-5` → `after_close` context (roughly 4:15 ET during standard market hours).

> Note: This workflow intentionally uses UTC cron expressions instead of a `timezone` key for broad GitHub Actions compatibility.

## Manual test runs (`workflow_dispatch`)

From the GitHub Actions UI, select **Scheduled Report** and click **Run workflow**.

Inputs:
- `run_context` (`morning` or `after_close`) — required.
- `run_date` (`YYYY-MM-DD`) — optional.
- `force` — optional boolean.
- `save_run` — optional boolean (default `true`).
- `compare` — optional boolean (default `true`).
- `email` — optional boolean (default `true`).
- `email_on_failure` — optional boolean (default `true`).

## Required secrets (production use)

Configure these GitHub repository secrets before relying on automation:

- `FINWALL_STORAGE_BACKEND`
- `FINWALL_DATABASE_URL`
- `FINWALL_EMAIL_PROVIDER`
- `FINWALL_EMAIL_FROM`
- `FINWALL_EMAIL_TO`
- `FINWALL_SMTP_HOST`
- `FINWALL_SMTP_PORT`
- `FINWALL_SMTP_USERNAME`
- `FINWALL_SMTP_PASSWORD`
- `FINWALL_SMTP_USE_STARTTLS`

The workflow also sets `FINWALL_ENV=production`.

## Optional provider/config secrets

Optional runtime settings can also be configured as secrets:

- `FINWALL_MARKET_DATA_PROVIDER`
- `FINWALL_MARKET_DATA_TIMEOUT_SECONDS`
- `FINWALL_FUNDAMENTAL_DATA_PROVIDER`
- `FINWALL_FUNDAMENTAL_DATA_TIMEOUT_SECONDS`
- `FINWALL_NEWS_PROVIDER`
- `FINWALL_NEWS_TIMEOUT_SECONDS`
- `FINWALL_NEWS_MAX_ARTICLES_PER_TOPIC`
- `FINWALL_NEWS_MAX_AGE_HOURS`
- `FINWALL_NARRATIVE_PROVIDER`
- `FINWALL_NARRATIVE_MAX_WORDS`
- `FINWALL_NARRATIVE_STYLE`

`FINWALL_MARKET_DATA_PROVIDER` is not required for normal live-price scheduled reports because Finwall defaults to `yfinance`. Set it only when deliberately overriding to `yahoo` or explicit `static` behavior.

## Email behavior

- `--email` triggers success notifications for generated scheduled reports.
- `--email-on-failure` triggers failure notifications when report generation fails unexpectedly.
- Workflow logs should not print secret values; secrets are injected via environment variables.
- Workflow failures still surface as non-zero job status when app execution fails unexpectedly.

## Save/compare behavior and persistence caveat

Scheduled and default manual runs pass `--save-run` and `--compare`.

Important caveat:
- GitHub-hosted runner filesystems are ephemeral.
- Local SQLite (`FINWALL_DATABASE_PATH=finwall.db`) is only a fallback for smoke tests/manual validation.
- Durable report history/comparison requires production storage through:
  - `FINWALL_STORAGE_BACKEND`
  - `FINWALL_DATABASE_URL`

If durable storage is not configured, runs may still execute, but report history and cross-run comparisons are not durable across workflow runs.

## Relationship to ADR 0001

`docs/adr/0001-finwall-scheduled-report-deployment.md` still recommends **Render Cron Jobs + external managed database** as the preferred production deployment path.

This workflow is a repo-owned scheduled automation option for issue-sized delivery and manual testing. It does not block adding Render Cron configuration later.

## First-run verification checklist

Before relying on automation:

1. Configure required secrets.
2. Run a manual workflow dispatch with:
   - `run_context=morning`
   - `run_date` set to a known trading day
   - `force=true` only if testing on a non-trading day
3. Confirm command completion and JSON output in logs.
4. Confirm success/failure email behavior (if configured).
5. Confirm durable persistence by verifying data in configured production storage backend.

## Disabling the workflow safely

Options:

- Disable the workflow from the GitHub Actions UI.
- Remove or comment out `on.schedule` entries to keep manual-only execution.
- Remove/rotate secrets if automation must be stopped quickly.

Disabling schedule entries is preferred over changing app logic.
