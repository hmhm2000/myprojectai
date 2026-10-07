"""Private alerts: CRUD, current-value preview and the history of triggers."""
import json

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from auth import get_current_user
from core.errors import NotFound
from database.db import get_db
from models.alerts import Alert, AlertEvent
from models.user import User
from schemas.alerts import AlertCheckOut, AlertEventOut, AlertIn, AlertOut, AlertPatch, Condition, MarkSeenIn
from services.alerts import preview, validate_condition
from services.candle_service import candle_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _get_alert(db: Session, alert_id: int, user: User) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise NotFound("alerts.not_found", "Alert not found")
    return alert


def _out(alert: Alert) -> AlertOut:
    return AlertOut(
        **{k: getattr(alert, k) for k in ("id", "symbol", "interval", "mode", "on_closed_candle", "active", "note",
                                         "last_state", "last_checked_at", "last_triggered_at", "created_at")},
        condition=Condition.model_validate_json(alert.condition),
        unseen_events=sum(1 for e in alert.events if not e.seen),
    )


@router.get("", response_model=list[AlertOut])
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_out(a) for a in db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.id.desc()).all()]


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(data: AlertIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    validate_condition(data.condition)
    alert = Alert(user_id=user.id, symbol=data.symbol, interval=data.interval, condition=data.condition.model_dump_json(),
                  mode=data.mode, on_closed_candle=data.on_closed_candle, note=data.note, active=True)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _out(alert)


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: int, data: AlertPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = _get_alert(db, alert_id, user)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("active") and not alert.active:
        alert.last_state = None          # re-armed: fire again if the condition is met
    for field, value in changes.items():
        setattr(alert, field, value)
    db.commit()
    db.refresh(alert)
    return _out(alert)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_alert(db, alert_id, user))
    db.commit()
    return Response(status_code=204)


@router.get("/{alert_id}/check", response_model=AlertCheckOut)
def check_alert(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current values of the condition - a preview that does not change the alert."""
    alert = _get_alert(db, alert_id, user)
    result = preview(Condition.model_validate_json(alert.condition), alert.symbol, alert.interval,
                     alert.on_closed_candle, candle_service)
    return AlertCheckOut(**result.__dict__)


@router.get("/events", response_model=list[AlertEventOut])
def list_events(unseen_only: bool = Query(False), limit: int = Query(100, ge=1, le=500),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(AlertEvent).join(Alert).filter(Alert.user_id == user.id)
    if unseen_only:
        query = query.filter(AlertEvent.seen.is_(False))
    events = query.order_by(AlertEvent.id.desc()).limit(limit).all()
    return [
        AlertEventOut(id=e.id, alert_id=e.alert_id, symbol=e.alert.symbol, interval=e.alert.interval,
                      condition=Condition.model_validate_json(e.alert.condition), note=e.alert.note,
                      triggered_at=e.triggered_at, candle_time=e.candle_time, details=json.loads(e.details), seen=e.seen)
        for e in events
    ]


@router.post("/events/seen", status_code=204)
def mark_seen(data: MarkSeenIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(AlertEvent).join(Alert).filter(Alert.user_id == user.id, AlertEvent.seen.is_(False))
    if data.ids is not None:
        query = query.filter(AlertEvent.id.in_(data.ids))
    for event in query.all():
        event.seen = True
    db.commit()
    return Response(status_code=204)
