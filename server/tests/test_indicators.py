import math
import statistics
from decimal import Decimal as D

import pytest

from core.errors import AppError
from indicators.base import OHLCV, get_indicator, validate_params
from indicators.builtin import rsi_series
from indicators.core import crossover, crossunder, ema, rma, sma, stdev
from indicators.service import compute_indicator
from services.candle_service import CandleSeries
from services.providers.base import Candle
from tests.conftest import login


def approx(series, expected):
    assert len(series) == len(expected)
    for got, want in zip(series, expected):
        assert (got is None and want is None) or got == pytest.approx(want), (series, expected)


def test_moving_averages_match_pine_definitions():
    approx(sma([1, 2, 3, 4, 5], 3), [None, None, 2, 3, 4])
    approx(sma([1, None, 3, 4, 5], 2), [None, None, None, 3.5, 4.5])          # na inside the window -> na
    # ta.ema: seeded with SMA(1,2,3) = 2, then alpha = 0.5
    approx(ema([1, 2, 3, 4, 5], 3), [None, None, 2, 3, 4])
    # ta.rma: alpha = 1/length, seeded with SMA(1,2) = 1.5
    approx(rma([1, 2, 3, 4], 2), [None, 1.5, 2.25, 3.125])
    approx(stdev([2, 4, 4, 4, 5, 5, 7, 9], 8), [None] * 7 + [2.0])            # population stdev


def test_rsi_hand_calculated_and_edge_cases():
    # diffs +1 -1 +1 +1, rma(2): up .5/.75/.875, down .5/.25/.125 -> RSI 50, 75, 87.5
    approx(rsi_series([1, 2, 1, 2, 3], 2), [None, None, 50, 75, 87.5])
    assert rsi_series(list(range(1, 30)), 14)[-1] == 100.0                     # only gains
    assert rsi_series(list(range(30, 1, -1)), 14)[-1] == 0.0                   # only losses


def test_bollinger_macd_stochastic():
    closes = [10, 11, 12, 11, 13, 14, 13, 15, 16, 15, 17, 18, 17, 19, 20, 19, 21, 22, 21, 23, 24]
    candles = OHLCV(list(range(len(closes))), closes, [c + 1 for c in closes], [c - 1 for c in closes], closes, [1] * len(closes))

    bb = get_indicator("bb").compute(candles, {"length": 20, "mult": 2.0, "source": "close"})
    window = closes[-20:]
    assert bb["basis"][-1] == pytest.approx(statistics.mean(window))
    assert bb["upper"][-1] == pytest.approx(statistics.mean(window) + 2 * statistics.pstdev(window))
    assert bb["lower"][-2] is not None and bb["basis"][-3] is None

    macd = get_indicator("macd").compute(candles, {"fast": 3, "slow": 5, "signal": 2, "source": "close"})
    i = len(closes) - 1
    assert macd["macd"][i] == pytest.approx(ema(closes, 3)[i] - ema(closes, 5)[i])
    assert macd["histogram"][i] == pytest.approx(macd["macd"][i] - macd["signal"][i])
    assert macd["signal"][4] is None and macd["signal"][5] is not None        # signal seeded after 2 MACD values

    stoch = get_indicator("stoch").compute(candles, {"k_length": 3, "k_smoothing": 1, "d_smoothing": 3})
    # last bar: close 24, high window max(22,24,25)=25, low window min(20,22,23)=20 -> 80
    assert stoch["k"][-1] == pytest.approx(100 * (24 - 20) / (25 - 20))
    assert stoch["d"][-1] == pytest.approx(sum(stoch["k"][-3:]) / 3)


def test_cross_detection():
    a = [1, 2, 3, 2, 1]
    b = [2, 2, 2, 2, 2]
    assert crossover(a, b) == [False, False, True, False, False]              # 2 <= 2 then 3 > 2
    assert crossunder(a, b) == [False, False, False, False, True]
    assert crossover([None, 3], [2, 2]) == [False, False]                     # na never crosses


def test_warmup_makes_results_independent_of_history_start():
    closes = [100 + 10 * math.sin(i / 7) + i * 0.1 for i in range(600)]
    full = OHLCV(list(range(600)), closes, closes, closes, closes, [1] * 600)
    for indicator_id, params in [("ema", {"length": 20}), ("rsi", {"length": 14}), ("macd", {})]:
        indicator = get_indicator(indicator_id)
        params = validate_params(indicator, params)
        warm = indicator.warmup(params)
        cut = 600 - 50 - warm                                                   # only warmup + 50 candles
        part = OHLCV(full.time[cut:], closes[cut:], closes[cut:], closes[cut:], closes[cut:], [1] * (600 - cut))
        for name in indicator.compute(full, params):
            assert indicator.compute(part, params)[name][-1] == pytest.approx(indicator.compute(full, params)[name][-1], rel=1e-4)


def test_param_validation():
    rsi = get_indicator("rsi")
    assert validate_params(rsi, {"length": "21"}) == {"length": 21, "source": "close"}
    for bad in ({"length": 0}, {"length": "abc"}, {"source": "volume"}, {"foo": 1}):
        with pytest.raises(AppError) as exc:
            validate_params(rsi, bad)
        assert exc.value.code == "indicators.invalid_param"
    with pytest.raises(AppError):
        get_indicator("nope")


class FakeCandleService:
    def __init__(self, count, step=3600, now=10_000 * 3600):
        self.now = now
        self.candles = [Candle(now - (count - i) * step, D(i + 1), D(i + 1), D(i + 1), D(i + 1), D(1)) for i in range(count + 1)]
        self.requested = None

    def get_candles(self, symbol, interval, start, end, max_candles=5000):
        self.requested = (start, end)
        return CandleSeries(symbol, interval, "fake", [c for c in self.candles if start <= c.time <= end])


def test_service_fetches_warmup_and_returns_requested_range():
    fake = FakeCandleService(200)
    start = fake.now - 10 * 3600
    result = compute_indicator(fake, "sma", {"length": 5}, "BTC", "1h", start, fake.now, now=fake.now + 60)
    assert fake.requested[0] == start - 5 * 3600                              # warmup candles fetched before start
    assert result.time[0] == start and len(result.time) == 11
    assert all(v is not None for v in result.outputs["sma"])                  # warmed up -> no leading na
    assert result.closed[-1] is False and result.closed[0] is True


def test_indicator_api(client, monkeypatch):
    import api.routes.indicators as routes
    fake = FakeCandleService(300)
    monkeypatch.setattr(routes, "candle_service", fake)
    headers = login(client)
    listing = {i["id"]: i for i in client.get("/api/indicators", headers=headers).json()}
    assert {"sma", "ema", "rsi", "macd", "bb", "stoch"} <= set(listing)
    assert listing["rsi"]["pane"] == "separate" and listing["rsi"]["levels"] == [30, 70]

    url = f"/api/indicators/rsi/values?symbol=btc&interval=1h&start={fake.now - 20 * 3600}&end={fake.now}"
    body = client.get(url + '&params={"length": 7}', headers=headers).json()
    assert body["params"] == {"length": 7, "source": "close"} and len(body["time"]) == 21
    assert body["outputs"]["rsi"][-1] == 100.0                               # rising fake prices
    assert client.get(url + "&params=nope", headers=headers).json()["code"] == "indicators.invalid_param"
