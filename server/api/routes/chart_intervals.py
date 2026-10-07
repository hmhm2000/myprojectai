"""The user's chart intervals: presets plus own (custom) ones, each optionally pinned as a button."""
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from core.errors import NotFound
from database.db import get_db
from models.chart_intervals import ChartInterval
from models.user import User
from services.intervals import NATIVE, parse

router = APIRouter(prefix="/api/chart-intervals", tags=["candles"])
PRESETS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
assert set(PRESETS) == NATIVE
MAX_CUSTOM = 50


class ChartIntervalIn(BaseModel):
    name: str


class ChartIntervalUpdate(BaseModel):
    pinned: bool


class ChartIntervalOut(BaseModel):
    name: str
    custom: bool
    pinned: bool


def _rows(db: Session, user: User) -> dict[str, ChartInterval]:
    return {r.name: r for r in db.query(ChartInterval).filter(ChartInterval.user_id == user.id)}


def _list(db: Session, user: User) -> list[ChartIntervalOut]:
    rows = _rows(db, user)
    out = [ChartIntervalOut(name=p, custom=False, pinned=rows[p].pinned if p in rows else True) for p in PRESETS]
    out += [ChartIntervalOut(name=r.name, custom=True, pinned=r.pinned) for r in rows.values() if r.custom]
    return sorted(out, key=lambda i: parse(i.name).seconds)      # shortest first


@router.get("", response_model=list[ChartIntervalOut])
def list_chart_intervals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _list(db, user)


@router.post("", response_model=list[ChartIntervalOut], status_code=201)
def add_chart_interval(data: ChartIntervalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a custom interval (pinned). A preset or an existing one is just pinned again."""
    name = parse(data.name).name
    rows = _rows(db, user)
    if name in rows:
        rows[name].pinned = True
    elif name not in PRESETS:
        if sum(r.custom for r in rows.values()) < MAX_CUSTOM:
            db.add(ChartInterval(user_id=user.id, name=name, custom=True, pinned=True))
    db.commit()
    return _list(db, user)


@router.put("/{name}", response_model=list[ChartIntervalOut])
def update_chart_interval(name: str, data: ChartIntervalUpdate,
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Pin / unpin an interval (pinned ones are shown as buttons above the chart)."""
    name = parse(name).name
    row = _rows(db, user).get(name)
    if row is None:
        if name not in PRESETS:
            raise NotFound("candles.interval_not_found", "Interval not found", interval=name)
        row = ChartInterval(user_id=user.id, name=name, custom=False)
        db.add(row)
    row.pinned = data.pinned
    db.commit()
    return _list(db, user)


@router.delete("/{name}", status_code=204)
def delete_chart_interval(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove a custom interval (presets can only be unpinned)."""
    row = _rows(db, user).get(parse(name).name)
    if row is None or not row.custom:
        raise NotFound("candles.interval_not_found", "Interval not found", interval=name)
    db.delete(row)
    db.commit()
    return Response(status_code=204)
