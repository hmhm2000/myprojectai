"""The user's chart indicators with their own settings (saved per user, not globally)."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from core.errors import BadRequest, NotFound
from database.db import get_db
from indicators.base import get_indicator, validate_params
from models.chart_indicators import ChartIndicator
from models.user import User
from services.providers.base import INTERVAL_SECONDS

router = APIRouter(prefix="/api/chart-indicators", tags=["indicators"])


class ChartIndicatorIn(BaseModel):
    indicator_id: str
    params: dict = Field(default_factory=dict)
    interval: Optional[str] = None       # own timeframe; None = follow the chart interval
    visible: bool = True


class ChartIndicatorUpdate(BaseModel):
    params: Optional[dict] = None
    interval: Optional[str] = None
    follow_chart: bool = False           # True -> clear the own interval
    visible: Optional[bool] = None


class ChartIndicatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indicator_id: str
    params: dict
    interval: Optional[str]
    visible: bool
    sort_order: int


def _out(item: ChartIndicator) -> ChartIndicatorOut:
    return ChartIndicatorOut(id=item.id, indicator_id=item.indicator_id, params=json.loads(item.params),
                             interval=item.interval, visible=item.visible, sort_order=item.sort_order)


def _check_interval(value: Optional[str]) -> None:
    if value is not None and value not in INTERVAL_SECONDS:
        raise BadRequest("candles.invalid_interval", f"Unsupported interval: {value}", interval=value)


def _get(db: Session, item_id: int, user: User) -> ChartIndicator:
    item = db.get(ChartIndicator, item_id)
    if item is None or item.user_id != user.id:
        raise NotFound("indicators.not_found", "Chart indicator not found", indicator=str(item_id))
    return item


@router.get("", response_model=list[ChartIndicatorOut])
def list_chart_indicators(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (db.query(ChartIndicator).filter(ChartIndicator.user_id == user.id)
             .order_by(ChartIndicator.sort_order, ChartIndicator.id).all())
    return [_out(i) for i in items]


@router.post("", response_model=ChartIndicatorOut, status_code=201)
def add_chart_indicator(data: ChartIndicatorIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    params = validate_params(get_indicator(data.indicator_id), data.params)   # stores defaults for missing params
    _check_interval(data.interval)
    last = db.query(func.max(ChartIndicator.sort_order)).filter(ChartIndicator.user_id == user.id).scalar() or 0
    item = ChartIndicator(user_id=user.id, indicator_id=data.indicator_id, params=json.dumps(params),
                          interval=data.interval, visible=data.visible, sort_order=last + 1)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)


@router.put("/{item_id}", response_model=ChartIndicatorOut)
def update_chart_indicator(item_id: int, data: ChartIndicatorUpdate,
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get(db, item_id, user)
    if data.params is not None:
        item.params = json.dumps(validate_params(get_indicator(item.indicator_id), data.params))
    if data.follow_chart:
        item.interval = None
    elif data.interval is not None:
        _check_interval(data.interval)
        item.interval = data.interval
    if data.visible is not None:
        item.visible = data.visible
    db.commit()
    db.refresh(item)
    return _out(item)


@router.post("/{item_id}/reset", response_model=ChartIndicatorOut)
def reset_chart_indicator(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Back to the conventional default settings of the indicator (and the chart interval)."""
    item = _get(db, item_id, user)
    item.params = json.dumps(validate_params(get_indicator(item.indicator_id), {}))
    item.interval = None
    db.commit()
    db.refresh(item)
    return _out(item)


@router.delete("/{item_id}", status_code=204)
def delete_chart_indicator(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get(db, item_id, user))
    db.commit()
    return Response(status_code=204)
