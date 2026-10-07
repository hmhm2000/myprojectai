from tests.conftest import login


def test_prices_require_login(client):
    assert client.get("/api/prices").status_code == 401


def test_get_prices_uses_cache(client, fake_prices):
    headers = login(client)
    body = client.get("/api/prices", headers=headers).json()
    assert body["quote_currency"] == "USDT"
    assert body["stale"] is False
    assert body["prices"]["BTC"] == {"price": "60000", "change_24h_pct": "1.5", "source": "okx", "stale": False}
    assert body["prices"]["SPX"]["source"] == "bybit"

    calls = fake_prices.okx.calls
    client.get("/api/prices", headers=headers)
    client.get("/api/prices?symbols=btc,spx", headers=headers)
    assert fake_prices.okx.calls == calls  # bez nowych zapytań do giełdy


def test_symbols_filter(client):
    headers = login(client)
    body = client.get("/api/prices?symbols=btc, SPX ,NOPE", headers=headers).json()
    assert set(body["prices"]) == {"BTC", "SPX"}


def test_force_refresh_limit(client, fake_prices):
    headers = login(client)
    client.get("/api/prices", headers=headers)

    first = client.post("/api/prices/refresh", headers=headers)
    assert first.status_code == 200

    second = client.post("/api/prices/refresh", headers=headers)
    assert second.status_code == 429
    assert second.json()["retry_after"] == 10
    assert second.headers["Retry-After"] == "10"
