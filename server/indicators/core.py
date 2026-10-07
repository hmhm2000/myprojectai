"""Math primitives for indicators, matching Pine Script (TradingView) semantics.

Series are plain lists aligned with the candles: one value per candle, None = Pine's `na`.
- sma: na until the window is full or when the window contains na,
- ema / rma: seeded with the SMA of the first full window (exactly like Pine's ta.ema / ta.rma),
  then recursive; an na input yields na and restarts the seeding,
- stdev: population standard deviation (Pine's ta.stdev with biased=true, the default),
- crossover(a, b): a[i] > b[i] and a[i-1] <= b[i-1] (Pine's ta.crossover); crossunder mirrors it.
Floats are used on purpose (speed); results are for charting/alerts, not accounting.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

Series = list[Optional[float]]


def _window(src: Sequence[Optional[float]], i: int, length: int) -> Optional[list[float]]:
    if length <= 0 or i < length - 1:
        return None
    window = src[i - length + 1:i + 1]
    return None if any(v is None for v in window) else list(window)


def sma(src: Sequence[Optional[float]], length: int) -> Series:
    out: Series = []
    for i in range(len(src)):
        window = _window(src, i, length)
        out.append(sum(window) / length if window else None)
    return out


def _smoothed(src: Sequence[Optional[float]], length: int, alpha: float) -> Series:
    """Pine: sum := na(sum[1]) ? ta.sma(src, length) : alpha * src + (1 - alpha) * sum[1]."""
    out: Series = []
    prev: Optional[float] = None
    for i, value in enumerate(src):
        if value is None:
            prev = None
        elif prev is None:
            window = _window(src, i, length)
            prev = sum(window) / length if window else None
        else:
            prev = alpha * value + (1 - alpha) * prev
        out.append(prev)
    return out


def ema(src: Sequence[Optional[float]], length: int) -> Series:
    return _smoothed(src, length, 2 / (length + 1))


def rma(src: Sequence[Optional[float]], length: int) -> Series:
    """Wilder's moving average (used by RSI, ATR)."""
    return _smoothed(src, length, 1 / length)


def stdev(src: Sequence[Optional[float]], length: int) -> Series:
    out: Series = []
    for i in range(len(src)):
        window = _window(src, i, length)
        if not window:
            out.append(None)
            continue
        mean = sum(window) / length
        out.append(math.sqrt(sum((v - mean) ** 2 for v in window) / length))
    return out


def highest(src: Sequence[Optional[float]], length: int) -> Series:
    return [max(w) if (w := _window(src, i, length)) else None for i in range(len(src))]


def lowest(src: Sequence[Optional[float]], length: int) -> Series:
    return [min(w) if (w := _window(src, i, length)) else None for i in range(len(src))]


def change(src: Sequence[Optional[float]]) -> Series:
    """src - src[1] (na on the first bar)."""
    return [None] + [b - a if a is not None and b is not None else None for a, b in zip(src, src[1:])]


def combine(op, *series: Sequence[Optional[float]]) -> Series:
    """Element-wise operation; na if any input is na."""
    return [None if any(v is None for v in values) else op(*values) for values in zip(*series)]


def crossover(a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> list[bool]:
    out = [False]
    for i in range(1, len(a)):
        values = (a[i], b[i], a[i - 1], b[i - 1])
        out.append(None not in values and a[i] > b[i] and a[i - 1] <= b[i - 1])
    return out


def crossunder(a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> list[bool]:
    out = [False]
    for i in range(1, len(a)):
        values = (a[i], b[i], a[i - 1], b[i - 1])
        out.append(None not in values and a[i] < b[i] and a[i - 1] >= b[i - 1])
    return out
