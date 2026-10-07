"""Position lifetime analysis: total duration and time spent below/above the entry price.

Computed on demand from exchange candles (nothing is stored in the database):
- start = purchase time, end = last sale when the position is fully closed, otherwise "now"
  (partial sales keep the position open, so its lifetime continues);
- each candle overlapping [start, end] counts as "below" when its close < buy price, otherwise
  "above"; the part of the lifetime without candles (e.g. very short positions) is "unknown";
- the candle interval is the smallest one giving at most ~1000 candles (1m ... 1d), so the
  precision is roughly one candle.
Results for closed positions never change, so they are cached in memory.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from services.providers.base import INTERVAL_SECONDS, Candle

TIMING_INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]
TARGET_CANDLES = 1000


@dataclass(frozen=True)
class TimeSplit:
    below_seconds: int
    above_seconds: int
    unknown_seconds: int


@dataclass(frozen=True)
class PositionTiming:
    start: datetime
    end: datetime
    is_open: bool
    duration_seconds: int
    below_seconds: int
    above_seconds: int
    unknown_seconds: int
    below_pct: Optional[Decimal]     # share of the known time spent below the entry price
    interval: str
    source: Optional[str]


def choose_interval(duration_seconds: int) -> str:
    for name in TIMING_INTERVALS:
        if duration_seconds / INTERVAL_SECONDS[name] <= TARGET_CANDLES:
            return name
    return TIMING_INTERVALS[-1]


def local_to_utc(value: datetime, tz_name: str) -> datetime:
    """Dates entered in the UI are stored as naive local time - convert them to aware UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(tz_name))
    return value.astimezone(timezone.utc)


def split_time(candles: list[Candle], step: int, start: int, end: int, entry_price: Decimal) -> TimeSplit:
    """Seconds of [start, end] spent below / above the entry price, judged by each candle's close."""
    below = above = 0
    for candle in candles:
        overlap = min(candle.time + step, end) - max(candle.time, start)
        if overlap <= 0:
            continue
        if candle.close < entry_price:
            below += overlap
        else:
            above += overlap
    total = max(0, end - start)
    return TimeSplit(below, above, max(0, total - below - above))


def compute_timing(position, candle_service, tz_name: str, now: datetime) -> PositionTiming:
    start = local_to_utc(position.bought_at, tz_name)
    open_qty = position.quantity - (position.fee_coin or 0) - sum((s.quantity for s in position.sales), Decimal(0))
    is_open = open_qty > 0
    end = now if is_open or not position.sales else local_to_utc(max(s.sold_at for s in position.sales), tz_name)
    end = max(end, start)
    start_s, end_s = int(start.timestamp()), int(end.timestamp())
    duration = end_s - start_s

    interval = choose_interval(duration)
    step = INTERVAL_SECONDS[interval]
    source = None
    candles: list[Candle] = []
    if duration > 0:
        series = candle_service.get_candles(position.symbol, interval, start_s, end_s,
                                            max_candles=duration // step + 2)
        source, candles = series.source, series.candles

    split = split_time(candles, step, start_s, end_s, position.buy_price)
    known = split.below_seconds + split.above_seconds
    below_pct = (Decimal(split.below_seconds) / known * 100).quantize(Decimal("0.01")) if known else None
    return PositionTiming(start, end, is_open, duration, split.below_seconds, split.above_seconds,
                          split.unknown_seconds, below_pct, interval, source)


# ------------------------------------------------------------------ cache for closed positions

_cache: dict[tuple, PositionTiming] = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _fingerprint(position) -> tuple:
    sales = tuple(sorted((s.id, str(s.quantity), s.sold_at.isoformat()) for s in position.sales))
    return (position.id, position.symbol, str(position.buy_price), str(position.quantity),
            str(position.fee_coin), position.bought_at.isoformat(), sales)


def position_timing(position, candle_service, tz_name: str, now: Optional[datetime] = None) -> PositionTiming:
    now = now or datetime.now(timezone.utc)
    key = _fingerprint(position)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    timing = compute_timing(position, candle_service, tz_name, now)
    if not timing.is_open:
        with _cache_lock:
            _cache[key] = timing
    return timing
