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
