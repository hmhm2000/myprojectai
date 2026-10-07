"""Indicator definitions and registry.

An indicator declares its parameters, outputs and how to draw them; `compute` gets the candles
(as float lists) plus validated params and returns one series per output, aligned with the candles.
The same definition is used by the chart API, alerts and analysis.

Adding an indicator: create a module in indicators/ (built-in) or indicators/custom/ (ports of your
Pine Script indicators) and call `register(Indicator(...))` - modules are imported automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.errors import BadRequest, NotFound
from indicators.core import Series

SOURCES = ("close", "open", "high", "low", "hl2", "hlc3", "ohlc4")


@dataclass(frozen=True)
class OHLCV:
    time: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]

    @classmethod
    def from_candles(cls, candles) -> "OHLCV":
        return cls(
            time=[c.time for c in candles],
            open=[float(c.open) for c in candles],
            high=[float(c.high) for c in candles],
            low=[float(c.low) for c in candles],
            close=[float(c.close) for c in candles],
            volume=[float(c.volume) for c in candles],
        )

    def source(self, name: str) -> list[float]:
        if name == "hl2":
            return [(h + l) / 2 for h, l in zip(self.high, self.low)]
        if name == "hlc3":
            return [(h + l + c) / 3 for h, l, c in zip(self.high, self.low, self.close)]
        if name == "ohlc4":
            return [(o + h + l + c) / 4 for o, h, l, c in zip(self.open, self.high, self.low, self.close)]
        return getattr(self, name)


@dataclass(frozen=True)
class Param:
    name: str
    type: str                      # "int" | "float" | "source"
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None


@dataclass(frozen=True)
class Output:
    name: str
    plot: str = "line"             # "line" | "histogram" | "signal" (1 = BUY, -1 = SELL, None = nothing)
    color: Optional[str] = None


@dataclass(frozen=True)
class Indicator:
    id: str
    name: str
    pane: str                      # "overlay" (on the price chart) | "separate" (own pane below)
    params: list[Param]
    outputs: list[Output]
    compute: Callable[[OHLCV, dict], dict[str, Series]]
    warmup: Callable[[dict], int]  # extra candles needed before the first displayed one
    levels: list[float] = field(default_factory=list)   # horizontal guide lines, e.g. RSI 30/70
    description: str = ""


REGISTRY: dict[str, Indicator] = {}


def register(indicator: Indicator) -> Indicator:
    if indicator.id in REGISTRY:
        raise ValueError(f"Indicator {indicator.id!r} registered twice")
    REGISTRY[indicator.id] = indicator
    return indicator


def get_indicator(indicator_id: str) -> Indicator:
    indicator = REGISTRY.get(indicator_id)
    if indicator is None:
        raise NotFound("indicators.not_found", f"Unknown indicator: {indicator_id}", indicator=indicator_id)
    return indicator


def validate_params(indicator: Indicator, raw: Optional[dict]) -> dict:
    """Defaults + type coercion + range checks for user-supplied params."""
    raw = raw or {}
    unknown = set(raw) - {p.name for p in indicator.params}
    if unknown:
        raise BadRequest("indicators.invalid_param", f"Unknown parameter(s): {', '.join(sorted(unknown))}",
                         param=", ".join(sorted(unknown)))
    result = {}
    for param in indicator.params:
        value = raw.get(param.name, param.default)
        try:
            if param.type == "int":
                value = int(value)
            elif param.type == "float":
                value = float(value)
            elif param.type == "source" and value not in SOURCES:
                raise ValueError
        except (TypeError, ValueError):
            raise BadRequest("indicators.invalid_param", f"Invalid value for {param.name}", param=param.name)
        if (param.min is not None and value < param.min) or (param.max is not None and value > param.max):
            raise BadRequest("indicators.invalid_param", f"{param.name} out of range", param=param.name)
        result[param.name] = value
    return result
