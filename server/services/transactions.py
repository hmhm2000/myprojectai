"""Transaction details: every entry of a portfolio (purchases, sales, transfers, futures) with its
origin and the original export data, plus the per-coin cost summary (average / FIFO / LIFO).

Exchange independent - reads the stored model only, never an export file.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from models.imports import AccountMovement, ImportChange, ImportFile
from models.portfolio import Portfolio, Position, Sale
from services.cost_basis import LedgerEvent, summarize

SPOT_MOVEMENTS = ("transfer_in", "transfer_out", "sell_uncovered")


def _load(text: Optional[str]) -> dict:
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


def _common(entry, files: dict[int, str], changes: dict[str, list]) -> dict:
    raw = _load(entry.raw)
    return {
        "source": entry.source, "external_id": entry.external_id, "imported_at": entry.imported_at,
        "file": files.get(entry.import_file_id) or raw.get("file"), "missing_in_export": entry.missing_in_export,
        "note": entry.note, "custom_fields": _load(entry.custom_fields),
        "raw_rows": raw.get("rows", []), "unallocated": raw.get("unallocated"),
        "changes": changes.get(entry.external_id, []) if entry.external_id else [],
    }


def list_transactions(db: Session, portfolio: Portfolio) -> list[dict]:
    files = {f.id: f.filename for f in db.query(ImportFile).filter(ImportFile.user_id == portfolio.user_id)}
    changes: dict[str, list] = {}
    for change in (db.query(ImportChange).filter(ImportChange.user_id == portfolio.user_id)
                   .order_by(ImportChange.changed_at, ImportChange.id)):
        changes.setdefault(change.external_id, []).append({
            "field": change.field, "old": change.old_value, "new": change.new_value,
            "changed_at": change.changed_at, "file": files.get(change.file_id)})

    items = []
    groups: dict[str, list[Sale]] = {}
    for position in portfolio.positions:
        items.append({
            "kind": "position", "id": str(position.id), "type": "buy", "symbol": position.symbol,
            "quantity": position.quantity, "price": position.buy_price, "fee_coin": position.fee_coin,
            "fee_quote": None, "value": position.buy_price * position.quantity, "occurred_at": position.bought_at,
            "journal": {"entry_reason": position.entry_reason, "tags": position.tags, "plan": position.plan},
            **_common(position, files, changes)})
        for sale in position.sales:
            groups.setdefault(sale.group_id, []).append(sale)
    for group_id, rows in groups.items():
        first = rows[0]
        quantity = sum((r.quantity for r in rows), Decimal(0))
        items.append({
            "kind": "sale", "id": group_id, "type": "sell", "symbol": first.position.symbol, "quantity": quantity,
            "price": first.price, "fee_coin": None, "fee_quote": sum((r.fee_quote for r in rows), Decimal(0)),
            "value": first.price * quantity, "occurred_at": first.sold_at,
            "journal": {"exit_reason": first.exit_reason}, **_common(first, files, changes)})
    for movement in db.query(AccountMovement).filter(AccountMovement.portfolio_id == portfolio.id):
        items.append({
            "kind": "movement", "id": str(movement.id), "type": movement.kind, "symbol": movement.symbol,
            "quantity": movement.quantity, "price": movement.price, "fee_coin": None, "fee_quote": movement.fee,
            "value": movement.value_usd, "occurred_at": movement.occurred_at, "journal": {},
            **_common(movement, files, changes)})
    items.sort(key=lambda i: (i["occurred_at"], i["id"]), reverse=True)
    return items


def ledger(db: Session, portfolio: Portfolio) -> dict[str, list[LedgerEvent]]:
    """Spot events per coin (futures are stored but not part of the spot result)."""
    events: dict[str, list[LedgerEvent]] = {}
    order = 0

    def add(symbol, event):
        events.setdefault(symbol, []).append(event)

    groups: dict[str, list[Sale]] = {}
    for position in portfolio.positions:
        order += 1
        add(position.symbol, LedgerEvent(position.bought_at, "buy", position.quantity, position.buy_price,
                                         fee_coin=position.fee_coin or Decimal(0), order=order))
        for sale in position.sales:
            groups.setdefault(sale.group_id, []).append(sale)
    for rows in groups.values():
        order += 1
        first = rows[0]
        unallocated = _load(first.raw).get("unallocated")
        quantity = sum((r.quantity for r in rows), Decimal(0)) + (Decimal(unallocated) if unallocated else 0)
        add(first.position.symbol, LedgerEvent(first.sold_at, "sell", quantity, first.price,
                                               fee_quote=sum((r.fee_quote for r in rows), Decimal(0)), order=order))
    for movement in db.query(AccountMovement).filter(AccountMovement.portfolio_id == portfolio.id,
                                                     AccountMovement.kind.in_(SPOT_MOVEMENTS)):
        order += 1
        kind = "sell" if movement.kind == "sell_uncovered" else movement.kind
        add(movement.symbol, LedgerEvent(movement.occurred_at, kind, movement.quantity, movement.price or Decimal(0),
                                         fee_quote=movement.fee or Decimal(0), value=movement.value_usd, order=order))
    return events


def cost_summaries(db: Session, portfolio: Portfolio, method: str, prices: dict[str, Optional[Decimal]],
                   symbol: Optional[str] = None) -> list[dict]:
    out = []
    for coin, events in sorted(ledger(db, portfolio).items()):
        if symbol and coin != symbol:
            continue
        summary = summarize(events, method, prices.get(coin))
        out.append({"symbol": coin, **summary.__dict__})
    return out
