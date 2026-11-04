"""Harmonic patterns: ratios of the standard patterns, confirmation, trade tracking, drawings for the chart."""
import pytest

from indicators.base import OHLCV, get_indicator, validate_params
from indicators.context import DataContext
from indicators.custom import harmonics
from indicators.custom.harmonics import _reach, _target, _zigzag, compute
from indicators.service import compute_indicator

H = 3600
ALL_OFF = {"bat": False, "butterfly": False, "crab": False, "shark": False, "cypher": False}


def candles(turns, after=()):
    """Candles running straight between price `turns` (bar, price), then `after` closes."""
    prices = []
    for (bar, price), (next_bar, next_price) in zip(turns, turns[1:]):
        prices += [price + (next_price - price) * k / (next_bar - bar) for k in range(next_bar - bar)]
    prices += [turns[-1][1], *after]
    return OHLCV([i * H for i in range(len(prices))], prices, [c + .01 for c in prices], [c - .01 for c in prices],
                 prices, [1.0] * len(prices))


# a bullish Gartley: AB = .618 XA, BC = .618 AB, AD = .786 XA
X, A = 100.0, 200.0
B = A - .618 * (A - X)
C = B + .618 * (A - B)
D = A - .786 * (A - X)
GARTLEY = [(0, 150), (10, X), (30, A), (45, B), (57, C), (75, D)]


def params(**changes):
    return validate_params(get_indicator("harmonics"), {**ALL_OFF, **changes})


def test_a_pivot_of_every_length_comes_from_one_pass():
    values = [1, 2, 3, 9, 3, 2, 1, 2, 3]
    assert _reach(values, 1, 5)[3] == 3
    assert _reach(values, -1, 5)[6] == 2
    points = _zigzag(values, values, _reach(values, 1, 5), _reach(values, -1, 5), 2)
    assert [(bar, is_high) for bar, _, is_high in points] == [(3, True), (6, False)]


def test_gartley_is_found_with_its_points_and_levels():
    data = candles(GARTLEY, after=[D + 2 * i for i in range(1, 12)])
    out = compute(data, params())
    pattern = next(p for p in out["drawings"] if p["kind"] == "gartley")
    assert pattern["bull"] is True and pattern["score"] > 90
    assert [p[0] // H for p in pattern["points"]] == [10, 30, 45, 57, 75]
    assert abs(pattern["points"][-1][1] - D) < .1
    assert pattern["prz"][0] < D < pattern["prz"][1]
    assert abs(pattern["t1"] - (D + .618 * (A - D))) < .1
    assert out["bull_pattern"][76] == 1.0 and sum(out["bull_pattern"]) == 1


def test_nothing_is_known_before_the_confirmation_of_d():
    full = candles(GARTLEY, after=[D + 2 * i for i in range(1, 12)])
    cut = OHLCV(full.time[:76], full.open[:76], full.high[:76], full.low[:76], full.close[:76], full.volume[:76])
    assert not compute(cut, params())["drawings"]


def test_a_pattern_past_the_prz_is_not_a_pattern():
    deep = [*GARTLEY[:-1], (75, X - 30)]
    assert not [p for p in compute(candles(deep, after=[60, 62, 64, 66]), params())["drawings"] if p["kind"] == "gartley"]


def test_trade_reaches_the_targets():
    rise = [D + .5, *(D + 4 * i for i in range(1, 60))]
    pattern = next(p for p in compute(candles(GARTLEY, after=rise), params())["drawings"] if p["kind"] == "gartley")
    assert pattern["status"] == "target2" and pattern["entry"] is not None


def test_trade_stops_out():
    fall = [D + 1, D - 10, D - 20, D - 30, D - 40, D - 50]
    pattern = next(p for p in compute(candles(GARTLEY, after=fall), params())["drawings"] if p["kind"] == "gartley")
    assert pattern["status"] == "failed"
    assert pattern["stop"] == pytest.approx(pattern["entry"] - abs(pattern["t1"] - pattern["entry"]) * .75)


def test_a_candle_reaching_the_stop_and_the_target_counts_as_the_stop():
    data = candles(GARTLEY, after=[D + 1, D + 2, D + 3, D + 4])
    data.high[-1], data.low[-1] = D + 100, D - 100
    pattern = next(p for p in compute(data, params())["drawings"] if p["kind"] == "gartley")
    assert pattern["status"] == "failed"


def test_a_pattern_in_progress_is_open_and_a_potential_one_is_optional():
    data = candles(GARTLEY, after=[D + 1, D + 2, D + 3])
    assert next(p for p in compute(data, params())["drawings"] if p["kind"] == "gartley")["status"] == "open"
    forming = candles(GARTLEY[:-1] + [(62, C - 8)])
    assert not compute(forming, params())["drawings"]
    assert [p["status"] for p in compute(forming, params(show_potential=True))["drawings"]] == ["potential"]


def test_targets_of_every_kind():
    args = (1, 100.0, 200.0, 138.2, 176.4, 121.4)
    assert _target("None", *args) is None and _target("B", *args) == 138.2
    assert abs(_target(".5 AD", *args) - (121.4 + .5 * 78.6)) < 1e-9
    assert abs(_target("1.272 XA", *args) - (121.4 + 127.2)) < 1e-9
    assert abs(_target(".618 CD", -1, 200.0, 100.0, 161.8, 123.6, 178.6) - (178.6 - .618 * 55)) < 1e-9


class Candles:
    def __init__(self, data):
        self.data, self.calls = data, 0

    def get_candles(self, symbol, interval, start, end, max_candles=0):
        self.calls += 1
        rows = [type("C", (), {"time": t, "open": o, "high": h, "low": lo, "close": c, "volume": 1.0})
                for t, o, h, lo, c in zip(self.data.time, self.data.open, self.data.high, self.data.low, self.data.close)]
        return type("S", (), {"candles": rows, "is_closed": lambda _, c, now: True})()


def test_the_api_result_keeps_only_shapes_that_changed_in_the_range_and_drawings_are_not_series():
    data = candles(GARTLEY, after=[D + 4 * i for i in range(1, 60)])
    now = data.time[-1] + 2 * H
    source = Candles(data)
    whole = compute_indicator(source, "harmonics", ALL_OFF, "BTC", "1h", 0, data.time[-1], now)
    assert whole.drawings and "drawings" not in whole.outputs
    late = compute_indicator(source, "harmonics", ALL_OFF, "BTC", "1h", data.time[-1], data.time[-1], now)
    assert not late.drawings


def test_a_forming_candle_is_not_read_and_the_result_is_reused_until_a_candle_closes(monkeypatch):
    harmonics._cache.clear()
    data = candles(GARTLEY, after=[D + 1, D + 2, D + 3])
    forming = data.time[-1] + 10
    with_context = OHLCV(data.time, data.open, data.high, data.low, data.close, data.volume,
                         DataContext(None, "BTC", "1h", forming))
    assert harmonics._closed(with_context) == len(data.time) - 1
    runs = []
    original = harmonics._detect
    monkeypatch.setattr(harmonics, "_detect", lambda *args: runs.append(1) or original(*args))
    first = compute(with_context, params())
    second = compute(with_context, params())
    assert len(runs) == 1 and first["drawings"] == second["drawings"]
