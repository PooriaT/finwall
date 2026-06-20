import json
import os
import subprocess
import sys
from dataclasses import asdict
from decimal import Decimal

from finwall.api import PortfolioResponse
from finwall.models import CashBalance, Holding, Portfolio


def test_export_openapi_script_writes_expected_paths(tmp_path):
    output_path = tmp_path / "finwall-openapi.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    subprocess.run(
        [
            sys.executable,
            "scripts/export_openapi.py",
            "--output",
            str(output_path),
        ],
        check=True,
        env=env,
    )

    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert "/api/v1/portfolio" in schema["paths"]
    assert "/api/v1/portfolio/analysis/charts" in schema["paths"]
    assert "/api/v1/portfolio/audit" in schema["paths"]


def test_portfolio_response_preserves_numeric_decimal_json_values():
    portfolio = Portfolio(
        name="Primary",
        cash_balances=(CashBalance("USD", Decimal("10.50")),),
        holdings=(Holding("MSFT", Decimal("1.25"), Decimal("20.75")),),
    )

    payload = PortfolioResponse.model_validate(asdict(portfolio)).model_dump(
        mode="json"
    )

    assert payload["cash_balances"][0]["amount"] == 10.5
    assert payload["holdings"][0]["share_count"] == 1.25
    assert payload["holdings"][0]["average_purchase_price"] == 20.75
