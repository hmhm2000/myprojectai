from dataclasses import replace

import auth
from tests.conftest import login


def create_portfolio(client, headers, name="Główny"):
    response = client.post("/api/portfolios", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def add_position(client, headers, portfolio_id, **overrides):
    body = {"symbol": "btc", "buy_price": "50000", "quantity": "1", "fee_coin": "0.001",
            "bought_at": "2026-09-01", "note": "test"} | overrides
    response = client.post(f"/api/portfolios/{portfolio_id}/positions", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_portfolio_crud(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    assert portfolio["coins"] == []
    assert portfolio["summary"]["invested"] == "0.00000000"
    assert portfolio["summary"]["value"] == "0.00000000"

    renamed = client.patch(f"/api/portfolios/{portfolio['id']}", json={"name": "  Długoterminowy "}, headers=headers)
    assert renamed.json()["name"] == "Długoterminowy"

    listed = client.get("/api/portfolios", headers=headers).json()
    assert [p["name"] for p in listed] == ["Długoterminowy"]

    assert client.delete(f"/api/portfolios/{portfolio['id']}", headers=headers).status_code == 204
    assert client.get("/api/portfolios", headers=headers).json() == []


def test_position_view_and_summary(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    add_position(client, headers, portfolio["id"])
    view = add_position(client, headers, portfolio["id"], symbol="SPX", buy_price="0.6",
                        quantity="1000", fee_coin="0", bought_at="2026-09-02T10:30:00")

    coins = {c["symbol"]: c for c in view["coins"]}
    btc = coins["BTC"]
    assert btc["price"]["price"] == "60000" and btc["price"]["source"] == "okx"
    assert btc["open_quantity"] == "0.999"
    assert btc["positions"][0]["unrealized_pnl"] == "9940.00000000"
    assert btc["positions"][0]["note"] == "test"

    spx = coins["SPX"]
    assert spx["price"]["source"] == "bybit"
    assert spx["unrealized_pnl"] == "-100.00000000"        # 1000 × (0,5 − 0,6)

    summary = view["summary"]
    assert summary["invested"] == "50600.00000000"
    assert summary["value"] == "60440.00000000"
    assert summary["unrealized_pnl"] == "9840.00000000"
    assert summary["missing_prices"] == []
    assert view["prices"]["stale"] is False


def sell(client, headers, portfolio_id, allocations, price="70000", fee="0", sold_at="2026-09-10"):
    body = {"price": price, "fee_quote": fee, "sold_at": sold_at,
            "allocations": [{"position_id": pid, "quantity": qty} for pid, qty in allocations]}
    return client.post(f"/api/portfolios/{portfolio_id}/sales", json=body, headers=headers)


def positions_of(view, symbol="BTC"):
    return next(c for c in view["coins"] if c["symbol"] == symbol)["positions"]


def test_sale_rules_and_new_position_after_close(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    view = add_position(client, headers, portfolio["id"], fee_coin="0")
    position_id = positions_of(view)[0]["id"]

    assert sell(client, headers, portfolio["id"], [(position_id, "1.5")]).status_code == 400

    view = sell(client, headers, portfolio["id"], [(position_id, "1")], fee="70").json()
    closed = positions_of(view)[0]
    assert closed["is_closed"] is True
    assert closed["realized_pnl"] == "19930.00000000"
    assert closed["total_pnl_pct"] == "39.86"

    # A new purchase after closing = a new, separate position (appended at the end).
    view = add_position(client, headers, portfolio["id"], buy_price="65000", fee_coin="0", bought_at="2026-09-20")
    btc = view["coins"][0]
    assert btc["open_positions"] == 1 and btc["closed_positions"] == 1
    new_position = btc["positions"][1]
    assert new_position["buy_price"] == "65000"
    assert new_position["total_pnl"] == "-5000.00000000"
    assert btc["realized_pnl"] == "19930.00000000"
    assert btc["unrealized_pnl"] == "-5000.00000000"
    assert btc["total_pnl"] == "14930.00000000"            # overall profit
    assert btc["total_cost"] == "115000.00000000"
    assert btc["total_pnl_pct"] == "12.98"

    # Deleting the sale reopens the position.
    group_id = closed["sales"][0]["group_id"]
    view = client.delete(f"/api/sale-groups/{group_id}", headers=headers).json()
    assert view["coins"][0]["open_positions"] == 2


def test_sale_from_several_positions(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    for price, day in (("40000", "01"), ("50000", "02"), ("60000", "03")):
        view = add_position(client, headers, portfolio["id"], buy_price=price, fee_coin="0", bought_at=f"2026-09-{day}")
    long_term, short_a, short_b = [p["id"] for p in positions_of(view)]

    # Sell 1.5 BTC from the two "short-term" positions only - the oldest stays untouched.
    view = sell(client, headers, portfolio["id"], [(short_a, "1"), (short_b, "0.5")], price="70000", fee="105").json()
    by_id = {p["id"]: p for p in positions_of(view)}
    assert by_id[long_term]["sales"] == []
    assert by_id[short_a]["is_closed"] is True
    assert by_id[short_b]["open_quantity"] == "0.5"

    # Fee split proportionally to quantity (1 : 0.5), same group.
    sale_a, sale_b = by_id[short_a]["sales"][0], by_id[short_b]["sales"][0]
    assert sale_a["group_id"] == sale_b["group_id"]
    assert (sale_a["fee_quote"], sale_b["fee_quote"]) == ("70", "35")
    assert by_id[short_a]["realized_pnl"] == "19930.00000000"      # 70 000 - 70 - 50 000
    assert by_id[short_b]["realized_pnl"] == "4965.00000000"       # 35 000 - 35 - 30 000

    # Edit the whole sale: different split, same group_id.
    group_id = sale_a["group_id"]
    body = {"price": "70000", "fee_quote": "0", "sold_at": "2026-09-10",
            "allocations": [{"position_id": short_b, "quantity": "1"}]}
    view = client.put(f"/api/sale-groups/{group_id}", json=body, headers=headers).json()
    by_id = {p["id"]: p for p in positions_of(view)}
    assert by_id[short_a]["sales"] == [] and by_id[short_a]["is_closed"] is False
    assert by_id[short_b]["is_closed"] is True
    assert by_id[short_b]["sales"][0]["group_id"] == group_id

    # Editing cannot exceed the quantity (computed without the old version of this sale).
    body["allocations"] = [{"position_id": short_b, "quantity": "1.1"}]
    assert client.put(f"/api/sale-groups/{group_id}", json=body, headers=headers).status_code == 400

    view = client.delete(f"/api/sale-groups/{group_id}", headers=headers).json()
    assert all(not p["sales"] for p in positions_of(view))


def test_sale_validation(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    add_position(client, headers, portfolio["id"])
    view = add_position(client, headers, portfolio["id"], symbol="ETH", buy_price="2000")
    btc_id = positions_of(view, "BTC")[0]["id"]
    eth_id = positions_of(view, "ETH")[0]["id"]

    mixed = sell(client, headers, portfolio["id"], [(btc_id, "0.1"), (eth_id, "0.1")])
    assert mixed.status_code == 400 and mixed.json()["code"] == "sale.mixed_coins"
    assert sell(client, headers, portfolio["id"], [(btc_id, "0.1"), (btc_id, "0.1")]).status_code == 422
    assert sell(client, headers, portfolio["id"], []).status_code == 422

    other = create_portfolio(client, headers, "Inny")
    assert sell(client, headers, other["id"], [(btc_id, "0.1")]).status_code == 404


def test_reorder_positions(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    add_position(client, headers, portfolio["id"], bought_at="2026-09-01")
    add_position(client, headers, portfolio["id"], symbol="ETH", buy_price="2000")
    add_position(client, headers, portfolio["id"], bought_at="2026-09-02")
    view = add_position(client, headers, portfolio["id"], bought_at="2026-09-03")
    ids = [p["id"] for p in positions_of(view)]

    new_order = [ids[2], ids[0], ids[1]]
    view = client.put(f"/api/portfolios/{portfolio['id']}/positions/order",
                      json={"position_ids": new_order}, headers=headers).json()
    assert [p["id"] for p in positions_of(view)] == new_order
    assert len(positions_of(view, "ETH")) == 1

    bad = client.put(f"/api/portfolios/{portfolio['id']}/positions/order",
                     json={"position_ids": [ids[0], ids[0]]}, headers=headers)
    assert bad.status_code == 400


def test_update_and_delete_position(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    view = add_position(client, headers, portfolio["id"], fee_coin="0")
    position_id = view["coins"][0]["positions"][0]["id"]
    sell(client, headers, portfolio["id"], [(position_id, "0.6")])

    body = {"symbol": "BTC", "buy_price": "48000", "quantity": "0.5", "fee_coin": "0", "bought_at": "2026-09-01"}
    assert client.put(f"/api/positions/{position_id}", json=body, headers=headers).status_code == 400  # < already sold

    body["quantity"] = "0.8"
    view = client.put(f"/api/positions/{position_id}", json=body, headers=headers).json()
    assert view["coins"][0]["positions"][0]["buy_price"] == "48000"

    view = client.delete(f"/api/positions/{position_id}", headers=headers).json()
    assert view["coins"] == []


def test_validation(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    url = f"/api/portfolios/{portfolio['id']}/positions"
    base = {"symbol": "BTC", "buy_price": "1", "quantity": "1", "bought_at": "2026-09-01"}
    assert client.post(url, json=base | {"buy_price": "-1"}, headers=headers).status_code == 422
    assert client.post(url, json=base | {"fee_coin": "1"}, headers=headers).status_code == 422
    assert client.post(url, json=base | {"symbol": "BT C"}, headers=headers).status_code == 422
    assert client.post("/api/portfolios", json={"name": "   "}, headers=headers).status_code == 422


def test_other_users_cannot_access(client, monkeypatch):
    admin = login(client)
    portfolio = create_portfolio(client, admin)
    view = add_position(client, admin, portfolio["id"])
    position_id = view["coins"][0]["positions"][0]["id"]

    monkeypatch.setattr(auth, "settings", replace(auth.settings, allow_registration=True))
    token = client.post("/api/auth/register", json={
        "username": "obcy", "email": "obcy@example.com", "password": "password123"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}

    assert client.get(f"/api/portfolios/{portfolio['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/portfolios/{portfolio['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/positions/{position_id}", headers=other).status_code == 404
    assert client.get("/api/portfolios", headers=other).json() == []
