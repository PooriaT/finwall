import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from finwall.api import create_app
from finwall.config import Settings


def build_client(tmp_path, token="secret"):
    app = create_app(
        Settings(
            storage_backend="sqlite",
            database_url="",
            database_path=str(tmp_path / "api.db"),
            api_token=token,
        )
    )
    return TestClient(app)


def auth_headers(token="secret"):
    return {"Authorization": f"Bearer {token}"}


def test_health_no_auth(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200


def test_auth_missing_and_invalid(tmp_path):
    client = build_client(tmp_path)
    missing = client.post(
        "/api/v1/portfolio/cash/add", json={"currency": "USD", "amount": "10"}
    )
    invalid = client.post(
        "/api/v1/portfolio/cash/add",
        headers=auth_headers("bad"),
        json={"currency": "USD", "amount": "10"},
    )
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "secret" not in missing.text


def test_portfolio_updates_flow(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    assert (
        client.post(
            "/api/v1/portfolio/cash/add",
            headers=h,
            json={"currency": "USD", "amount": "1000"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/portfolio/cash/withdraw",
            headers=h,
            json={"currency": "USD", "amount": "100"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/portfolio/holdings",
            headers=h,
            json={
                "ticker": "NVDA",
                "shares": "2",
                "average_price": "100",
                "sector": "Technology",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/portfolio/trades/buy",
            headers=h,
            json={
                "ticker": "NVDA",
                "shares": "1",
                "price": "120",
                "currency": "USD",
                "trade_date": "2026-01-01",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/portfolio/trades/sell",
            headers=h,
            json={"ticker": "NVDA", "shares": "10", "price": "120", "currency": "USD"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/portfolio/orders",
            headers=h,
            json={
                "ticker": "NVDA",
                "side": "sell",
                "order_type": "stop_limit",
                "shares": "1",
                "limit_price": "95",
                "stop_price": "96",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/portfolio/orders",
            headers=h,
            json={
                "ticker": "NVDA",
                "side": "sell",
                "order_type": "stop_limit",
                "shares": "1",
                "limit_price": "95",
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/portfolio/watchlist",
            headers=h,
            json={"ticker": "AAPL", "note": "watch"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/portfolio/goal",
            headers=h,
            json={"name": "Grow", "target_amount": "25000"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/portfolio/timeline",
            headers=h,
            json={"start_date": "2026-01-01", "target_date": "2027-01-01"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/portfolio/risk-profile",
            headers=h,
            json={"level": "moderate", "notes": "balanced"},
        ).status_code
        == 200
    )
    state = client.get("/api/v1/portfolio", headers=h)
    assert state.status_code == 200
    body = state.json()
    assert body["cash_balances"]
    assert isinstance(body["cash_balances"][0]["amount"], int | float)
    assert isinstance(body["holdings"][0]["share_count"], int | float)
    assert isinstance(body["holdings"][0]["average_purchase_price"], int | float)
    assert body["risk_profile"]["level"] == "moderate"


def test_api_token_missing_rejects(tmp_path):
    client = build_client(tmp_path, token="")
    response = client.post(
        "/api/v1/portfolio/cash/add",
        headers=auth_headers("anything"),
        json={"currency": "USD", "amount": "10"},
    )
    assert response.status_code == 401


def test_cash_withdraw_invalid_returns_400(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()

    missing_currency = client.post(
        "/api/v1/portfolio/cash/withdraw",
        headers=h,
        json={"currency": "USD", "amount": "10"},
    )
    assert missing_currency.status_code == 400

    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "5"},
    )
    overdraw = client.post(
        "/api/v1/portfolio/cash/withdraw",
        headers=h,
        json={"currency": "USD", "amount": "10"},
    )
    assert overdraw.status_code == 400


def test_trade_buy_invalid_payload_returns_400(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()

    response = client.post(
        "/api/v1/portfolio/trades/buy",
        headers=h,
        json={"ticker": "NVDA", "shares": "0", "price": "120", "currency": "USD"},
    )

    assert response.status_code == 400


def test_admin_login_logout_and_cookie_auth(tmp_path):
    client = build_client(tmp_path)
    login = client.get("/admin/login")
    assert login.status_code == 200
    assert "Finwall Admin Login" in login.text
    assert "/admin/static/admin.css" in login.text
    assert client.get("/admin", follow_redirects=False).status_code == 401
    bad = client.post("/admin/login", data={"token": "bad"})
    assert bad.status_code == 401
    ok = client.post("/admin/login", data={"token": "secret"}, follow_redirects=False)
    assert ok.status_code == 303
    assert "finwall_admin_token" in ok.headers.get("set-cookie", "")
    home = client.get("/admin")
    assert home.status_code == 200
    assert "Dashboard" in home.text
    assert "Portfolio" in home.text
    assert "Logout" in home.text
    assert "secret" not in home.text
    out = client.post("/admin/logout", follow_redirects=False)
    assert out.status_code == 303


def test_admin_cookie_authorizes_api_reads_only(tmp_path):
    client = build_client(tmp_path)
    client.post("/admin/login", data={"token": "secret"})

    portfolio = client.get("/api/v1/portfolio")
    charts = client.get("/api/v1/portfolio/analysis/charts")
    audit = client.get("/api/v1/portfolio/audit")
    mutation = client.post(
        "/api/v1/portfolio/cash/add",
        json={"currency": "USD", "amount": "10"},
    )

    assert portfolio.status_code == 200
    assert portfolio.json()["name"] == "Primary"
    assert charts.status_code == 200
    assert charts.json()["portfolio_name"] == "Primary"
    assert audit.status_code == 200
    assert "events" in audit.json()
    assert mutation.status_code == 401


def test_admin_css_static_asset_served(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/admin/static/admin.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert ".nav" in response.text


def test_admin_forms_update_portfolio(tmp_path):
    client = build_client(tmp_path)
    client.post("/admin/login", data={"token": "secret"})
    assert (
        client.post(
            "/admin/cash/add",
            data={"currency": "USD", "amount": "100"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/cash/withdraw",
            data={"currency": "USD", "amount": "25"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/holdings",
            data={
                "ticker": "NVDA",
                "shares": "1",
                "average_price": "100",
                "sector": "Tech",
            },
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/holdings/delete", data={"ticker": "NVDA"}, follow_redirects=False
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/orders",
            data={
                "ticker": "NVDA",
                "side": "sell",
                "order_type": "stop_limit",
                "shares": "1",
                "limit_price": "99",
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/admin/watchlist",
            data={"ticker": "AAPL", "note": "watch"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/goal",
            data={"name": "Grow", "target_amount": "5000"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/timeline",
            data={"start_date": "2026-01-01", "target_date": "2027-01-01"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/admin/risk-profile",
            data={"level": "moderate", "notes": "balanced"},
            follow_redirects=False,
        ).status_code
        == 303
    )


def test_audit_views_return_empty_on_fresh_database(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()

    response = client.get("/api/v1/portfolio/audit", headers=h)
    assert response.status_code == 200
    assert response.json() == {"events": []}

    client.post("/admin/login", data={"token": "secret"})
    page = client.get("/admin/audit")
    assert page.status_code == 200
    assert "Audit events" in page.text


def test_audit_endpoint_and_web_audit_page(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    response = client.get("/api/v1/portfolio/audit", headers=h)
    assert response.status_code == 200
    events = response.json()["events"]
    assert events
    assert events[0]["source"] == "api"
    assert "secret" not in response.text

    assert client.get("/admin/audit").status_code == 401
    client.post("/admin/login", data={"token": "secret"})
    client.post("/admin/cash/add", data={"currency": "USD", "amount": "25"})
    page = client.get("/admin/audit")
    assert page.status_code == 200
    assert "web" in page.text
    assert "secret" not in page.text


def test_admin_form_error_sanitized(tmp_path):
    client = build_client(tmp_path)
    client.post("/admin/login", data={"token": "secret"})
    response = client.post(
        "/admin/cash/add", data={"currency": "USD", "amount": "bad\nTraceback"}
    )
    assert response.status_code == 422
    assert "Traceback" not in response.text
    assert "invalid decimal" in response.text


def test_admin_flash_renders_after_redirect(tmp_path):
    client = build_client(tmp_path)
    client.post("/admin/login", data={"token": "secret"})
    response = client.post("/admin/cash/add", data={"currency": "USD", "amount": "100"})
    assert response.status_code == 200
    assert "Cash updated" in response.text


def test_admin_pages_use_shared_layout_and_do_not_render_token(tmp_path):
    client = build_client(tmp_path)
    client.post("/admin/login", data={"token": "secret"})
    for path in (
        "/admin",
        "/admin/portfolio",
        "/admin/audit",
        "/admin/cash",
        "/admin/holdings",
        "/admin/trades",
        "/admin/orders",
        "/admin/watchlist",
        "/admin/settings",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert "Finwall Admin" in response.text
        assert "/admin/static/admin.css" in response.text
        assert "Dashboard" in response.text
        assert "secret" not in response.text


def test_admin_orders_form_lists_supported_order_types(tmp_path):
    client = build_client(tmp_path)
    client.post("/admin/login", data={"token": "secret"})

    response = client.get("/admin/orders")

    assert response.status_code == 200
    assert "limit, stop_loss, stop_limit" in response.text
    assert "market, limit, stop" not in response.text


def test_admin_dashboard_renders_read_only_overview(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    client.post(
        "/api/v1/portfolio/holdings",
        headers=h,
        json={"ticker": "NVDA", "shares": "2", "average_price": "100"},
    )
    client.post(
        "/api/v1/portfolio/orders",
        headers=h,
        json={
            "ticker": "NVDA",
            "side": "sell",
            "order_type": "stop_loss",
            "shares": "1",
            "stop_price": "90",
        },
    )
    client.post(
        "/api/v1/portfolio/watchlist",
        headers=h,
        json={"ticker": "AAPL", "note": "watch"},
    )
    client.put(
        "/api/v1/portfolio/goal",
        headers=h,
        json={"name": "Grow", "target_amount": "25000"},
    )
    client.put(
        "/api/v1/portfolio/timeline",
        headers=h,
        json={"start_date": "2026-01-01", "target_date": "2027-01-01"},
    )
    client.put(
        "/api/v1/portfolio/risk-profile",
        headers=h,
        json={"level": "moderate", "notes": "balanced"},
    )
    client.post("/admin/login", data={"token": "secret"})

    response = client.get("/admin")

    assert response.status_code == 200
    for text in (
        "Dashboard",
        "Portfolio Summary",
        "Charts",
        "Allocation by holding",
        "Cash vs invested",
        "Unrealized gain/loss by holding",
        "Risk warnings by severity",
        "Price unavailable",
        "chart-card",
        "Cash",
        "Holdings",
        "Active Orders",
        "Watchlist",
        "Goal And Risk Profile",
        "Risk Status",
        "Live Data Status",
        "Latest Report",
        "Latest Audit",
        "NVDA",
        "AAPL",
        "Grow",
        "moderate",
        "Valuation status",
        "missing",
        "Configured market data provider",
        "static",
        "/admin/audit",
    ):
        assert text in response.text
    assert "No report has been saved yet." in response.text
    assert "Chart area" not in response.text
    assert "Charts are intentionally not included" not in response.text
    assert 'form method="post" action="/admin/cash' not in response.text
    assert 'form method="post" action="/admin/holdings' not in response.text
    assert 'form method="post" action="/admin/orders' not in response.text
    chart_section = response.text.split(
        '<h2 id="dashboard-charts-title">Charts</h2>', 1
    )[1].split('<section class="panel table-wrap">', 1)[0]
    assert "<form" not in chart_section
    assert "secret" not in response.text


def test_admin_dashboard_handles_empty_portfolio(tmp_path):
    client = build_client(tmp_path)
    client.post("/admin/login", data={"token": "secret"})

    response = client.get("/admin")

    assert response.status_code == 200
    assert "No cash balances have been recorded." in response.text
    assert "No holdings have been recorded." in response.text
    assert "No active orders." in response.text
    assert "No watchlist items." in response.text
    assert "Current goal has not been configured." in response.text
    assert "Risk profile has not been configured." in response.text
    assert "complete" in response.text
    assert "Charts" in response.text
    assert "No holdings are available for allocation charts." in response.text
    assert "No holdings are available for unrealized gain/loss charts." in response.text
    assert "Risk warnings by severity" in response.text


def test_admin_dashboard_reuses_price_snapshot_for_charts(tmp_path, monkeypatch):
    from decimal import Decimal

    from finwall.market_data import MarketPrice, StaticMarketDataProvider

    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/holdings",
        headers=h,
        json={"ticker": "AAPL", "shares": "2", "average_price": "100"},
    )

    calls = {"count": 0}

    def provider(_name, _timeout):
        return StaticMarketDataProvider(
            {"AAPL": MarketPrice("AAPL", Decimal("150"), "USD", "test", True)}
        )

    def fetch_once(portfolio, provider_instance):
        calls["count"] += 1
        from finwall.market_data import fetch_portfolio_latest_prices

        return fetch_portfolio_latest_prices(portfolio, provider_instance)

    def fail_if_chart_data_refetches(_portfolio, _provider):
        raise AssertionError("chart data should reuse the dashboard price snapshot")

    monkeypatch.setattr("finwall.admin_dashboard.build_market_data_provider", provider)
    monkeypatch.setattr(
        "finwall.admin_dashboard.fetch_portfolio_latest_prices", fetch_once
    )
    monkeypatch.setattr(
        "finwall.chart_data.fetch_portfolio_latest_prices", fail_if_chart_data_refetches
    )
    client.post("/admin/login", data={"token": "secret"})
    calls["count"] = 0

    response = client.get("/admin")

    assert response.status_code == 200
    assert "AAPL" in response.text
    assert "300.00" in response.text
    assert calls["count"] == 1


def test_admin_dashboard_charts_render_priced_missing_and_risk_data(
    tmp_path, monkeypatch
):
    from decimal import Decimal

    from finwall.market_data import MarketPrice, StaticMarketDataProvider

    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    client.post(
        "/api/v1/portfolio/holdings",
        headers=h,
        json={"ticker": "AAPL", "shares": "2", "average_price": "100"},
    )
    client.post(
        "/api/v1/portfolio/holdings",
        headers=h,
        json={"ticker": "MSFT", "shares": "1", "average_price": "300"},
    )

    def provider(_name, _timeout):
        return StaticMarketDataProvider(
            {"AAPL": MarketPrice("AAPL", Decimal("150"), "USD", "test", True)}
        )

    monkeypatch.setattr("finwall.chart_data.build_market_data_provider", provider)
    monkeypatch.setattr("finwall.admin_dashboard.build_market_data_provider", provider)
    client.post("/admin/login", data={"token": "secret"})

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Allocation by holding" in response.text
    assert "AAPL" in response.text
    assert "300.00" in response.text
    assert "MSFT" in response.text
    assert "Price unavailable for MSFT" in response.text
    assert "Cash vs invested" in response.text
    assert "partial" in response.text
    assert "Unrealized gain/loss by holding" in response.text
    assert "100.00" in response.text
    assert "Risk warnings by severity" in response.text
    assert "Medium" in response.text or "medium" in response.text
    assert "chart-bar-positive" in response.text
    assert "secret" not in response.text


def test_admin_dashboard_shows_latest_report_metadata(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    with client.app.state.store._connect() as connection:
        portfolio_id = client.app.state.store._require_portfolio_id(
            connection, "Primary"
        )
        connection.execute(
            """
            INSERT INTO report_runs (
                portfolio_id, created_at, command_context, report_summary, report_json,
                price_completeness_status, valuation_status, recommendation_summary
            ) VALUES (?, '2026-06-17T00:00:00', 'admin-test', 'summary', '{}',
                      'complete', 'complete', 'Hold positions')
            """,
            (portfolio_id,),
        )
    client.post("/admin/login", data={"token": "secret"})

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Report id" in response.text
    assert "admin-test" in response.text
    assert "Hold positions" in response.text


def test_admin_dashboard_keeps_api_bearer_auth_working(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/api/v1/portfolio", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["name"] == "Primary"


def test_analysis_chart_endpoints_require_bearer_auth(tmp_path):
    client = build_client(tmp_path)

    missing = client.get("/api/v1/portfolio/analysis/charts")
    invalid = client.get(
        "/api/v1/portfolio/analysis/charts", headers=auth_headers("bad")
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "secret" not in missing.text
    assert "secret" not in invalid.text


def test_analysis_aggregate_empty_portfolio_has_expected_chart_keys(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/api/v1/portfolio/analysis/charts", headers=auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio_name"] == "Primary"
    assert set(payload["charts"]) == {
        "allocation_by_holding",
        "allocation_by_sector",
        "cash_vs_invested",
        "unrealized_gain_loss_by_holding",
        "risk_warnings_by_severity",
        "report_history_summary",
    }
    assert payload["charts"]["allocation_by_holding"]["points"] == []
    assert payload["charts"]["allocation_by_sector"]["points"] == []


def test_analysis_charts_include_prices_missing_sectors_and_risk(tmp_path, monkeypatch):
    from decimal import Decimal

    from finwall.market_data import MarketPrice, StaticMarketDataProvider

    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    client.post(
        "/api/v1/portfolio/holdings",
        headers=h,
        json={"ticker": "AAPL", "shares": "2", "average_price": "100"},
    )
    client.post(
        "/api/v1/portfolio/holdings",
        headers=h,
        json={
            "ticker": "MSFT",
            "shares": "1",
            "average_price": "300",
            "sector": "Technology",
        },
    )

    def provider(_name, _timeout):
        return StaticMarketDataProvider(
            {"AAPL": MarketPrice("AAPL", Decimal("150"), "USD", "test", True)}
        )

    monkeypatch.setattr("finwall.chart_data.build_market_data_provider", provider)

    aggregate = client.get("/api/v1/portfolio/analysis/charts", headers=h).json()
    holdings = aggregate["charts"]["allocation_by_holding"]["points"]
    assert holdings[0]["key"] == "AAPL"
    assert holdings[0]["value"] == "300.00"
    assert holdings[0]["status"] == "available"
    assert holdings[1]["key"] == "MSFT"
    assert holdings[1]["value"] is None
    assert holdings[1]["status"] == "missing_price"

    sectors = client.get(
        "/api/v1/portfolio/analysis/allocation/sectors", headers=h
    ).json()
    assert sectors["points"][0]["key"] == "Technology"
    assert sectors["points"][0]["value"] is None
    assert sectors["points"][0]["status"] == "missing_price"
    assert sectors["points"][0]["metadata"]["missing_tickers"] == ["MSFT"]
    assert sectors["points"][1]["key"] == "Uncategorized"
    assert sectors["points"][1]["value"] == "300.00"
    assert sectors["points"][1]["status"] == "available"
    assert sectors["points"][1]["metadata"]["tickers"] == ["AAPL"]
    assert sectors["warnings"]

    cash = client.get("/api/v1/portfolio/analysis/cash-vs-invested", headers=h).json()
    assert cash["points"][0]["metadata"]["valuation_status"] == "missing_prices"
    assert cash["points"][0]["metadata"]["price_completeness_status"] == "partial"

    unrealized = client.get(
        "/api/v1/portfolio/analysis/unrealized-gain-loss", headers=h
    ).json()
    assert unrealized["points"][0]["value"] == "100.00"
    assert unrealized["points"][1]["value"] is None
    assert unrealized["points"][1]["status"] == "missing_price"

    risk = client.get("/api/v1/portfolio/analysis/risk-warnings", headers=h).json()
    assert any(point["key"] == "medium" for point in risk["points"])


def test_analysis_report_history_metadata_and_limit_cap(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    with client.app.state.store._connect() as connection:
        portfolio_id = client.app.state.store._require_portfolio_id(
            connection, "Primary"
        )
        for index in range(55):
            connection.execute(
                """
                INSERT INTO report_runs (
                    portfolio_id, created_at, command_context, report_summary,
                    report_json, price_completeness_status, valuation_status,
                    recommendation_summary
                ) VALUES (?, ?, ?, ?, '{}', 'complete', 'complete', ?)
                """,
                (
                    portfolio_id,
                    f"2026-06-17T00:00:{index:02d}",
                    f"ctx-{index}",
                    f"summary-{index}",
                    f"recommend-{index}",
                ),
            )

    response = client.get(
        "/api/v1/portfolio/analysis/report-history?report_history_limit=99",
        headers=h,
    )

    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) == 50
    assert points[0]["metadata"]["command_context"] == "ctx-54"
    assert points[0]["metadata"]["recommendation_summary"] == "recommend-54"


def _audit_events(client, headers):
    response = client.get("/api/v1/portfolio/audit", headers=headers)
    assert response.status_code == 200
    return response.json()["events"]


def test_api_mutation_audit_coverage(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    client.post(
        "/api/v1/portfolio/cash/withdraw",
        headers=h,
        json={"currency": "USD", "amount": "10"},
    )
    client.post(
        "/api/v1/portfolio/holdings",
        headers=h,
        json={"ticker": "MSFT", "shares": "5", "average_price": "20"},
    )
    client.delete("/api/v1/portfolio/holdings/MSFT", headers=h)
    client.post(
        "/api/v1/portfolio/trades/buy",
        headers=h,
        json={"ticker": "AAPL", "shares": "2", "price": "100", "currency": "USD"},
    )
    client.post(
        "/api/v1/portfolio/trades/sell",
        headers=h,
        json={"ticker": "AAPL", "shares": "1", "price": "110", "currency": "USD"},
    )
    client.post(
        "/api/v1/portfolio/orders",
        headers=h,
        json={
            "ticker": "AAPL",
            "side": "sell",
            "order_type": "limit",
            "shares": "1",
            "limit_price": "150",
        },
    )
    client.delete("/api/v1/portfolio/orders/AAPL", headers=h)
    client.post(
        "/api/v1/portfolio/watchlist",
        headers=h,
        json={"ticker": "TSLA", "note": "watch"},
    )
    client.delete("/api/v1/portfolio/watchlist/TSLA", headers=h)
    client.put(
        "/api/v1/portfolio/goal",
        headers=h,
        json={"name": "Grow", "target_amount": "10000"},
    )
    client.put(
        "/api/v1/portfolio/timeline",
        headers=h,
        json={"start_date": "2026-01-01", "target_date": "2027-01-01"},
    )
    client.put(
        "/api/v1/portfolio/risk-profile",
        headers=h,
        json={"level": "moderate", "notes": "ok"},
    )

    events = _audit_events(client, h)
    actions = {event["action"] for event in events if event["status"] == "succeeded"}
    assert {
        "cash_add",
        "cash_withdraw",
        "holding_upsert",
        "holding_delete",
        "trade_buy",
        "trade_sell",
        "order_upsert",
        "order_delete",
        "watchlist_upsert",
        "watchlist_delete",
        "goal_set",
        "timeline_set",
        "risk_profile_set",
    } <= actions
    assert all(event["actor"] == "api-admin" for event in events)
    assert all(event["source"] == "api" for event in events)
    assert "secret" not in str(events)
    assert any(
        event["before_json"] is not None or event["after_json"] is not None
        for event in events
    )


def test_failed_validation_audit_events_are_safe(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    client.post(
        "/api/v1/portfolio/cash/add",
        headers=h,
        json={"currency": "USD", "amount": "100"},
    )
    client.post(
        "/api/v1/portfolio/cash/withdraw",
        headers=h,
        json={"currency": "USD", "amount": "1000"},
    )
    client.post(
        "/api/v1/portfolio/trades/sell",
        headers=h,
        json={"ticker": "AAPL", "shares": "10", "price": "1", "currency": "USD"},
    )
    client.post(
        "/api/v1/portfolio/cash/withdraw",
        headers=h,
        json={"currency": "USD", "amount": "bad\nTraceback"},
    )
    client.post(
        "/api/v1/portfolio/orders",
        headers=h,
        json={
            "ticker": "AAPL",
            "side": "buy",
            "order_type": "limit",
            "shares": "1",
            "limit_price": "bad",
        },
    )

    client.post("/admin/login", data={"token": "secret"})
    client.post(
        "/admin/trades/sell",
        data={"ticker": "AAPL", "shares": "10", "price": "1", "currency": "USD"},
    )
    client.post(
        "/admin/orders",
        data={"ticker": "AAPL", "side": "buy", "order_type": "limit", "shares": "1"},
    )
    client.post("/admin/risk-profile", data={"level": "invalid", "notes": "bad"})

    events = _audit_events(client, h)
    failed = [event for event in events if event["status"] == "failed"]
    actions = {event["action"] for event in failed}
    assert {
        "cash_withdraw",
        "trade_sell",
        "order_upsert",
        "risk_profile_set",
    } <= actions
    assert any(
        event["action"] == "order_upsert" and event["source"] == "api"
        for event in failed
    )
    assert any(
        event["action"] == "trade_sell" and event["source"] == "web" for event in failed
    )
    assert all(event["safe_error_message"] for event in failed)
    assert "secret" not in str(failed)
    assert "Traceback" not in str(failed)


def test_admin_mutation_audit_coverage(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()
    client.post("/admin/login", data={"token": "secret"})
    client.post("/admin/cash/add", data={"currency": "USD", "amount": "1000"})
    client.post("/admin/cash/withdraw", data={"currency": "USD", "amount": "10"})
    client.post(
        "/admin/holdings", data={"ticker": "MSFT", "shares": "5", "average_price": "20"}
    )
    client.post("/admin/holdings/delete", data={"ticker": "MSFT"})
    client.post(
        "/admin/trades/buy",
        data={"ticker": "AAPL", "shares": "2", "price": "100", "currency": "USD"},
    )
    client.post(
        "/admin/trades/sell",
        data={"ticker": "AAPL", "shares": "1", "price": "110", "currency": "USD"},
    )
    client.post(
        "/admin/orders",
        data={
            "ticker": "AAPL",
            "side": "sell",
            "order_type": "limit",
            "shares": "1",
            "limit_price": "150",
        },
    )
    client.post("/admin/orders/delete", data={"ticker": "AAPL"})
    client.post("/admin/watchlist", data={"ticker": "TSLA", "note": "watch"})
    client.post("/admin/watchlist/delete", data={"ticker": "TSLA"})
    client.post("/admin/goal", data={"name": "Grow", "target_amount": "10000"})
    client.post(
        "/admin/timeline",
        data={"start_date": "2026-01-01", "target_date": "2027-01-01"},
    )
    client.post("/admin/risk-profile", data={"level": "moderate", "notes": "ok"})

    events = _audit_events(client, h)
    actions = {event["action"] for event in events if event["status"] == "succeeded"}
    assert {
        "cash_add",
        "cash_withdraw",
        "holding_upsert",
        "holding_delete",
        "trade_buy",
        "trade_sell",
        "order_upsert",
        "order_delete",
        "watchlist_upsert",
        "watchlist_delete",
        "goal_set",
        "timeline_set",
        "risk_profile_set",
    } <= actions
    assert all(event["actor"] == "web-admin" for event in events)
    assert all(event["source"] == "web" for event in events)
    page = client.get("/admin/audit")
    assert page.status_code == 200
    assert "secret" not in page.text
