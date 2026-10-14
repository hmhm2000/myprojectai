from tests.conftest import login


def test_favorite_lists_flow(client):
    headers = login(client)
    created = client.post("/api/favorite-lists", json={"name": "Memy"}, headers=headers)
    assert created.status_code == 201
    list_id = created.json()["id"]

    response = client.post(f"/api/favorite-lists/{list_id}/coins", json={"symbol": "spx"}, headers=headers)
    assert response.status_code == 201
    assert [c["symbol"] for c in response.json()["coins"]] == ["SPX"]

    client.post(f"/api/favorite-lists/{list_id}/coins", json={"symbol": "PEPE"}, headers=headers)
    duplicate = client.post(f"/api/favorite-lists/{list_id}/coins", json={"symbol": "SPX"}, headers=headers)
    assert duplicate.status_code == 409

    response = client.delete(f"/api/favorite-lists/{list_id}/coins/spx", headers=headers)
    assert [c["symbol"] for c in response.json()["coins"]] == ["PEPE"]

    renamed = client.patch(f"/api/favorite-lists/{list_id}", json={"name": "Memecoiny"}, headers=headers)
    assert renamed.json()["name"] == "Memecoiny"

    client.post("/api/favorite-lists", json={"name": "Duże"}, headers=headers)
    lists = client.get("/api/favorite-lists", headers=headers).json()
    assert [l["name"] for l in lists] == ["Memecoiny", "Duże"]

    assert client.delete(f"/api/favorite-lists/{list_id}", headers=headers).status_code == 204
    assert [l["name"] for l in client.get("/api/favorite-lists", headers=headers).json()] == ["Duże"]


def test_my_coins_lists_favorites_and_held_coins(client):
    headers = login(client)
    list_id = client.post("/api/favorite-lists", json={"name": "Moje"}, headers=headers).json()["id"]
    for symbol in ("ETH", "SPX", "ETH"):
        client.post(f"/api/favorite-lists/{list_id}/coins", json={"symbol": symbol}, headers=headers)
    portfolio = client.post("/api/portfolios", json={"name": "P"}, headers=headers).json()
    for symbol in ("BTC", "DOGE"):
        client.post(f"/api/portfolios/{portfolio['id']}/positions", headers=headers, json={
            "symbol": symbol, "buy_price": "1", "quantity": "2", "bought_at": "2026-07-01T10:00:00"})
    doge = next(p["id"] for c in client.get(f"/api/portfolios/{portfolio['id']}", headers=headers).json()["coins"]
                if c["symbol"] == "DOGE" for p in c["positions"])
    client.post(f"/api/portfolios/{portfolio['id']}/sales", headers=headers, json={
        "price": "1", "sold_at": "2026-07-02T10:00:00", "allocations": [{"position_id": doge, "quantity": "2"}]})
    mine = client.get("/api/my-coins", headers=headers).json()
    assert mine == {"favorites": ["ETH", "SPX"], "held": ["BTC"]}        # DOGE fully sold
