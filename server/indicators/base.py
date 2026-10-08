"""Indicator definitions and registry.

An indicator declares its parameters, outputs and how to draw them; `compute` gets the candles
(as float lists) plus validated params and returns one series per output, aligned with the candles.
The same definition is used by the chart API, alerts and analysis.

Adding an indicator: create a module in indicators/ (built-in) or indicators/custom/ (ports of your
Pine Script indicators) and call `register(Indicator(...))` - modules are imported automatically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from core.errors import AppError, BadRequest, NotFound
from indicators.core import Series

if TYPE_CHECKING:
    from indicators.context import DataContext, HigherTimeframe

SOURCES = ("close", "open", "high", "low", "hl2", "hlc3", "ohlc4")
COLOR = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


@dataclass(frozen=True)
class OHLCV:
    time: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    # symbol / interval / candle source - lets an indicator read another timeframe (Pine's security)
    context: Optional["DataContext"] = field(default=None, compare=False, repr=False)

    @classmethod
    def from_candles(cls, candles, context: Optional["DataContext"] = None) -> "OHLCV":
        return cls(
            time=[c.time for c in candles],
            open=[float(c.open) for c in candles],
            high=[float(c.high) for c in candles],
            low=[float(c.low) for c in candles],
            close=[float(c.close) for c in candles],
            volume=[float(c.volume) for c in candles],
            context=context,
        )

    def security(self, interval: str, warmup: int = 200) -> Optional["HigherTimeframe"]:
        """Candles of another timeframe covering these candles (None when there is no candle source or
        the exchange fails) - values computed on them are placed back with `.map()` without look-ahead."""
        if self.context is None or not self.time:
            return None
        try:
            return self.context.security(self, interval, warmup)
        except AppError:
            return None

    def wants(self, *outputs: str) -> bool:
        """True when any of these outputs is needed by the caller (always, when not told otherwise)."""
        wanted = self.context.outputs if self.context is not None else None
        return wanted is None or any(name in wanted for name in outputs)

    def perp(self, symbol: Optional[str] = None) -> Optional["OHLCV"]:
        """Candles of the coin's USDT perpetual (or of `symbol`) aligned with these candles; None if unavailable."""
        if self.context is None or not self.time:
            return None
        try:
            return self.context.perp(self, symbol or self.context.symbol)
        except AppError:
            return None

    def open_interest(self, symbol: Optional[str] = None) -> Optional[Series]:
        """Open interest (USDT perpetual) per candle - like TradingView's <SYMBOL>_OI close; None if unavailable."""
        if self.context is None or not self.time:
            return None
        try:
            return self.context.open_interest(self, symbol or self.context.symbol)
        except AppError:
            return None

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
    type: str                      # "int" | "float" | "source" | "bool" | "color" (#rrggbb[aa]) | "timeframe" (e.g. "4h")
                                   # | "symbol" (a coin, e.g. "ETH")
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    label: str = ""                # original title (Pine input title); the UI translates it when it can
    group: str = ""                # section in the settings (Pine input group)


@dataclass(frozen=True)
class Output:
    """One plotted series. Colors are "#rrggbb[aa]" or "@param" (taken from a color parameter).

    plot:
      "line" | "stepline" | "histogram" - a line / steps / bars,
      "area"   - filled towards 0 (Pine plot.style_area), `color` above 0, `color_below` below,
      "points" - separate dots (Pine plot.style_circles / plotchar dots), `radius`,
      "char"   - a symbol (`char`) at the value (Pine plotchar with location.absolute),
      "band"   - fill between two other outputs (`between`) like Pine fill(),
      "signal" - 1 = BUY, -1 = SELL markers,
      "background" - colors the whole pane behind candles where the value is 1 (Pine bgcolor),
      "barcolor"   - colors the price candles (Pine barcolor), color from `palette`,
      "none"   - not drawn (helper series, alert conditions).
    Per-point colors: the indicator also returns "<name>:color" = index into `palette` (None = not drawn).
    """
    name: str
    plot: str = "line"
    color: Optional[str] = None
    color_below: Optional[str] = None
    opacity: float = 1.0           # multiplies the alpha of the color (Pine transp)
    width: int = 1
    radius: float = 2.0
    char: str = ""
    palette: tuple = ()
    between: tuple = ()
    label: str = ""
    alert: bool = True             # usable in alert conditions


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
    summary: tuple = ()            # params shown on the indicator tile (default: all number params)


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
            value = _coerce(param, value)
        except (TypeError, ValueError, AppError):
            raise BadRequest("indicators.invalid_param", f"Invalid value for {param.name}", param=param.name)
        numeric = param.type in ("int", "float")
        if numeric and ((param.min is not None and value < param.min) or (param.max is not None and value > param.max)):
            raise BadRequest("indicators.invalid_param", f"{param.name} out of range", param=param.name)
        result[param.name] = value
    return result


def _coerce(param: Param, value: Any) -> Any:
    if param.type == "bool":
        if isinstance(value, bool):
            return value
        if value in ("true", "false"):
            return value == "true"
        raise ValueError
    if isinstance(value, bool):
        raise ValueError                                   # True is not a number here
    if param.type == "int":
        if float(value) != int(float(value)):
            raise ValueError
        return int(float(value))
    if param.type == "float":
        return float(value)
    if param.type == "source":
        if value not in SOURCES:
            raise ValueError
        return value
    if param.type == "color":
        if not isinstance(value, str) or not COLOR.match(value):
            raise ValueError
        return value.lower()
    if param.type == "symbol":
        value = str(value).strip().upper()
        if not re.match(r"^[A-Z0-9]{1,20}$", value):
            raise ValueError
        return value
    if param.type == "timeframe":
        from services.intervals import parse

        return parse(str(value)).name
    raise ValueError
