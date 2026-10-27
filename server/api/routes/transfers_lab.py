"""Test view of deposits / withdrawals across exchanges (read only, see services/transfers_lab.py)."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database.db import get_db
from models.user import User
from services import transfers_lab
from services.price_service import price_service

router = APIRouter(prefix="/api/transfers-lab", tags=["transfers-lab"])


class AddressLabelIn(BaseModel):
    address: str = Field(min_length=1, max_length=200)
    owner: Optional[Literal["own", "foreign"]] = None
    label: Optional[str] = Field(None, max_length=100)


@router.get("")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prices = {s: q.price for s, q in price_service.get_snapshot().quotes.items()}
    return transfers_lab.overview(db, user, prices)


@router.put("/address", status_code=204)
def label_address(data: AddressLabelIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark a withdrawal address as the user's own wallet (or not) - the only thing this view saves."""
    transfers_lab.set_label(db, user, data.address, data.owner, data.label)
    return Response(status_code=204)
