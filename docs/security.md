# Security and privacy hardening

Finwall includes application-level hardening for local development and self-managed deployment.

## Secret setup basics
- Store secrets in environment variables, not source files.
- Never commit `.env` files.
- Never paste real portfolio data or secrets into logs, issues, PRs, or screenshots.

## Required variables for API/admin mode
- `FINWALL_API_ENABLED=true`
- `FINWALL_API_TOKEN=<strong-random-token>`
- Prefer `FINWALL_API_HOST=127.0.0.1` unless network exposure is intentional.

## Required variables for SMTP mode
- `FINWALL_EMAIL_PROVIDER=smtp`
- `FINWALL_EMAIL_FROM`, `FINWALL_EMAIL_TO`, `FINWALL_SMTP_HOST`
- Optional auth: `FINWALL_SMTP_USERNAME`, `FINWALL_SMTP_PASSWORD`

## Storage secret handling
- `FINWALL_STORAGE_BACKEND=sqlite` stores local data in `FINWALL_DATABASE_PATH`.
- `FINWALL_STORAGE_BACKEND=postgres` requires `FINWALL_DATABASE_URL`.
- Do not share database URLs publicly.

## API token guidance
Use a long random token; avoid placeholder values such as `admin`, `token`, or `changeme`.

## Run runtime checks
```bash
poetry run finwall security-check
poetry run finwall security-check --json
```

## Privacy assumptions
- Local SQLite data is sensitive financial data.
- Reports and scheduled email summaries can contain sensitive portfolio context.
- Email delivery sends report summaries through your configured provider.
- API/admin should be protected with token auth plus host/network controls.

## Scope limits
This is application-level hardening only. It does not implement enterprise compliance, encryption-at-rest, KMS, SSO, RBAC, SOC2, or broker security certification.
