"""Trade journal analysis - deterministic statistics over CLOSED positions (no AI).

A "trade" = one fully closed position: its result is final (realized), so win rate and averages are
not distorted by price moves. Open positions are only counted.
- win = total P/L > 0 (break-even counts as a non-win),
- tags: stats per tag (a trade with several tags counts for each of them),
- reasons: deterministic keyword stats from the free-text entry reason
  (lowercased words of >= 3 characters, stop words removed, keywords used in >= 2 trades),
- timing (duration, time below the entry price) comes from position_timing and is optional:
  a trade whose candles can't be fetched is simply left out of the timing averages.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Iterable, Optional

from services.pnl import percent, position_metrics, q

MIN_KEYWORD_TRADES = 2
STOP_WORDS = {
    # Polish
    "and", "ale", "bez", "byl", "była", "było", "dla", "jak", "jest", "już", "lub", "nad", "nie", "oraz", "pod",
    "się", "tak", "też", "tylko", "przy", "przez", "żeby", "gdy", "bardzo", "jeszcze", "może", "potem", "więc",
    "cena", "ceny", "cenie", "kupno", "kupiłem", "wejście", "wejscie",
    # English
    "the", "for", "with", "from", "that", "this", "was", "are", "but", "not", "into", "price", "buy", "bought",
}
WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)


@dataclass(frozen=True)
class Trade:
    position_id: int
    portfolio_id: int
    symbol: str
    bought_at: datetime
    closed_at: datetime
    cost: Decimal
    pnl: Decimal
    pnl_pct: Optional[Decimal]
    tags: list[str]
    entry_reason: Optional[str]
    exit_reasons: list[str]
    duration_seconds: Optional[int] = None
    below_seconds: Optional[int] = None
    below_pct: Optional[Decimal] = None

    @property
    def is_win(self) -> bool:
        return self.pnl > 0


@dataclass(frozen=True)
class GroupStats:
    trades: int
    wins: int
    win_rate: Optional[Decimal]
    total_pnl: Decimal
    avg_pnl: Optional[Decimal]
    avg_pnl_pct: Optional[Decimal]
    avg_duration_seconds: Optional[int]
    avg_below_seconds: Optional[int]
    avg_below_pct: Optional[Decimal]


def keywords(text: Optional[str]) -> set[str]:
    return {w for w in WORD.findall((text or "").lower()) if w not in STOP_WORDS and not w.isdigit()}


def _avg(values: list) -> Optional[Decimal]:
    return q(sum(values, Decimal(0)) / len(values)) if values else None


def group_stats(trades: Iterable[Trade]) -> GroupStats:
    trades = list(trades)
    wins = sum(1 for t in trades if t.is_win)
    pnl_pcts = [t.pnl_pct for t in trades if t.pnl_pct is not None]
    durations = [t.duration_seconds for t in trades if t.duration_seconds is not None]
    belows = [t.below_seconds for t in trades if t.below_seconds is not None]
    below_pcts = [t.below_pct for t in trades if t.below_pct is not None]
    return GroupStats(
        trades=len(trades),
        wins=wins,
        win_rate=percent(Decimal(wins), Decimal(len(trades))) if trades else None,
        total_pnl=q(sum((t.pnl for t in trades), Decimal(0))),
        avg_pnl=_avg([t.pnl for t in trades]),
        avg_pnl_pct=q(sum(pnl_pcts, Decimal(0)) / len(pnl_pcts), Decimal("0.01")) if pnl_pcts else None,
        avg_duration_seconds=round(sum(durations) / len(durations)) if durations else None,
        avg_below_seconds=round(sum(belows) / len(belows)) if belows else None,
        avg_below_pct=q(sum(below_pcts, Decimal(0)) / len(below_pcts), Decimal("0.01")) if below_pcts else None,
    )


def trade_from_position(position) -> Optional[Trade]:
    """A Trade for a fully closed position, None for open ones."""
    metrics = position_metrics(position, None)
    if not metrics.is_closed or not position.sales:
        return None
    return Trade(
        position_id=position.id,
        portfolio_id=position.portfolio_id,
        symbol=position.symbol,
        bought_at=position.bought_at,
        closed_at=max(s.sold_at for s in position.sales),
        cost=metrics.cost,
        pnl=metrics.total_pnl,
        pnl_pct=metrics.total_pnl_pct,
        tags=list(position.tags),
        entry_reason=position.entry_reason,
        exit_reasons=sorted({s.exit_reason for s in position.sales if s.exit_reason}),
    )


def with_timing(trades: list[Trade], positions_by_id: dict, timing_fn: Callable) -> list[Trade]:
    """Attach duration / time below entry (in parallel; failures leave the fields empty)."""
    def attach(trade: Trade) -> Trade:
        try:
            timing = timing_fn(positions_by_id[trade.position_id])
        except Exception:  # candles unavailable etc. - the trade still counts in PnL stats
            return trade
        return Trade(**{**trade.__dict__, "duration_seconds": timing.duration_seconds,
                        "below_seconds": timing.below_seconds, "below_pct": timing.below_pct})

    if not trades:
        return trades
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(attach, trades))


def journal_stats(trades: list[Trade]) -> dict:
    tags = sorted({tag for t in trades for tag in t.tags})
    by_keyword: dict[str, list[Trade]] = {}
    for trade in trades:
        for word in keywords(trade.entry_reason):
            by_keyword.setdefault(word, []).append(trade)

    def tag_rows():
        rows = [{"tag": tag, **group_stats(t for t in trades if tag in t.tags).__dict__} for tag in tags]
        untagged = [t for t in trades if not t.tags]
        if untagged:
            rows.append({"tag": None, **group_stats(untagged).__dict__})
        return sorted(rows, key=lambda r: (-r["trades"], r["tag"] or "~"))

    keyword_rows = [
        {"keyword": word, **group_stats(items).__dict__}
        for word, items in by_keyword.items() if len(items) >= MIN_KEYWORD_TRADES
    ]
    keyword_rows.sort(key=lambda r: (-r["trades"], -(r["win_rate"] or 0), r["keyword"]))

    return {
        "overall": group_stats(trades),
        "winners": group_stats(t for t in trades if t.is_win),
        "losers": group_stats(t for t in trades if not t.is_win),
        "tags": tag_rows(),
        "keywords": keyword_rows,
        "trades": sorted(trades, key=lambda t: t.closed_at, reverse=True),
    }
