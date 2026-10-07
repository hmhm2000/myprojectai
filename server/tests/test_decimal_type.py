from datetime import datetime
from decimal import Decimal

from sqlalchemy import text

from database.db import SessionLocal
from models import Portfolio, Position, User


def test_amounts_are_stored_exactly():
    with SessionLocal() as db:
        user = User(username="u", email="u@example.com", hashed_password="x")
        portfolio = Portfolio(user=user, name="Test")
        position = Position(
            portfolio=portfolio,
            symbol="SPX",
            buy_price=Decimal("0.123456789012345678"),
            quantity="1000.10",
            fee_coin=Decimal("0"),
            bought_at=datetime(2026, 10, 1),
        )
        db.add(position)
        db.commit()
        position_id = position.id

    with SessionLocal() as db:
        raw = db.execute(text("SELECT buy_price, quantity FROM positions")).one()
        assert raw == ("0.123456789012345678", "1000.1")

        loaded = db.get(Position, position_id)
        assert loaded.buy_price == Decimal("0.123456789012345678")
        assert isinstance(loaded.quantity, Decimal)


def test_deleting_portfolio_cascades_to_positions():
    with SessionLocal() as db:
        user = User(username="u", email="u@example.com", hashed_password="x")
        portfolio = Portfolio(user=user, name="Test")
        db.add(Position(portfolio=portfolio, symbol="BTC", buy_price=1, quantity=1, bought_at=datetime(2026, 1, 1)))
        db.commit()

        db.delete(portfolio)
        db.commit()
        assert db.query(Position).count() == 0
