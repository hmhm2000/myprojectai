from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from auth import get_current_user
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
def get_prices(symbols: str = Query("", description="Np. BTC,SPX; puste = wszystkie dostępne")):
    """Ceny z cache backendu. Giełdy są odpytywane tylko, gdy cache jest starszy niż TTL."""
    wanted = {s.strip().upper() for s in symbols.split(",") if s.strip()}
    return to_response(price_service.get_snapshot(), wanted or None)


@router.post("/refresh", response_model=PricesResponse)
def force_refresh():
    """Wymuszone pobranie cen (przycisk "Odśwież ceny"), z minimalnym odstępem."""
    try:
        return to_response(price_service.force_refresh())
    except RefreshTooSoon as exc:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "retry_after": exc.retry_after},
            headers={"Retry-After": str(exc.retry_after)},
        )
