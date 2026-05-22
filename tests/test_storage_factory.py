import pytest

from finwall.storage import SQLitePortfolioStore
from finwall.storage_factory import build_portfolio_store, resolve_sqlite_database_path


def test_default_sqlite_store_selected() -> None:
    store = build_portfolio_store(
        backend="sqlite", database_path="finwall.db", database_url=None
    )
    assert isinstance(store, SQLitePortfolioStore)


def test_sqlite_database_url_is_used_without_cli_override() -> None:
    path = resolve_sqlite_database_path(
        "finwall.db", "sqlite:///tmp/finwall-prod.db", cli_database_override=False
    )
    assert path == "tmp/finwall-prod.db"


def test_sqlite_cli_database_override_wins_over_database_url() -> None:
    path = resolve_sqlite_database_path(
        "custom.db", "sqlite:///tmp/finwall-prod.db", cli_database_override=True
    )
    assert path == "custom.db"


def test_unknown_storage_backend_fails_safely() -> None:
    with pytest.raises(ValueError, match="Unsupported storage backend"):
        build_portfolio_store(
            backend="unknown", database_path="finwall.db", database_url=None
        )


def test_postgres_backend_requires_database_url() -> None:
    with pytest.raises(ValueError, match="not implemented yet"):
        build_portfolio_store(
            backend="postgres", database_path="finwall.db", database_url=None
        )


def test_postgres_url_not_exposed_in_errors() -> None:
    bad_url = "mysql://user:secret@example/db"
    with pytest.raises(ValueError) as exc:
        build_portfolio_store(
            backend="postgres", database_path="finwall.db", database_url=bad_url
        )
    assert bad_url not in str(exc.value)


def test_postgres_backend_not_implemented_yet() -> None:
    with pytest.raises(ValueError, match="not implemented yet"):
        build_portfolio_store(
            backend="postgres",
            database_path="finwall.db",
            database_url="postgresql://USER:PASSWORD@HOST:5432/DBNAME",
        )


def test_sqlite3_alias_selects_sqlite_store() -> None:
    store = build_portfolio_store(
        backend="sqlite3", database_path="finwall.db", database_url=None
    )
    assert isinstance(store, SQLitePortfolioStore)


def test_postgresql_alias_not_implemented_yet() -> None:
    with pytest.raises(ValueError, match="not implemented yet"):
        build_portfolio_store(
            backend="postgresql",
            database_path="finwall.db",
            database_url="postgresql://USER:PASSWORD@HOST:5432/DBNAME",
        )
