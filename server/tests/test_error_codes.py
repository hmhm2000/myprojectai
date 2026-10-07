"""The frontend translates errors by code, so the response format is part of the API contract."""
from tests.conftest import login
from tests.test_portfolios_api import add_position, create_portfolio, positions_of, sell


def test_app_error_has_code_detail_and_params(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    view = add_position(client, headers, portfolio["id"], quantity="1", fee_coin="0", bought_at="2026-09-01")
    position_id = positions_of(view)[0]["id"]

    body = sell(client, headers, portfolio["id"], [(position_id, "2")]).json()
    assert body["code"] == "sale.exceeds_available"
    assert body["params"] == {"date": "2026-09-01T00:00:00", "max": "1", "symbol": "BTC"}
    assert body["detail"].startswith("Position from 2026-09-01")


def test_not_found_and_auth_codes(client):
    headers = login(client)
    assert client.get("/api/portfolios/999", headers=headers).json()["code"] == "portfolio.not_found"
    bad_login = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401 and bad_login.json()["code"] == "auth.invalid_credentials"
    register = client.post("/api/auth/register", json={"username": "abc", "email": "a@b.co", "password": "password123"})
    assert register.json()["code"] == "auth.registration_disabled"


def test_validation_errors_use_custom_types(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    url = f"/api/portfolios/{portfolio['id']}/positions"
    base = {"symbol": "BTC", "buy_price": "1", "quantity": "1", "bought_at": "2026-09-01"}

    fee = client.post(url, json=base | {"fee_coin": "1"}, headers=headers).json()
    assert fee["detail"][0]["type"] == "fee_not_below_quantity"
    symbol = client.post(url, json=base | {"symbol": "B T C"}, headers=headers).json()
    assert symbol["detail"][0]["type"] == "invalid_symbol"
