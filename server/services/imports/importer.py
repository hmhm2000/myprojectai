"""Import of exchange export files into the ordinary portfolio model.

Every exchange has its own import portfolio (kind = "import", source = exchange, e.g. "OKX"), created
on the first import - manual portfolios are never used or changed by an import.
A purchase becomes a Position and a sale a sale group - created by the same code as the manual form
(`_write_sale_group`), with `source` / `external_id` / `raw`. Transfers and futures are stored as
AccountMovements (details view only). Rules:
- a file with the same sha256 as an imported one is skipped ("already imported"),
- key (source, external_id): new -> created; same values -> nothing; different values -> the export
  fields are updated, manual fields (journal, notes, own fields, chart flag) are kept and every change
  is logged in import_changes,
- nothing with another source (manual entries, other exchanges) is ever read for writing or deleted,
- entries of this source missing from a newer file (within the period it covers) are only flagged,
- a new id whose (time, order id, action, amount, price) already exists is a warning, not a duplicate,
- sales are assigned to this source's purchases of the same portfolio FIFO (like the form's FIFO
  hint); a part not covered by purchases (coins that came by transfer) is reported.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from models.imports import AccountMovement, ImportChange, ImportFile
from models.portfolio import Portfolio, Position, Sale, utcnow
from models.user import User
from services.imports.adapters.base import ImportRecord, ParsedExport
from services.imports.adapters.okx import QUOTES, OkxAdapter
from services.pnl import held_quantity

logger = logging.getLogger(__name__)

ADAPTERS = [OkxAdapter()]
BALANCE_TOLERANCE = Decimal("0.00000001")
SALE_NAMESPACE = uuid.UUID("5b0c6f43-6f1e-4d3b-9a43-2f6f0c3e7a11")
_lock = threading.Lock()


@dataclass
class FileResult:
    filename: str
    status: str                    # imported | already_imported | unrecognized | error
    source: Optional[str] = None
    rows_total: int = 0
    rows_new: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    rows_unchanged: int = 0
    warnings: list[dict] = field(default_factory=list)
    message: Optional[str] = None


@dataclass
class SaleDef:
    external_id: str
    symbol: str
    portfolio_id: int
    price: Decimal
    quantity: Decimal
    fee_quote: Decimal
    sold_at: datetime
    fingerprint: str
    raw: dict
    import_file_id: Optional[int]
    imported_at: datetime
    manual: dict = field(default_factory=dict)   # exit_reason, show_on_chart, note, custom_fields


# ------------------------------------------------------------------ helpers

def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_time(moment: datetime) -> datetime:
    """Export time (timezone aware) -> naive local time, the way bought_at / sold_at are stored."""
    return moment.astimezone(ZoneInfo(settings.user_timezone)).replace(tzinfo=None)


def detect_adapter(path: Path):
    head = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    return next((a for a in ADAPTERS if a.detect(path, head)), None)


def import_portfolio(db: Session, user: User, source: str, name: Optional[str] = None) -> Portfolio:
    """The exchange's own import portfolio (kind "import", source = exchange) - created when missing.
    Looked up by kind + source only: a manual portfolio with the same name is never used."""
    portfolio = (db.query(Portfolio).filter(Portfolio.user_id == user.id, Portfolio.kind == "import",
                                            Portfolio.source == source).order_by(Portfolio.id).first())
    if portfolio is None:
        portfolio = Portfolio(user_id=user.id, name=name or source.upper(), kind="import", source=source)
        db.add(portfolio)
        db.flush()
    return portfolio


def _raw(record: ImportRecord, filename: str, **extra) -> dict:
    return {"file": filename, "values": record.csv_values(), "rows": record.rows, **extra}


def _load(text: Optional[str]) -> dict:
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


class _Index:
    """This user's entries of one source, by external_id."""

    def __init__(self, db: Session, user: User, source: str):
        mine = (Portfolio.user_id == user.id, Portfolio.kind == "import", Portfolio.source == source)
        self.positions = {p.external_id: p for p in (
            db.query(Position).join(Portfolio).filter(*mine, Position.source == source,
                                                      Position.external_id.isnot(None)))}
        self.sales: dict[str, list[Sale]] = {}
        for sale in (db.query(Sale).join(Position).join(Portfolio)
                     .filter(*mine, Sale.source == source, Sale.external_id.isnot(None))):
            self.sales.setdefault(sale.external_id, []).append(sale)
        self.movements = {m.external_id: m for m in db.query(AccountMovement).filter(
            AccountMovement.user_id == user.id, AccountMovement.source == source,
            AccountMovement.external_id.isnot(None))}
        self.fingerprints: dict[str, str] = {}
        for entry in [*self.positions.values(), *(rows[0] for rows in self.sales.values()), *self.movements.values()]:
            if entry.fingerprint:
                self.fingerprints[entry.fingerprint] = entry.external_id

    def find(self, external_id: str):
        return self.positions.get(external_id) or self.sales.get(external_id) or self.movements.get(external_id)


# ------------------------------------------------------------------ public

def sync_folder(db: Session, user: User, folder: Path = None) -> list[FileResult]:
    """Import every new file of the folder (created if missing). Removing a file deletes nothing."""
    folder = Path(folder or settings.import_dir)
    folder.mkdir(parents=True, exist_ok=True)
    with _lock:
        return [import_file(db, user, path) for path in sorted(folder.glob("*.csv"))]


def import_file(db: Session, user: User, path: Path) -> FileResult:
    sha = sha256_of(path)
    if db.query(ImportFile).filter(ImportFile.user_id == user.id, ImportFile.sha256 == sha).first():
        return FileResult(path.name, "already_imported")
    adapter = detect_adapter(path)
    if adapter is None:
        return FileResult(path.name, "unrecognized")
    try:
        parsed = adapter.parse(path)
        result = _import_parsed(db, user, path.name, sha, parsed, adapter.name)
        db.commit()
        logger.info("Imported %s: %s new, %s updated, %s skipped, %s unchanged", path.name, result.rows_new,
                    result.rows_updated, result.rows_skipped, result.rows_unchanged)
        return result
    except Exception as exc:   # one broken file must not stop the others
        db.rollback()
        logger.exception("Import of %s failed", path.name)
        return FileResult(path.name, "error", adapter.source, message=str(exc)[:300])


# ------------------------------------------------------------------ import of one parsed file

def _import_parsed(db: Session, user: User, filename: str, sha: str, parsed: ParsedExport,
                   exchange_name: Optional[str] = None) -> FileResult:
    source = parsed.source
    now = utcnow()
    portfolio = import_portfolio(db, user, source, exchange_name)
    file_row = ImportFile(user_id=user.id, filename=filename, sha256=sha, source=source, imported_at=now,
                          rows_total=parsed.rows_total)
    db.add(file_row)
    db.flush()
    result = FileResult(filename, "imported", source, rows_total=parsed.rows_total, rows_skipped=parsed.rows_skipped,
                        warnings=list(parsed.warnings))
    index = _Index(db, user, source)
    sale_defs: dict[str, SaleDef] = {}
    seen: set[str] = set()
    last_order = db.query(func.max(Position.sort_order)).filter(Position.portfolio_id == portfolio.id).scalar() or 0

    def log(external_id, old: dict, new: dict):
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                db.add(ImportChange(user_id=user.id, source=source, external_id=external_id, field=key,
                                    old_value=old.get(key), new_value=new.get(key), file_id=file_row.id,
                                    changed_at=now))

    for record in parsed.records:
        ext = record.external_id
        seen.add(ext)
        existing = index.find(ext)
        if existing is None:
            owner = index.fingerprints.get(record.fingerprint)
            if record.fingerprint and owner and owner != ext:
                result.rows_skipped += record.row_count
                result.warnings.append({"code": "duplicate_fingerprint", "params": {"id": ext, "existing": owner}})
                continue
            index.fingerprints[record.fingerprint] = ext
            result.rows_new += record.row_count
            if record.kind == "buy":
                last_order += 1
                position = Position(
                    portfolio_id=portfolio.id, symbol=record.symbol, buy_price=record.price, quantity=record.quantity,
                    fee_coin=record.fee_coin, bought_at=local_time(record.occurred_at), sort_order=last_order,
                    source=source, external_id=ext, fingerprint=record.fingerprint,
                    raw=json.dumps(_raw(record, filename)), import_file_id=file_row.id, imported_at=now)
                db.add(position)
                index.positions[ext] = position
            elif record.kind == "sell":
                sale_defs[ext] = _sale_def(record, portfolio.id, filename, file_row.id, now)
            else:
                db.add(_movement(record, user, portfolio.id, filename, file_row.id, now))
            continue

        old_raw = _load(existing[0].raw if isinstance(existing, list) else existing.raw)
        old_values = old_raw.get("values", {})
        new_values = record.csv_values()
        if old_values == new_values:
            result.rows_unchanged += record.row_count
            continue
        if old_values.get("kind") not in (None, record.kind):
            result.rows_skipped += record.row_count
            result.warnings.append({"code": "kind_changed", "params": {"id": ext, "old": old_values.get("kind"),
                                                                       "new": record.kind}})
            continue
        result.rows_updated += record.row_count
        log(ext, old_values, new_values)
        raw = {**old_raw, **_raw(record, filename)}
        if isinstance(existing, Position):
            existing.symbol, existing.buy_price, existing.quantity = record.symbol, record.price, record.quantity
            existing.fee_coin, existing.bought_at = record.fee_coin, local_time(record.occurred_at)
            existing.raw, existing.import_file_id = json.dumps(raw), file_row.id
        elif isinstance(existing, list) or (isinstance(existing, AccountMovement) and existing.kind == "sell_uncovered"):
            rows = existing if isinstance(existing, list) else []
            definition = _sale_def(record, rows[0].position.portfolio_id if rows else existing.portfolio_id,
                                   filename, file_row.id, (rows[0] if rows else existing).imported_at or now)
            definition.manual = _manual_fields(existing)
            sale_defs[ext] = definition
        else:
            existing.symbol, existing.quantity, existing.price = record.symbol, record.quantity, record.price
            existing.fee = record.fee_quote or None
            existing.value_usd, existing.occurred_at = record.value_usd, local_time(record.occurred_at)
            existing.raw, existing.import_file_id = json.dumps(raw), file_row.id

    db.flush()
    affected = {(d.portfolio_id, d.symbol) for d in sale_defs.values()}
    affected |= {(p.portfolio_id, p.symbol) for p in index.positions.values() if p.import_file_id == file_row.id}
    for portfolio_id, symbol in sorted(affected):
        _rebuild_sales(db, user, source, portfolio_id, symbol, sale_defs, result)
    db.flush()
    _flag_missing(db, user, source, parsed, seen)
    result.warnings += _balance_check(db, user, source, parsed)

    for name in ("rows_new", "rows_updated", "rows_skipped", "rows_unchanged"):
        setattr(file_row, name, getattr(result, name))
    file_row.warnings = json.dumps(result.warnings)
    return result


def _sale_def(record: ImportRecord, portfolio_id: int, filename: str, file_id: int, imported_at) -> SaleDef:
    return SaleDef(record.external_id, record.symbol, portfolio_id, record.price, record.quantity, record.fee_quote,
                   local_time(record.occurred_at), record.fingerprint, _raw(record, filename), file_id, imported_at)


def _movement(record: ImportRecord, user: User, portfolio_id: int, filename: str, file_id: int, now) -> AccountMovement:
    return AccountMovement(
        user_id=user.id, portfolio_id=portfolio_id, kind=record.kind, symbol=record.symbol, quantity=record.quantity,
        price=record.price, fee=record.fee_quote or None, value_usd=record.value_usd,
        occurred_at=local_time(record.occurred_at), source=record.source, external_id=record.external_id,
        fingerprint=record.fingerprint, raw=json.dumps(_raw(record, filename)), import_file_id=file_id, imported_at=now)


def _manual_fields(entry) -> dict:
    """What the user added by hand to a sale - kept when the sale is rebuilt."""
    if isinstance(entry, list):
        first = entry[0]
        return {"exit_reason": first.exit_reason, "show_on_chart": first.show_on_chart, "note": first.note,
                "custom_fields": first.custom_fields}
    return {"note": entry.note, "custom_fields": entry.custom_fields}


def _existing_sale_def(rows: list[Sale]) -> SaleDef:
    first = rows[0]
    raw = _load(first.raw)
    values = raw.get("values", {})
    definition = SaleDef(
        first.external_id, first.position.symbol, first.position.portfolio_id, first.price,
        Decimal(values.get("quantity") or sum((r.quantity for r in rows), Decimal(0))),
        sum((r.fee_quote for r in rows), Decimal(0)), first.sold_at, first.fingerprint or "", raw,
        first.import_file_id, first.imported_at or utcnow())
    definition.manual = _manual_fields(rows)
    return definition


def _uncovered_sale_def(movement: AccountMovement) -> SaleDef:
    definition = SaleDef(movement.external_id, movement.symbol, movement.portfolio_id, movement.price,
                         movement.quantity, movement.fee or Decimal(0), movement.occurred_at,
                         movement.fingerprint or "", _load(movement.raw), movement.import_file_id,
                         movement.imported_at or utcnow())
    definition.manual = _manual_fields(movement)
    return definition


def _rebuild_sales(db: Session, user: User, source: str, portfolio_id: int, symbol: str,
                   changed: dict[str, SaleDef], result: FileResult) -> None:
    """(Re)assign all sales of this source for one coin of one portfolio to its purchases, FIFO."""
    from api.routes.portfolios import _write_sale_group     # the same code as the manual sale form
    from schemas.portfolio import SaleAllocationIn, SaleIn

    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio.kind != "import":            # never touch a manual portfolio
        return
    rows = (db.query(Sale).join(Position).filter(Position.portfolio_id == portfolio_id, Position.symbol == symbol,
                                                 Sale.source == source).all())
    uncovered = db.query(AccountMovement).filter(
        AccountMovement.user_id == user.id, AccountMovement.portfolio_id == portfolio_id,
        AccountMovement.symbol == symbol, AccountMovement.source == source,
        AccountMovement.kind == "sell_uncovered").all()
    groups: dict[str, list[Sale]] = {}
    for row in rows:
        groups.setdefault(row.external_id, []).append(row)
    definitions = {ext: _existing_sale_def(group) for ext, group in groups.items()}
    definitions.update({m.external_id: _uncovered_sale_def(m) for m in uncovered})
    definitions.update({ext: d for ext, d in changed.items() if d.portfolio_id == portfolio_id and d.symbol == symbol})

    for row in rows:
        db.delete(row)
    for movement in uncovered:
        db.delete(movement)
    db.flush()
    db.expire_all()

    positions = (db.query(Position).filter(Position.portfolio_id == portfolio_id, Position.symbol == symbol,
                                           Position.source == source)
                 .order_by(Position.bought_at, Position.id).all())
    # other sales already on these purchases (e.g. added by hand) stay where they are
    available = {p.id: held_quantity(p) - sum((s.quantity for s in p.sales), Decimal(0)) for p in positions}

    for definition in sorted(definitions.values(), key=lambda d: (d.sold_at, d.external_id)):
        allocations, left = [], definition.quantity
        for position in positions:
            if left <= 0:
                break
            if position.bought_at > definition.sold_at or available[position.id] <= 0:
                continue
            take = min(left, available[position.id])
            available[position.id] -= take
            left -= take
            allocations.append(SaleAllocationIn(position_id=position.id, quantity=take))
        raw = {**definition.raw, "unallocated": str(left) if left > 0 else None}
        common = dict(source=source, external_id=definition.external_id, fingerprint=definition.fingerprint,
                      raw=json.dumps(raw), import_file_id=definition.import_file_id,
                      imported_at=definition.imported_at, note=definition.manual.get("note"),
                      custom_fields=definition.manual.get("custom_fields"))
        if left > 0:
            result.warnings.append({"code": "sale_uncovered", "params": {
                "id": definition.external_id, "symbol": symbol, "quantity": format(left.normalize(), "f")}})
        if not allocations:
            db.add(AccountMovement(user_id=user.id, portfolio_id=portfolio_id, kind="sell_uncovered", symbol=symbol,
                                   quantity=definition.quantity, price=definition.price,
                                   fee=definition.fee_quote or None, occurred_at=definition.sold_at, **common))
            continue
        group_id = str(uuid.uuid5(SALE_NAMESPACE, f"{source}:{definition.external_id}"))
        _write_sale_group(db, portfolio, SaleIn(
            price=definition.price, fee_quote=definition.fee_quote, sold_at=definition.sold_at,
            exit_reason=definition.manual.get("exit_reason"),
            show_on_chart=definition.manual.get("show_on_chart", True), allocations=allocations), group_id)
        db.flush()
        for sale in db.query(Sale).filter(Sale.group_id == group_id):
            for name, value in common.items():
                setattr(sale, name, value)
        db.flush()
        for position in positions:
            db.expire(position, ["sales"])


def _flag_missing(db: Session, user: User, source: str, parsed: ParsedExport, seen: set[str]) -> None:
    """Entries of this source inside the period of the file but not in it: flag (never delete)."""
    if parsed.period is None:
        return
    start, end = (local_time(t) for t in parsed.period)
    mine = (Portfolio.user_id == user.id, Portfolio.kind == "import", Portfolio.source == source)
    entries = [
        (p, p.bought_at) for p in db.query(Position).join(Portfolio).filter(
            *mine, Position.source == source, Position.external_id.isnot(None))
    ] + [
        (s, s.sold_at) for s in db.query(Sale).join(Position).join(Portfolio).filter(
            *mine, Sale.source == source, Sale.external_id.isnot(None))
    ] + [
        (m, m.occurred_at) for m in db.query(AccountMovement).filter(
            AccountMovement.user_id == user.id, AccountMovement.source == source,
            AccountMovement.external_id.isnot(None))
    ]
    for entry, moment in entries:
        if start <= moment < end:
            entry.missing_in_export = entry.external_id not in seen


def source_balances(db: Session, user: User, source: str) -> dict[str, Decimal]:
    """Coin balances from this source's stored entries (purchases - sales +/- transfers)."""
    balances: dict[str, Decimal] = {}

    def add(symbol, amount):
        balances[symbol] = balances.get(symbol, Decimal(0)) + amount

    mine = (Portfolio.user_id == user.id, Portfolio.kind == "import", Portfolio.source == source)
    for p in db.query(Position).join(Portfolio).filter(*mine, Position.source == source):
        add(p.symbol, held_quantity(p))
    seen_groups = set()
    for s in db.query(Sale).join(Position).join(Portfolio).filter(*mine, Sale.source == source):
        add(s.position.symbol, -s.quantity)
        if s.group_id not in seen_groups:
            seen_groups.add(s.group_id)
            unallocated = _load(s.raw).get("unallocated")
            if unallocated:
                add(s.position.symbol, -Decimal(unallocated))
    for m in db.query(AccountMovement).filter(AccountMovement.user_id == user.id, AccountMovement.source == source):
        if m.kind == "transfer_in":
            add(m.symbol, m.quantity)
        elif m.kind in ("transfer_out", "sell_uncovered"):
            add(m.symbol, -m.quantity)
    return balances


def _balance_check(db: Session, user: User, source: str, parsed: ParsedExport) -> list[dict]:
    """Compare the coin balances with the export's Balance column (after its last row)."""
    computed = source_balances(db, user, source)
    out = []
    for coin, expected in sorted(parsed.balances.items()):
        if coin in QUOTES:
            continue
        actual = computed.get(coin, Decimal(0))
        ok = abs(actual - expected) <= BALANCE_TOLERANCE
        out.append({"code": "balance_ok" if ok else "balance_mismatch", "params": {
            "coin": coin, "export": format(expected.normalize(), "f"), "computed": format(actual.normalize(), "f")}})
    return out


def startup_import() -> None:
    """Import new files from the folder for IMPORT_USERNAME (runs in a background thread at start-up)."""
    from database.db import SessionLocal

    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == settings.import_username).first()
            if user is None:
                logger.warning("Import at start-up skipped: user %s does not exist", settings.import_username)
                return
            for result in sync_folder(db, user):
                if result.status != "already_imported":
                    logger.info("Import %s: %s", result.filename, result.status)
    except Exception:
        logger.exception("Import at start-up failed")
