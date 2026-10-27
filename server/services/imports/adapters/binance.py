"""Binance "Spot Trade History" export (Orders > Spot Order > Trade History > Export, CSV).

Format: one header line Order No, Time, Pair, Side, Price, Executed, Amount, Fee (+ AOR Conversion
Pair / Rate, empty); the file name holds the time zone of the Time column, e.g.
"Binance-Spot-Trade-History-202610271452(UTC+1)-part1-of1.csv". Executed / Amount / Fee carry their
currency glued to the number ("0.1291ETH", "199.64USDC", "0.00012265ETH") - Executed is the coin,
Amount the quote currency.

Every row is one executed fill (no status - cancelled orders without fills are not in the file).
Fills of one order may be identical rows (same price and size): they are all real. All fills of an
order become ONE purchase / sale like OKX (summed quantity and fees, price weighted by quantity, time of
the first fill); external_id = Order No. Purchases keep the fee in the coin, sales in the quote
currency; a fee in another coin (BNB) is reported and not counted. Stablecoin / fiat swaps (USDCUSDT,
USDTPLN) are conversions. A coin bought for fiat (ETHPLN) is priced in USDT with the USDT/fiat rate of
the nearest swap in the same file (reported with the rate); without one the order is skipped.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from services.imports.adapters.base import ImportRecord, ParsedExport
from services.imports.adapters.bybit_account import STABLE
from services.imports.adapters.okx import PRICE_STEP, QUOTES, _dec

REQUIRED = {"Order No", "Time", "Pair", "Side", "Price", "Executed", "Amount", "Fee"}
TZ = re.compile(r"\(UTC\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?\)", re.I)
NUMBER = re.compile(r"^\s*([0-9][0-9.,]*)\s*([A-Za-z][A-Za-z0-9]*)?\s*$")
FIAT = {"PLN", "EUR", "USD", "GBP", "TRY", "BRL", "UAH"}


def _amount(value: str, unit: str) -> Decimal:
    """'0.1291ETH' with unit ETH -> 0.1291 (the unit is cut from the end - "E" of ETH is not an exponent,
    and coins may start with a digit: '5.21INCH')."""
    value = (value or "").strip()
    if unit and value.upper().endswith(unit):
        value = value[: -len(unit)]
    return _dec(value.replace(",", ""))


def _units(row: dict) -> tuple[str, str]:
    """(coin, quote) of the row: the split of Pair whose parts end Executed and Amount."""
    pair, executed, amount = row["Pair"].upper(), row["Executed"].upper(), row["Amount"].upper()
    for i in range(1, len(pair)):
        base, quote = pair[:i], pair[i:]
        if executed.endswith(base) and amount.endswith(quote):
            return base, quote
    return "", ""


def _fee(value: str, base: str, quote: str) -> tuple[Decimal, str]:
    for unit in (base, quote):
        if unit and value.upper().endswith(unit):
            return _amount(value, unit), unit
    match = NUMBER.match(value or "")
    return (_dec(match.group(1).replace(",", "")), (match.group(2) or "").upper()) if match else (Decimal(0), "")


def _tz(name: str) -> timezone:
    match = TZ.search(name)
    if not match:
        return timezone.utc
    sign = 1 if match.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3) or 0)))


class BinanceAdapter:
    source = "binance"
    name = "Binance"

    def detect(self, path: Path, head: str) -> bool:
        lines = head.lstrip("﻿").splitlines()
        return bool(lines) and REQUIRED <= {c.strip() for c in next(csv.reader([lines[0]]))}

    def parse(self, path: Path) -> ParsedExport:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(handle)]
        rows = [r for r in rows if r.get("Order No")]
        tz = _tz(path.name)
        when = lambda row: datetime.strptime(row["Time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        result = ParsedExport(source=self.source, records=[], rows_total=len(rows))
        if rows:
            times = [when(r) for r in rows]
            result.period = (min(times), max(times) + timedelta(seconds=1))

        orders: dict[tuple[str, str, str], list[dict]] = {}
        for row in rows:
            orders.setdefault((row["Order No"], row["Pair"], row["Side"].lower()), []).append(row)
        rates = self._fiat_rates(orders, when)
        for (order, pair, side), fills in orders.items():
            self._order(order, pair, side, sorted(fills, key=when), when, rates, result)
        result.records.sort(key=lambda r: (r.occurred_at, r.external_id))
        return result

    @staticmethod
    def _fiat_rates(orders, when) -> list[tuple[datetime, str, Decimal]]:
        """(time, fiat, fiat per USDT/USDC) of every stablecoin <-> fiat swap in the file."""
        rates = []
        for fills in orders.values():
            base, quote = _units(fills[0])
            if base in QUOTES and quote in FIAT:
                amount = sum((_amount(r["Executed"], base) for r in fills), Decimal(0))
                value = sum((_amount(r["Amount"], quote) for r in fills), Decimal(0))
                if amount:
                    rates.append((when(fills[0]), quote, value / amount))
        return rates

    def _order(self, order, pair, side, fills, when, rates, result: ParsedExport) -> None:
        base, quote = _units(fills[0])
        if side not in ("buy", "sell") or not base:
            result.rows_skipped += len(fills)
            result.warnings.append({"code": "unsupported_row", "params": {"id": order, "type": pair, "action": side}})
            return
        amount = sum((_amount(r["Executed"], base) for r in fills), Decimal(0))
        value = sum((_amount(r["Executed"], base) * _dec(r["Price"]) for r in fills), Decimal(0))
        price = (value / amount).quantize(PRICE_STEP) if amount else Decimal(0)
        fee_coin = fee_quote = Decimal(0)
        for row in fills:
            fee, unit = _fee(row["Fee"], base, quote)
            if unit == base:
                fee_coin += fee
            elif unit == quote:
                fee_quote += fee
            elif fee:
                result.warnings.append({"code": "fee_other_coin", "params": {
                    "id": order, "fee": format(fee.normalize(), "f"), "coin": unit}})

        kind, record_quote = side, quote
        if base in STABLE and quote in STABLE | FIAT:
            kind = "conversion"
        elif quote in FIAT:
            moment = when(fills[0])
            known = [r for r in rates if r[1] == quote]
            if not known:
                result.rows_skipped += len(fills)
                result.warnings.append({"code": "unsupported_pair", "params": {"symbol": pair, "order": order}})
                return
            rate = min(known, key=lambda r: abs(r[0] - moment))[2]
            price, fee_quote, record_quote = (price / rate).quantize(PRICE_STEP), fee_quote / rate, "USDT"
            result.warnings.append({"code": "fiat_converted", "params": {
                "id": order, "symbol": pair, "rate": format(rate.quantize(Decimal("0.0001")), "f"), "fiat": quote}})
        elif quote not in QUOTES:
            result.rows_skipped += len(fills)
            result.warnings.append({"code": "unsupported_pair", "params": {"symbol": pair, "order": order}})
            return

        if kind == "buy" and fee_quote and price:              # purchases keep the fee in the coin
            fee_coin, fee_quote = fee_coin + fee_quote / price, Decimal(0)
        if kind == "sell" and fee_coin:                        # sales keep the fee in the quote currency
            fee_coin, fee_quote = Decimal(0), fee_quote + fee_coin * price
        first = fills[0]
        result.records.append(ImportRecord(
            source=self.source, external_id=order, kind=kind, symbol=base, quantity=amount,
            occurred_at=when(first), price=price, quote=record_quote, fee_coin=fee_coin, fee_quote=fee_quote,
            fingerprint="|".join((first["Time"], order, side, str(amount), str(price))),
            rows=fills, row_count=len(fills)))
