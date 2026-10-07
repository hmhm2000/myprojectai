"""Profit/loss calculations (all in Decimal).

For a single position (purchase):
    cost        = buy_price × quantity                (USDT spent)
    held        = quantity − fee_in_coin
    open        = held − sum of sold quantities
    sold_cost   = cost × sold / held
    realized    = Σ(sold_qty × sale_price − fee_USDT) − sold_cost
    unrealized  = open × current_price − (cost − sold_cost)
    total       = realized + unrealized,  % = total / cost
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional, Protocol

ZERO = Decimal(0)
MONEY = Decimal("0.00000001")
PERCENT = Decimal("0.01")


def q(value: Decimal, exp: Decimal = MONEY) -> Decimal:
    return value.quantize(exp, rounding=ROUND_HALF_UP)


def percent(part: Optional[Decimal], base: Decimal) -> Optional[Decimal]:
    if part is None or base <= 0:
        return None
    return q(part / base * 100, PERCENT)


class SaleLike(Protocol):
    price: Decimal
    quantity: Decimal
    fee_quote: Decimal


class PositionLike(Protocol):
    buy_price: Decimal
    quantity: Decimal
    fee_coin: Decimal
    sales: Iterable[SaleLike]


@dataclass(frozen=True)
class PositionMetrics:
    held_quantity: Decimal
    sold_quantity: Decimal
    open_quantity: Decimal
    cost: Decimal
    open_cost: Decimal
    proceeds: Decimal
    realized_pnl: Decimal
    value: Optional[Decimal]            # None = no price for an open position
    unrealized_pnl: Optional[Decimal]
    total_pnl: Optional[Decimal]
    total_pnl_pct: Optional[Decimal]
    is_closed: bool


def held_quantity(position: PositionLike) -> Decimal:
    return position.quantity - (position.fee_coin or ZERO)


def sold_quantity(position: PositionLike, exclude_group: Optional[str] = None) -> Decimal:
    """Sold quantity; exclude_group skips the sale that is currently being edited."""
    return sum(
        (s.quantity for s in position.sales if exclude_group is None or getattr(s, "group_id", None) != exclude_group),
        ZERO,
    )


def position_metrics(position: PositionLike, current_price: Optional[Decimal]) -> PositionMetrics:
    held = held_quantity(position)
    sold = sold_quantity(position)
    open_qty = held - sold
    cost = position.buy_price * position.quantity
    proceeds = sum((s.price * s.quantity - (s.fee_quote or ZERO) for s in position.sales), ZERO)
    sold_cost = cost * sold / held if held > 0 else cost
    open_cost = cost - sold_cost
    realized = proceeds - sold_cost

    if open_qty <= 0:
        value, unrealized = ZERO, ZERO
    elif current_price is None:
        value, unrealized = None, None
    else:
        value = open_qty * current_price
        unrealized = value - open_cost

    total = None if unrealized is None else realized + unrealized
    return PositionMetrics(
        held_quantity=held,
        sold_quantity=sold,
        open_quantity=open_qty,
        cost=q(cost),
        open_cost=q(open_cost),
        proceeds=q(proceeds),
        realized_pnl=q(realized),
        value=None if value is None else q(value),
        unrealized_pnl=None if unrealized is None else q(unrealized),
        total_pnl=None if total is None else q(total),
        total_pnl_pct=percent(total, cost),
        is_closed=open_qty <= 0,
    )


@dataclass(frozen=True)
class GroupMetrics:
    """Totals for a coin or the whole portfolio (open part + realized profit)."""
    open_quantity: Decimal
    invested: Decimal                   # cost of the open part
    total_cost: Decimal                 # cost of all positions (closed ones too)
    value: Optional[Decimal]            # None = no open position has a price
    unrealized_pnl: Optional[Decimal]   # profit of open positions only
    unrealized_pnl_pct: Optional[Decimal]
    realized_pnl: Decimal               # profit from sales (closed positions too)
    total_pnl: Optional[Decimal]        # overall profit = realized + unrealized
    total_pnl_pct: Optional[Decimal]    # overall profit / cost of all positions
    missing_price: bool                 # some open positions have no price (totals incomplete)


def group_metrics(metrics: Iterable[PositionMetrics]) -> GroupMetrics:
    metrics = list(metrics)
    open_items = [m for m in metrics if not m.is_closed]
    priced = [m for m in open_items if m.value is not None]
    missing = len(priced) < len(open_items)

    invested_priced = sum((m.open_cost for m in priced), ZERO)
    realized = sum((m.realized_pnl for m in metrics), ZERO)
    if open_items and not priced:
        value = unrealized = None
    else:
        value = sum((m.value for m in priced), ZERO)
        unrealized = sum((m.unrealized_pnl for m in priced), ZERO)

    total_cost = sum((m.cost for m in metrics), ZERO)
    total = None if unrealized is None else realized + unrealized
    if not open_items:
        total = realized  # only closed positions: the result doesn't depend on price
    return GroupMetrics(
        open_quantity=sum((m.open_quantity for m in open_items), ZERO),
        invested=q(sum((m.open_cost for m in open_items), ZERO)),
        total_cost=q(total_cost),
        value=None if value is None else q(value),
        unrealized_pnl=None if unrealized is None else q(unrealized),
        unrealized_pnl_pct=percent(unrealized, invested_priced),
        realized_pnl=q(realized),
        total_pnl=None if total is None else q(total),
        total_pnl_pct=percent(total, total_cost),
        missing_price=missing,
    )


def split_fee(fee: Decimal, quantities: list[Decimal]) -> list[Decimal]:
    """Split a sale fee across positions proportionally to the sold quantity.

    The parts always add up exactly to the fee (the rounding remainder goes to the last part).
    """
    total_quantity = sum(quantities, ZERO)
    if fee == 0 or total_quantity <= 0:
        return [ZERO for _ in quantities]
    parts = [q(fee * quantity / total_quantity) for quantity in quantities[:-1]]
    return parts + [fee - sum(parts, ZERO)]


@dataclass(frozen=True)
class AveragePrices:
    avg_buy_price: Optional[Decimal]     # average buy price of open positions (weighted by remaining quantity)
    break_even_price: Optional[Decimal]  # open cost / open quantity (includes the fee taken in coin)


def average_prices(items: Iterable[tuple[PositionLike, PositionMetrics]]) -> AveragePrices:
    """Averages for the open positions of one coin.

    The weight is the quantity still open on each position - after a (partial) sale the
    average updates automatically and closed positions stop counting.
    """
    open_items = [(p, m) for p, m in items if not m.is_closed and m.held_quantity > 0]
    open_quantity = sum((m.open_quantity for _, m in open_items), ZERO)
    if open_quantity <= 0:
        return AveragePrices(None, None)
    weighted_price = sum((p.buy_price * m.open_quantity for p, m in open_items), ZERO)
    open_cost = sum((p.buy_price * p.quantity * m.open_quantity / m.held_quantity for p, m in open_items), ZERO)
    return AveragePrices(
        avg_buy_price=q(weighted_price / open_quantity),
        break_even_price=q(open_cost / open_quantity),
    )
