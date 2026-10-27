"""Test view of deposits / withdrawals between exchanges (services/transfers_lab.py).

The view only reads the export files and the stored trades - the one thing it saves is how the user
labelled a withdrawal address (own wallet or not). Nothing here changes portfolios or trades.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from database.db import Base
from models.portfolio import utcnow


class TransferAddress(Base):
    __tablename__ = "transfer_addresses"
    __table_args__ = (UniqueConstraint("user_id", "address", name="uq_transfer_addresses_user_address"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    address = Column(String, nullable=False)
    owner = Column(String, nullable=True)          # own | foreign | None (not decided)
    label = Column(String, nullable=True)          # e.g. "Phantom", "MetaMask"
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
