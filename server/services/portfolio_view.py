"""Składa widok portfela: pozycje pogrupowane po coinie + podsumowania (ceny z cache)."""
from collections import defaultdict

from models.portfolio import Portfolio, Position
from schemas.portfolio import (
    CoinOut, GroupOut, PortfolioListItem, PortfolioOut, PositionOut, PriceInfo, PricesMeta, SaleOut, SummaryOut,
)
from services.pnl import GroupMetrics, average_prices, group_metrics, position_metrics
from services.price_service import Snapshot


def _group_fields(group: GroupMetrics) -> dict:
    return GroupOut(
        invested=group.invested,
        total_cost=group.total_cost,
        value=group.value,
        unrealized_pnl=group.unrealized_pnl,
        unrealized_pnl_pct=group.unrealized_pnl_pct,
        realized_pnl=group.realized_pnl,
        total_pnl=group.total_pnl,
        total_pnl_pct=group.total_pnl_pct,
    ).model_dump()


def _position_out(position: Position, metrics) -> PositionOut:
    return PositionOut(
        id=position.id,
        symbol=position.symbol,
        buy_price=position.buy_price,
        quantity=position.quantity,
        fee_coin=position.fee_coin,
        bought_at=position.bought_at,
        note=position.note,
        sort_order=position.sort_order,
        sales=[SaleOut.model_validate(sale) for sale in position.sales],
        held_quantity=metrics.held_quantity,
        sold_quantity=metrics.sold_quantity,
        open_quantity=metrics.open_quantity,
        cost=metrics.cost,
        open_cost=metrics.open_cost,
        realized_pnl=metrics.realized_pnl,
        value=metrics.value,
        unrealized_pnl=metrics.unrealized_pnl,
        total_pnl=metrics.total_pnl,
        total_pnl_pct=metrics.total_pnl_pct,
        is_closed=metrics.is_closed,
    )


def _coins_and_summary(portfolio: Portfolio, snapshot: Snapshot) -> tuple[list[CoinOut], SummaryOut]:
    by_symbol: dict[str, list[Position]] = defaultdict(list)
    for position in portfolio.positions:
        by_symbol[position.symbol].append(position)

    coins: list[CoinOut] = []
    all_metrics = []
    for symbol, positions in by_symbol.items():
        quote = snapshot.quotes.get(symbol)
        price = quote.price if quote else None
        pairs = [(p, position_metrics(p, price)) for p in positions]
        metrics = [m for _, m in pairs]
        all_metrics.extend(metrics)
        group = group_metrics(metrics)
        averages = average_prices(pairs)
        # Zapisana kolejność (przeciąganie); sortowanie wg daty/ceny robi frontend.
        pairs.sort(key=lambda pm: (pm[0].sort_order, pm[0].id))
        coins.append(CoinOut(
            symbol=symbol,
            price=PriceInfo(price=quote.price, change_24h_pct=quote.change_24h_pct,
                            source=quote.source, stale=quote.stale) if quote else None,
            open_quantity=group.open_quantity,
            avg_buy_price=averages.avg_buy_price,
            break_even_price=averages.break_even_price,
            missing_price=group.missing_price,
            open_positions=sum(1 for m in metrics if not m.is_closed),
            closed_positions=sum(1 for m in metrics if m.is_closed),
            positions=[_position_out(p, m) for p, m in pairs],
            **_group_fields(group),
        ))

    # Coiny z otwartymi pozycjami według wartości, na końcu w pełni zamknięte.
    coins.sort(key=lambda c: (c.open_positions == 0, -(c.value or 0), c.symbol))

    summary_group = group_metrics(all_metrics)
    summary = SummaryOut(
        missing_prices=sorted(c.symbol for c in coins if c.missing_price),
        **_group_fields(summary_group),
    )
    return coins, summary


def build_portfolio(portfolio: Portfolio, snapshot: Snapshot) -> PortfolioOut:
    coins, summary = _coins_and_summary(portfolio, snapshot)
    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        summary=summary,
        coins=coins,
        prices=PricesMeta(fetched_at=snapshot.fetched_at, stale=snapshot.stale),
    )


def build_list_item(portfolio: Portfolio, snapshot: Snapshot) -> PortfolioListItem:
    _, summary = _coins_and_summary(portfolio, snapshot)
    return PortfolioListItem(
        id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        positions_count=len(portfolio.positions),
        summary=summary,
    )
