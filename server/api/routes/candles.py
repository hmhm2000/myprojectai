"""Candles (OHLCV) for the chart - served from the shared candle service (same source and cache as position timing)."""
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth import get_current_user
from schemas.common import Amount
from services.candle_service import candle_service
from services.intervals import parse

router = APIRouter(prefix="/api/candles", tags=["candles"], dependencies=[Depends(get_current_user)])


class CandleOut(BaseModel):
    time: int            # open time, unix seconds (UTC)
    open: Amount
    high: Amount
    low: Amount
    close: Amount
    volume: Amount
    closed: bool         # False for the still-forming last candle


class CandlesOut(BaseModel):
    symbol: str
    interval: str
    source: str
    candles: list[CandleOut]


@router.get("", response_model=CandlesOut)
def get_candles(
    symbol: str = Query(..., description="Coin, e.g. BTC"),
    interval: str = Query("1h", description="1m 5m 15m 30m 1h 4h 1d 1w 1M or custom like 2h, 3d, 2w, 3M"),
    limit: int = Query(500, ge=1, le=1500),
    before: Optional[int] = Query(None, description="Only candles opened before this unix time (older history)"),
):
    symbol = symbol.strip().upper()
    spec = parse(interval)
    step = spec.seconds
    now = int(time.time())
    end = (before - 1) if before else now
    start = end - limit * step
    series = candle_service.get_candles(symbol, spec.name, start, end, max_candles=limit + 1)
    candles = [c for c in series.candles if not before or c.time < before][-limit:]
    return CandlesOut(
        symbol=symbol,
        interval=spec.name,
        source=series.source,
        candles=[CandleOut(**c.__dict__, closed=series.is_closed(c, now)) for c in candles],
    )
