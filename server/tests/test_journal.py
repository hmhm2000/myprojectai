from tests.conftest import login
from tests.test_portfolios_api import add_position, create_portfolio, positions_of, sell


def test_position_journal_fields_roundtrip(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    view = add_position(
        client, headers, portfolio["id"],
        buy_price="103500",
        entry_reason="Duży spadek do wsparcia. RSI 30m < 30, cena pod dolną BB.",
        tags=[" rsi", "SUPPORT", "bb", "dip", "RSI", "", "price action"],
        plan="Trzymam do TP, SL pod wsparciem",
        target_price="110000",
        stop_loss="98500",
    )
    position = positions_of(view)[0]
    assert position["entry_reason"].startswith("Duży spadek")
    assert position["tags"] == ["RSI", "SUPPORT", "BB", "DIP", "PRICE_ACTION"]   # normalized, de-duplicated
    assert position["plan"] == "Trzymam do TP, SL pod wsparciem"
    assert (position["target_price"], position["stop_loss"]) == ("110000", "98500")

    # Journal fields are optional and editable; PnL is unaffected.
    body = {"symbol": "BTC", "buy_price": "103500", "quantity": "1", "fee_coin": "0.001", "bought_at": "2026-09-01",
            "tags": []}
    view = client.put(f"/api/positions/{position['id']}", json=body, headers=headers).json()
    edited = positions_of(view)[0]
    assert edited["tags"] == [] and edited["entry_reason"] is None and edited["target_price"] is None
    assert edited["cost"] == position["cost"]


def test_sale_exit_reason_and_tag_validation(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    view = add_position(client, headers, portfolio["id"])
    position_id = positions_of(view)[0]["id"]

    body = {"price": "70000", "sold_at": "2026-09-10", "exit_reason": "TP osiągnięty",
            "allocations": [{"position_id": position_id, "quantity": "0.5"}]}
    view = client.post(f"/api/portfolios/{portfolio['id']}/sales", json=body, headers=headers).json()
    assert positions_of(view)[0]["sales"][0]["exit_reason"] == "TP osiągnięty"

    bad = client.post(f"/api/portfolios/{portfolio['id']}/positions", headers=headers, json={
        "symbol": "BTC", "buy_price": "1", "quantity": "1", "bought_at": "2026-09-01", "tags": ["RSI<30"]})
    assert bad.status_code == 422 and bad.json()["detail"][0]["type"] == "invalid_tag"
    bad = client.post(f"/api/portfolios/{portfolio['id']}/positions", headers=headers, json={
        "symbol": "BTC", "buy_price": "1", "quantity": "1", "bought_at": "2026-09-01", "stop_loss": "-5"})
    assert bad.status_code == 422
