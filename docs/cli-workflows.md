# CLI workflows

This guide focuses on common command patterns. For full options, run `poetry run finwall <command> --help`.

## Portfolio maintenance

### Cash and holdings

```bash
poetry run finwall --database finwall.db add-cash USD 2000
poetry run finwall --database finwall.db withdraw-cash USD 200
poetry run finwall --database finwall.db add-holding AAPL 3 180 --sector Technology
```

### Record buys/sells

```bash
poetry run finwall --database finwall.db record-buy AAPL 1 182 --currency USD --date 2026-05-20
poetry run finwall --database finwall.db record-sell AAPL 1 190 --currency USD --date 2026-05-21
```

### Orders and watchlist

```bash
poetry run finwall --database finwall.db add-order NVDA buy limit 2 --limit-price 118
poetry run finwall --database finwall.db update-order NVDA buy stop_limit 2 --limit-price 118 --stop-price 120
poetry run finwall --database finwall.db remove-order NVDA
poetry run finwall --database finwall.db add-watchlist MSFT --note "Earnings follow-up"
poetry run finwall --database finwall.db remove-watchlist MSFT
```

### Goal, timeline, risk

```bash
poetry run finwall --database finwall.db set-goal "Home down payment" --target-amount 80000
poetry run finwall --database finwall.db set-timeline 2026-01-01 --target-date 2030-01-01
poetry run finwall --database finwall.db set-risk moderate --notes "Example profile"
```

## Analysis and reporting

```bash
poetry run finwall --database finwall.db snapshot --price NVDA=120
poetry run finwall --database finwall.db snapshot --live-prices --risk --json
poetry run finwall --database finwall.db evaluate-order NVDA buy limit --entry-price 120 --limit-price 118 --shares 2 --price NVDA=120
poetry run finwall --database finwall.db recommendations --live-prices --json
poetry run finwall --database finwall.db report --live-prices --market-index SP500 --compare --save-run
```

Additional command examples:

```bash
poetry run finwall --database finwall.db technicals --holdings-only
poetry run finwall --database finwall.db market-condition --primary-index SP500 --include-nasdaq
poetry run finwall --database finwall.db fundamentals-summary --json
poetry run finwall --database finwall.db news-summary --include-market --include-sectors
poetry run finwall --database finwall.db security-check --json
poetry run finwall --database finwall.db market-data-diagnostics --ticker NVDA --index SP500 --json
```

## Persistence and run history

```bash
poetry run finwall --database finwall.db report --save-run --compare
poetry run finwall --database finwall.db run-scheduled-report --run-context morning --save-run --compare
poetry run finwall --database finwall.db scheduled-runs --limit 10 --json
```

If API/admin mode is enabled, audit events are available via API (`/api/v1/portfolio/audit`) and admin UI (`/admin/audit`).
