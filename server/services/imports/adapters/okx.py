"""OKX "Trading History" export (Assets > Order center > Download, CSV).

Format: a first line "UID:...,Account Type:...,Time Zone:UTC+8", then a header with the columns
id, Order id, Time, Trade Type, Symbol, Action, Amount, Trading Unit, Filled Price, PnL, Fee, Fee Unit,
Position Change, Position Balance, Balance Change, Balance, Balance Unit, Filled_price-USD, Pnl-USD,
Fee-USD, Balance-USD, Balance_change-USD. Times are in the time zone from the first line.

Spot: every fill is TWO rows with the same Order id - one for the coin (Balance Unit = BTC; Action
says Buy / Sell, fee in BTC on purchases) and one for the quote currency (Balance Unit = USDC, the
opposite Action, fee in USDC on sales). Their ids are not consecutive and one order may have several
fills, so a coin row is paired with the quote row of the same order whose amount = coin amount x
price. The record's external_id is the id of the coin row.
Transfer rows (Transfer in / out) -> transfers; Futures rows -> futures (stored, not part of spot).
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from services.imports.adapters.base import ImportRecord, ParsedExport

QUOTES = {"USDT", "USDC", "USD"}
REQUIRED = {"id", "Order id", "Time", "Trade Type", "Symbol", "Action", "Amount", "Filled Price", "Fee",
            "Fee Unit", "Balance Change", "Balance", "Balance Unit"}
PERIOD = re.compile(r"(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})")
TZ = re.compile(r"Time Zone:\s*UTC\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?", re.I)


def _dec(value) -> Decimal:
    try:
        return Decimal(str(value).strip() or "0")
    except InvalidOperation:
        return Decimal(0)


def _tz(first_line: str) -> timezone:
    match = TZ.search(first_line)
    if not match:
        return timezone.utc
    sign = 1 if match.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3) or 0)))


def _fingerprint(row: dict) -> str:
    return "|".join(row.get(k, "").strip() for k in ("Time", "Order id", "Action", "Amount", "Filled Price"))


class OkxAdapter:
    source = "okx"

    def detect(self, path: Path, head: str) -> bool:
        lines = head.lstrip("﻿").splitlines()
        return len(lines) >= 2 and "Time Zone" in lines[0] and REQUIRED <= set(next(csv.reader([lines[1]])))

    def parse(self, path: Path) -> ParsedExport:
        text = path.read_text(encoding="utf-8-sig")
        first_line, _, body = text.partition("\n")
        tz = _tz(first_line)
        rows = list(csv.DictReader(io.StringIO(body)))
        result = ParsedExport(source=self.source, records=[], rows_total=len(rows))
        when = lambda row: datetime.strptime(row["Time"].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)

        match = PERIOD.search(path.name)
        if match:
            start = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=tz)
            end = datetime.strptime(match.group(2), "%Y-%m-%d").replace(tzinfo=tz) + timedelta(days=1)
            result.period = (start, end)
        elif rows:
            times = [when(r) for r in rows]
            result.period = (min(times), max(times))

        for row in sorted(rows, key=lambda r: (r["Time"], int(r["id"] or 0))):
            if row.get("Balance Unit"):
                result.balances[row["Balance Unit"].strip()] = _dec(row["Balance"])

        spot: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            kind = row["Trade Type"].strip()
            action = row["Action"].strip().lower()
            if kind == "Spot":
                spot.setdefault((row["Order id"], row["Symbol"]), []).append(row)
            elif kind == "Transfer" and action in ("transfer in", "transfer out"):
                result.records.append(self._transfer(row, when(row)))
            elif kind in ("Futures", "Perpetual", "Swap", "Margin", "Options"):
                result.records.append(self._futures(row, when(row)))
            else:
                result.rows_skipped += 1
                result.warnings.append({"code": "unsupported_row", "params": {"id": row["id"], "type": kind,
                                                                             "action": row["Action"]}})

        for (order_id, symbol), group in spot.items():
            self._spot(order_id, symbol, group, when, result)
        result.records.sort(key=lambda r: (r.occurred_at, r.external_id))
        return result

    # ------------------------------------------------------------------ rows -> records

    def _spot(self, order_id, symbol, group, when, result: ParsedExport) -> None:
        base, _, quote = symbol.partition("-")
        if quote not in QUOTES:
            result.rows_skipped += len(group)
            result.warnings.append({"code": "unsupported_pair", "params": {"symbol": symbol, "order": order_id}})
            return
        coin_rows = [r for r in group if r["Balance Unit"].strip() == base]
        quote_rows = [r for r in group if r["Balance Unit"].strip() == quote]
        for row in coin_rows:
            price = _dec(row["Filled Price"])
            amount = _dec(row["Amount"])
            pair = self._pair(row, quote_rows, amount * price)
            if pair is not None:
                quote_rows.remove(pair)
            else:
                result.warnings.append({"code": "unpaired_row", "params": {"id": row["id"], "symbol": symbol}})
            legs = [row] + ([pair] if pair else [])
            fee_coin = sum((-_dec(r["Fee"]) for r in legs if r["Fee Unit"].strip() == base), Decimal(0))
            fee_quote = sum((-_dec(r["Fee"]) for r in legs if r["Fee Unit"].strip() == quote), Decimal(0))
            side = row["Action"].strip().lower()
            if side not in ("buy", "sell"):
                result.rows_skipped += len(legs)
                continue
            if side == "buy" and fee_quote and price:        # purchases keep the fee in the coin
                fee_coin, fee_quote = fee_coin + fee_quote / price, Decimal(0)
            if side == "sell" and fee_coin:                  # sales keep the fee in the quote currency
                fee_coin, fee_quote = Decimal(0), fee_quote + fee_coin * price
            result.records.append(ImportRecord(
                source=self.source, external_id=row["id"].strip(), kind=side, symbol=base, quantity=amount,
                occurred_at=when(row), price=price, quote=quote, fee_coin=fee_coin, fee_quote=fee_quote,
                fingerprint=_fingerprint(row), rows=legs, row_count=len(legs)))
        for row in quote_rows:                               # quote rows without a coin row
            result.rows_skipped += 1
            result.warnings.append({"code": "unpaired_row", "params": {"id": row["id"], "symbol": symbol}})

    @staticmethod
    def _pair(row: dict, candidates: list[dict], expected: Decimal) -> Optional[dict]:
        same_price = [r for r in candidates if _dec(r["Filled Price"]) == _dec(row["Filled Price"])]
        if not same_price:
            return None
        best = min(same_price, key=lambda r: abs(_dec(r["Amount"]) - expected))
        tolerance = max(expected * Decimal("0.00001"), Decimal("0.00000001"))
        return best if abs(_dec(best["Amount"]) - expected) <= tolerance else None

    def _transfer(self, row: dict, when: datetime) -> ImportRecord:
        incoming = row["Action"].strip().lower() == "transfer in"
        return ImportRecord(
            source=self.source, external_id=row["id"].strip(), kind="transfer_in" if incoming else "transfer_out",
            symbol=row["Balance Unit"].strip(), quantity=abs(_dec(row["Balance Change"])), occurred_at=when,
            value_usd=abs(_dec(row.get("Balance_change-USD"))), fingerprint=_fingerprint(row), rows=[row])

    def _futures(self, row: dict, when: datetime) -> ImportRecord:
        return ImportRecord(
            source=self.source, external_id=row["id"].strip(), kind="futures", symbol=row["Symbol"].strip(),
            quantity=_dec(row["Amount"]), occurred_at=when, price=_dec(row["Filled Price"]),
            quote=row["Fee Unit"].strip() or None, fee_quote=-_dec(row["Fee"]),
            value_usd=_dec(row.get("Pnl-USD")), fingerprint=_fingerprint(row), rows=[row])
