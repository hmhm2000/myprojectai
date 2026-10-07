from decimal import Decimal as D

from services.pnl import average_prices, position_metrics
from tests.conftest import login
from tests.test_pnl import position, sale
from tests.test_portfolios_api import add_position, create_portfolio, positions_of, sell


def averages(*positions):
    return average_prices([(p, position_metrics(p, D("1"))) for p in positions])


def test_average_is_weighted_by_open_quantity():
    result = averages(position("100", "1"), position("200", "3"))
    assert result.avg_buy_price == D("175")          # (100×1 + 200×3) / 4
    assert result.break_even_price == D("175")


def test_average_follows_remaining_quantity_after_sales():
    cheap = position("100", "2", sales=[sale("150", "1.5")])   # 0.5 left
    expensive = position("200", "1")
    result = averages(cheap, expensive)
    assert result.avg_buy_price == D("166.66666667")  # (100×0,5 + 200×1) / 1,5


def test_closed_positions_are_ignored():
    closed = position("100", "1", sales=[sale("150", "1")])
    result = averages(closed, position("300", "2"))
    assert result.avg_buy_price == D("300")
    assert averages(closed).avg_buy_price is None


def test_break_even_includes_coin_fee():
    # 1 BTC at 50,000, fee 0.001 BTC -> 0.999 held for 50,000 USDT
    result = averages(position("50000", "1", "0.001"))
    assert result.avg_buy_price == D("50000")
    assert result.break_even_price == D("50050.05005005")


def test_coin_average_in_portfolio_view(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    add_position(client, headers, portfolio["id"], buy_price="40000", quantity="1", fee_coin="0")
    view = add_position(client, headers, portfolio["id"], buy_price="60000", quantity="1", fee_coin="0")
    btc = view["coins"][0]
    assert btc["avg_buy_price"] == "50000.00000000"

    # Selling half of the cheaper position -> the average moves towards the more expensive one.
    cheap_id = positions_of(view)[0]["id"]
    view = sell(client, headers, portfolio["id"], [(cheap_id, "0.5")]).json()
    assert view["coins"][0]["avg_buy_price"] == "53333.33333333"   # (40 000×0,5 + 60 000×1) / 1,5

    # Cheaper position fully sold -> average = the other price.
    view = sell(client, headers, portfolio["id"], [(cheap_id, "0.5")]).json()
    assert view["coins"][0]["avg_buy_price"] == "60000.00000000"
