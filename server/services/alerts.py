"""Alert evaluation - uses the same indicator implementations as the chart (indicators.base registry).

Every ~minute all active alerts are checked, grouped by (symbol, interval) so the candles are
fetched once per group. A condition is `left op right`, each side a price, a fixed value or an
indicator output. When it is evaluated depends on the alert's trigger:

- "intrabar"  - immediately: on the forming candle at every check (current price), at most one
                trigger per candle;
- "bar_open"  - once per candle, when a new candle opens, with the values at that moment (the new
                candle counts with its open price only);
- "bar_close" - once per candle, after it closes (confirmed values, nothing repaints).

An alert fires on the transition "not met -> met" (edge), so a condition that stays true does not
spam; "once" alerts are deactivated after firing, "repeat" alerts re-arm when the condition stops
being met.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from core.errors import BadRequest
from indicators.base import OHLCV, get_indicator, validate_params
from indicators.core import crossover, crossunder
from models.alerts import Alert, AlertEvent
from schemas.alerts import Condition
from services.intervals import parse

logger = logging.getLogger(__name__)

EXTRA_CANDLES = 5
TRIGGERS = ("intrabar", "bar_open", "bar_close")
PER_CANDLE = ("bar_open", "bar_close")          # evaluated once per candle


# ------------------------------------------------------------------ condition validation

def validate_condition(condition: Condition) -> None:
    sides = (condition.left, condition.right)
    if all(side.type == "value" for side in sides):
        raise BadRequest("alerts.invalid_condition", "At least one side must be the price or an indicator")
    for side in sides:
        if side.type == "indicator":
            indicator = get_indicator(side.id)
            side.params = validate_params(indicator, side.params)
            if side.output not in {o.name for o in indicator.outputs}:
                raise BadRequest("alerts.invalid_condition", f"Unknown output {side.output} of {side.id}",
                                 output=side.output)


def warmup_for(condition: Condition) -> int:
    warm = 1
    for side in (condition.left, condition.right):
        if side.type == "indicator":
            indicator = get_indicator(side.id)
            warm = max(warm, indicator.warmup(validate_params(indicator, side.params)))
    return warm


# ------------------------------------------------------------------ evaluation

def operand_series(operand, data: OHLCV) -> list[Optional[float]]:
    if operand.type == "price":
        return list(data.close)
    if operand.type == "value":
        return [operand.value] * len(data.close)
    indicator = get_indicator(operand.id)
    return indicator.compute(data, validate_params(indicator, operand.params))[operand.output]


@dataclass(frozen=True)
class Evaluation:
    met: bool
    left: Optional[float]
    right: Optional[float]
    price: Optional[float]
    candle_time: Optional[int]


def evaluate(condition: Condition, data: OHLCV, index: int) -> Evaluation:
    if index < 0 or index >= len(data.close):
        return Evaluation(False, None, None, None, None)
    left = operand_series(condition.left, data)
    right = operand_series(condition.right, data)
    lv, rv = left[index], right[index]
    if lv is None or rv is None:
        met = False
    elif condition.op == "crosses_above":
        met = crossover(left, right)[index]
    elif condition.op == "crosses_below":
        met = crossunder(left, right)[index]
    else:
        met = {">": lv > rv, "<": lv < rv, ">=": lv >= rv, "<=": lv <= rv, "==": lv == rv}[condition.op]
    return Evaluation(bool(met), lv, rv, data.close[index], data.time[index])


def at_open(data: OHLCV, index: int) -> OHLCV:
    """Candles up to `index`, the last one as it was right after it opened (only its open price)."""
    o = data.open[index]
    cut = index + 1
    return OHLCV(time=data.time[:cut], open=data.open[:cut], high=data.high[:index] + [o],
                 low=data.low[:index] + [o], close=data.close[:index] + [o], volume=data.volume[:index] + [0.0])


def evaluation_point(data: OHLCV, interval: str, trigger: str, now: float) -> tuple[OHLCV, int]:
    """Data and index of the candle the condition is evaluated on (-1 = nothing to evaluate yet)."""
    spec = parse(interval)
    last = len(data.time) - 1
    if trigger == "bar_close":
        for i in range(last, -1, -1):
            if spec.is_closed(data.time[i], now):
                return data, i
        return data, -1
    forming = last >= 0 and not spec.is_closed(data.time[last], now)
    if trigger == "bar_open":
        return (at_open(data, last), last) if forming else (data, -1)
    return data, last                            # intrabar: the newest candle


def load_data(candle_service, symbol: str, interval: str, warmup: int, now: float) -> OHLCV:
    step = parse(interval).seconds
    count = warmup + EXTRA_CANDLES
    series = candle_service.get_candles(symbol, interval, int(now) - count * step, int(now), max_candles=count + 2)
    return OHLCV.from_candles(series.candles)


def preview(alert_condition: Condition, symbol: str, interval: str, trigger: str,
            candle_service, now: Optional[float] = None) -> Evaluation:
    now = now or time.time()
    data = load_data(candle_service, symbol, interval, warmup_for(alert_condition), now)
    return evaluate(alert_condition, *evaluation_point(data, interval, trigger, now))


def _last_trigger_candle(db, alert: Alert) -> Optional[int]:
    row = (db.query(AlertEvent.candle_time).filter(AlertEvent.alert_id == alert.id)
           .order_by(AlertEvent.id.desc()).first())
    return row[0] if row else None


def check_alerts(db, candle_service, now: Optional[float] = None) -> list[AlertEvent]:
    """Evaluate all active alerts; returns the events created in this run."""
    now = now or time.time()
    now_dt = datetime.fromtimestamp(now, timezone.utc).replace(tzinfo=None)
    groups: dict[tuple[str, str], list[tuple[Alert, Condition]]] = defaultdict(list)
    for alert in db.query(Alert).filter(Alert.active.is_(True)).all():
        groups[(alert.symbol, alert.interval)].append((alert, Condition.model_validate_json(alert.condition)))

    events: list[AlertEvent] = []
    for (symbol, interval), items in groups.items():
        try:
            data = load_data(candle_service, symbol, interval, max(warmup_for(c) for _, c in items), now)
        except Exception as exc:  # exchange down etc. - try again next minute
            logger.warning("Alert check skipped for %s %s: %s", symbol, interval, exc)
            continue
        for alert, condition in items:
            alert.last_checked_at = now_dt
            point, index = evaluation_point(data, interval, alert.trigger, now)
            if index < 0:
                continue
            candle_time = point.time[index]
            if alert.trigger in PER_CANDLE and alert.last_candle_time == candle_time:
                continue                                         # this candle was already evaluated
            result = evaluate(condition, point, index)
            fire = result.met and alert.last_state is not True   # edge: not met -> met
            if fire and alert.trigger == "intrabar" and _last_trigger_candle(db, alert) == candle_time:
                fire = False                                     # at most one trigger per candle
            alert.last_state = result.met
            alert.last_candle_time = candle_time
            if not fire:
                continue
            event = AlertEvent(alert_id=alert.id, triggered_at=now_dt, candle_time=result.candle_time,
                               details=json.dumps({"left": result.left, "right": result.right, "price": result.price}))
            db.add(event)
            events.append(event)
            alert.last_triggered_at = now_dt
            if alert.mode == "once":
                alert.active = False
            logger.info("Alert %s fired: %s %s %s", alert.id, symbol, interval, alert.condition)
    db.commit()
    return events


# ------------------------------------------------------------------ background checker

class AlertScheduler:
    def __init__(self, session_factory, candle_service, interval_seconds: int):
        self._session_factory = session_factory
        self._candle_service = candle_service
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._interval <= 0 or self._thread:
            return
        self._thread = threading.Thread(target=self._run, name="alert-checker", daemon=True)
        self._thread.start()
        logger.info("Alert checker started (every %s s)", self._interval)

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                with self._session_factory() as db:
                    check_alerts(db, self._candle_service)
            except Exception:
                logger.exception("Alert check failed")
