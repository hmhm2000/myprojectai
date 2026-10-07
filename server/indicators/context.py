"""Access to other timeframes from inside an indicator (Pine's security / request.security).

`OHLCV.security("4h")` returns the 4h candles covering the indicator's candles; values computed on
them are placed back onto the indicator's candles with `.map()` - each candle gets the value of the
last 4h candle CLOSED by its end (no look-ahead, history never repaints), only the newest candle may
show the still-forming 4h value.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from indicators.core import Series
from services.intervals import parse

if TYPE_CHECKING:
    from indicators.base import OHLCV

MAX_CANDLES = 6000


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
    _cache: dict = field(default_factory=dict, compare=False, repr=False)

    def security(self, base: "OHLCV", interval: str, warmup: int) -> HigherTimeframe:
        from indicators.base import OHLCV

        spec = parse(interval)
        key = (spec.name, base.time[0], warmup)
        if key not in self._cache:
            start = base.time[0] - warmup * spec.seconds
            end = int(self.now)
            count = min(MAX_CANDLES, math.ceil((end - start) / spec.seconds) + 2)
            series = self.candle_service.get_candles(self.symbol, spec.name, start, end, max_candles=count)
            data = OHLCV.from_candles(series.candles)
            self._cache[key] = HigherTimeframe(spec.name, data, base, self.interval, self.now)
        return self._cache[key]
