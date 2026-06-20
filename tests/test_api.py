import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from finwall.api import WEB_SESSION_COOKIE_NAME, create_app
from finwall.config import Settings


def build_client(tmp_path, token="secret", app_env="development"):
    app = create_app(
        Settings(
            app_env=app_env,
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


def test_web_login_fails_when_api_token_missing(tmp_path):
    client = build_client(tmp_path, token="")

    response = client.post("/api/v1/auth/login", json={"token": "anything"})

    assert response.status_code == 401
    assert "anything" not in response.text
    assert WEB_SESSION_COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_web_login_fails_with_invalid_token(tmp_path):
    client = build_client(tmp_path)

    response = client.post("/api/v1/auth/login", json={"token": "bad"})

    assert response.status_code == 401
    assert "secret" not in response.text
    assert "bad" not in response.text
    assert WEB_SESSION_COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_web_login_sets_http_only_session_cookie_without_returning_token(tmp_path):
    client = build_client(tmp_path)

    response = client.post("/api/v1/auth/login", json={"token": "secret"})

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    assert "secret" not in response.text
    set_cookie = response.headers.get("set-cookie", "")
    assert WEB_SESSION_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie


def test_web_login_sets_secure_cookie_in_production(tmp_path):
    client = build_client(tmp_path, app_env="production")

    response = client.post("/api/v1/auth/login", json={"token": "secret"})

    assert response.status_code == 200
    assert "Secure" in response.headers.get("set-cookie", "")


def test_web_session_endpoint_requires_valid_cookie(tmp_path):
    client = build_client(tmp_path)

    missing = client.get("/api/v1/auth/session")
    invalid = client.get(
        "/api/v1/auth/session", cookies={WEB_SESSION_COOKIE_NAME: "bad"}
    )
    login = client.post("/api/v1/auth/login", json={"token": "secret"})
    valid = client.get("/api/v1/auth/session")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert login.status_code == 200
    assert valid.status_code == 200
    assert valid.json() == {"authenticated": True}
    assert "secret" not in valid.text


def test_web_logout_clears_session_cookie(tmp_path):
    client = build_client(tmp_path)
    client.post("/api/v1/auth/login", json={"token": "secret"})

    response = client.post("/api/v1/auth/logout")
    session = client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}
    set_cookie = response.headers.get("set-cookie", "")
    assert WEB_SESSION_COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie
    assert session.status_code == 401


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


def test_obsolete_jinja_admin_routes_are_removed(tmp_path):
    client = build_client(tmp_path)

    assert client.get("/admin").status_code == 404
    assert client.get("/admin/login").status_code == 404
    assert client.post("/admin/login", data={"token": "secret"}).status_code == 404
    assert client.get("/admin/static/admin.css").status_code == 404


def test_web_session_cookie_authorizes_api_reads_only(tmp_path):
    client = build_client(tmp_path)
    login = client.post("/api/v1/auth/login", json={"token": "secret"})

    portfolio = client.get("/api/v1/portfolio")
    charts = client.get("/api/v1/portfolio/analysis/charts")
    audit = client.get("/api/v1/portfolio/audit")
    mutation = client.post(
        "/api/v1/portfolio/cash/add",
        json={"currency": "USD", "amount": "10"},
    )

    assert login.status_code == 200
    assert portfolio.status_code == 200
    assert portfolio.json()["name"] == "Primary"
    assert charts.status_code == 200
    assert charts.json()["portfolio_name"] == "Primary"
    assert audit.status_code == 200
    assert "events" in audit.json()
    assert mutation.status_code == 401


def test_session_cookie_does_not_authorize_mutation_endpoints(tmp_path):
    client = build_client(tmp_path)
    login = client.post("/api/v1/auth/login", json={"token": "secret"})

    mutations = [
        ("post", "/api/v1/portfolio/cash/add", {"currency": "USD", "amount": "10"}),
        (
            "post",
            "/api/v1/portfolio/cash/withdraw",
            {"currency": "USD", "amount": "10"},
        ),
        (
            "post",
            "/api/v1/portfolio/holdings",
            {"ticker": "NVDA", "shares": "1", "average_price": "100"},
        ),
        ("delete", "/api/v1/portfolio/holdings/NVDA", None),
        (
            "post",
            "/api/v1/portfolio/trades/buy",
            {"ticker": "NVDA", "shares": "1", "price": "120", "currency": "USD"},
        ),
        (
            "post",
            "/api/v1/portfolio/trades/sell",
            {"ticker": "NVDA", "shares": "1", "price": "120", "currency": "USD"},
        ),
        (
            "post",
            "/api/v1/portfolio/orders",
            {
                "ticker": "NVDA",
                "side": "sell",
                "order_type": "limit",
                "shares": "1",
                "limit_price": "150",
            },
        ),
        ("delete", "/api/v1/portfolio/orders/NVDA", None),
        ("post", "/api/v1/portfolio/watchlist", {"ticker": "AAPL", "note": "watch"}),
        ("delete", "/api/v1/portfolio/watchlist/AAPL", None),
        ("put", "/api/v1/portfolio/goal", {"name": "Grow", "target_amount": "25000"}),
        (
            "put",
            "/api/v1/portfolio/timeline",
            {"start_date": "2026-01-01", "target_date": "2027-01-01"},
        ),
        (
            "put",
            "/api/v1/portfolio/risk-profile",
            {"level": "moderate", "notes": "balanced"},
        ),
    ]

    assert login.status_code == 200
    for method, path, payload in mutations:
        request = getattr(client, method)
        response = request(path, json=payload) if payload else request(path)
        assert response.status_code == 401
        assert "secret" not in response.text


def test_audit_endpoint_returns_empty_on_fresh_database(tmp_path):
    client = build_client(tmp_path)
    h = auth_headers()

    response = client.get("/api/v1/portfolio/audit", headers=h)
    assert response.status_code == 200
    assert response.json() == {"events": []}


def test_audit_endpoint_records_api_mutation_without_leaking_token(tmp_path):
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


def test_bearer_auth_still_authorizes_api_reads(tmp_path):
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

    events = _audit_events(client, h)
    failed = [event for event in events if event["status"] == "failed"]
    actions = {event["action"] for event in failed}
    assert {
        "cash_withdraw",
        "trade_sell",
        "order_upsert",
    } <= actions
    assert any(
        event["action"] == "order_upsert" and event["source"] == "api"
        for event in failed
    )
    assert all(event["safe_error_message"] for event in failed)
    assert "secret" not in str(failed)
    assert "Traceback" not in str(failed)
