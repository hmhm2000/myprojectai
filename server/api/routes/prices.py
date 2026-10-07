from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from core.errors import AppError
from schemas.prices import PricesResponse, QuoteResponse, SourceStatusResponse
from services.price_service import RefreshTooSoon, Snapshot, price_service

router = APIRouter(prefix="/api/prices", tags=["prices"], dependencies=[Depends(get_current_user)])


def to_response(snapshot: Snapshot, symbols: Optional[set[str]] = None) -> PricesResponse:
    quotes = snapshot.quotes.items()
    if symbols:
        quotes = [(symbol, quote) for symbol, quote in quotes if symbol in symbols]
    return PricesResponse(
        quote_currency=snapshot.quote_currency,
        fetched_at=snapshot.fetched_at,
        stale=snapshot.stale,
        ttl_seconds=snapshot.ttl_seconds,
        force_available_in=snapshot.force_available_in,
        sources=[SourceStatusResponse(**vars(source)) for source in snapshot.sources],
        prices={
            symbol: QuoteResponse(
                price=quote.price,
                change_24h_pct=quote.change_24h_pct,
                source=quote.source,
                stale=quote.stale,
            )
            for symbol, quote in sorted(quotes)
        },
    )


@router.get("", response_model=PricesResponse)
def get_prices(symbols: str = Query("", description="E.g. BTC,SPX; empty = all available")):
    """Prices from the backend cache. Exchanges are queried only when the cache is older than the TTL."""
    wanted = {s.strip().upper() for s in symbols.split(",") if s.strip()}
    return to_response(price_service.get_snapshot(), wanted or None)


@router.post("/refresh", response_model=PricesResponse)
def force_refresh():
    """Forced price refresh ("Refresh prices" button), rate limited."""
    try:
        return to_response(price_service.force_refresh())
    except RefreshTooSoon as exc:
        raise AppError(
            429, "prices.refresh_too_soon", str(exc),
            headers={"Retry-After": str(exc.retry_after)}, retry_after=exc.retry_after,
        ) from exc
