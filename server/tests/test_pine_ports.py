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
