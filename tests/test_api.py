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
