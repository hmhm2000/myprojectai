from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from schemas.common import Amount


class QuoteResponse(BaseModel):
    price: Amount
    change_24h_pct: Optional[Amount]
    source: str
    stale: bool


class SourceStatusResponse(BaseModel):
    name: str
    ok: bool
    fetched_at: Optional[datetime]
    stale: bool
    error: Optional[str]
    count: int


class PricesResponse(BaseModel):
    quote_currency: str
    fetched_at: Optional[datetime]
    stale: bool
    ttl_seconds: int
    force_available_in: int
    sources: list[SourceStatusResponse]
    prices: dict[str, QuoteResponse]
