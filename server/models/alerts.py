from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.db import Base
from models.portfolio import utcnow


class Alert(Base):
    """A private alert: `condition` (JSON) is evaluated on the candles of symbol/interval about once a minute."""

    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String, nullable=False)
    interval = Column(String, nullable=False)
    condition = Column(Text, nullable=False)          # JSON: {"left": operand, "op": ">", "right": operand}
    mode = Column(String, nullable=False, default="once")          # "once" (then deactivated) | "repeat"
    trigger = Column(String, nullable=False, default="bar_close")   # "intrabar" | "bar_open" | "bar_close"
    active = Column(Boolean, nullable=False, default=True)
    note = Column(Text, nullable=True)
    last_state = Column(Boolean, nullable=True)       # result of the previous check (edge detection)
    last_candle_time = Column(Integer, nullable=True) # candle of the previous check (bar_open/bar_close: once per candle)
    last_checked_at = Column(DateTime, nullable=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    events = relationship("AlertEvent", back_populates="alert", cascade="all, delete-orphan",
                          order_by="AlertEvent.triggered_at.desc()")


class AlertEvent(Base):
    """One trigger of an alert, with the values that met the condition."""

    __tablename__ = "alert_events"
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    triggered_at = Column(DateTime, nullable=False, default=utcnow)
    candle_time = Column(Integer, nullable=False)     # unix s of the candle that met the condition
    details = Column(Text, nullable=False)            # JSON: {"left": value, "right": value, "price": close}
    seen = Column(Boolean, nullable=False, default=False)

    alert = relationship("Alert", back_populates="events")
