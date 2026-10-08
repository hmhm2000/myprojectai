"""One-off cleanup of manual portfolios: remove manual positions and sales except the kept symbols (SPX).

1. `plan()` - dry run: what would be removed / kept per manual portfolio, nothing changes,
2. `execute()` - only with the counts of the dry run (so nothing else is removed than what the user
   saw) and an explicit confirmation; first a full backup of ALL manual portfolios, positions and sales
   to data/backups/manual-YYYYMMDD-HHMM.json, then the removal. Portfolios stay (only emptied ones can
   be removed, as a separate choice). Import portfolios are never touched.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from config import settings
from core.errors import AppError, BadRequest
from models.imports import AccountMovement
from models.portfolio import Portfolio
from models.user import User

KEEP_SYMBOLS = ("SPX",)


def _manual_portfolios(db: Session, user: User) -> list[Portfolio]:
    return (db.query(Portfolio).filter(Portfolio.user_id == user.id, Portfolio.kind == "manual")
            .order_by(Portfolio.id).all())


def plan(db: Session, user: User) -> dict:
    portfolios, totals = [], {"positions": 0, "sales": 0, "movements": 0, "kept_positions": 0, "kept_sales": 0}
    for portfolio in _manual_portfolios(db, user):
        remove = [p for p in portfolio.positions if p.symbol not in KEEP_SYMBOLS]
        keep = [p for p in portfolio.positions if p.symbol in KEEP_SYMBOLS]
        movements = db.query(AccountMovement).filter(AccountMovement.portfolio_id == portfolio.id,
                                                     AccountMovement.symbol.notin_(KEEP_SYMBOLS)).count()
        row = {
            "id": portfolio.id, "name": portfolio.name,
            "positions": len(remove), "sales": len({s.group_id for p in remove for s in p.sales}),
            "movements": movements,
            "kept_positions": len(keep), "kept_sales": len({s.group_id for p in keep for s in p.sales}),
            "symbols": sorted({p.symbol for p in remove}),
            "empty_after": not keep,
        }
        portfolios.append(row)
        for key in totals:
            totals[key] += row[key]
    return {"keep_symbols": list(KEEP_SYMBOLS), "portfolios": portfolios, **totals}


def _json_default(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value))


def backup(db: Session, user: User, folder: Path = None) -> Path:
    """All manual portfolios with every position and sale (all columns) as JSON."""
    folder = Path(folder or settings.backup_dir)
    folder.mkdir(parents=True, exist_ok=True)
    columns = lambda row: {c.name: getattr(row, c.name) for c in row.__table__.columns}
    data = {
        "created_at": datetime.now(), "user": user.username,
        "portfolios": [
            {**columns(portfolio), "positions": [
                {**columns(position), "sales": [columns(sale) for sale in position.sales]}
                for position in portfolio.positions],
             "movements": [columns(m) for m in db.query(AccountMovement)
                           .filter(AccountMovement.portfolio_id == portfolio.id)]}
            for portfolio in _manual_portfolios(db, user)
        ],
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    path = folder / f"manual-{stamp}.json"
    counter = 1
    while path.exists():                     # two runs in the same minute
        counter += 1
        path = folder / f"manual-{stamp}-{counter}.json"
    path.write_text(json.dumps(data, default=_json_default, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def execute(db: Session, user: User, confirm: bool, positions: int, sales: int,
            delete_empty_portfolios: bool = False) -> dict:
    if not confirm:
        raise BadRequest("cleanup.not_confirmed", "The cleanup has to be confirmed")
    current = plan(db, user)
    if (current["positions"], current["sales"]) != (positions, sales):
        raise AppError(409, "cleanup.plan_changed", "Data changed since the dry run - check again",
                       positions=current["positions"], sales=current["sales"])
    path = backup(db, user)
    removed_portfolios = []
    for portfolio in _manual_portfolios(db, user):
        for position in [p for p in portfolio.positions if p.symbol not in KEEP_SYMBOLS]:
            db.delete(position)                      # its sales go with it (cascade)
        for movement in db.query(AccountMovement).filter(AccountMovement.portfolio_id == portfolio.id,
                                                         AccountMovement.symbol.notin_(KEEP_SYMBOLS)):
            db.delete(movement)
        db.flush()
        db.refresh(portfolio)
        if delete_empty_portfolios and not portfolio.positions:
            removed_portfolios.append(portfolio.name)
            db.delete(portfolio)
    db.commit()
    return {"backup": str(path.resolve()), "positions": current["positions"], "sales": current["sales"],
            "movements": current["movements"], "removed_portfolios": removed_portfolios}
