from decimal import Decimal as D
from types import SimpleNamespace

from services.pnl import group_metrics, position_metrics, split_fee


def position(buy_price, quantity, fee_coin="0", sales=()):
    return SimpleNamespace(buy_price=D(buy_price), quantity=D(quantity), fee_coin=D(fee_coin), sales=list(sales))


def sale(price, quantity, fee_quote="0"):
    return SimpleNamespace(price=D(price), quantity=D(quantity), fee_quote=D(fee_quote))


def test_open_position_with_coin_fee():
    # 1 BTC po 50 000, opłata 0,001 BTC -> na koncie 0,999 BTC
    m = position_metrics(position("50000", "1", "0.001"), D("60000"))
    assert m.held_quantity == D("0.999")
    assert m.cost == D("50000")
    assert m.value == D("59940")
    assert m.unrealized_pnl == D("9940")
    assert m.total_pnl_pct == D("19.88")
    assert m.is_closed is False


def test_partial_sale_splits_realized_and_unrealized():
    p = position("50000", "1", "0.001", [sale("70000", "0.5", "35")])
    m = position_metrics(p, D("60000"))
    assert m.open_quantity == D("0.499")
    assert m.realized_pnl == D("9939.97497497")      # 34 965 − 50 000 × 0,5/0,999
    assert m.unrealized_pnl == D("4965.02502503")
    assert m.total_pnl == D("14905")                  # 34 965 + 29 940 − 50 000
    assert m.total_pnl_pct == D("29.81")


def test_closed_position_needs_no_price():
    p = position("100", "2", sales=[sale("150", "1.5"), sale("80", "0.5", "1")])
    m = position_metrics(p, None)
    assert m.is_closed is True
    assert m.value == 0
    assert m.realized_pnl == D("64")                  # 225 + 39 − 200
    assert m.total_pnl == D("64")
    assert m.total_pnl_pct == D("32.00")


def test_open_position_without_price():
    m = position_metrics(position("1", "10"), None)
    assert m.value is None and m.total_pnl is None and m.total_pnl_pct is None


def test_each_purchase_has_own_pnl_not_average():
    cheap = position_metrics(position("0.20", "1000"), D("0.42"))
    expensive = position_metrics(position("0.60", "1000"), D("0.42"))
    assert cheap.total_pnl == D("220")
    assert expensive.total_pnl == D("-180")

    group = group_metrics([cheap, expensive])
    assert group.invested == D("800")
    assert group.value == D("840")
    assert group.unrealized_pnl == D("40")
    assert group.unrealized_pnl_pct == D("5.00")


def test_group_with_missing_price_is_flagged():
    priced = position_metrics(position("10", "1"), D("12"))
    unpriced = position_metrics(position("5", "1"), None)
    group = group_metrics([priced, unpriced])
    assert group.missing_price is True
    assert group.value == D("12")
    assert group.unrealized_pnl_pct == D("20.00")     # liczone tylko z wycenionych


def test_group_total_includes_closed_positions():
    closed = position_metrics(position("100", "1", sales=[sale("150", "1")]), D("1"))
    open_ = position_metrics(position("100", "1"), D("90"))
    group = group_metrics([closed, open_])
    assert group.unrealized_pnl == D("-10")        # tylko otwarte
    assert group.realized_pnl == D("50")
    assert group.total_pnl == D("40")               # ogólny
    assert group.total_cost == D("200")
    assert group.total_pnl_pct == D("20.00")


def test_only_closed_positions_have_total_without_price():
    closed = position_metrics(position("100", "1", sales=[sale("80", "1")]), None)
    group = group_metrics([closed])
    assert group.total_pnl == D("-20")
    assert group.unrealized_pnl == 0


def test_split_fee_is_proportional_and_exact():
    assert split_fee(D("105"), [D("1"), D("0.5")]) == [D("70"), D("35")]
    parts = split_fee(D("1"), [D("1"), D("1"), D("1")])
    assert sum(parts) == D("1")
    assert parts[0] == D("0.33333333")
    assert split_fee(D("0"), [D("1"), D("2")]) == [0, 0]
