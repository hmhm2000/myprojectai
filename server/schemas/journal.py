from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import Amount


class GroupStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trades: int
    wins: int
    win_rate: Optional[Amount]
    total_pnl: Amount
    avg_pnl: Optional[Amount]
    avg_pnl_pct: Optional[Amount]
    avg_duration_seconds: Optional[int]
    avg_below_seconds: Optional[int]       # average time spent below the entry price
    avg_below_pct: Optional[Amount]


class TagStatsOut(GroupStatsOut):
    tag: Optional[str]                      # None = trades without tags


class KeywordStatsOut(GroupStatsOut):
    keyword: str


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: int
    portfolio_id: int
    symbol: str
    bought_at: datetime
    closed_at: datetime
    cost: Amount
    pnl: Amount
    pnl_pct: Optional[Amount]
    tags: list[str]
    entry_reason: Optional[str]
    exit_reasons: list[str]
    duration_seconds: Optional[int]
    below_seconds: Optional[int]
    below_pct: Optional[Amount]


class JournalStatsOut(BaseModel):
    open_positions: int                     # not analysed (result not final yet)
    overall: GroupStatsOut
    winners: GroupStatsOut
    losers: GroupStatsOut
    tags: list[TagStatsOut]
    keywords: list[KeywordStatsOut]
    trades: list[TradeOut]
