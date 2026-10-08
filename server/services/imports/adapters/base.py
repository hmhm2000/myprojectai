"""Exchange export adapters - one per exchange.

An adapter only knows its file format: it recognises the file and maps it to `ImportRecord`s
(purchase, sale, transfer, futures) with `source` + `external_id`. Everything after that - saving
positions / sales, deduplication, cost calculations - is shared and exchange independent, so a new
exchange = a new adapter registered in `ADAPTERS`, no changes elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, Protocol

KINDS = ("buy", "sell", "transfer_in", "transfer_out", "futures")


@dataclass(frozen=True)
class ImportRecord:
    source: str                    # "okx"
    external_id: str               # unique per source (OKX: the "id" column of the main row)
    kind: str                      # one of KINDS
    symbol: str                    # coin (BTC) - for futures the instrument (BTC-USD-UM-XPERP-...)
    quantity: Decimal              # coins bought / sold / transferred (gross, before fees)
    occurred_at: datetime          # timezone aware
    price: Optional[Decimal] = None          # per coin, in the quote currency
    quote: Optional[str] = None              # USDC / USDT
    fee_coin: Decimal = Decimal(0)           # purchase fee taken in the coin
    fee_quote: Decimal = Decimal(0)          # sale fee taken in the quote currency
    value_usd: Optional[Decimal] = None      # e.g. value of a transfer at that moment
    fingerprint: str = ""                    # (time, order id, action, amount, filled price)
    rows: list[dict] = field(default_factory=list)   # the original export rows (all columns)
    row_count: int = 1                        # how many export rows make up this record

    def csv_values(self) -> dict:
        """Values that come from the export (compared on re-import; manual fields are never part of it)."""
        return {
            "kind": self.kind, "symbol": self.symbol, "quantity": str(self.quantity), "price": str(self.price),
            "fee_coin": str(self.fee_coin), "fee_quote": str(self.fee_quote),
            "occurred_at": self.occurred_at.isoformat(), "value_usd": str(self.value_usd),
        }


@dataclass
class ParsedExport:
    source: str
    records: list[ImportRecord]
    rows_total: int                                   # data rows in the file
    rows_skipped: int = 0                             # rows that could not be used
    warnings: list[dict] = field(default_factory=list)   # [{code, params}]
    period: Optional[tuple[datetime, datetime]] = None   # time range the export covers
    balances: dict[str, Decimal] = field(default_factory=dict)  # coin -> balance after the last row


class ExchangeAdapter(Protocol):
    source: str                    # "okx" - stored on every entry and on the exchange's import portfolio
    name: str                      # "OKX" - name of the import portfolio

    def detect(self, path: Path, head: str) -> bool:
        """True when the file (its first lines in `head`) is an export of this exchange."""

    def parse(self, path: Path) -> ParsedExport:
        """Map the rows of the file to import records."""
