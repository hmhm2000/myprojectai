"""Candle intervals: native exchange intervals and custom ones built by aggregation.

Names: <n><unit>, unit m (minutes), h (hours), d (days), w (weeks), M (months), e.g. 15m, 4h, 3d,
2w, 1M. Input is case-insensitive except m/M (minute vs month): "3D" -> "3d", "2W" -> "2w".

- Native (fetched directly from OKX/Bybit): 1m 5m 15m 30m 1h 4h 1d 1w 1M.
- Custom intervals are aggregated from the largest native interval that divides them
  (2h <- 1h, 8h <- 4h, 3d <- 1d, 2w <- 1w, 3M <- 1M):
  open = first open, high = max, low = min, close = last close, volume = sum.
- Buckets are anchored like the exchanges do: minutes/hours/days at the Unix epoch (UTC midnight),
  weeks on Monday 00:00 UTC, months on calendar months (multi-month buckets start in January).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from core.errors import BadRequest
from services.providers.base import Candle

UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
MONTH_SECONDS = 2_629_800            # average month (30.4375 days) - only for size estimates
WEEK_ANCHOR = 4 * 86400              # 1970-01-05, Monday 00:00 UTC
NATIVE = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"}
MAX_SECONDS = 366 * 86400            # longest custom interval (about a year)
NAME = re.compile(r"^(\d{1,4})([mhdwMHDW])$")


@dataclass(frozen=True)
class Interval:
    name: str
    n: int
    unit: str                        # m, h, d, w, M

    @property
    def native(self) -> bool:
        return self.name in NATIVE

    @property
    def seconds(self) -> int:
        """Exact length for fixed intervals, average length for months."""
        return self.n * (MONTH_SECONDS if self.unit == "M" else UNIT_SECONDS[self.unit])

    @property
    def base(self) -> "Interval":
        """Native interval the candles are fetched in (itself when native)."""
        if self.native:
            return self
        if self.unit == "m":
            size = next(s for s in (30, 15, 5, 1) if self.n % s == 0)
            return parse(f"{size}m")
        if self.unit == "h":
            return parse("4h" if self.n % 4 == 0 else "1h")
        return parse(f"1{self.unit}")

    # -------------------------------------------------------------- buckets

    def bucket_start(self, t: int) -> int:
        if self.unit == "M":
            dt = datetime.fromtimestamp(max(t, 0), timezone.utc)   # no market data before 1970
            index = dt.year * 12 + dt.month - 1
            index -= index % self.n
            return int(datetime(index // 12, index % 12 + 1, 1, tzinfo=timezone.utc).timestamp())
        step = self.seconds
        anchor = WEEK_ANCHOR if self.unit == "w" else 0
        return t - (t - anchor) % step

    def next_start(self, t: int) -> int:
        """Start of the next candle = end of the candle that contains t."""
        start = self.bucket_start(t)
        if self.unit == "M":
            dt = datetime.fromtimestamp(start, timezone.utc)
            index = dt.year * 12 + dt.month - 1 + self.n
            return int(datetime(index // 12, index % 12 + 1, 1, tzinfo=timezone.utc).timestamp())
        return start + self.seconds

    def is_closed(self, t: int, now: float) -> bool:
        return self.next_start(t) <= now

    def times(self, start: int, end: int) -> list[int]:
        """Candle open times covering [start, end]."""
        out, t = [], self.bucket_start(start)
        while t <= end:
            out.append(t)
            t = self.next_start(t)
        return out


def parse(name: str) -> Interval:
    match = NAME.match((name or "").strip())
    if not match:
        raise BadRequest("candles.invalid_interval", f"Unsupported interval: {name}", interval=name)
    n, unit = int(match.group(1)), match.group(2)
    unit = unit if unit in ("m", "M") else unit.lower()
    interval = Interval(f"{n}{unit}", n, unit)
    too_long = (unit == "M" and n > 12) or (unit != "M" and interval.seconds > MAX_SECONDS)
    if n < 1 or too_long:
        raise BadRequest("candles.invalid_interval", f"Unsupported interval: {name}", interval=name)
    return interval


def aggregate(candles: list[Candle], interval: Interval) -> list[Candle]:
    """Merge base candles (oldest first) into candles of `interval`."""
    out: list[Candle] = []
    bucket = None
    group: list[Candle] = []
    for candle in candles:
        b = interval.bucket_start(candle.time)
        if b != bucket and group:
            out.append(_merge(bucket, group))
            group = []
        bucket = b
        group.append(candle)
    if group:
        out.append(_merge(bucket, group))
    return out


def _merge(time: int, group: list[Candle]) -> Candle:
    return Candle(
        time=time,
        open=group[0].open,
        high=max(c.high for c in group),
        low=min(c.low for c in group),
        close=group[-1].close,
        volume=sum((c.volume for c in group), group[0].volume * 0),
    )
