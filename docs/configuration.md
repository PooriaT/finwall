# Configuration reference

> Status: Configuration supports **supported primary** local SQLite workflows plus **supported secondary** automation surfaces. Some providers/backends remain optional or constrained.

Finwall reads runtime settings from environment variables. `.env.example` provides safe placeholders.

## Secret handling basics

- Do **not** commit `.env`.
- Configure secrets through your deployment platform or GitHub repository secrets.
- Never paste SMTP passwords, DB URLs, or API tokens into logs, issues, or screenshots.

## Environment

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_ENV` | Runtime environment label used by app/security behavior. | `development` | No | Recommended (`production` for deployed runs). | `production` |

## Storage

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_STORAGE_BACKEND` | Storage backend selector. Use `sqlite` today (`postgres` is not implemented at runtime). | `sqlite` | No | Keep `sqlite` for local and scheduled runs. | `sqlite` |
| `FINWALL_DATABASE_PATH` | SQLite file path. | `finwall.db` | No (used automatically) | Optional fallback only. | `finwall.db` |
| `FINWALL_DATABASE_URL` | Optional SQLite URL override when using `sqlite:///...`; do not use for Postgres today. | empty | No | Optional in SQLite mode only. | `sqlite:///finwall.db` |

> Current limitation: selecting `FINWALL_STORAGE_BACKEND=postgres` fails at runtime because Postgres storage is not implemented yet. Use SQLite for now in both local and scheduled environments.

## Market data

Market/fundamentals/news inputs are decision-support enrichments. They can be stale, partial, or unavailable depending on provider behavior and runtime conditions.


| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_MARKET_DATA_PROVIDER` | Market quote provider. | `static` | No | Optional | `static` |
| `FINWALL_MARKET_DATA_TIMEOUT_SECONDS` | Quote-provider timeout. | `5` | No | Optional | `5` |

## Fundamentals

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_FUNDAMENTAL_DATA_PROVIDER` | Fundamentals provider selector. | `static` | No | Optional | `static` |
| `FINWALL_FUNDAMENTAL_DATA_TIMEOUT_SECONDS` | Fundamentals timeout. | `5` | No | Optional | `5` |

## News

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_NEWS_PROVIDER` | News provider selector. | `static` | No | Optional | `static` |
| `FINWALL_NEWS_TIMEOUT_SECONDS` | News provider timeout. | `5` | No | Optional | `5` |
| `FINWALL_NEWS_MAX_ARTICLES_PER_TOPIC` | Max news items per topic. | `5` | No | Optional | `5` |
| `FINWALL_NEWS_MAX_AGE_HOURS` | Max age filter for news freshness window. | `72` | No | Optional | `72` |

## Narrative

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_NARRATIVE_PROVIDER` | Narrative provider selector. | `disabled` | No | Optional | `disabled` |
| `FINWALL_NARRATIVE_MAX_WORDS` | Narrative length cap. | `500` | No | Optional | `500` |
| `FINWALL_NARRATIVE_STYLE` | Narrative style label. | `plain_english` | No | Optional | `plain_english` |
| `FINWALL_OLLAMA_BASE_URL` | Local Ollama API base URL (used when provider is `ollama`). | `http://localhost:11434` | No | Optional | `http://localhost:11434` |
| `FINWALL_OLLAMA_MODEL` | Ollama model name (used when provider is `ollama`). | `gemma3:latest` | No | Optional | `gemma3:latest` |
| `FINWALL_OLLAMA_TIMEOUT_SECONDS` | Ollama request timeout (seconds). | `30` | No | Optional | `30` |

When `FINWALL_NARRATIVE_PROVIDER=ollama`, narratives are optional explainers only. They cannot
override deterministic recommendation, risk, or report outputs. Invalid/unsafe narrative output should safely fall back to deterministic messaging.

## Email / SMTP

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_EMAIL_PROVIDER` | Email mode (`disabled` or `smtp`). | `disabled` | No | Yes if using `--email` or `--email-on-failure`. | `smtp` |
| `FINWALL_EMAIL_FROM` | Sender address. | empty | No | Yes for SMTP mode. | `alerts@example.test` |
| `FINWALL_EMAIL_TO` | Default recipients (comma-separated). | empty | No | Yes for SMTP mode unless overridden by `--email-to`. | `owner@example.test,ops@example.test` |
| `FINWALL_EMAIL_TIMEOUT_SECONDS` | Email timeout. | `10` | No | Recommended in SMTP mode. | `10` |
| `FINWALL_SMTP_HOST` | SMTP host. | empty | No | Yes for SMTP mode. | `smtp.example.test` |
| `FINWALL_SMTP_PORT` | SMTP port. | `587` | No | Yes for SMTP mode. | `587` |
| `FINWALL_SMTP_USERNAME` | SMTP username. | empty | No | Optional (depends on server). | `smtp-user` |
| `FINWALL_SMTP_PASSWORD` | SMTP password/secret. | empty | No | Optional/required depending on server auth. | `use-platform-secret` |
| `FINWALL_SMTP_USE_STARTTLS` | STARTTLS toggle. | `true` | No | Recommended in SMTP mode unless server requires otherwise. | `true` |

See also: [docs/email-notifications.md](email-notifications.md)

## API / admin

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_API_ENABLED` | Enables API/admin server mode in CLI launch path. | `false` | No | Required if you intentionally run API/admin mode. | `true` |
| `FINWALL_API_TOKEN` | Bearer token and admin login secret. | empty | No | Required for API/admin mode. | `change-me-long-random-token` |
| `FINWALL_API_HOST` | API bind host. | `127.0.0.1` | No | Recommended to keep loopback unless protected network exposure is deliberate. | `127.0.0.1` |
| `FINWALL_API_PORT` | API bind port. | `8000` | No | Optional | `8000` |

See also: [docs/api-admin.md](api-admin.md)
