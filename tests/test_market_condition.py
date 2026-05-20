from datetime import date, timedelta
from decimal import Decimal

from finwall.cli import run
from finwall.market_condition import MarketConditionStatus, classify_market_condition
from finwall.market_data import HistoricalPriceBar, StaticMarketDataProvider
from finwall.models import Holding, Portfolio
from finwall.recommendations import build_recommendation_report
from finwall.reports import build_decision_support_report
from finwall.risk import assess_portfolio_risk
from finwall.snapshot import generate_snapshot


def _bars(
    start: Decimal, step: Decimal, days: int, symbol: str
) -> tuple[HistoricalPriceBar, ...]:
    begin = date(2025, 1, 1)
    out = []
    for i in range(days):
        out.append(
            HistoricalPriceBar(
                symbol,
                (begin + timedelta(days=i)).isoformat(),
                start + (step * i),
                1000,
                "static",
            )
        )
    return tuple(out)


def test_favorable_trend() -> None:
    provider = StaticMarketDataProvider(
        historical_prices={"^GSPC": _bars(Decimal("100"), Decimal("1"), 250, "^GSPC")}
    )
    report = classify_market_condition(provider)
    assert report.status == MarketConditionStatus.FAVORABLE


def test_risky_trend() -> None:
    provider = StaticMarketDataProvider(
        historical_prices={"^GSPC": _bars(Decimal("300"), Decimal("-1"), 250, "^GSPC")}
    )
    report = classify_market_condition(provider)
    assert report.status == MarketConditionStatus.RISKY


def test_neutral_mixed_trend() -> None:
    provider = StaticMarketDataProvider(
        historical_prices={
            "^GSPC": _bars(Decimal("100"), Decimal("1"), 250, "^GSPC"),
            "^IXIC": _bars(Decimal("300"), Decimal("-1"), 250, "^IXIC"),
        }
    )
    report = classify_market_condition(provider, include_nasdaq=True)
    assert report.status == MarketConditionStatus.NEUTRAL


def test_missing_data_insufficient() -> None:
    provider = StaticMarketDataProvider(historical_prices={})
    report = classify_market_condition(provider)
    assert report.status == MarketConditionStatus.INSUFFICIENT_DATA


def test_short_history_insufficient() -> None:
    provider = StaticMarketDataProvider(
        historical_prices={"^GSPC": _bars(Decimal("100"), Decimal("1"), 40, "^GSPC")}
    )
    report = classify_market_condition(provider)
    assert report.status == MarketConditionStatus.INSUFFICIENT_DATA


def test_nasdaq_confirmation_blocks_favorable() -> None:
    provider = StaticMarketDataProvider(
        historical_prices={
            "^GSPC": _bars(Decimal("100"), Decimal("1"), 250, "^GSPC"),
            "^IXIC": _bars(Decimal("300"), Decimal("-1"), 250, "^IXIC"),
        }
    )
    report = classify_market_condition(provider, include_nasdaq=True)
    assert report.status != MarketConditionStatus.FAVORABLE


def test_volatility_warning() -> None:
    bars = []
    day = date(2025, 1, 1)
    price = Decimal("100")
    for i in range(250):
        if i > 230:
            price = price * (Decimal("1.08") if i % 2 == 0 else Decimal("0.92"))
        bars.append(
            HistoricalPriceBar(
                "^GSPC", (day + timedelta(days=i)).isoformat(), price, 1000, "static"
            )
        )
    report = classify_market_condition(
        StaticMarketDataProvider(historical_prices={"^GSPC": tuple(bars)})
    )
    assert any("volatility proxy elevated" in w for w in report.warnings)


def test_report_json_serializes() -> None:
    report = classify_market_condition(
        StaticMarketDataProvider(
            historical_prices={
                "^GSPC": _bars(Decimal("100"), Decimal("1"), 250, "^GSPC")
            }
        )
    )
    assert '"status": "favorable"' in report.to_json()


def test_cli_market_condition_outputs(tmp_path, monkeypatch, capsys) -> None:
    db = tmp_path / "f.db"
    provider = StaticMarketDataProvider(
        historical_prices={"^GSPC": _bars(Decimal("100"), Decimal("1"), 250, "^GSPC")}
    )
    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)
    run(["--database", str(db), "market-condition"])
    assert "Status:" in capsys.readouterr().out


def test_cli_market_condition_json(tmp_path, monkeypatch, capsys) -> None:
    db = tmp_path / "f.db"
    provider = StaticMarketDataProvider(
        historical_prices={"^GSPC": _bars(Decimal("100"), Decimal("1"), 250, "^GSPC")}
    )
    monkeypatch.setattr("finwall.cli.build_market_data_provider", lambda *_: provider)
    run(["--database", str(db), "market-condition", "--json"])
    assert '"status": "favorable"' in capsys.readouterr().out


def test_report_uses_market_condition_when_provided() -> None:
    portfolio = Portfolio(
        name="P", holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),)
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("100")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    rec = build_recommendation_report(portfolio, snapshot, risk)
    mc = classify_market_condition(
        StaticMarketDataProvider(
            historical_prices={
                "^GSPC": _bars(Decimal("100"), Decimal("1"), 250, "^GSPC")
            }
        )
    )
    report = build_decision_support_report(
        portfolio, snapshot, risk, rec, market_condition_report=mc
    )
    assert report.market_condition.status == "favorable"
