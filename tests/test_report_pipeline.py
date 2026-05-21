from finwall.cli import run, settings
from finwall.report_pipeline import build_deterministic_report_artifacts
from finwall.storage import SQLitePortfolioStore


def _args(**overrides):
    base = {
        "price": ["NVDA=120"],
        "live_prices": False,
        "market_index": None,
        "include_nasdaq": False,
        "market_condition_days": 30,
    }
    base.update(overrides)
    return type("Args", (), base)()


def test_pipeline_builds_deterministic_artifacts_without_narrative(tmp_path) -> None:
    database = tmp_path / "finwall.db"
    run(["--database", str(database), "add-holding", "NVDA", "1", "100"])
    store = SQLitePortfolioStore(database)
    portfolio = store.get_portfolio("Primary")
    assert portfolio is not None

    artifacts = build_deterministic_report_artifacts(
        args=_args(),
        portfolio=portfolio,
        settings=settings,
    )

    assert "portfolio_snapshot" in artifacts.payload
    assert artifacts.recommendation_report.holdings
