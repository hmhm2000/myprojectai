"""Trade journal analysis (statistics over closed positions)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import get_current_user
from config import settings
from core.errors import NotFound
from database.db import get_db
from models.portfolio import Portfolio, Position
from models.user import User
from schemas.journal import JournalStatsOut
from services.candle_service import candle_service
from services.journal_stats import journal_stats, trade_from_position, with_timing
from services.position_timing import position_timing

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("/stats", response_model=JournalStatsOut)
def get_journal_stats(
    portfolio_id: Optional[int] = Query(None, description="Only this portfolio; empty = all portfolios"),
    timing: bool = Query(True, description="Include duration / time below entry (needs exchange candles)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Position).join(Portfolio).filter(Portfolio.user_id == user.id)
    if portfolio_id is not None:
        if not db.query(Portfolio).filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id).first():
            raise NotFound("portfolio.not_found", "Portfolio not found")
        query = query.filter(Position.portfolio_id == portfolio_id)
    positions = query.all()

    trades = [t for t in (trade_from_position(p) for p in positions) if t]
    if timing:
        by_id = {p.id: p for p in positions}
        trades = with_timing(trades, by_id, lambda p: position_timing(p, candle_service, settings.user_timezone))

    stats = journal_stats(trades)
    return {"open_positions": len(positions) - len(trades), **stats}
