from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from database.db import Base
from models.portfolio import utcnow


class ChartIndicator(Base):
    """An indicator on the user's chart with its own settings (saved per user)."""

    __tablename__ = "chart_indicators"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    indicator_id = Column(String, nullable=False)        # e.g. "sma"
    params = Column(Text, nullable=False, default="{}")  # JSON, validated against the indicator definition
    interval = Column(String, nullable=True)             # own timeframe, e.g. "1d"; None = follow the chart
    visible = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utcnow)
