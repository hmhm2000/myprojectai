from dataclasses import replace
from decimal import Decimal as D

import auth
from indicators.service import compute_indicator, map_to_chart
from services.candle_service import CandleSeries
from services.providers.base import INTERVAL_SECONDS, Candle
from tests.conftest import login

H, DAY = 3600, 86400


def test_map_to_chart_has_no_lookahead():
    days = [0, DAY, 2 * DAY]                         # day 0 and day 1 closed, day 2 forming
    values = [10.0, 20.0, 30.0]
    now = 2 * DAY + 5 * H + 30                       # 05:00 of day 2
    chart = list(range(DAY - 2 * H, 2 * DAY + 5 * H + 1, H))   # 22:00 of day 0 ... 05:00 of day 2
    mapped = dict(zip(chart, map_to_chart(days, DAY, values, chart, H, now)))

    assert mapped[DAY - 2 * H] is None               # day 0 not closed yet at 22:00 -> nothing earlier
    assert mapped[DAY - H] == 10.0                   # 23:00 candle ends when day 0 closes -> day 0 value
    assert mapped[DAY + 10 * H] == 10.0              # inside day 1: still the last CLOSED day (no look-ahead)
    assert mapped[2 * DAY - H] == 20.0               # last hour of day 1 -> day 1 value
    assert mapped[2 * DAY + 3 * H] == 20.0           # closed 03:00 candle of day 2: last closed day, not live
    assert mapped[2 * DAY + 5 * H] == 30.0           # only the current chart candle shows the live day-2 value


class MultiTF:
    """Fake candle service: price = number of hours since 0, for any interval."""

    def get_candles(self, symbol, interval, start, end, max_candles=5000):
        step = INTERVAL_SECONDS[interval]
        first = start // step * step
        candles = [Candle(t, D(t // H), D(t // H), D(t // H), D(t // H + step // H - 1), D(1))
                   for t in range(max(first, 0), end + 1, step)]
        return CandleSeries(symbol, interval, "fake", candles[-max_candles:])


def test_compute_on_own_interval():
    now = 30 * DAY + 12 * H + 60
    start = 30 * DAY
    result = compute_indicator(MultiTF(), "sma", {"length": 2}, "BTC", "1h", start, now, now, indicator_interval="1d")
    assert result.time[0] == start and result.time[1] - result.time[0] == H      # chart (1h) candles
    # SMA(2) of daily closes: day k close = 24k + 23 -> at 30d 00:00 the last closed day is 29
    day_close = lambda k: 24 * k + 23
    assert result.outputs["sma"][0] == (day_close(28) + day_close(29)) / 2
    same = compute_indicator(MultiTF(), "sma", {"length": 2}, "BTC", "1h", start, now, now)
    assert same.outputs["sma"][0] != result.outputs["sma"][0]


def test_chart_indicator_settings_per_user(client, monkeypatch):
    headers = login(client)
    created = client.post("/api/chart-indicators", json={"indicator_id": "sma", "params": {"length": 100},
                                                          "interval": "1d"}, headers=headers).json()
    assert created["params"] == {"length": 100, "source": "close"} and created["interval"] == "1d"
    rsi = client.post("/api/chart-indicators", json={"indicator_id": "rsi"}, headers=headers).json()
    assert rsi["params"] == {"length": 14, "source": "close"} and rsi["interval"] is None   # conventional defaults

    updated = client.put(f"/api/chart-indicators/{rsi['id']}", json={"params": {"length": 21}, "interval": "4h",
                                                                     "visible": False}, headers=headers).json()
    assert updated["params"]["length"] == 21 and updated["interval"] == "4h" and updated["visible"] is False
    follow = client.put(f"/api/chart-indicators/{rsi['id']}", json={"follow_chart": True}, headers=headers).json()
    assert follow["interval"] is None
    assert rsi["axis_value"] is None                                       # default for the indicator
    shown = client.put(f"/api/chart-indicators/{rsi['id']}", json={"axis_value": True}, headers=headers).json()
    assert shown["axis_value"] is True and shown["params"]["length"] == 21  # other settings kept

    client.put(f"/api/chart-indicators/{created['id']}", json={"axis_value": False}, headers=headers)
    reset = client.post(f"/api/chart-indicators/{created['id']}/reset", headers=headers).json()
    assert reset["axis_value"] is None
    assert reset["params"] == {"length": 20, "source": "close"} and reset["interval"] is None

    bad = client.post("/api/chart-indicators", json={"indicator_id": "sma", "params": {"length": 0}}, headers=headers)
    assert bad.json()["code"] == "indicators.invalid_param"
    bad = client.post("/api/chart-indicators", json={"indicator_id": "sma", "interval": "2x"}, headers=headers)
    assert bad.json()["code"] == "candles.invalid_interval"

    assert [i["indicator_id"] for i in client.get("/api/chart-indicators", headers=headers).json()] == ["sma", "rsi"]

    # Another user has their own (empty) set and can't touch these.
    monkeypatch.setattr(auth, "settings", replace(auth.settings, allow_registration=True))
    token = client.post("/api/auth/register", json={"username": "other", "email": "o@example.com",
                                                    "password": "password123"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/chart-indicators", headers=other).json() == []
    assert client.delete(f"/api/chart-indicators/{rsi['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/chart-indicators/{rsi['id']}", headers=headers).status_code == 204
