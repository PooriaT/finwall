from decimal import Decimal

from finwall.market_data import (
    IndexQuote,
    MarketPrice,
    StaticMarketDataProvider,
    fetch_portfolio_latest_prices,
)
from finwall.models import Holding, Portfolio


def test_static_provider_returns_configured_prices_and_index_quote() -> None:
    provider = StaticMarketDataProvider(
        prices={"NVDA": MarketPrice("NVDA", Decimal("950.10"), "USD", "static", True)},
        index_quotes={"SP500": IndexQuote("SP500", Decimal("5000.00"), "static", True)},
    )

    prices = provider.get_latest_prices(["NVDA", "AAPL"])
    assert prices["NVDA"].available is True
    assert prices["NVDA"].price == Decimal("950.10")
    assert prices["AAPL"].available is False

    quote = provider.get_index_quote("SP500")
    assert quote.available is True
    assert quote.price == Decimal("5000.00")


def test_fetch_portfolio_latest_prices_skips_missing_and_collects_warnings() -> None:
    portfolio = Portfolio(
        name="Primary",
        holdings=(
            Holding("NVDA", Decimal("2"), Decimal("800")),
            Holding("PLTR", Decimal("3"), Decimal("20")),
        ),
    )
    provider = StaticMarketDataProvider(
        prices={
            "NVDA": MarketPrice("NVDA", Decimal("900"), "USD", "static", True),
            "PLTR": MarketPrice("PLTR", None, "USD", "static", False, "missing"),
        }
    )

    latest_prices, warnings = fetch_portfolio_latest_prices(portfolio, provider)

    assert latest_prices == {"NVDA": Decimal("900")}
    assert warnings == ["PLTR: missing"]
