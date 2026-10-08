"""Access to other timeframes from inside an indicator (Pine's security / request.security).

`OHLCV.security("4h")` returns the 4h candles covering the indicator's candles; values computed on
them are placed back onto the indicator's candles with `.map()` - each candle gets the value of the
last 4h candle CLOSED by its end (no look-ahead, history never repaints), only the newest candle may
show the still-forming 4h value.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from indicators.core import Series
from services.intervals import parse

if TYPE_CHECKING:
    from indicators.base import OHLCV

MAX_CANDLES = 6000
LOWER_TF_CANDLES = 1500   # a LOWER timeframe (e.g. 1h on a 1D chart) is read only for its newest candles


@dataclass(frozen=True)
class HigherTimeframe:
    interval: str
    data: "OHLCV"                 # candles of `interval`
    base: "OHLCV"                 # the indicator's own candles
    base_interval: str
    now: float

    def map(self, values: Series) -> Series:
        """Values computed on `data` -> one value per candle of `base`."""
        from indicators.service import map_to_chart

        return map_to_chart(self.data.time, parse(self.interval), values,
                            self.base.time, parse(self.base_interval), self.now)


@dataclass(frozen=True)
class DataContext:
    candle_service: Any
    symbol: str
    interval: str                 # interval of the candles this context belongs to
    now: float
    # outputs the caller needs (None = all) - lets an indicator skip work for outputs nobody uses
    outputs: Optional[frozenset] = None
    _cache: dict = field(default_factory=dict, compare=False, repr=False)

    def security(self, base: "OHLCV", interval: str, warmup: int) -> HigherTimeframe:
        from indicators.base import OHLCV

        spec = parse(interval)
        key = (spec.name, base.time[0], warmup)
        if key not in self._cache:
            start = base.time[0] - warmup * spec.seconds
            end = int(self.now)
            if spec.seconds < parse(self.interval).seconds:
                # thousands of 1h candles for years of daily candles would take many requests;
                # older chart candles then simply have no value from that timeframe
                start = max(start, end - LOWER_TF_CANDLES * spec.seconds)
            count = min(MAX_CANDLES, math.ceil((end - start) / spec.seconds) + 2)
            series = self.candle_service.get_candles(self.symbol, spec.name, start, end, max_candles=count)
            data = OHLCV.from_candles(series.candles)
            self._cache[key] = HigherTimeframe(spec.name, data, base, self.interval, self.now)
        return self._cache[key]

    def perp(self, base: "OHLCV", symbol: str) -> "OHLCV":
        """The USDT perpetual's candles of `symbol` on the same candles as `base` (None where missing)."""
        from indicators.base import OHLCV

        spec = parse(self.interval)
        series = self.candle_service.get_candles(symbol, spec.name, base.time[0], int(self.now),
                                                 max_candles=len(base.time) + 2, market="perp")
        by_time = {c.time: c for c in series.candles}
        rows = [by_time.get(t) for t in base.time]
        pick = lambda attr: [None if c is None else float(getattr(c, attr)) for c in rows]
        return OHLCV(list(base.time), pick("open"), pick("high"), pick("low"), pick("close"), pick("volume"))

    def open_interest(self, base: "OHLCV", symbol: str) -> Series:
        """Open interest "close" of every candle of `base`: the OI at the candle's end (the newest
        candle: the latest known value). None before the exchange's history starts."""
        from services.open_interest import open_interest_service, period_for

        spec = parse(self.interval)
        period = period_for(spec.name)
        points = open_interest_service.get(symbol, period, base.time[0] - parse(period).seconds, int(self.now))
        times = [p[0] for p in points]
        out: Series = []
        for t in base.time:
            k = bisect.bisect_right(times, min(spec.next_start(t), self.now)) - 1
            out.append(points[k][1] if k >= 0 else None)
        return out
