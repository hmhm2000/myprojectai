"""Indicator values for a symbol/interval/time range - the single entry point used by the chart API and alerts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import indicators  # noqa: F401  (loads built-in and custom indicators)
from indicators.base import OHLCV, get_indicator, validate_params
from indicators.core import Series
from services.intervals import Interval, parse

MAX_CANDLES = 6000


@dataclass(frozen=True)
class IndicatorResult:
    indicator_id: str
    params: dict
    time: list[int]                 # candle open times in the requested range
    closed: list[bool]              # False for the still-forming candle (value may still change)
    outputs: dict[str, Series]


def _end_fn(interval):
    """Candle end (= next candle start) for an Interval or a fixed step in seconds."""
    return interval.next_start if isinstance(interval, Interval) else (lambda t: t + interval)


def map_to_chart(source_times: list[int], source_interval, values: Series,
                 chart_times: list[int], chart_interval, now: float) -> Series:
    """Values computed on another timeframe, placed on the chart candles - without look-ahead.

    A chart candle gets the value of the last source candle that is CLOSED by the end of that chart
    candle, so history never shows information from the future. Only the current (still forming) chart
    candle shows the provisional value of the forming source candle - like TradingView's
    request.security with lookahead off after a reload.
    """
    source_end = _end_fn(source_interval)
    chart_end_of = _end_fn(chart_interval)
    out: Series = []
    j = -1                                  # last source candle closed by the end of the chart candle
    for t in chart_times:
        chart_end = chart_end_of(t)
        while j + 1 < len(source_times) and source_end(source_times[j + 1]) <= chart_end:
            j += 1
        k = j
        nxt = j + 1
        live = chart_end > now              # the current chart candle
        if live and nxt < len(source_times) and source_times[nxt] <= t and source_end(source_times[nxt]) > now:
            k = nxt                         # the forming source candle (live value)
        out.append(values[k] if k >= 0 else None)
    return out


def compute_indicator(candle_service, indicator_id: str, raw_params: Optional[dict], symbol: str,
                      interval: str, start: int, end: int, now: float,
                      indicator_interval: Optional[str] = None) -> IndicatorResult:
    """Compute over [start, end] (unix s), fetching `warmup` extra candles before `start`.

    `indicator_interval` (e.g. "1d" on a 1h chart) computes the indicator on that timeframe and
    maps the values onto the chart candles (see map_to_chart).
    """
    indicator = get_indicator(indicator_id)
    params = validate_params(indicator, raw_params)
    chart_spec = parse(interval)
    source_spec = parse(indicator_interval or interval)
    source_interval = source_spec.name
    interval = chart_spec.name
    source_step = source_spec.seconds
    warmup = indicator.warmup(params)
    extra = 0 if source_interval == interval else 1   # one more source candle for the mapping
    fetch_start = start - (warmup + extra) * source_step
    max_candles = min(MAX_CANDLES, (end - fetch_start) // source_step + 2)
    series = candle_service.get_candles(symbol, source_interval, fetch_start, end, max_candles=max_candles)

    data = OHLCV.from_candles(series.candles)
    outputs = indicator.compute(data, params)

    if source_interval == interval:
        first = next((i for i, t in enumerate(data.time) if t >= chart_spec.bucket_start(start)), len(data.time))
        return IndicatorResult(
            indicator_id=indicator.id,
            params=params,
            time=data.time[first:],
            closed=[series.is_closed(c, now) for c in series.candles[first:]],
            outputs={name: values[first:] for name, values in outputs.items()},
        )

    chart_times = chart_spec.times(start, end)
    return IndicatorResult(
        indicator_id=indicator.id,
        params=params,
        time=chart_times,
        closed=[chart_spec.is_closed(t, now) for t in chart_times],
        outputs={name: map_to_chart(data.time, source_spec, values, chart_times, chart_spec, now)
                 for name, values in outputs.items()},
    )
