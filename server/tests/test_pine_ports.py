import math
import random
from decimal import Decimal as D

import pytest

from core.errors import AppError
from indicators.base import OHLCV, get_indicator, validate_params
from indicators.context import DataContext
from indicators.core import atr, ema, offset_left, valuewhen
from indicators.custom.vmc_cipher_b import find_divs, schaff
from services.candle_service import CandleSeries
from services.intervals import parse
from services.providers.base import Candle

H = 3600


def walk(n, seed=1, step=H):
    """Random-walk candles with real open/high/low/close."""
    rnd = random.Random(seed)
    price, rows = 100.0, []
    for i in range(n):
        o = price
        c = max(1.0, o * (1 + rnd.gauss(0, 0.01)))
        h, l = max(o, c) * (1 + abs(rnd.gauss(0, 0.004))), min(o, c) * (1 - abs(rnd.gauss(0, 0.004)))
        rows.append((i * step, o, h, l, c))
        price = c
    t, o, h, l, c = (list(x) for x in zip(*rows))
    return OHLCV(t, o, h, l, c, [1.0] * n)


def tail(data, count):
    return OHLCV(data.time[-count:], data.open[-count:], data.high[-count:], data.low[-count:],
                 data.close[-count:], data.volume[-count:])


def test_kcb_bands():
    data = walk(300)
    kcb = get_indicator("kcb")
    params = validate_params(kcb, {})
    assert params == {"length": 20, "atr_length": 10, "mult": 1.0, "source": "close", "basis_color": "#e4e4e7",
                      "band1_color": "#4caf50", "band2_color": "#ff5252", "band3_color": "#2196f3"}
    out = kcb.compute(data, params)
    ma, rng = ema(data.close, 20), atr(data.high, data.low, data.close, 10)
    assert out["basis"][-1] == pytest.approx(ma[-1])
    for k in (1, 2, 3):
        assert out[f"upper_{k}"][-1] == pytest.approx(ma[-1] + k * rng[-1])
        assert out[f"lower_{k}"][-1] == pytest.approx(ma[-1] - k * rng[-1])
    wider = kcb.compute(data, validate_params(kcb, {"mult": 2}))
    assert wider["upper_1"][-1] == pytest.approx(ma[-1] + 2 * rng[-1])


@pytest.mark.parametrize("indicator_id", ["kcb", "vmc_cipher_b"])
def test_warmup_makes_results_independent_of_history_start(indicator_id):
    full = walk(1500)
    indicator = get_indicator(indicator_id)
    params = validate_params(indicator, {"tc_line": True} if indicator_id == "vmc_cipher_b" else {})
    part = tail(full, indicator.warmup(params) + 50)
    a, b = indicator.compute(full, params), indicator.compute(part, params)
    checked = 0
    for name, values in a.items():
        if ":" in name or values[-1] is None:
            continue
        assert b[name][-1] == pytest.approx(values[-1], rel=1e-3, abs=1e-3), name
        checked += 1
    assert checked >= 7


def test_vmc_outputs_and_signals_on_real_like_data():
    data = walk(1500, seed=7)
    vmc = get_indicator("vmc_cipher_b")
    out = vmc.compute(data, validate_params(vmc, {}))
    assert all(len(v) == len(data.time) for v in out.values())
    assert {o.name for o in vmc.outputs if o.plot != "band"} <= set(out)
    assert -150 < out["wt2"][-1] < 150 and 0 <= out["rsi"][-1] <= 100 and 0 <= out["stoch_k"][-1] <= 100
    # a "buy" signal (green circle) = WT cross up while oversold; the cross dot is on every cross
    for i, buy in enumerate(out["buy"]):
        if buy:
            assert out["cross_dot"][i] is not None and out["wt2"][i] <= -53 and out["buy_dot"][i] == -107
    assert any(out["buy_small"]) and any(out["sell_small"])
    hidden = vmc.compute(data, validate_params(vmc, {"wt_show": False, "rsi_show": False}))
    assert set(hidden["wt1"]) == {None} and set(hidden["rsi"]) == {None}
    assert hidden["buy"] == out["buy"]                                   # alert conditions don't depend on drawing


def test_divergence_detection():
    # src makes a lower high (fractal at index 7: 50 vs 60 at index 2) while the price makes a higher high
    src = [10, 30, 60, 30, 10, 20, 40, 50, 40, 20]
    high = [1, 2, 10, 2, 1, 2, 3, 12, 3, 2]
    low = [0] * 10
    divs = find_divs(src, high, low, 45, -65, True)
    assert divs["top"][4] and divs["top"][9]                             # confirmed 2 candles after the top
    assert divs["bear"][9] and not divs["bear"][4]                       # second top: regular bearish divergence
    assert valuewhen([0, 1, 0, 0], [5, 6, 7, 8]) == [None, 6, 6, 6]
    assert offset_left([1, 2, 3, 4], 2) == [3, 4, None, None]


def test_schaff_is_bounded():
    data = walk(600)
    tc = schaff(data.close, 10, 23, 50, 0.5)
    assert all(v is not None for v in tc)                                # Pine nz(): defined from the first candle
    assert all(-1e-9 <= v <= 100 + 1e-9 for v in tc[200:])


def test_new_param_types():
    vmc = get_indicator("vmc_cipher_b")
    p = validate_params(vmc, {"wt_show": False, "wt1_color": "#AABBCC80", "sommi_vwap_tf": "12H", "ob_level": "70"})
    assert p["wt_show"] is False and p["wt1_color"] == "#aabbcc80" and p["sommi_vwap_tf"] == "12h" and p["ob_level"] == 70
    assert p["os_level"] == -53 and p["stoch_use_log"] is True                    # defaults kept
    for bad in ({"wt_show": "yes"}, {"wt1_color": "red"}, {"sommi_vwap_tf": "7x"}, {"ob_level": 1.5},
                {"wt_channel_len": True}):
        with pytest.raises(AppError):
            validate_params(vmc, bad)


class Hourly:
    """Fake candle service: hourly candles of a random walk, aggregated for other intervals."""

    def __init__(self, data):
        self.data = data

    def get_candles(self, symbol, interval, start, end, max_candles=5000):
        from services.intervals import aggregate

        spec = parse(interval)
        candles = [Candle(t, D(str(o)), D(str(h)), D(str(l)), D(str(c)), D(1))
                   for t, o, h, l, c in zip(self.data.time, self.data.open, self.data.high, self.data.low, self.data.close)
                   if t <= end]
        if spec.name != "1h":
            candles = aggregate(candles, spec)
        return CandleSeries(symbol, spec.name, "fake", [c for c in candles if c.time >= spec.bucket_start(start)][-max_candles:])


def test_higher_timeframe_without_lookahead():
    hourly = walk(24 * 20)
    now = hourly.time[-1] + 1800                                         # inside the last hour
    service = Hourly(hourly)
    base = OHLCV.from_candles(service.get_candles("BTC", "1h", 0, now).candles, DataContext(service, "BTC", "1h", now))
    four = base.security("4h")
    mapped = four.map(four.data.close)
    t = base.time.index(4 * H * 10 + H)                                  # 01:00 inside the 4h candle starting 00:00
    # candles inside a 4h candle see the PREVIOUS (closed) 4h candle, never the future close
    assert mapped[t] == four.data.close[four.data.time.index(4 * H * 9)]
    assert OHLCV(base.time, base.open, base.high, base.low, base.close, base.volume).security("4h") is None

    # VMC with Sommi diamond/flag on: computes with the higher timeframes
    vmc = get_indicator("vmc_cipher_b")
    out = vmc.compute(base, validate_params(vmc, {"sommi_show_vwap": True}))
    assert out["sommi_vwap"][-1] is not None


def test_alert_on_pine_signal(client):
    from tests.conftest import login

    headers = login(client)
    body = {"symbol": "BTC", "interval": "4h", "trigger": "bar_close", "condition": {
        "left": {"type": "indicator", "id": "vmc_cipher_b", "params": {"os_level": -60}, "output": "buy"},
        "op": "==", "right": {"type": "value", "value": 1}}}
    created = client.post("/api/alerts", json=body, headers=headers)
    assert created.status_code == 201, created.text
    params = created.json()["condition"]["left"]["params"]
    assert params["os_level"] == -60 and params["wt_channel_len"] == 9          # defaults stored with the alert
    body["condition"]["left"]["output"] = "kd_fill"                             # a fill is not a value
    assert client.post("/api/alerts", json=body, headers=headers).json()["code"] == "alerts.invalid_condition"


def test_macd_hist_colors():
    closes = [100 + 5 * math.sin(i / 6) for i in range(300)]
    data = OHLCV(list(range(300)), closes, closes, closes, closes, [1.0] * 300)
    ind = get_indicator("macd_hist")
    out = ind.compute(data, validate_params(ind, {}))
    assert out["histogram"] == out["macd"]                               # MT4: histogram = MACD line
    for i in range(60, 300):
        h, prev, c = out["histogram"][i], out["histogram"][i - 1], out["histogram:color"][i]
        expected = 0 if h >= 0 and h > prev else 1 if h >= 0 and h < prev else 2 if h < 0 and h < prev else 3
        assert c == expected


class PerpMarket:
    """Fake candle service: spot candles from `spot`, perpetual from `perp` (None = not listed)."""

    def __init__(self, spot, perp):
        self.spot, self.perp = spot, perp

    def get_candles(self, symbol, interval, start, end, max_candles=5000, market="spot"):
        src = self.perp if market == "perp" else self.spot
        if src is None:
            raise AppError(404, "candles.symbol_not_found", "no perp")
        candles = [Candle(t, D(str(o)), D(str(h)), D(str(l)), D(str(c)), D(str(v)))
                   for t, o, h, l, c, v in zip(src.time, src.open, src.high, src.low, src.close, src.volume)]
        return CandleSeries(symbol, interval, "fake", candles)


def flat_candles(volumes, bull=True):
    n = len(volumes)
    o, c = ([100.0] * n, [101.0] * n) if bull else ([101.0] * n, [100.0] * n)
    return OHLCV([i * H for i in range(n)], o, [102.0] * n, [99.0] * n, c, list(volumes))


def test_pvsra_vector_candles_and_perp_volume():
    ind = get_indicator("pvsra")
    spot = flat_candles([10] * 12 + [16, 25, 10])
    spot.high[12], spot.low[12] = 101.0, 100.0         # narrow candle: 160% volume but spread x volume not the highest
    perp = flat_candles([10] * 12 + [10, 10, 30], bull=False)
    now = 20 * H

    def run(spot_data, perp_data, **params):
        ctx = DataContext(PerpMarket(spot_data, perp_data), "BTC", "1h", now)
        base = OHLCV(spot_data.time, spot_data.open, spot_data.high, spot_data.low, spot_data.close, spot_data.volume, ctx)
        return ind.compute(base, validate_params(ind, params))

    own = run(spot, perp, use_perp_volume=False)
    assert own["volume:color"][12:15] == [2, 0, 4]                 # 160% -> 150 bull, 250% -> 200 bull, normal
    assert own["rising_bull"][12] == 1.0 and own["peak_bull"][13] == 1.0 and own["vector"][14] == 0.0
    perp_out = run(spot, perp)                                     # default: the perpetual's volume
    assert perp_out["volume"][-1] == 30 and perp_out["volume:color"][-1] == 1 and perp_out["peak_bear"][-1] == 1.0
    fallback = run(spot, None)                                     # no perpetual -> chart's own candles
    assert fallback["volume"] == own["volume"]
    hidden = run(spot, None, candle_colors=False)
    assert set(hidden["candles"]) == {None}


def test_oi_rsi_signals(monkeypatch):
    import services.open_interest as oi_module

    n = 200
    rising = [100 + i for i in range(n)]                           # price only rises -> RSI 100
    data_spot = OHLCV([i * H for i in range(n)], rising, rising, rising, rising, [1.0] * n)
    points = [(i * H, 1000.0 - i) for i in range(n + 1)]           # OI only falls -> OI RSI 0

    calls = []
    def fake_get(symbol, period, start, end):
        calls.append((symbol, period))
        return [p for p in points if start <= p[0] <= end]
    monkeypatch.setattr(oi_module.open_interest_service, "get", fake_get)

    ctx = DataContext(PerpMarket(data_spot, None), "BTC", "1h", n * H)
    base = OHLCV(data_spot.time, rising, rising, rising, rising, [1.0] * n, ctx)
    ind = get_indicator("oi_rsi")
    out = ind.compute(base, validate_params(ind, {}))
    assert out["oi_rsi"][-1] == 0 and out["rsi"][-1] == 100
    assert out["sell"][-1] == 1.0 and out["sell_background"][-1] == 1.0 and out["combined"][-1] == 1.0
    assert out["buy"][-1] == 0.0
    assert calls[-1] == ("BTC", "1h")
    ind.compute(base, validate_params(ind, {"override_symbol": True, "symbol": "eth"}))
    assert calls[-1] == ("ETH", "1h")
    no_context = ind.compute(data_spot, validate_params(ind, {}))  # no OI available -> OI lines empty, RSI works
    assert set(no_context["oi_rsi"]) == {None} and no_context["rsi"][-1] == 100


def test_open_interest_close_is_value_at_candle_end(monkeypatch):
    import services.open_interest as oi_module

    monkeypatch.setattr(oi_module.open_interest_service, "get",
                        lambda symbol, period, start, end: [(t, float(t // H)) for t in range(0, 10 * H + 1, H)])
    now = 9 * H + 1800
    ctx = DataContext(None, "BTC", "1h", now)
    base = OHLCV([i * H for i in range(10)], [1.0] * 10, [1.0] * 10, [1.0] * 10, [1.0] * 10, [1.0] * 10, ctx)
    oi = base.open_interest()
    assert oi[0] == 1.0 and oi[8] == 9.0                           # candle 08:00-09:00 closes with OI at 09:00
    assert oi[9] == 9.0                                            # forming candle: latest known value (not the future)


def test_bybit_open_interest_paging(monkeypatch):
    import services.open_interest as oi_module

    pages = {None: ([{"openInterest": "5", "timestamp": "7200000"}, {"openInterest": "4", "timestamp": "3600000"}], "next"),
             "next": ([{"openInterest": "3", "timestamp": "0"}], "")}
    def fake_get_json(url, params, timeout, exchange):
        rows, cursor = pages[params.get("cursor")]
        assert params["category"] == "linear" and params["symbol"] == "BTCUSDT" and params["intervalTime"] == "1h"
        return {"retCode": 0, "result": {"list": rows, "nextPageCursor": cursor}}
    monkeypatch.setattr(oi_module, "get_json", fake_get_json)
    assert oi_module.fetch_bybit("BTC", "USDT", "1h", 0, 7200, 5) == [(0, 3.0), (3600, 4.0), (7200, 5.0)]
