from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from pydantic_core import PydanticCustomError

from schemas.common import Amount

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Note = Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]]
JournalText = Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]]
OptionalPrice = Optional[Annotated[Decimal, Field(gt=0, max_digits=38, decimal_places=18)]]
PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=38, decimal_places=18)]
NonNegativeAmount = Annotated[Decimal, Field(ge=0, max_digits=38, decimal_places=18)]


# Custom validation errors use PydanticCustomError: the error "type" (e.g. "invalid_symbol")
# is the code the frontend translates (errors.validation.<type> in the locale files).

def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not symbol or len(symbol) > 20 or not symbol.isalnum() or not symbol.isascii():
        raise PydanticCustomError("invalid_symbol", "Coin symbol must contain only letters/digits, e.g. BTC")
    return symbol


MAX_TAGS = 20


def normalize_tags(value: list[str]) -> list[str]:
    """Trim, uppercase and de-duplicate tags (order kept); letters, digits, "_" and "-" only."""
    result: list[str] = []
    for raw in value or []:
        tag = raw.strip().upper().replace(" ", "_")
        if not tag:
            continue
        if len(tag) > 30 or not all(ch.isalnum() or ch in "_-" for ch in tag) or not tag.isascii():
            raise PydanticCustomError("invalid_tag", "Tags may contain only letters, digits, '_' and '-'")
        if tag not in result:
            result.append(tag)
    if len(result) > MAX_TAGS:
        raise PydanticCustomError("too_many_tags", "Too many tags")
    return result


# ------------------------------------------------------------------ input

class PortfolioIn(BaseModel):
    name: Name


class PositionIn(BaseModel):
    symbol: str
    buy_price: PositiveAmount
    quantity: PositiveAmount
    fee_coin: NonNegativeAmount = Decimal(0)
    bought_at: datetime
    # Trade journal (all optional)
    entry_reason: JournalText = None
    tags: list[str] = Field(default_factory=list)
    plan: JournalText = None
    target_price: OptionalPrice = None
    stop_loss: OptionalPrice = None
    show_on_chart: bool = True        # presentation only

    _symbol = field_validator("symbol")(normalize_symbol)
    _tags = field_validator("tags")(normalize_tags)

    @model_validator(mode="after")
    def fee_lower_than_quantity(self):
        if self.fee_coin >= self.quantity:
            raise PydanticCustomError("fee_not_below_quantity", "Fee must be lower than the bought quantity")
        return self


class SaleAllocationIn(BaseModel):
    position_id: int
    quantity: PositiveAmount


class SaleIn(BaseModel):
    """One sale, split across one or more positions of the same coin."""

    price: PositiveAmount
    fee_quote: NonNegativeAmount = Decimal(0)   # total fee for the whole sale (USDT)
    sold_at: datetime
    exit_reason: JournalText = None   # trade journal: why I sold
    show_on_chart: bool = True        # presentation only
    allocations: list[SaleAllocationIn] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_positions(self):
        ids = [a.position_id for a in self.allocations]
        if len(ids) != len(set(ids)):
            raise PydanticCustomError("duplicate_position", "Each position can appear only once in a sale")
        return self


class ShowOnChartIn(BaseModel):
    show_on_chart: bool


class PositionOrderIn(BaseModel):
    """New order of positions (e.g. of one coin) - list of ids from top to bottom."""

    position_ids: list[int] = Field(min_length=1, max_length=1000)


# ------------------------------------------------------------------ output

class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: str
    price: Amount
    quantity: Amount
    fee_quote: Amount
    sold_at: datetime
    exit_reason: Optional[str]
    show_on_chart: bool


class PositionOut(BaseModel):
    id: int
    symbol: str
    buy_price: Amount
    quantity: Amount
    fee_coin: Amount
    bought_at: datetime
    entry_reason: Optional[str]
    tags: list[str]
    plan: Optional[str]
    target_price: Optional[Amount]
    stop_loss: Optional[Amount]
    show_on_chart: bool
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
    invested: Amount                    # cost of the open part
    total_cost: Amount                  # cost of all positions (closed ones too)
    value: Optional[Amount]
    unrealized_pnl: Optional[Amount]    # profit of open positions only
    unrealized_pnl_pct: Optional[Amount]
    realized_pnl: Amount
    total_pnl: Optional[Amount]         # overall profit (realized + open)
    total_pnl_pct: Optional[Amount]


class CoinOut(GroupOut):
    symbol: str
    price: Optional[PriceInfo]
    open_quantity: Amount
    avg_buy_price: Optional[Amount]       # average buy price of open positions
    break_even_price: Optional[Amount]    # break-even price (including fee in coin)
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
    kind: str = "manual"              # "manual" | "import"
    source: Optional[str] = None      # exchange of an import portfolio
    cost_method: str = "average"
    summary: SummaryOut
    coins: list[CoinOut]
    prices: PricesMeta


class PortfolioListItem(BaseModel):
    id: int
    name: str
    created_at: datetime
    kind: str = "manual"
    source: Optional[str] = None
    positions_count: int
    summary: SummaryOut


class PositionTimingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: datetime                   # UTC
    end: datetime                     # UTC; "now" for open positions
    is_open: bool
    duration_seconds: int
    below_seconds: int                # time with candle close below the buy price
    above_seconds: int
    unknown_seconds: int              # part of the lifetime without candles
    below_pct: Optional[Amount]       # below / (below + above) * 100
    interval: str                     # candle interval used for the calculation
    source: Optional[str]
