"""Import of exchange exports (CSV) - files, change history, account movements and settings.

Trades from an import are stored as ordinary positions / sales (models.portfolio) with
`source` + `external_id`; this module holds what the manual model has no place for.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from database.db import Base
from database.types import DecimalString
from models.portfolio import utcnow


class ImportFile(Base):
    """One processed export file (a file with the same sha256 is not processed again)."""

    __tablename__ = "import_files"
    __table_args__ = (UniqueConstraint("user_id", "sha256", name="uq_import_files_user_sha256"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    sha256 = Column(String(64), nullable=False)
    source = Column(String, nullable=False)                 # "okx"
    imported_at = Column(DateTime, nullable=False, default=utcnow)
    rows_total = Column(Integer, nullable=False, default=0)
    rows_new = Column(Integer, nullable=False, default=0)
    rows_updated = Column(Integer, nullable=False, default=0)
    rows_skipped = Column(Integer, nullable=False, default=0)
    rows_unchanged = Column(Integer, nullable=False, default=0)
    warnings = Column(Text, nullable=False, default="[]")   # JSON list of {code, params}


class ImportChange(Base):
    """History of values changed by a later import (what was, what is, when, from which file)."""

    __tablename__ = "import_changes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String, nullable=False)
    external_id = Column(String, nullable=False, index=True)
    field = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    file_id = Column(Integer, ForeignKey("import_files.id", ondelete="SET NULL"), nullable=True)
    changed_at = Column(DateTime, nullable=False, default=utcnow)


class AccountMovement(Base):
    """Account entries that are not a purchase or a sale: transfers in/out, futures, sales without a
    matching purchase. Shown in the transaction details, never in the main portfolio view."""

    __tablename__ = "account_movements"
    __table_args__ = (UniqueConstraint("user_id", "source", "external_id", name="uq_account_movements_external"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True, index=True)
    kind = Column(String, nullable=False)                  # transfer_in | transfer_out | futures | sell_uncovered
    symbol = Column(String, nullable=False)                # coin, or the futures instrument
    quantity = Column(DecimalString, nullable=False)
    price = Column(DecimalString, nullable=True)
    fee = Column(DecimalString, nullable=True)
    value_usd = Column(DecimalString, nullable=True)       # e.g. value of a transfer at that time
    occurred_at = Column(DateTime, nullable=False)          # local time, like bought_at / sold_at
    # Same import fields as positions / sales
    source = Column(String, nullable=False, default="manual")
    external_id = Column(String, nullable=True)
    fingerprint = Column(String, nullable=True, index=True)
    raw = Column(Text, nullable=True)
    import_file_id = Column(Integer, ForeignKey("import_files.id", ondelete="SET NULL"), nullable=True)
    imported_at = Column(DateTime, nullable=True)
    missing_in_export = Column(Boolean, nullable=False, default=False)
    note = Column(Text, nullable=True)
    custom_fields = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ImportSettings(Base):
    """Per user: which portfolio imported trades go to and the cost method of the details view."""

    __tablename__ = "import_settings"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True)
    cost_method = Column(String, nullable=False, default="average")   # average | fifo | lifo
