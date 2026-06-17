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
    assert 'form method="post" action="/admin/cash' not in response.text
    assert 'form method="post" action="/admin/holdings' not in response.text
    assert 'form method="post" action="/admin/orders' not in response.text
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
