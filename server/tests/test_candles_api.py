from tests.conftest import login
from tests.test_position_timing import FakeCandles


def test_candles_endpoint(client, monkeypatch):
    import api.routes.candles as routes
    fake = FakeCandles(["100", "101"])
    monkeypatch.setattr(routes, "candle_service", fake)
    headers = login(client)

    body = client.get("/api/candles?symbol=btc&interval=1h&limit=5", headers=headers).json()
    assert body["symbol"] == "BTC" and body["source"] == "fake"
    assert len(body["candles"]) == 5
    times = [c["time"] for c in body["candles"]]
    assert times == sorted(times) and all(b - a == 3600 for a, b in zip(times, times[1:]))
    assert body["candles"][-1]["closed"] is False and body["candles"][0]["closed"] is True

    older = client.get(f"/api/candles?symbol=BTC&interval=1h&limit=3&before={times[0]}", headers=headers).json()
    assert [c["time"] for c in older["candles"]] == [times[0] - 3 * 3600, times[0] - 2 * 3600, times[0] - 3600]
    assert client.get("/api/candles?symbol=BTC", headers={}).status_code == 401
