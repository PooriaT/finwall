from pathlib import Path

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
        raise ValueError(
            "Postgres storage backend is not implemented yet. Use sqlite for now."
        )
    raise ValueError(
        "Unsupported storage backend. Allowed values are 'sqlite' and 'postgres'."
    )
