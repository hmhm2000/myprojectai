from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.portfolio import Note, normalize_symbol

Operator = Literal[">", "<", ">=", "<=", "==", "crosses_above", "crosses_below"]
Trigger = Literal["intrabar", "bar_open", "bar_close"]   # see services/alerts.py


class PriceOperand(BaseModel):
    type: Literal["price"]                 # candle close (= current price on the forming candle)


class ValueOperand(BaseModel):
    type: Literal["value"]
    value: float


class IndicatorOperand(BaseModel):
    type: Literal["indicator"]
    id: str                                # e.g. "rsi"
    params: dict = Field(default_factory=dict)
    output: str                            # e.g. "rsi", "lower" (BB), "signal" (MACD)


Operand = Annotated[Union[PriceOperand, ValueOperand, IndicatorOperand], Field(discriminator="type")]


class Condition(BaseModel):
    left: Operand
    op: Operator
    right: Operand


class AlertIn(BaseModel):
    symbol: str
    interval: str = "1h"
    condition: Condition
    mode: Literal["once", "repeat"] = "once"
    trigger: Trigger = "bar_close"
    note: Note = None

    _symbol = field_validator("symbol")(normalize_symbol)

    @field_validator("interval")
    @classmethod
    def _interval(cls, value: str) -> str:
        from services.intervals import parse

        return parse(value).name


class AlertPatch(BaseModel):
    active: Optional[bool] = None
    mode: Optional[Literal["once", "repeat"]] = None
    trigger: Optional[Trigger] = None
    note: Note = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    interval: str
    condition: Condition
    mode: str
    trigger: str
    active: bool
    note: Optional[str]
    last_state: Optional[bool]
    last_checked_at: Optional[datetime]
    last_triggered_at: Optional[datetime]
    created_at: datetime
    unseen_events: int = 0


class AlertEventOut(BaseModel):
    id: int
    alert_id: int
    symbol: str
    interval: str
    condition: Condition
    note: Optional[str]
    triggered_at: datetime                 # UTC
    candle_time: int
    details: dict
    seen: bool


class AlertCheckOut(BaseModel):
    """Current values of a condition (preview, does not change the alert)."""
    met: bool
    left: Optional[float]
    right: Optional[float]
    price: Optional[float]
    candle_time: Optional[int]


class MarkSeenIn(BaseModel):
    ids: Optional[list[int]] = None        # None = all events of the user
