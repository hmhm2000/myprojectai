"""Wyliczenia zysku/straty (wszystko w Decimal).

Dla jednej pozycji (zakupu):
    koszt           = cena_zakupu × ilość               (ile USDT wydano)
    posiadane       = ilość − opłata_w_coinie
    otwarte         = posiadane − suma sprzedanych
    koszt_sprzed.   = koszt × sprzedane / posiadane
    zrealizowany    = Σ(ilość_sprz × cena_sprz − opłata_USDT) − koszt_sprzed.
    niezrealizowany = otwarte × cena_bieżąca − (koszt − koszt_sprzed.)
    zysk całkowity  = zrealizowany + niezrealizowany,  % = zysk / koszt
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
    value: Optional[Decimal]            # None = brak ceny dla otwartej pozycji
    unrealized_pnl: Optional[Decimal]
    total_pnl: Optional[Decimal]
    total_pnl_pct: Optional[Decimal]
    is_closed: bool


def held_quantity(position: PositionLike) -> Decimal:
    return position.quantity - (position.fee_coin or ZERO)


def sold_quantity(position: PositionLike, exclude_group: Optional[str] = None) -> Decimal:
    """Sprzedana ilość; exclude_group pomija sprzedaż, która jest właśnie edytowana."""
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
    """Suma dla coina lub całego portfela (tylko część otwarta + zrealizowany zysk)."""
    open_quantity: Decimal
    invested: Decimal                   # koszt otwartej części
    total_cost: Decimal                 # koszt wszystkich pozycji (też zamkniętych)
    value: Optional[Decimal]            # None = żadna otwarta pozycja nie ma ceny
    unrealized_pnl: Optional[Decimal]   # zysk tylko z otwartych pozycji
    unrealized_pnl_pct: Optional[Decimal]
    realized_pnl: Decimal               # zysk ze sprzedaży (także pozycji zamkniętych)
    total_pnl: Optional[Decimal]        # zysk ogólny = zrealizowany + niezrealizowany
    total_pnl_pct: Optional[Decimal]    # zysk ogólny / koszt wszystkich pozycji
    missing_price: bool                 # część otwartych pozycji nie ma ceny (sumy niepełne)


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
        total = realized  # same zamknięte pozycje: wynik nie zależy od ceny
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
    """Rozdziela opłatę sprzedaży na pozycje proporcjonalnie do sprzedanej ilości.

    Suma części jest zawsze dokładnie równa opłacie (reszta z zaokrągleń trafia do ostatniej).
    """
    total_quantity = sum(quantities, ZERO)
    if fee == 0 or total_quantity <= 0:
        return [ZERO for _ in quantities]
    parts = [q(fee * quantity / total_quantity) for quantity in quantities[:-1]]
    return parts + [fee - sum(parts, ZERO)]
