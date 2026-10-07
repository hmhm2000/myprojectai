from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from schemas.common import Amount

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Note = Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]]
PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=38, decimal_places=18)]
NonNegativeAmount = Annotated[Decimal, Field(ge=0, max_digits=38, decimal_places=18)]


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not symbol or len(symbol) > 20 or not symbol.isalnum() or not symbol.isascii():
        raise ValueError("Symbol coina: same litery/cyfry, np. BTC")
    return symbol


# ------------------------------------------------------------------ wejście

class PortfolioIn(BaseModel):
    name: Name


class PositionIn(BaseModel):
    symbol: str
    buy_price: PositiveAmount
    quantity: PositiveAmount
    fee_coin: NonNegativeAmount = Decimal(0)
    bought_at: datetime
    note: Note = None

    _symbol = field_validator("symbol")(normalize_symbol)

    @model_validator(mode="after")
    def fee_lower_than_quantity(self):
        if self.fee_coin >= self.quantity:
            raise ValueError("Opłata musi być mniejsza niż kupiona ilość")
        return self


class SaleAllocationIn(BaseModel):
    position_id: int
    quantity: PositiveAmount


class SaleIn(BaseModel):
    """Jedna sprzedaż, rozdzielona na jedną lub kilka pozycji tego samego coina."""

    price: PositiveAmount
    fee_quote: NonNegativeAmount = Decimal(0)   # łączna opłata za całą sprzedaż (USDT)
    sold_at: datetime
    note: Note = None
    allocations: list[SaleAllocationIn] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_positions(self):
        ids = [a.position_id for a in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("Każda pozycja może wystąpić w sprzedaży tylko raz")
        return self


class PositionOrderIn(BaseModel):
    """Nowa kolejność pozycji (np. jednego coina) - lista id od góry do dołu."""

    position_ids: list[int] = Field(min_length=1, max_length=1000)


# ------------------------------------------------------------------ wyjście

class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: str
    price: Amount
    quantity: Amount
    fee_quote: Amount
    sold_at: datetime
    note: Optional[str]


class PositionOut(BaseModel):
    id: int
    symbol: str
    buy_price: Amount
    quantity: Amount
    fee_coin: Amount
    bought_at: datetime
    note: Optional[str]
    sort_order: int
    sales: list[SaleOut]

    held_quantity: Amount
    sold_quantity: Amount
    open_quantity: Amount
    cost: Amount
    open_cost: Amount
    realized_pnl: Amount
    value: Optional[Amount]
    unrealized_pnl: Optional[Amount]
    total_pnl: Optional[Amount]
    total_pnl_pct: Optional[Amount]
    is_closed: bool


class PriceInfo(BaseModel):
    price: Amount
    change_24h_pct: Optional[Amount]
    source: str
    stale: bool


class GroupOut(BaseModel):
    invested: Amount                    # koszt otwartej części
    total_cost: Amount                  # koszt wszystkich pozycji (też zamkniętych)
    value: Optional[Amount]
    unrealized_pnl: Optional[Amount]    # zysk tylko z otwartych pozycji
    unrealized_pnl_pct: Optional[Amount]
    realized_pnl: Amount
    total_pnl: Optional[Amount]         # zysk ogólny (zrealizowany + otwarte)
    total_pnl_pct: Optional[Amount]


class CoinOut(GroupOut):
    symbol: str
    price: Optional[PriceInfo]
    open_quantity: Amount
    missing_price: bool
    open_positions: int
    closed_positions: int
    positions: list[PositionOut]


class SummaryOut(GroupOut):
    missing_prices: list[str]


class PricesMeta(BaseModel):
    fetched_at: Optional[datetime]
    stale: bool


class PortfolioOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    summary: SummaryOut
    coins: list[CoinOut]
    prices: PricesMeta


class PortfolioListItem(BaseModel):
    id: int
    name: str
    created_at: datetime
    positions_count: int
    summary: SummaryOut
