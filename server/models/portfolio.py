from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.db import Base
from database.types import DecimalString


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
    """Jeden zakup. Zysk liczony jest osobno dla każdej pozycji."""

    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)  # np. "BTC"
    buy_price = Column(DecimalString, nullable=False)    # w walucie kwotowania (USDT) za 1 coin
    quantity = Column(DecimalString, nullable=False)     # kupiona ilość (przed opłatą)
    fee_coin = Column(DecimalString, nullable=False, default=0)  # opłata pobrana w coinie
    bought_at = Column(DateTime, nullable=False)
    note = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)  # kolejność ustawiana przeciąganiem
    created_at = Column(DateTime, nullable=False, default=utcnow)

    portfolio = relationship("Portfolio", back_populates="positions")
    sales = relationship(
        "Sale",
        back_populates="position",
        cascade="all, delete-orphan",
        order_by="Sale.sold_at",
    )


class Sale(Base):
    """Sprzedaż (częściowa lub całkowita) konkretnej pozycji.

    Jedna transakcja sprzedaży może obejmować kilka pozycji - wtedy jest zapisana jako kilka
    wierszy z tym samym group_id (ta sama cena i data, opłata rozdzielona proporcjonalnie).
    """

    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), nullable=False, index=True)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(DecimalString, nullable=False)       # cena sprzedaży za 1 coin
    quantity = Column(DecimalString, nullable=False)    # sprzedana ilość coina
    fee_quote = Column(DecimalString, nullable=False, default=0)  # opłata w USDT
    sold_at = Column(DateTime, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    position = relationship("Position", back_populates="sales")
