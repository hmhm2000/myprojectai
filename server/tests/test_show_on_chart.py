from tests.conftest import login
from tests.test_portfolios_api import add_position, create_portfolio, positions_of, sell


def strip_flags(value):
    """The portfolio view without the presentation-only show_on_chart flags."""
    if isinstance(value, dict):
        return {k: strip_flags(v) for k, v in value.items() if k != "show_on_chart"}
    if isinstance(value, list):
        return [strip_flags(v) for v in value]
    return value


def test_show_on_chart_is_presentation_only(client):
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    add_position(client, headers, portfolio["id"], buy_price="40000", fee_coin="0.001", bought_at="2026-09-01T10:15")
    view = add_position(client, headers, portfolio["id"], buy_price="60000", fee_coin="0", show_on_chart=False)
    first, second = positions_of(view)
    assert first["show_on_chart"] is True and second["show_on_chart"] is False     # default on, can be off on create
    view = sell(client, headers, portfolio["id"], [(first["id"], "0.5")], price="70000", fee="5").json()
    sale = positions_of(view)[0]["sales"][0]
    assert sale["show_on_chart"] is True

    before = client.get(f"/api/portfolios/{portfolio['id']}", headers=headers).json()
    client.patch(f"/api/positions/{first['id']}/chart", json={"show_on_chart": False}, headers=headers)
    after = client.patch(f"/api/sale-groups/{sale['group_id']}/chart", json={"show_on_chart": False}, headers=headers).json()

    hidden = positions_of(after)
    assert hidden[0]["show_on_chart"] is False and hidden[0]["sales"][0]["show_on_chart"] is False
    assert hidden[0]["bought_at"] == "2026-09-01T10:15:00"                         # real purchase time unchanged
    # FIFO, PnL, average price, quantities, totals - all identical
    assert strip_flags(after) == strip_flags(before)

    stats_hidden = client.get("/api/journal/stats?timing=false", headers=headers).json()
    client.patch(f"/api/positions/{first['id']}/chart", json={"show_on_chart": True}, headers=headers)
    assert client.get("/api/journal/stats?timing=false", headers=headers).json() == stats_hidden
