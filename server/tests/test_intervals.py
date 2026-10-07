from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from core.errors import AppError
from services.candle_service import CandleService
from services.intervals import aggregate, parse
from services.providers.base import Candle

DAY = 86400


def ts(*args):
    return int(datetime(*args, tzinfo=timezone.utc).timestamp())


def test_parse_names_and_base():
    assert parse("3D").name == "3d" and parse("2W").name == "2w" and parse("1M").name == "1M"
    assert parse("15m").name == "15m" and parse("4H").name == "4h"
    assert parse("1w").native and parse("1M").native and not parse("3d").native
    assert parse("3d").base.name == "1d" and parse("2w").base.name == "1w" and parse("3M").base.name == "1M"
    assert parse("2h").base.name == "1h" and parse("8h").base.name == "4h" and parse("45m").base.name == "15m"
    for bad in ("", "3x", "0d", "400d", "13M", "d3"):
        with pytest.raises(AppError):
            parse(bad)


def test_bucket_anchoring():
    t = ts(2026, 10, 8, 15, 30)                                 # Thursday
    assert parse("1w").bucket_start(t) == ts(2026, 10, 5)     # Monday 00:00 UTC, like the exchanges
    assert parse("1M").bucket_start(t) == ts(2026, 10, 1)
    assert parse("1M").next_start(t) == ts(2026, 11, 1)
    assert parse("3M").bucket_start(t) == ts(2026, 10, 1) and parse("3M").next_start(t) == ts(2027, 1, 1)
    assert parse("1M").next_start(ts(2026, 12, 15)) == ts(2027, 1, 1)
    three = parse("3d").bucket_start(t)
    assert three % (3 * DAY) == 0 and three <= t < three + 3 * DAY  # epoch-aligned 3-day buckets
    two_weeks = parse("2w").bucket_start(t)
    assert datetime.fromtimestamp(two_weeks, timezone.utc).weekday() == 0 and two_weeks <= t
    assert parse("1d").times(ts(2026, 1, 1, 12), ts(2026, 1, 3)) == [ts(2026, 1, 1), ts(2026, 1, 2), ts(2026, 1, 3)]


def candle(t, o, h, l, c, v="1"):
    return Candle(t, D(o), D(h), D(l), D(c), D(v))


def test_aggregate_ohlcv():
    start = parse("3d").bucket_start(ts(2026, 1, 10))
    days = [candle(start + i * DAY, 10 + i, 20 + i, 5 - i, 11 + i, "2") for i in range(4)]
    out = aggregate(days, parse("3d"))
    assert len(out) == 2
    first = out[0]
    assert (first.time, first.open, first.high, first.low, first.close, first.volume) == \
        (start, D(10), D(22), D(3), D(13), D(6))                # open first, max high, min low, close last, sum volume
    assert out[1].time == start + 3 * DAY and out[1].open == D(13)


class Prices:
    quote_currency = "USDT"

    def sources_for(self, symbol):
        return ["bybit"]


class DailyExchange:
    """Fake exchange with daily candles; records every request."""

    def __init__(self):
        self.calls = []

    def __call__(self, symbol, quote, interval, start_ms, end_ms, max_candles, timeout):
        self.calls.append((interval, start_ms // 1000, end_ms // 1000))
        step = parse(interval).seconds
        first = parse(interval).bucket_start(start_ms // 1000)
        return [candle(t, 1, 2, 0.5, 1.5) for t in range(first, end_ms // 1000 + 1, step)]


def test_range_cache_fetches_only_missing_parts():
    exchange = DailyExchange()
    clock = {"now": ts(2026, 3, 1, 12)}
    service = CandleService(Prices(), {"bybit": exchange}, now=lambda: clock["now"])

    service.get_candles("BTC", "1d", ts(2026, 2, 1), clock["now"])
    assert len(exchange.calls) == 1

    service.get_candles("BTC", "1d", ts(2026, 2, 10), clock["now"])        # inside the range, fresh
    assert len(exchange.calls) == 1

    service.get_candles("BTC", "1d", ts(2026, 1, 1), clock["now"])         # older history
    assert exchange.calls[-1][1:] == (ts(2026, 1, 1), ts(2026, 2, 1) - 1)  # only the missing part

    series = service.get_candles("BTC", "3d", ts(2026, 1, 10), clock["now"])   # aggregated from cached 1d
    assert len(exchange.calls) == 2 and series.interval == "3d"
    assert all(b.time - a.time == 3 * DAY for a, b in zip(series.candles, series.candles[1:]))

    clock["now"] += 20                                                      # live tail: fresh for 30 s
    service.get_candles("BTC", "1d", ts(2026, 2, 1), clock["now"])
    assert len(exchange.calls) == 2
    clock["now"] += 11                                                      # 31 s since the last live fetch
    service.get_candles("BTC", "1d", ts(2026, 2, 1), clock["now"])
    assert len(exchange.calls) == 3 and exchange.calls[-1][1] == ts(2026, 3, 1)   # from the last stored candle


def test_month_chart_times_and_is_closed():
    spec = parse("1M")
    assert spec.times(ts(2026, 1, 15), ts(2026, 3, 1)) == [ts(2026, 1, 1), ts(2026, 2, 1), ts(2026, 3, 1)]
    assert spec.is_closed(ts(2026, 2, 1), ts(2026, 3, 1)) and not spec.is_closed(ts(2026, 3, 1), ts(2026, 3, 20))
