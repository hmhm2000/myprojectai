"""Bybit spot "Trade History" export (Orders > Spot order > Trade history > Export, CSV).

Format: one header line with the columns Spot Pairs, Order Type, Direction, feeCoin, ExecFeeV2,
Filled Value, Filled Price, Filled Quantity, Fees, Transaction ID, Order No., Timestamp (UTC); the
file name holds the period as unix seconds (Bybit-Spot-TradeHistory-<start>-<end>.csv, end inclusive).

Every row is ONE executed fill - the file has no order status: a cancelled order without fills is not
in it at all, a partly filled and then cancelled one only with the filled part. Pairs have no
separator (SPXUSDC). Purchases pay the fee in the coin, sales in the quote currency (feeCoin). Times are
UTC and only to the minute ("17:52 2026-05-06"). Like OKX, all fills of an order become ONE purchase /
sale: summed quantity and fees, price = average weighted by quantity, time of the first fill. The
record's external_id is the Order No.; the Transaction IDs of the fills are kept as legacy_ids.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from services.imports.adapters.base import ImportRecord, ParsedExport
from services.imports.adapters.okx import PRICE_STEP, _dec

QUOTES = ("USDT", "USDC", "USD")           # longest first: SPXUSDC is SPX / USDC, not SPXUSD / C
REQUIRED = {"Spot Pairs", "Direction", "feeCoin", "Filled Price", "Filled Quantity", "Transaction ID",
            "Order No.", "Timestamp (UTC)"}
PERIOD = re.compile(r"-(\d{9,11})-(\d{9,11})\.csv$", re.I)
TIME_FORMATS = ("%H:%M %Y-%m-%d", "%H:%M:%S %Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")


def _when(value: str) -> datetime:
    value = value.strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError(f"Unknown Bybit time format: {value!r}")


def _fee(row: dict) -> Decimal:
    """ExecFeeV2 (current exports); older ones had the amount in "Fees" ("--" when empty)."""
    for column in ("ExecFeeV2", "Fees"):
        value = (row.get(column) or "").strip()
        if value and value != "--":
            return abs(_dec(value))
    return Decimal(0)


class BybitAdapter:
    source = "bybit"
    name = "Bybit"

    def detect(self, path: Path, head: str) -> bool:
        lines = head.lstrip("﻿").splitlines()
        return bool(lines) and REQUIRED <= {c.strip() for c in next(csv.reader([lines[0]]))}

    def parse(self, path: Path) -> ParsedExport:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k}
                    for row in csv.DictReader(handle)]
        rows = [r for r in rows if r.get("Spot Pairs")]
        result = ParsedExport(source=self.source, records=[], rows_total=len(rows))

        match = PERIOD.search(path.name)
        if match:
            start, end = (datetime.fromtimestamp(int(g), tz=timezone.utc) for g in match.groups())
            result.period = (start, end + timedelta(seconds=1))
        elif rows:
            times = [_when(r["Timestamp (UTC)"]) for r in rows]
            result.period = (min(times), max(times) + timedelta(minutes=1))

        orders: dict[tuple[str, str, str], list[dict]] = {}
        for row in rows:
            side = row["Direction"].lower()
            if side not in ("buy", "sell"):
                result.rows_skipped += 1
                result.warnings.append({"code": "unsupported_row", "params": {
                    "id": row["Transaction ID"], "type": row["Spot Pairs"], "action": row["Direction"]}})
                continue
            order = row["Order No."] or row["Transaction ID"]
            orders.setdefault((order, row["Spot Pairs"], side), []).append(row)

        for (order, pair, side), fills in orders.items():
            self._order(order, pair, side, fills, result)
        result.records.sort(key=lambda r: (r.occurred_at, r.external_id))
        return result

    def _order(self, order: str, pair: str, side: str, fills: list[dict], result: ParsedExport) -> None:
        quote = next((q for q in QUOTES if pair.endswith(q) and len(pair) > len(q)), None)
        if quote is None:
            result.rows_skipped += len(fills)
            result.warnings.append({"code": "unsupported_pair", "params": {"symbol": pair, "order": order}})
            return
        base = pair[: -len(quote)]
        fills = sorted(fills, key=lambda r: (_when(r["Timestamp (UTC)"]), r["Transaction ID"]))
        amount = sum((_dec(r["Filled Quantity"]) for r in fills), Decimal(0))
        value = sum((_dec(r["Filled Quantity"]) * _dec(r["Filled Price"]) for r in fills), Decimal(0))
        price = (value / amount).quantize(PRICE_STEP) if amount else Decimal(0)

        fee_coin = fee_quote = Decimal(0)
        for row in fills:
            unit = row["feeCoin"].upper()
            if unit == base:
                fee_coin += _fee(row)
            elif unit == quote:
                fee_quote += _fee(row)
            elif _fee(row):                                  # e.g. a fee discount paid in another coin
                result.warnings.append({"code": "fee_other_coin", "params": {
                    "id": row["Transaction ID"], "fee": format(_fee(row).normalize(), "f"), "coin": unit}})
        if side == "buy" and fee_quote and price:            # purchases keep the fee in the coin
            fee_coin, fee_quote = fee_coin + fee_quote / price, Decimal(0)
        if side == "sell" and fee_coin:                      # sales keep the fee in the quote currency
            fee_coin, fee_quote = Decimal(0), fee_quote + fee_coin * price

        first = fills[0]
        occurred_at = _when(first["Timestamp (UTC)"])
        fingerprint = "|".join((first["Timestamp (UTC)"], order, side, str(amount), str(price)))
        result.records.append(ImportRecord(
            source=self.source, external_id=order, kind=side, symbol=base, quantity=amount,
            occurred_at=occurred_at, price=price, quote=quote, fee_coin=fee_coin, fee_quote=fee_quote,
            fingerprint=fingerprint, rows=fills, row_count=len(fills),
            legacy_ids=tuple(r["Transaction ID"] for r in fills)))
