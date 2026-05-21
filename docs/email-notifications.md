# Email notifications

Finwall supports scheduled report notifications through a provider switch.

## Provider modes

- `FINWALL_EMAIL_PROVIDER=disabled` (default): no emails are sent.
- `FINWALL_EMAIL_PROVIDER=smtp`: SMTP delivery is enabled.

## Required SMTP settings

When `FINWALL_EMAIL_PROVIDER=smtp`, configure:

- `FINWALL_EMAIL_FROM`
- `FINWALL_EMAIL_TO` (comma-separated default recipients)
- `FINWALL_SMTP_HOST`
- `FINWALL_SMTP_PORT` (default `587`)
- Optional/depends on server: `FINWALL_SMTP_USERNAME`, `FINWALL_SMTP_PASSWORD`
- `FINWALL_SMTP_USE_STARTTLS` (default `true`)

## CLI flags for scheduled command

`run-scheduled-report` supports:

- `--email` for success notifications.
- `--email-on-failure` for failure notifications.
- `--email-to` to override recipients for a specific run.

Example:

```bash
poetry run finwall --database finwall.db run-scheduled-report \
  --run-context morning \
  --save-run --compare \
  --email --email-on-failure \
  --email-to owner@example.test
```

## What emails contain

- Success notifications: scheduled run context/date and report summary content from that run.
- Failure notifications: safe error summary for the failed scheduled run path.

## Safe operations

- Keep provider secrets in environment variables or secret managers.
- Do not print SMTP passwords/tokens in logs or screenshots.
- For local testing, use `FINWALL_EMAIL_PROVIDER=disabled` or a safe SMTP sandbox account.
