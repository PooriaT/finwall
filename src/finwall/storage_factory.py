from pathlib import Path

from finwall.postgres_storage import PostgresPortfolioStore
from finwall.storage import SQLitePortfolioStore
from finwall.storage_interface import PortfolioStore


def resolve_sqlite_database_path(
    database_path: str, database_url: str | None, cli_database_override: bool
) -> str:
    if cli_database_override:
        return database_path
    if database_url and database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    return database_path


def build_portfolio_store(
    *,
    backend: str,
    database_path: str,
    database_url: str | None,
    cli_database_override: bool = False,
) -> PortfolioStore:
    normalized = backend.strip().lower()
    if normalized == "sqlite":
        resolved_path = resolve_sqlite_database_path(
            database_path, database_url, cli_database_override
        )
        return SQLitePortfolioStore(Path(resolved_path))
    if normalized == "postgres":
        if not database_url:
            raise ValueError(
                "Postgres storage backend requires FINWALL_DATABASE_URL to be set."
            )
        if not (
            database_url.startswith("postgresql://")
            or database_url.startswith("postgresql+psycopg://")
        ):
            raise ValueError(
                "Postgres storage backend requires a PostgreSQL URL in FINWALL_DATABASE_URL."
            )
        return PostgresPortfolioStore(database_url)
    raise ValueError(
        "Unsupported storage backend. Allowed values are 'sqlite' and 'postgres'."
    )
