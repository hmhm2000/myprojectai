"""Favorite coin lists. The frontend takes prices from /api/prices (same cache)."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from auth import get_current_user
from core.errors import AppError, NotFound
from database.db import get_db
from models.favorites import FavoriteCoin, FavoriteList
from models.user import User
from schemas.favorites import FavoriteCoinIn, FavoriteListIn, FavoriteListOut

router = APIRouter(prefix="/api/favorite-lists", tags=["favorites"])


def _get_list(db: Session, list_id: int, user: User) -> FavoriteList:
    favorite_list = db.get(FavoriteList, list_id)
    if favorite_list is None or favorite_list.user_id != user.id:
        raise NotFound("favorites.list_not_found", "Favorite list not found")
    return favorite_list


@router.get("", response_model=list[FavoriteListOut])
def get_lists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(FavoriteList).filter(FavoriteList.user_id == user.id).order_by(FavoriteList.id).all()


@router.post("", response_model=FavoriteListOut, status_code=201)
def create_list(data: FavoriteListIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favorite_list = FavoriteList(user_id=user.id, name=data.name)
    db.add(favorite_list)
    db.commit()
    db.refresh(favorite_list)
    return favorite_list


@router.patch("/{list_id}", response_model=FavoriteListOut)
def rename_list(list_id: int, data: FavoriteListIn,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favorite_list = _get_list(db, list_id, user)
    favorite_list.name = data.name
    db.commit()
    db.refresh(favorite_list)
    return favorite_list


@router.delete("/{list_id}", status_code=204)
def delete_list(list_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_list(db, list_id, user))
    db.commit()
    return Response(status_code=204)


@router.post("/{list_id}/coins", response_model=FavoriteListOut, status_code=201)
def add_coin(list_id: int, data: FavoriteCoinIn,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favorite_list = _get_list(db, list_id, user)
    if any(coin.symbol == data.symbol for coin in favorite_list.coins):
        raise AppError(409, "favorites.coin_exists", f"{data.symbol} is already on this list", symbol=data.symbol)
    favorite_list.coins.append(FavoriteCoin(symbol=data.symbol))
    db.commit()
    db.refresh(favorite_list)
    return favorite_list


@router.delete("/{list_id}/coins/{symbol}", response_model=FavoriteListOut)
def remove_coin(list_id: int, symbol: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favorite_list = _get_list(db, list_id, user)
    symbol = symbol.strip().upper()
    coin = next((c for c in favorite_list.coins if c.symbol == symbol), None)
    if coin is None:
        raise NotFound("favorites.coin_not_found", "This coin is not on the list", symbol=symbol)
    favorite_list.coins.remove(coin)
    db.commit()
    db.refresh(favorite_list)
    return favorite_list
