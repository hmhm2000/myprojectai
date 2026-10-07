"""Portfele, pozycje (zakupy) i sprzedaże.

Każda zmiana zwraca od razu przeliczony widok portfela, żeby frontend nie musiał dociągać danych.

Sprzedaż to "grupa": jedna transakcja (cena, data, łączna opłata) rozdzielona na jedną lub kilka
pozycji tego samego coina. W bazie każda część to osobny wiersz Sale z tym samym group_id,
dzięki czemu zysk dalej liczy się osobno dla każdej pozycji.
"""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database.db import get_db
from models.portfolio import Portfolio, Position, Sale
from models.user import User
from schemas.portfolio import (
    PortfolioIn, PortfolioListItem, PortfolioOut, PositionIn, PositionOrderIn, SaleIn,
)
from services.pnl import held_quantity, sold_quantity, split_fee
from services.portfolio_view import build_list_item, build_portfolio
from services.price_service import price_service

router = APIRouter(prefix="/api", tags=["portfolios"])


def _fmt(value: Decimal) -> str:
    return format(value.normalize(), "f")


# ------------------------------------------------------------------ helpers

def _get_portfolio(db: Session, portfolio_id: int, user: User) -> Portfolio:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="Portfel nie istnieje")
    return portfolio


def _get_position(db: Session, position_id: int, user: User) -> Position:
    position = db.get(Position, position_id)
    if position is None or position.portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="Pozycja nie istnieje")
    return position


def _get_sale_group(db: Session, group_id: str, user: User) -> list[Sale]:
    sales = db.query(Sale).filter(Sale.group_id == group_id).all()
    if not sales or sales[0].position.portfolio.user_id != user.id:
        raise HTTPException(status_code=404, detail="Sprzedaż nie istnieje")
    return sales


def _view(db: Session, portfolio: Portfolio) -> PortfolioOut:
    db.refresh(portfolio)
    return build_portfolio(portfolio, price_service.get_snapshot())


def _write_sale_group(db: Session, portfolio: Portfolio, data: SaleIn, group_id: str) -> None:
    """Sprawdza i zapisuje sprzedaż rozdzieloną na pozycje (przy edycji stara wersja grupy jest pomijana)."""
    positions = []
    for allocation in data.allocations:
        position = db.get(Position, allocation.position_id)
        if position is None or position.portfolio_id != portfolio.id:
            raise HTTPException(status_code=404, detail="Pozycja nie istnieje w tym portfelu")
        positions.append(position)

    if len({p.symbol for p in positions}) > 1:
        raise HTTPException(status_code=400, detail="Jedna sprzedaż może obejmować pozycje tylko jednego coina")

    for position, allocation in zip(positions, data.allocations):
        available = held_quantity(position) - sold_quantity(position, exclude_group=group_id)
        if allocation.quantity > available:
            raise HTTPException(
                status_code=400,
                detail=f"Pozycja z {position.bought_at:%d.%m.%Y}: można sprzedać najwyżej {_fmt(available)} {position.symbol}",
            )

    # Przy edycji: usuwamy starą wersję grupy i zapisujemy nową pod tym samym group_id.
    db.query(Sale).filter(Sale.group_id == group_id).delete(synchronize_session="fetch")
    fees = split_fee(data.fee_quote, [a.quantity for a in data.allocations])
    for allocation, fee in zip(data.allocations, fees):
        db.add(Sale(
            group_id=group_id,
            position_id=allocation.position_id,
            price=data.price,
            quantity=allocation.quantity,
            fee_quote=fee,
            sold_at=data.sold_at,
            note=data.note,
        ))


# ---------------------------------------------------------------- portfele

@router.get("/portfolios", response_model=list[PortfolioListItem])
def list_portfolios(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    snapshot = price_service.get_snapshot()
    portfolios = db.query(Portfolio).filter(Portfolio.user_id == user.id).order_by(Portfolio.id).all()
    return [build_list_item(p, snapshot) for p in portfolios]


@router.post("/portfolios", response_model=PortfolioOut, status_code=201)
def create_portfolio(data: PortfolioIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolio = Portfolio(user_id=user.id, name=data.name)
    db.add(portfolio)
    db.commit()
    return _view(db, portfolio)


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioOut)
def get_portfolio(portfolio_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _view(db, _get_portfolio(db, portfolio_id, user))


@router.patch("/portfolios/{portfolio_id}", response_model=PortfolioOut)
def rename_portfolio(portfolio_id: int, data: PortfolioIn,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolio = _get_portfolio(db, portfolio_id, user)
    portfolio.name = data.name
    db.commit()
    return _view(db, portfolio)


@router.delete("/portfolios/{portfolio_id}", status_code=204)
def delete_portfolio(portfolio_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_portfolio(db, portfolio_id, user))
    db.commit()
    return Response(status_code=204)


# ----------------------------------------------------------------- pozycje

@router.post("/portfolios/{portfolio_id}/positions", response_model=PortfolioOut, status_code=201)
def add_position(portfolio_id: int, data: PositionIn,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolio = _get_portfolio(db, portfolio_id, user)
    last = db.query(func.max(Position.sort_order)).filter(Position.portfolio_id == portfolio.id).scalar() or 0
    db.add(Position(portfolio_id=portfolio.id, sort_order=last + 1, **data.model_dump()))
    db.commit()
    return _view(db, portfolio)


@router.put("/portfolios/{portfolio_id}/positions/order", response_model=PortfolioOut)
def reorder_positions(portfolio_id: int, data: PositionOrderIn,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Zapisuje kolejność ustawioną przeciąganiem (np. pozycji jednego coina)."""
    portfolio = _get_portfolio(db, portfolio_id, user)
    by_id = {p.id: p for p in portfolio.positions}
    if len(set(data.position_ids)) != len(data.position_ids) or any(i not in by_id for i in data.position_ids):
        raise HTTPException(status_code=400, detail="Nieprawidłowa lista pozycji")
    # Pozycje dostają swoje dotychczasowe "miejsca", tylko w nowej kolejności - reszta portfela się nie zmienia.
    slots = sorted(by_id[i].sort_order for i in data.position_ids)
    for slot, position_id in zip(slots, data.position_ids):
        by_id[position_id].sort_order = slot
    db.commit()
    return _view(db, portfolio)


@router.put("/positions/{position_id}", response_model=PortfolioOut)
def update_position(position_id: int, data: PositionIn,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    position = _get_position(db, position_id, user)
    if position.sales and data.symbol != position.symbol:
        raise HTTPException(status_code=400, detail="Nie można zmienić coina pozycji, która ma sprzedaże")
    if data.quantity - data.fee_coin < sold_quantity(position):
        raise HTTPException(status_code=400, detail="Ilość po opłacie nie może być mniejsza niż już sprzedana")
    for field, value in data.model_dump().items():
        setattr(position, field, value)
    db.commit()
    return _view(db, position.portfolio)


@router.delete("/positions/{position_id}", response_model=PortfolioOut)
def delete_position(position_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    position = _get_position(db, position_id, user)
    portfolio = position.portfolio
    # Sprzedaż obejmująca też inne pozycje traci tylko część z tej pozycji.
    db.delete(position)
    db.commit()
    return _view(db, portfolio)


# --------------------------------------------------------------- sprzedaże

@router.post("/portfolios/{portfolio_id}/sales", response_model=PortfolioOut, status_code=201)
def add_sale(portfolio_id: int, data: SaleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolio = _get_portfolio(db, portfolio_id, user)
    _write_sale_group(db, portfolio, data, group_id=str(uuid.uuid4()))
    db.commit()
    return _view(db, portfolio)


@router.put("/sale-groups/{group_id}", response_model=PortfolioOut)
def update_sale(group_id: str, data: SaleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolio = _get_sale_group(db, group_id, user)[0].position.portfolio
    _write_sale_group(db, portfolio, data, group_id=group_id)
    db.commit()
    return _view(db, portfolio)


@router.delete("/sale-groups/{group_id}", response_model=PortfolioOut)
def delete_sale(group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sales = _get_sale_group(db, group_id, user)
    portfolio = sales[0].position.portfolio
    for sale in sales:
        db.delete(sale)
    db.commit()
    return _view(db, portfolio)
