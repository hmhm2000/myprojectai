"""Futures (perpetual) positions rebuilt from the stored fills - exchange independent.

Fills are AccountMovements of kind "futures" with a `futures` JSON (see the import adapters):
account (uta / copytrading / okx), quote (settlement currency), action (open / close / funding), side
(long / short), position
(size after the fill, "" when the export has none), pnl (gross, closes), fee (cost > 0), funding
(booked: > 0 received, < 0 paid), liquidation.

A position is one run of a side of a contract on an account: it starts with an open from size 0 and
ends when the size is back to 0. Fills of the same second are not always in order in the exports, so
they are chained by the size after each fill (the fill that continues from the current size goes
first). Funding goes to the position open at that time (same side if known, else any of the contract).
Result: net = pnl - fees + funding.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from models.imports import AccountMovement
from models.portfolio import Portfolio

ZERO = Decimal(0)
TOLERANCE = Decimal("0.0000001")


@dataclass
class Fill:
    id: int
    time: datetime
    account: str
    contract: str
    action: str
    side: str
    quantity: Decimal
    price: Optional[Decimal]
    position: Optional[Decimal]
    pnl: Decimal
    fee: Decimal
    funding: Decimal
    liquidation: bool
    quote: Optional[str]

    @property
    def before(self) -> Optional[Decimal]:
        """Size of the side before this fill (from the size after it)."""
        if self.position is None or self.action == "funding":
            return self.position
        return self.position - self.quantity if self.action == "open" else self.position + self.quantity


@dataclass
class FuturesPosition:
    account: str
    contract: str
    side: str
    opened_at: datetime
    source: str = ""
    quote: Optional[str] = None
    closed_at: Optional[datetime] = None
    size: Decimal = ZERO                  # open size now
    max_size: Decimal = ZERO
    opened: Decimal = ZERO                # opened quantity (all opens)
    closed: Decimal = ZERO
    open_value: Decimal = ZERO
    close_value: Decimal = ZERO
    pnl: Decimal = ZERO
    fees: Decimal = ZERO
    funding: Decimal = ZERO
    liquidated: bool = False
    fills: list[Fill] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.size > TOLERANCE

    @property
    def net(self) -> Decimal:
        return self.pnl - self.fees + self.funding

    def out(self) -> dict:
        return {
            "id": f"{self.account}:{self.contract}:{self.side}:{self.opened_at.isoformat()}",
            "account": self.account, "contract": self.contract, "side": self.side, "source": self.source,
            "quote": self.quote, "status": "open" if self.is_open else "closed",
            "opened_at": self.opened_at, "closed_at": None if self.is_open else self.closed_at,
            "quantity": self.max_size, "open_size": self.size if self.is_open else ZERO,
            "entry_price": self.open_value / self.opened if self.opened else None,
            "exit_price": self.close_value / self.closed if self.closed else None,
            "pnl": self.pnl, "fees": self.fees, "funding": self.funding, "net": self.net,
            "liquidated": self.liquidated,
            "fills": [{"time": f.time, "action": f.action, "quantity": f.quantity, "price": f.price,
                       "pnl": f.pnl, "fee": f.fee, "funding": f.funding, "liquidation": f.liquidation}
                      for f in self.fills],
        }


def _dec(value) -> Optional[Decimal]:
    return None if value in (None, "") else Decimal(str(value))


def load_fills(db: Session, portfolio: Portfolio) -> list[tuple[str, Fill]]:
    out = []
    for m in (db.query(AccountMovement).filter(AccountMovement.portfolio_id == portfolio.id,
                                               AccountMovement.kind == "futures", AccountMovement.futures.isnot(None))):
        data = json.loads(m.futures)
        out.append((m.source, Fill(
            id=m.id, time=m.occurred_at, account=data.get("account") or m.source, contract=m.symbol,
            action=data["action"], side=data["side"], quantity=Decimal(m.quantity), price=_dec(m.price),
            position=_dec(data.get("position")), pnl=_dec(data.get("pnl")) or ZERO, fee=_dec(data.get("fee")) or ZERO,
            funding=_dec(data.get("funding")) or ZERO, liquidation=bool(data.get("liquidation")),
            quote=data.get("quote"))))
    return out


def _ordered(fills: list[Fill], sizes: dict) -> list[Fill]:
    """Fills of one second: funding first (it belongs to the size held before), then each fill whose
    size before matches the current size of its side; the rest in their stored order."""
    pending = sorted(fills, key=lambda f: (f.action != "funding", f.action != "close", f.id))
    out = []
    while pending:
        pick = next((f for f in pending if f.action == "funding"), None)
        if pick is None:
            pick = next((f for f in pending if f.before is not None
                         and abs(f.before - sizes.get((f.account, f.contract, f.side), ZERO)) <= TOLERANCE), pending[0])
        pending.remove(pick)
        out.append(pick)
        key = (pick.account, pick.contract, pick.side)
        if pick.action == "open":
            sizes[key] = sizes.get(key, ZERO) + pick.quantity
        elif pick.action == "close":
            sizes[key] = max(sizes.get(key, ZERO) - pick.quantity, ZERO)
    return out


def build_positions(fills: list[tuple[str, Fill]]) -> list[FuturesPosition]:
    source_of = {id(f): source for source, f in fills}
    by_time: dict[datetime, list[Fill]] = defaultdict(list)
    for _, fill in fills:
        by_time[fill.time].append(fill)

    sizes: dict[tuple, Decimal] = {}
    current: dict[tuple, FuturesPosition] = {}          # open position per (account, contract, side)
    last: dict[tuple, FuturesPosition] = {}
    positions: list[FuturesPosition] = []
    orphans = 0
    for moment in sorted(by_time):
        for fill in _ordered(by_time[moment], dict(sizes)):
            key = (fill.account, fill.contract, fill.side)
            if fill.action == "funding":
                target = current.get(key) or next((p for k, p in current.items() if k[:2] == key[:2]), None) \
                    or last.get(key)
                if target is None:
                    orphans += 1
                    continue
                target.funding += fill.funding
                target.pnl += fill.pnl                     # USDC contracts settle PnL with the funding
                target.fills.append(fill)
                continue
            position = current.get(key)
            if position is None:
                position = FuturesPosition(fill.account, fill.contract, fill.side, fill.time,
                                           source=source_of[id(fill)])
                current[key] = position
                positions.append(position)
            position.fills.append(fill)
            position.fees += fill.fee
            position.liquidated |= fill.liquidation
            if fill.price is not None and position.quote is None:
                position.quote = fill.quote
            if fill.action == "open":
                position.size += fill.quantity
                position.opened += fill.quantity
                position.open_value += fill.quantity * (fill.price or ZERO)
                position.max_size = max(position.max_size, position.size)
            else:
                position.size = max(position.size - fill.quantity, ZERO)
                position.closed += fill.quantity
                position.close_value += fill.quantity * (fill.price or ZERO)
                position.pnl += fill.pnl
                position.closed_at = fill.time
                if position.max_size == 0:                 # opened before the first export
                    position.max_size = fill.quantity
            sizes[key] = position.size
            if not position.is_open:
                last[key] = current.pop(key)
    return positions


def _totals(positions: list[FuturesPosition]) -> dict:
    closed = [p for p in positions if not p.is_open]
    wins = [p for p in closed if p.net > 0]
    return {
        "positions": len(positions), "closed": len(closed), "open": len(positions) - len(closed),
        "wins": len(wins), "losses": len(closed) - len(wins),
        "win_rate": (Decimal(len(wins)) / len(closed) * 100).quantize(Decimal("0.1")) if closed else None,
        "pnl": sum((p.pnl for p in positions), ZERO), "fees": sum((p.fees for p in positions), ZERO),
        "funding": sum((p.funding for p in positions), ZERO), "net": sum((p.net for p in positions), ZERO),
        "liquidations": sum(1 for p in positions if p.liquidated),
    }


def futures_overview(db: Session, portfolio: Portfolio) -> dict:
    """Positions (newest first) with their fills, totals, and totals per contract / account / month."""
    positions = build_positions(load_fills(db, portfolio))
    groups: dict[str, dict[str, list]] = {"contract": defaultdict(list), "account": defaultdict(list),
                                          "month": defaultdict(list)}
    for p in positions:
        groups["contract"][p.contract].append(p)
        groups["account"][p.account].append(p)
        groups["month"][(p.closed_at or p.opened_at).strftime("%Y-%m")].append(p)
    return {
        "summary": _totals(positions),
        "by": {name: sorted(({"key": key, **_totals(items)} for key, items in group.items()),
                            key=lambda row: row["key"], reverse=name == "month")
               for name, group in groups.items()},
        "positions": [p.out() for p in sorted(positions, key=lambda p: p.closed_at or p.opened_at, reverse=True)],
    }
