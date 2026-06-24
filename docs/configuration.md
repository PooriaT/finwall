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

| Variable | Description | Default | Required? | Used by | Example |
| --- | --- | --- | --- | --- | --- |
| `FINWALL_MARKET_DATA_PROVIDER` | Market quote provider override/debug selector. Supported values: `yfinance`, `yahoo`, `static`. Unknown values use safe static provider behavior. | `yfinance` | No | Optional | `yfinance` |
| `FINWALL_MARKET_DATA_TIMEOUT_SECONDS` | Per-request timeout for live market-data providers. Invalid, empty, or non-positive values fall back to 5 seconds. | `5.0` | No | Optional | `3` |

Finwall defaults to `yfinance` for live market prices, with a direct Yahoo public-endpoint fallback for the default market-data provider. Normal users do not need to set `FINWALL_MARKET_DATA_PROVIDER`; use it only to debug or force `yfinance`, `yahoo`, or explicit `static` behavior. See the [live-data provider reference](live-data-providers.md) for the provider matrix, fallback behavior, status meanings, caveats, and static/manual override guidance.

Diagnostics:

```bash
poetry run finwall market-data-check --ticker AAPL --historical-days 30
poetry run finwall market-data-check --json
FINWALL_MARKET_DATA_PROVIDER=yahoo poetry run finwall market-data-check --json
FINWALL_MARKET_DATA_PROVIDER=static poetry run finwall --database finwall.db snapshot --price NVDA=120
```

Run `market-data-check` to diagnose default live-provider availability, provider overrides, or local connectivity. It reports provider selection, effective provider, timeout, yfinance availability where practical, a sample latest quote check, a sample historical-price check, and fallback/live-data status where available. Diagnostic examples are network-dependent and should not be required to pass in CI.

## Fundamentals

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_FUNDAMENTAL_DATA_PROVIDER` | Fundamentals provider selector. Supported values: `yfinance`, `static`. Unknown values use safe static provider behavior. | `yfinance` | No | Optional | `yfinance` |
| `FINWALL_FUNDAMENTAL_DATA_TIMEOUT_SECONDS` | Fundamentals timeout. | `5` | No | Optional | `5` |

Finwall defaults to a small `yfinance` fundamentals provider. Normal users do not need to set this variable; use `static` for fixtures or unavailable static behavior. See the [live-data provider reference](live-data-providers.md) for supported fields, limitations, and status guidance.

Fundamentals are not authoritative recommendation drivers unless explicitly integrated into deterministic rules elsewhere. The static fundamentals provider remains available for tests, demos, and explicit manual overrides. Neither provider supplies financial advice, paid-provider coverage, broker-grade guarantees, full financial statement modeling, broker integration, caching, or automatic trading.

## News

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_NEWS_PROVIDER` | News provider selector. Supported values: `yfinance`, `static`. Unknown values use safe static fallback behavior. | `yfinance` | No | Optional | `yfinance` |
| `FINWALL_NEWS_TIMEOUT_SECONDS` | News provider timeout. | `5` | No | Optional | `5` |
| `FINWALL_NEWS_MAX_ARTICLES_PER_TOPIC` | Max news items per topic. | `5` | No | Optional | `5` |
| `FINWALL_NEWS_MAX_AGE_HOURS` | Max age filter for news freshness window. | `72` | No | Optional | `72` |

Finwall defaults to live `yfinance` ticker/company news when provider data is available. Normal users do not need to set this variable; use `static` for fixtures or unavailable static behavior. See the [live-data provider reference](live-data-providers.md) for the news provider contract, caveats, and static/manual guidance.

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

## API / frontend

| Variable | Purpose | Default | Required (local-only) | Required (scheduled/email/API) | Example |
|---|---|---|---|---|---|
| `FINWALL_API_ENABLED` | Enables API server mode in CLI launch path. | `false` | No | Required if you intentionally run API mode. | `true` |
| `FINWALL_API_TOKEN` | Bearer token and browser session login secret. | empty | No | Required for API/frontend mode. | `change-me-long-random-token` |
| `FINWALL_API_HOST` | API bind host. | `127.0.0.1` | No | Recommended to keep loopback unless protected network exposure is deliberate. | `127.0.0.1` |
| `FINWALL_API_PORT` | API bind port. | `8000` | No | Optional | `8000` |

See also: [docs/api-admin.md](api-admin.md)


## Live-data status contract

Finwall exposes a shared `live_data_status` contract for frontend, API, CLI diagnostics, and report payloads. Status values are:

- `live`: the evaluated data source returned the requested data for that surface.
- `partial`: some requested items were available and some were missing.
- `unavailable`: the evaluated source could not provide usable data.
- `static`: the configured source is static/sample/manual fallback data rather than a live provider.
- `manual`: user-supplied values were used instead of provider fetches.
- `unknown`: only configuration is known or the domain has not been evaluated.

Provider status is decision-support metadata only. It is not a guarantee that data is real-time, complete, broker-grade, or suitable for trading automation. The contract does not add caching, new providers, broker integration, or automatic trading.
