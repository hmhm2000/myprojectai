"""Bybit.com account exports (Orders > Export > Account statements, ZIPs of CSVs).

Every file starts with a line "UID: ...,Company Name: ,Country: " and then a header; the file name
holds the period (..._20250101_20251231_0.csv, UTC days, end inclusive). Four kinds of files:

- AssetChangeDetails_uta: ledger of the Unified Trading Account - every balance change, newest first.
  Spot trades have Action "--" and Type TRADE: each fill is a row for the coin and a row for the
  quote currency with the same second, pair and direction. There are no order ids, so the fills of
  one second + pair + direction become ONE purchase / sale (summed quantity and fees, price weighted
  by quantity); external_id = "<pair>:<side>:<time>". Swaps between stablecoins / fiat (USDCUSDT,
  USDTPLN) are conversions, not positions. Perpetual rows (Action OPEN / CLOSE / SETTLEMENT) and the
  transfers to / from the Funding account are not imported here.
- AssetChangeDetails_fund: Funding account - deposits, withdrawals, airdrops -> transfers. Transfers
  between the user's own Bybit accounts (UTA, copy trading, MT5) are internal and skipped.
- AssetChangeDetails_copytrading: copy trading futures account - not imported here.
- withdrawDepositHistory: the same deposits / withdrawals as the Funding ledger (with chain and tx id,
  amounts without the network fee) - recognised but not imported, the Funding ledger is used instead.

A file only covers some kinds of entries (`ParsedExport.kinds`), so e.g. the Funding file never flags
the spot trades of the same account as missing.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from services.imports.adapters.base import ImportRecord, ParsedExport
from services.imports.adapters.okx import PRICE_STEP, QUOTES, _dec

STABLE = QUOTES | {"USDE", "DAI", "FDUSD", "EUR", "PLN", "USD1"}   # pairs of these are conversions
UTA = {"Currency", "Contract", "Type", "Direction", "Quantity", "Position", "Filled Price", "Fee Paid",
       "Cash Flow", "Change", "Wallet Balance", "Action", "Time(UTC)"}
FUND = {"Date & Time(UTC)", "Coin", "QTY", "Type", "Account Balance", "Description"}
HISTORY = {"Date", "Type", "Asset", "Chain", "Amount", "Tx ID", "Status"}
COPY = {"Time", "Currency", "Contract", "Type", "Direction", "Quantity", "Fee Paid", "Cash Flow", "Trade ID",
        "Order ID"}
FUND_IN = {"deposit": "transfer_in", "fiat": "transfer_in", "airdrop": "transfer_in", "withdraw": "transfer_out"}
FUND_INTERNAL = {"transfer in", "transfer out", "copy trading"}
PERIOD = re.compile(r"_(\d{8})_(\d{8})(?:_\d+)?\.csv$", re.I)


def _when(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _amount(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _kind(head: str):
    lines = head.lstrip("﻿").splitlines()
    if len(lines) < 2 or not lines[0].startswith("UID:"):
        return None
    columns = {c.strip() for c in next(csv.reader([lines[1]]))}
    for kind, required in (("uta", UTA), ("copytrading", COPY), ("fund", FUND), ("history", HISTORY)):
        if required <= columns:
            return kind
    return None


class BybitAccountAdapter:
    source = "bybit_com"
    name = "Bybit.com"

    def detect(self, path: Path, head: str) -> bool:
        return _kind(head) is not None

    def parse(self, path: Path) -> ParsedExport:
        text = path.read_text(encoding="utf-8-sig")
        kind = _kind(text[:4096])
        _, _, body = text.partition("\n")
        rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(io.StringIO(body))]
        result = ParsedExport(source=self.source, records=[], rows_total=len(rows), kinds=set())
        match = PERIOD.search(path.name)
        if match:
            start, end = (datetime.strptime(g, "%Y%m%d").replace(tzinfo=timezone.utc) for g in match.groups())
            result.period = (start, end + timedelta(days=1))

        if kind == "uta":
            self._uta(rows, result)
        elif kind == "fund":
            self._fund(rows, result)
        else:                                   # history / copytrading: recognised, nothing to import
            result.rows_skipped = len(rows)
            code = "deposit_history_skipped" if kind == "history" else "futures_not_imported"
            result.warnings.append({"code": code, "params": {"count": len(rows)}})
        result.records.sort(key=lambda r: (r.occurred_at, r.external_id))
        return result

    # ------------------------------------------------------------------ Unified Trading Account

    def _uta(self, rows: list[dict], result: ParsedExport) -> None:
        result.kinds = {"buy", "sell", "conversion"}
        result.balances = self._balances(rows)

        groups: dict[tuple[str, str, str], list[dict]] = {}
        ignored = Counter()
        for row in rows:
            action, kind = row["Action"].upper(), row["Type"].upper()
            if action == "--" and kind == "TRADE" and row["Contract"]:
                groups.setdefault((row["Time(UTC)"], row["Contract"], row["Direction"].lower()), []).append(row)
            elif action in ("OPEN", "CLOSE", "SETTLEMENT"):
                ignored["futures_not_imported"] += 1
            elif kind in ("TRANSFER_IN", "TRANSFER_OUT"):
                ignored["internal_transfers_skipped"] += 1
            else:
                result.rows_skipped += 1
                result.warnings.append({"code": "unsupported_row", "params": {
                    "id": row["Time(UTC)"], "type": f"{row['Type']} {row['Currency']} {row['Change']}",
                    "action": row["Action"]}})
        for code, count in ignored.items():
            result.rows_skipped += count
            result.warnings.append({"code": code, "params": {"count": count}})
        for (time, pair, side), group in groups.items():
            self._spot(time, pair, side, group, result)

    @staticmethod
    def _balances(rows: list[dict]) -> dict[str, Decimal]:
        """Wallet Balance of every currency after its last row. Rows of the same second are not in
        order in the file, so the last one is the row no other row of that second starts from."""
        last: dict[str, list[dict]] = {}
        for row in rows:
            moment, current = _when(row["Time(UTC)"]), last.get(row["Currency"])
            if current is None or moment > _when(current[0]["Time(UTC)"]):
                last[row["Currency"]] = [row]
            elif moment == _when(current[0]["Time(UTC)"]):
                current.append(row)
        balances = {}
        for coin, group in last.items():
            starts = {_dec(r["Wallet Balance"]) - _dec(r["Change"]) for r in group}
            ends = [r for r in group if _dec(r["Wallet Balance"]) not in starts]
            balances[coin] = _dec((ends[0] if len(ends) == 1 else group[0])["Wallet Balance"])
        return balances

    def _spot(self, time: str, pair: str, side: str, group: list[dict], result: ParsedExport) -> None:
        currencies = {r["Currency"] for r in group}
        quote = next((c for c in currencies if pair.endswith(c) and pair[: -len(c)] in currencies), None)
        if side not in ("buy", "sell") or quote is None:
            result.rows_skipped += len(group)
            result.warnings.append({"code": "unsupported_pair", "params": {"symbol": pair, "order": time}})
            return
        base = pair[: -len(quote)]
        coin_rows = [r for r in group if r["Currency"] == base]
        quote_rows = [r for r in group if r["Currency"] == quote]
        amount = sum((abs(_dec(r["Quantity"])) for r in coin_rows), Decimal(0))
        value = sum((abs(_dec(r["Quantity"])) * _dec(r["Filled Price"]) for r in coin_rows), Decimal(0))
        price = (value / amount).quantize(PRICE_STEP) if amount else Decimal(0)
        fee_coin = sum((abs(_dec(r["Fee Paid"])) for r in coin_rows), Decimal(0))
        fee_quote = sum((abs(_dec(r["Fee Paid"])) for r in quote_rows), Decimal(0))
        if side == "buy" and fee_quote and price:          # purchases keep the fee in the coin
            fee_coin, fee_quote = fee_coin + fee_quote / price, Decimal(0)
        if side == "sell" and fee_coin:                    # sales keep the fee in the quote currency
            fee_coin, fee_quote = Decimal(0), fee_quote + fee_coin * price
        conversion = base in STABLE or quote not in QUOTES
        external_id = f"{pair}:{side}:{time}"
        result.records.append(ImportRecord(
            source=self.source, external_id=external_id, kind="conversion" if conversion else side, symbol=base,
            quantity=amount, occurred_at=_when(time), price=price, quote=quote, fee_coin=fee_coin,
            fee_quote=fee_quote, fingerprint=f"{external_id}|{_amount(amount)}|{price}",
            rows=group, row_count=len(group)))

    # ------------------------------------------------------------------ Funding account

    def _fund(self, rows: list[dict], result: ParsedExport) -> None:
        result.kinds = {"transfer_in", "transfer_out"}
        internal = 0
        for row in rows:
            kind = row["Type"].lower()
            if kind in FUND_INTERNAL:
                internal += 1
                continue
            if kind not in FUND_IN:
                result.rows_skipped += 1
                result.warnings.append({"code": "unsupported_row", "params": {
                    "id": row["Date & Time(UTC)"], "type": row["Type"], "action": row["Description"]}})
                continue
            quantity = abs(_dec(row["QTY"]))
            external_id = f"fund:{kind}:{row['Date & Time(UTC)']}:{row['Coin']}:{_amount(quantity)}"
            result.records.append(ImportRecord(
                source=self.source, external_id=external_id, kind=FUND_IN[kind], symbol=row["Coin"],
                quantity=quantity, occurred_at=_when(row["Date & Time(UTC)"]), fingerprint=external_id,
                rows=[row]))
        if internal:
            result.rows_skipped += internal
            result.warnings.append({"code": "internal_transfers_skipped", "params": {"count": internal}})
