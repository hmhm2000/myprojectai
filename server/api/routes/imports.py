"""Import panel (export files in the folder, sync, flagged entries) and transaction details."""
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from config import settings
from core.errors import BadRequest, NotFound
from database.db import get_db
from models.imports import AccountMovement, ImportFile
from models.portfolio import Portfolio, Position, Sale
from models.user import User
from services.cost_basis import METHODS
from services.futures import futures_overview
from services.imports import importer
from services.price_service import price_service
from services.transactions import cost_summaries, list_transactions

router = APIRouter(tags=["import"])
_last_sync: dict[int, list[dict]] = {}     # user id -> results of the last sync (shown in the panel)


class CostMethodIn(BaseModel):
    cost_method: Literal["average", "fifo", "lifo"]


class MissingActionIn(BaseModel):
    kind: Literal["position", "sale", "movement"]
    id: str


class SyncIn(BaseModel):
    files: Optional[list[str]] = None       # files ticked in the panel; none given = all new ones


class FolderIn(BaseModel):
    folder: str = Field(max_length=255)     # "" = files lying directly in the import folder
    selected: bool


class DetailsIn(BaseModel):
    note: Optional[str] = Field(None, max_length=4000)
    custom_fields: Optional[dict[str, str]] = None


def _file_out(row: ImportFile) -> dict:
    return {"id": row.id, "filename": row.filename, "sha256": row.sha256, "source": row.source,
            "imported_at": row.imported_at, "rows_total": row.rows_total, "rows_new": row.rows_new,
            "rows_updated": row.rows_updated, "rows_skipped": row.rows_skipped, "rows_unchanged": row.rows_unchanged,
            "warnings": json.loads(row.warnings or "[]")}


def _missing(db: Session, user: User) -> list[dict]:
    out = []
    for p in db.query(Position).join(Portfolio).filter(Portfolio.user_id == user.id, Position.missing_in_export.is_(True)):
        out.append({"kind": "position", "id": str(p.id), "type": "buy", "symbol": p.symbol, "quantity": p.quantity,
                    "price": p.buy_price, "occurred_at": p.bought_at, "source": p.source, "external_id": p.external_id})
    groups = set()
    for s in db.query(Sale).join(Position).join(Portfolio).filter(Portfolio.user_id == user.id,
                                                                  Sale.missing_in_export.is_(True)):
        if s.group_id in groups:
            continue
        groups.add(s.group_id)
        out.append({"kind": "sale", "id": s.group_id, "type": "sell", "symbol": s.position.symbol, "quantity": s.quantity,
                    "price": s.price, "occurred_at": s.sold_at, "source": s.source, "external_id": s.external_id})
    for m in db.query(AccountMovement).filter(AccountMovement.user_id == user.id,
                                              AccountMovement.missing_in_export.is_(True)):
        out.append({"kind": "movement", "id": str(m.id), "type": m.kind, "symbol": m.symbol, "quantity": m.quantity,
                    "price": m.price, "occurred_at": m.occurred_at, "source": m.source, "external_id": m.external_id})
    return sorted(out, key=lambda e: e["occurred_at"], reverse=True)


def _status(db: Session, user: User) -> dict:
    folder = Path(settings.import_dir)
    folder.mkdir(parents=True, exist_ok=True)
    imported = {f.sha256: f for f in db.query(ImportFile).filter(ImportFile.user_id == user.id)}
    skipped = importer.skipped_folders(user)
    files = []
    for entry in importer.import_entries(folder):
        if entry.path.suffix.lower() == ".zip":     # not listed: the user unpacks what should be imported
            continue
        name = entry.account or ""
        modified = datetime.fromtimestamp(entry.path.stat().st_mtime)
        if name in skipped:                 # unticked: not read at all
            files.append({"filename": entry.label, "folder": name, "modified": modified, "status": "skipped",
                          "import": None})
            continue
        try:
            data = entry.read_bytes()
        except importer.READ_ERRORS:
            files.append({"filename": entry.label, "folder": name, "modified": modified, "status": "error",
                          "import": None})
            continue
        sha = hashlib.sha256(data).hexdigest()
        row = imported.get(sha)
        status = "imported" if row else "new" if importer.detect_adapter(Path(entry.name), data) else "unrecognized"
        files.append({"filename": entry.label, "folder": name, "size": len(data), "modified": modified, "sha256": sha,
                      "status": status, "import": _file_out(row) if row else None})
    files.sort(key=lambda f: (f["modified"], f["filename"]), reverse=True)      # the newest on top
    folders = []
    for name in importer.import_folders(folder):
        mine = [f for f in files if f["folder"] == name]
        account = importer.ACCOUNTS.get(name.lower())
        folders.append({"name": name, "portfolio": account[1] if account else None, "selected": name not in skipped,
                        "files": len(mine), "new": sum(f["status"] == "new" for f in mine)})
    history = (db.query(ImportFile).filter(ImportFile.user_id == user.id)
               .order_by(ImportFile.imported_at.desc(), ImportFile.id.desc()).limit(50).all())
    portfolios = (db.query(Portfolio).filter(Portfolio.user_id == user.id, Portfolio.kind == "import")
                  .order_by(Portfolio.id).all())
    return {"folder": str(folder.resolve()), "folders": folders,
            "portfolios": [{"id": p.id, "name": p.name, "source": p.source} for p in portfolios],
            "files": files, "history": [_file_out(h) for h in history], "last_sync": _last_sync.get(user.id, []),
            "missing": _missing(db, user)}


@router.get("/api/import")
def import_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _status(db, user)


@router.put("/api/import/folders")
def select_folder(data: FolderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tick or untick a subfolder for the sync - remembered per user, also for the import at start-up."""
    skipped = set(importer.skipped_folders(user))
    skipped = skipped - {data.folder} if data.selected else skipped | {data.folder}
    user.import_skipped_folders = json.dumps(sorted(skipped))
    db.commit()
    return _status(db, user)


@router.post("/api/import/sync")
def import_sync(data: Optional[SyncIn] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Import the files ticked in the panel, or every new file of the ticked folders."""
    only = set(data.files) if data and data.files is not None else None
    _last_sync[user.id] = [r.__dict__ for r in importer.sync_folder(db, user, only=only)]
    return _status(db, user)


@router.post("/api/import/reprocess")
def import_reprocess(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Go through every file of the ticked folders again, also the imported ones (same upsert - no duplicates)."""
    _last_sync[user.id] = [r.__dict__ for r in importer.sync_folder(db, user, reprocess=True)]
    return _status(db, user)


def _flagged(db: Session, user: User, data: MissingActionIn):
    if data.kind == "position":
        entry = db.get(Position, int(data.id)) if data.id.isdigit() else None
        entries = [entry] if entry and entry.portfolio.user_id == user.id else []
    elif data.kind == "sale":
        entries = [s for s in db.query(Sale).filter(Sale.group_id == data.id) if s.position.portfolio.user_id == user.id]
    else:
        entry = db.get(AccountMovement, int(data.id)) if data.id.isdigit() else None
        entries = [entry] if entry and entry.user_id == user.id else []
    if not entries:
        raise NotFound("import.entry_not_found", "Entry not found")
    if not entries[0].missing_in_export:
        raise BadRequest("import.entry_not_flagged", "Entry is not flagged as missing from the export")
    return entries


@router.post("/api/import/missing/keep")
def keep_missing(data: MissingActionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Keep an entry that is missing from the latest export (removes the flag)."""
    for entry in _flagged(db, user, data):
        entry.missing_in_export = False
    db.commit()
    return _status(db, user)


@router.post("/api/import/missing/delete")
def delete_missing(data: MissingActionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete an entry missing from the latest export - only on the user's decision."""
    for entry in _flagged(db, user, data):
        db.delete(entry)
    db.commit()
    return _status(db, user)


# ------------------------------------------------------------------ transaction details

def _portfolio(db: Session, portfolio_id: int, user: User) -> Portfolio:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or portfolio.user_id != user.id:
        raise NotFound("portfolio.not_found", "Portfolio not found")
    return portfolio


@router.get("/api/portfolios/{portfolio_id}/transactions")
def transactions(portfolio_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_transactions(db, _portfolio(db, portfolio_id, user))


@router.get("/api/portfolios/{portfolio_id}/futures")
def futures(portfolio_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Futures positions rebuilt from the imported fills, with totals per contract / account / month."""
    return futures_overview(db, _portfolio(db, portfolio_id, user))


@router.put("/api/portfolios/{portfolio_id}/cost-method", status_code=204)
def set_cost_method(portfolio_id: int, data: CostMethodIn,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cost method of the details view - remembered per portfolio."""
    _portfolio(db, portfolio_id, user).cost_method = data.cost_method
    db.commit()
    return Response(status_code=204)


@router.get("/api/portfolios/{portfolio_id}/cost-summary")
def cost_summary(portfolio_id: int, method: Optional[str] = Query(None), symbol: Optional[str] = Query(None),
                 price: Optional[Decimal] = Query(None, gt=0),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Balance, cost, realized (net of fees) and unrealized per coin - average / FIFO / LIFO.
    `price` (with `symbol`) overrides the current price for the unrealized result."""
    portfolio = _portfolio(db, portfolio_id, user)
    method = method or portfolio.cost_method          # default: the method remembered for the portfolio
    if method not in METHODS:
        raise BadRequest("import.invalid_method", "Unknown cost method", method=method)
    snapshot = price_service.get_snapshot()
    prices = {s: q.price for s, q in snapshot.quotes.items()}
    if symbol and price is not None:
        prices[symbol.upper()] = price
    return cost_summaries(db, portfolio, method, prices, symbol.upper() if symbol else None)


@router.patch("/api/transactions/{kind}/{entry_id}")
def update_details(kind: Literal["position", "sale", "movement"], entry_id: str, data: DetailsIn,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Notes and own fields of an entry (any source)."""
    if kind == "position":
        entry = db.get(Position, int(entry_id)) if entry_id.isdigit() else None
        entries = [entry] if entry and entry.portfolio.user_id == user.id else []
    elif kind == "sale":
        entries = [s for s in db.query(Sale).filter(Sale.group_id == entry_id) if s.position.portfolio.user_id == user.id]
    else:
        entry = db.get(AccountMovement, int(entry_id)) if entry_id.isdigit() else None
        entries = [entry] if entry and entry.user_id == user.id else []
    if not entries:
        raise NotFound("import.entry_not_found", "Entry not found")
    changes = data.model_dump(exclude_unset=True)
    for entry in entries:
        if "note" in changes:
            entry.note = (data.note or "").strip() or None
        if "custom_fields" in changes:
            fields = {k.strip(): v.strip() for k, v in (data.custom_fields or {}).items() if k.strip()}
            entry.custom_fields = json.dumps(fields) if fields else None
    db.commit()
    return Response(status_code=204)

