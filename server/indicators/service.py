"""Indicator values for a symbol/interval/time range - the single entry point used by the chart API and alerts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import indicators  # noqa: F401  (loads built-in and custom indicators)
from indicators.base import OHLCV, get_indicator, validate_params
from indicators.core import Series
from services.providers.base import INTERVAL_SECONDS

MAX_CANDLES = 6000


@dataclass(frozen=True)
class IndicatorResult:
    indicator_id: str
    params: dict
    time: list[int]                 # candle open times in the requested range
    closed: list[bool]              # False for the still-forming candle (value may still change)
    outputs: dict[str, Series]


def compute_indicator(candle_service, indicator_id: str, raw_params: Optional[dict], symbol: str,
                      interval: str, start: int, end: int, now: float) -> IndicatorResult:
    """Compute over [start, end] (unix s), fetching `warmup` extra candles before `start`."""
    indicator = get_indicator(indicator_id)
    params = validate_params(indicator, raw_params)
    step = INTERVAL_SECONDS.get(interval, 3600)
    warmup = indicator.warmup(params)
    fetch_start = start - warmup * step
    max_candles = min(MAX_CANDLES, (end - fetch_start) // step + 2)
    series = candle_service.get_candles(symbol, interval, fetch_start, end, max_candles=max_candles)

    data = OHLCV.from_candles(series.candles)
    outputs = indicator.compute(data, params)
    first = next((i for i, t in enumerate(data.time) if t >= start - start % step), len(data.time))
    return IndicatorResult(
        indicator_id=indicator.id,
        params=params,
        time=data.time[first:],
        closed=[series.is_closed(c, now) for c in series.candles[first:]],
        outputs={name: values[first:] for name, values in outputs.items()},
    )
