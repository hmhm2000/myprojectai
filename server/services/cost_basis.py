"""Cost basis of one coin from its history - weighted average, FIFO or LIFO (all Decimal).

Works on plain ledger events built from the stored entries (positions, sales, transfers), so it is
the same for manual entries and for every exchange import:
- buy:          adds (quantity - fee in coin) at cost quantity x price (the quote spent),
- transfer_in:  adds the quantity at its value at that time (unknown value = 0 cost),
- sell:         removes the quantity; realized = quantity x price - fee - cost of the removed coins,
- transfer_out: removes the quantity with its cost - moved to another account, not a profit or loss.
Removing more than is held (e.g. coins from before the export) is reported as `uncovered`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

ZERO = Decimal(0)
METHODS = ("average", "fifo", "lifo")


@dataclass(frozen=True)
class LedgerEvent:
    time: datetime
    kind: str                     # buy | sell | transfer_in | transfer_out
    quantity: Decimal
    price: Decimal = ZERO
    fee_coin: Decimal = ZERO      # buy: fee taken in the coin
    fee_quote: Decimal = ZERO     # sell: fee in the quote currency
    value: Optional[Decimal] = None   # transfer_in: value at that time
    order: int = 0                # tie-break for events at the same time


@dataclass(frozen=True)
class CostSummary:
    method: str
    balance: Decimal              # coins held
    cost: Decimal                 # cost of the coins held
    average_cost: Optional[Decimal]   # cost / balance
    realized: Decimal             # net of fees
    fees: Decimal                 # all fees in the quote currency (coin fees valued at the trade price)
    transferred_out: Decimal
    transferred_out_cost: Decimal
    transferred_out_average_cost: Optional[Decimal]   # cost per coin of what was moved out
    uncovered: Decimal            # sold / sent but not held according to the history
    price: Optional[Decimal]
    value: Optional[Decimal]
    unrealized: Optional[Decimal]


def summarize(events: Iterable[LedgerEvent], method: str = "average", price: Optional[Decimal] = None) -> CostSummary:
    if method not in METHODS:
        raise ValueError(f"Unknown cost method: {method}")
    lots: list[list[Decimal]] = []      # [quantity, cost] (FIFO / LIFO); one lot for the average
    realized = fees = out_qty = out_cost = uncovered = ZERO

    def remove(quantity: Decimal) -> Decimal:
        """Take `quantity` out of the lots, return its cost."""
        nonlocal uncovered
        if method == "average":
            held = sum((lot[0] for lot in lots), ZERO)
            cost = sum((lot[1] for lot in lots), ZERO)
            taken = min(quantity, held)
            removed = cost * taken / held if held > 0 else ZERO
            lots[:] = [[held - taken, cost - removed]] if held - taken > 0 else []
            uncovered += quantity - taken
            return removed
        removed, left = ZERO, quantity
        while left > 0 and lots:
            lot = lots[0] if method == "fifo" else lots[-1]
            take = min(left, lot[0])
            part = lot[1] * take / lot[0]
            lot[0] -= take
            lot[1] -= part
            removed += part
            left -= take
            if lot[0] <= 0:
                lots.remove(lot)
        uncovered += left
        return removed

    for event in sorted(events, key=lambda e: (e.time, e.order)):
        if event.kind == "buy":
            lots.append([event.quantity - event.fee_coin, event.quantity * event.price])
            fees += event.fee_coin * event.price
        elif event.kind == "transfer_in":
            lots.append([event.quantity, event.value or ZERO])
        elif event.kind == "sell":
            cost = remove(event.quantity)
            realized += event.quantity * event.price - event.fee_quote - cost
            fees += event.fee_quote
        elif event.kind == "transfer_out":
            out_cost += remove(event.quantity)
            out_qty += event.quantity
        if method == "average" and len(lots) > 1:
            lots[:] = [[sum((l[0] for l in lots), ZERO), sum((l[1] for l in lots), ZERO)]]

    balance = sum((lot[0] for lot in lots), ZERO)
    cost = sum((lot[1] for lot in lots), ZERO)
    value = None if price is None else balance * price
    return CostSummary(
        method=method, balance=balance, cost=cost, average_cost=cost / balance if balance > 0 else None,
        realized=realized, fees=fees, transferred_out=out_qty, transferred_out_cost=out_cost,
        transferred_out_average_cost=out_cost / out_qty if out_qty > 0 else None, uncovered=uncovered,
        price=price, value=value, unrealized=None if value is None else value - cost,
    )
