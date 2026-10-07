from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database.db import Base
from models.portfolio import utcnow


class FavoriteList(Base):
    __tablename__ = "favorite_lists"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="favorite_lists")
    coins = relationship(
        "FavoriteCoin",
        back_populates="favorite_list",
        cascade="all, delete-orphan",
        order_by="FavoriteCoin.added_at",
    )


class FavoriteCoin(Base):
    __tablename__ = "favorite_coins"
    __table_args__ = (UniqueConstraint("list_id", "symbol", name="uq_favorite_coin_list_symbol"),)

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("favorite_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String, nullable=False)  # e.g. "SPX"
    added_at = Column(DateTime, nullable=False, default=utcnow)

    favorite_list = relationship("FavoriteList", back_populates="coins")
