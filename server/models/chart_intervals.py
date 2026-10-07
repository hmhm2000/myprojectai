from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint

from database.db import Base


class ChartInterval(Base):
    """The user's chart interval: a custom one (3d, 2w ...) or a preset with a changed "pinned" state.

    Presets (1m ... 1M) without a row are pinned (shown as buttons above the chart)."""

    __tablename__ = "chart_intervals"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_chart_intervals_user_name"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)                # canonical name, e.g. "3d"
    custom = Column(Boolean, nullable=False, default=True)
    pinned = Column(Boolean, nullable=False, default=True)
