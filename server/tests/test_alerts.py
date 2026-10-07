from decimal import Decimal as D

import pytest

from database.db import SessionLocal
from indicators.base import OHLCV
from schemas.alerts import Condition
from services.alerts import check_alerts, evaluate, evaluation_point
from services.candle_service import CandleSeries
from services.providers.base import Candle
from tests.conftest import login

H = 3600
NOW = 1000 * H + 60          # one minute into the forming candle


class Market:
    """Fake candle service with editable closes; the last candle is the forming one."""

    def __init__(self, closes):
        self.closes = list(closes)

    def get_candles(self, symbol, interval, start, end, max_candles=5000):
        first = end // H * H - (len(self.closes) - 1) * H          # candles end at the requested time
        # open = previous close (the forming candle opened at the last closed price)
        opens = self.closes[:1] + self.closes[:-1]
        candles = [Candle(first + i * H, D(str(o)), D(str(max(o, c))), D(str(min(o, c))), D(str(c)), D(1))
                   for i, (o, c) in enumerate(zip(opens, self.closes))]
        return CandleSeries(symbol, interval, "fake", [c for c in candles if c.time >= start - H][-max_candles:])


def cond(data):
    return Condition.model_validate(data)


PRICE = {"type": "price"}


def value(v):
    return {"type": "value", "value": v}


def test_evaluate_price_and_closed_candle():
    data = OHLCV.from_candles(Market([100, 105, 111]).get_candles("BTC", "1h", 0, NOW).candles)
    closed = evaluation_point(data, "1h", "bar_close", NOW)[1]
    assert closed == 1 and evaluation_point(data, "1h", "intrabar", NOW)[1] == 2   # forming candle excluded by default
    at_open, index = evaluation_point(data, "1h", "bar_open", NOW)
    assert index == 2 and at_open.close[2] == 105 and at_open.high[2] == 105        # new candle = its open only
    assert evaluate(cond({"left": PRICE, "op": ">", "right": value(110)}), data, closed).met is False
    result = evaluate(cond({"left": PRICE, "op": ">", "right": value(110)}), data, 2)
    assert result.met is True and result.left == 111 and result.right == 110


def test_evaluate_indicator_and_crossing():
    closes = [100] * 20 + [101, 102, 103]
    data = OHLCV.from_candles(Market(closes).get_candles("BTC", "1h", 0, NOW).candles)
    sma3 = {"type": "indicator", "id": "sma", "params": {"length": 3}, "output": "sma"}
    crossing = cond({"left": PRICE, "op": "crosses_above", "right": sma3})
    assert evaluate(crossing, data, 20).met is True                           # 101 crosses above SMA(3)=100.33
    assert evaluate(crossing, data, 21).met is False                          # already above - no new cross
    rsi = {"type": "indicator", "id": "rsi", "params": {"length": 2}, "output": "rsi"}
    assert evaluate(cond({"left": rsi, "op": ">=", "right": value(100)}), data, 22).met is True


def create(client, headers, **overrides):
    body = {"symbol": "btc", "interval": "1h", "condition": {"left": PRICE, "op": ">", "right": value(110)}} | overrides
    response = client.post("/api/alerts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_alert_fires_on_edge_once_and_repeat(client):
    headers = login(client)
    once = create(client, headers)
    repeat = create(client, headers, mode="repeat")
    market = Market([100, 105, 106])

    with SessionLocal() as db:                                                 # every step = the next hour
        assert check_alerts(db, market, NOW) == []                             # 105 (closed) not > 110
        market.closes += [112, 113]
        assert len(check_alerts(db, market, NOW + H)) == 2                     # closed 112 -> both fire
        market.closes += [114]
        assert check_alerts(db, market, NOW + 2 * H) == []                     # still met -> no spam
        market.closes += [108]
        check_alerts(db, market, NOW + 3 * H)                                  # closed 114 - still met
        market.closes += [109]
        check_alerts(db, market, NOW + 4 * H)                                  # closed 108 -> repeat re-arms
        market.closes += [116]
        fired = check_alerts(db, market, NOW + 5 * H)                          # closed 109 - not met
        market.closes += [117]
        fired += check_alerts(db, market, NOW + 6 * H)                         # closed 116 -> repeat fires
        assert [e.alert_id for e in fired] == [repeat["id"]]                   # "once" was deactivated

    alerts = {a["id"]: a for a in client.get("/api/alerts", headers=headers).json()}
    assert alerts[once["id"]]["active"] is False and alerts[repeat["id"]]["active"] is True
    assert alerts[repeat["id"]]["unseen_events"] == 2

    events = client.get("/api/alerts/events?unseen_only=true", headers=headers).json()
    assert len(events) == 3 and events[0]["details"]["price"] == 116 and events[0]["symbol"] == "BTC"
    client.post("/api/alerts/events/seen", json={"ids": [events[0]["id"]]}, headers=headers)
    assert len(client.get("/api/alerts/events?unseen_only=true", headers=headers).json()) == 2
    client.post("/api/alerts/events/seen", json={}, headers=headers)
    assert client.get("/api/alerts/events?unseen_only=true", headers=headers).json() == []

    # Re-activating resets the state so the alert can fire again.
    patched = client.patch(f"/api/alerts/{once['id']}", json={"active": True}, headers=headers).json()
    assert patched["active"] is True and patched["last_state"] is None


def test_alert_validation_preview_and_isolation(client, monkeypatch):
    import api.routes.alerts as routes
    monkeypatch.setattr(routes, "candle_service", Market([100, 120, 121]))
    headers = login(client)

    bad = client.post("/api/alerts", headers=headers, json={"symbol": "BTC", "condition": {
        "left": value(1), "op": ">", "right": value(2)}})
    assert bad.status_code == 400 and bad.json()["code"] == "alerts.invalid_condition"
    bad = client.post("/api/alerts", headers=headers, json={"symbol": "BTC", "condition": {
        "left": {"type": "indicator", "id": "rsi", "output": "nope"}, "op": "<", "right": value(30)}})
    assert bad.json()["code"] == "alerts.invalid_condition"
    bad = client.post("/api/alerts", headers=headers, json={"symbol": "BTC", "condition": {
        "left": {"type": "indicator", "id": "nope", "output": "x"}, "op": "<", "right": value(30)}})
    assert bad.json()["code"] == "indicators.not_found"

    alert = create(client, headers)
    check = client.get(f"/api/alerts/{alert['id']}/check", headers=headers).json()
    assert check == {"met": True, "left": 120.0, "right": 110.0, "price": 120.0, "candle_time": check["candle_time"]}

    # Rsi defaults filled in when stored.
    rsi = create(client, headers, condition={"left": {"type": "indicator", "id": "rsi", "output": "rsi"}, "op": "<",
                                             "right": value(30)})
    assert rsi["condition"]["left"]["params"] == {"length": 14, "source": "close"}

    assert client.delete(f"/api/alerts/{alert['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/alerts/{alert['id']}/check", headers=headers).status_code == 404


def test_trigger_modes(client):
    headers = login(client)
    close = create(client, headers, mode="repeat")                       # bar_close (default)
    opening = create(client, headers, mode="repeat", trigger="bar_open")
    intrabar = create(client, headers, mode="repeat", trigger="intrabar")
    market = Market([100, 105, 108])                                      # forming candle at 108

    def fired(now):
        with SessionLocal() as db:
            return sorted(e.alert_id for e in check_alerts(db, market, now))

    assert fired(NOW) == []
    market.closes = [100, 105, 112]                    # price jumps inside the forming candle
    assert fired(NOW + 60) == [intrabar["id"]]         # only "immediately"
    market.closes = [100, 105, 109]
    fired(NOW + 120)                                   # back below - intrabar re-arms
    market.closes = [100, 105, 113]
    assert fired(NOW + 180) == []                      # met again in the SAME candle: max one trigger per candle

    # Next hour: the 113 candle closed, a new one opens at 113 and drops to 104.
    market.closes = [100, 105, 113, 104]
    nxt = NOW + H
    assert fired(nxt) == [close["id"], opening["id"]]  # closed candle 113 > 110; new candle opened at 113
    assert fired(nxt + 60) == []                       # both evaluated once per candle - no repeat

    alerts = {a["id"]: a for a in client.get("/api/alerts", headers=headers).json()}
    assert alerts[opening["id"]]["trigger"] == "bar_open" and alerts[close["id"]]["trigger"] == "bar_close"

    # Changing the trigger re-arms the alert.
    patched = client.patch(f"/api/alerts/{close['id']}", json={"trigger": "intrabar"}, headers=headers).json()
    assert patched["trigger"] == "intrabar" and patched["last_state"] is None
    bad = client.post("/api/alerts", headers=headers, json={"symbol": "BTC", "trigger": "sometimes", "condition": {
        "left": PRICE, "op": ">", "right": value(1)}})
    assert bad.status_code == 422
