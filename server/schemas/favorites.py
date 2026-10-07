from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from schemas.portfolio import Name, normalize_symbol


class FavoriteListIn(BaseModel):
    name: Name


class FavoriteCoinIn(BaseModel):
    symbol: str

    _symbol = field_validator("symbol")(normalize_symbol)


class FavoriteCoinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    added_at: datetime


class FavoriteListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    coins: list[FavoriteCoinOut]
