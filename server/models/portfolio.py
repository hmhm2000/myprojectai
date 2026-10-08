from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.db import Base
from database.types import DecimalString, TagList


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Portfolio(Base):
    __tablename__ = "portfolios"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="portfolios")
    positions = relationship(
        "Position",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        order_by="Position.sort_order",
    )


class Position(Base):
    """A single purchase. Profit/loss is calculated separately for every position."""

    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)  # e.g. "BTC"
    buy_price = Column(DecimalString, nullable=False)    # in quote currency (USDT) per 1 coin
    quantity = Column(DecimalString, nullable=False)     # bought quantity (before fee)
    fee_coin = Column(DecimalString, nullable=False, default=0)  # fee taken in coin
    bought_at = Column(DateTime, nullable=False)
    # Trade journal (entry)
    entry_reason = Column(Text, nullable=True)            # why I bought - free text
    tags = Column(TagList, nullable=False, default=list)  # optional tags, e.g. ["RSI", "SUPPORT"]
    plan = Column(Text, nullable=True)
    target_price = Column(DecimalString, nullable=True)
    stop_loss = Column(DecimalString, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)  # order set by drag & drop
    show_on_chart = Column(Boolean, nullable=False, default=True)  # presentation only - never used in calculations
    created_at = Column(DateTime, nullable=False, default=utcnow)
    # Origin: "manual" (the form) or an exchange import ("okx"); the same model and fields for both.
    source = Column(String, nullable=False, default="manual", server_default="manual")
    external_id = Column(String, nullable=True, index=True)   # e.g. OKX "id" of the trade row
    fingerprint = Column(String, nullable=True, index=True)   # duplicate guard (time, order, action, amount, price)
    raw = Column(Text, nullable=True)                          # JSON: the original export rows (details view only)
    import_file_id = Column(Integer, ForeignKey("import_files.id", ondelete="SET NULL"), nullable=True)
    imported_at = Column(DateTime, nullable=True)
    missing_in_export = Column(Boolean, nullable=False, default=False, server_default="0")
    note = Column(Text, nullable=True)                         # details view: free notes
    custom_fields = Column(Text, nullable=True)                # details view: JSON {name: value}

    portfolio = relationship("Portfolio", back_populates="positions")
    sales = relationship(
        "Sale",
        back_populates="position",
        cascade="all, delete-orphan",
        order_by="Sale.sold_at",
    )


class Sale(Base):
    """A (partial or full) sale of one position.

    A single sale transaction may cover several positions - it is then stored as several
    rows sharing the same group_id (same price and date, fee split proportionally).
    """

    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), nullable=False, index=True)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(DecimalString, nullable=False)       # sale price per 1 coin
    quantity = Column(DecimalString, nullable=False)    # sold coin quantity
    fee_quote = Column(DecimalString, nullable=False, default=0)  # fee in quote currency (USDT)
    sold_at = Column(DateTime, nullable=False)
    exit_reason = Column(Text, nullable=True)  # trade journal: why I sold
    show_on_chart = Column(Boolean, nullable=False, default=True)  # presentation only
    created_at = Column(DateTime, nullable=False, default=utcnow)
    # Origin: "manual" (the form) or an exchange import ("okx"); same on every row of a sale group.
    source = Column(String, nullable=False, default="manual", server_default="manual")
    external_id = Column(String, nullable=True, index=True)   # e.g. OKX "id" of the trade row
    fingerprint = Column(String, nullable=True, index=True)   # duplicate guard (time, order, action, amount, price)
    raw = Column(Text, nullable=True)                          # JSON: the original export rows (details view only)
    import_file_id = Column(Integer, ForeignKey("import_files.id", ondelete="SET NULL"), nullable=True)
    imported_at = Column(DateTime, nullable=True)
    missing_in_export = Column(Boolean, nullable=False, default=False, server_default="0")
    note = Column(Text, nullable=True)                         # details view: free notes
    custom_fields = Column(Text, nullable=True)                # details view: JSON {name: value}

    position = relationship("Position", back_populates="sales")
