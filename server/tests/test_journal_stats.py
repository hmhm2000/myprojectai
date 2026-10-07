from datetime import datetime
from decimal import Decimal as D

from services.journal_stats import Trade, journal_stats, keywords
from tests.conftest import login
from tests.test_portfolios_api import add_position, create_portfolio, positions_of, sell
from tests.test_position_timing import FakeCandles


def trade(pid, pnl, tags=(), reason=None, pct=None, duration=None, below=None):
    return Trade(pid, 1, "BTC", datetime(2026, 1, 1), datetime(2026, 1, 2), D(100), D(pnl), D(pct or pnl),
                 list(tags), reason, [], duration, below, None)


def test_stats_by_tag_keyword_and_outcome():
    trades = [
        trade(1, "50", ["RSI", "SUPPORT"], "RSI poniżej 30 na wsparciu", duration=3600, below=600),
        trade(2, "-20", ["RSI"], "RSI poniżej 30, FOMO", duration=7200, below=5400),
        trade(3, "30", ["SUPPORT"], "Odbicie od wsparciu", duration=1800, below=0),
        trade(4, "-10", [], "FOMO"),
    ]
    stats = journal_stats(trades)

    overall = stats["overall"]
    assert (overall.trades, overall.wins, overall.win_rate) == (4, 2, D("50.00"))
    assert overall.total_pnl == D("50") and overall.avg_pnl == D("12.5")
    assert overall.avg_duration_seconds == 4200               # trades without timing are skipped

    assert stats["winners"].avg_below_seconds == 300
    assert stats["losers"].avg_below_seconds == 5400

    tags = {row["tag"]: row for row in stats["tags"]}
    assert tags["RSI"]["trades"] == 2 and tags["RSI"]["win_rate"] == D("50.00")
    assert tags["SUPPORT"]["win_rate"] == D("100.00") and tags["SUPPORT"]["avg_pnl"] == D("40")
    assert tags[None]["trades"] == 1                            # untagged bucket

    words = {row["keyword"]: row for row in stats["keywords"]}
    assert words["fomo"]["trades"] == 2 and words["fomo"]["wins"] == 0
    assert words["rsi"]["trades"] == 2
    assert "odbicie" not in words                               # used only once
    assert keywords("Cena RSI 30, na wsparciu!") == {"rsi", "wsparciu"}


def test_journal_endpoint_uses_closed_positions(client, monkeypatch):
    import api.routes.journal as journal_routes
    monkeypatch.setattr(journal_routes, "candle_service", FakeCandles(["90", "110"]))
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    add_position(client, headers, portfolio["id"], buy_price="100", fee_coin="0", tags=["DIP"],
                 entry_reason="Dip", bought_at="2026-01-01T13:00")
    view = add_position(client, headers, portfolio["id"], buy_price="100", fee_coin="0", tags=["DIP", "RSI"],
                        bought_at="2026-01-01T13:00")
    winner, loser = (p["id"] for p in positions_of(view))
    sell(client, headers, portfolio["id"], [(winner, "1")], price="120", sold_at="2026-01-01T15:00")
    sell(client, headers, portfolio["id"], [(loser, "0.5")], price="80", sold_at="2026-01-01T15:00")  # still open

    body = client.get("/api/journal/stats", headers=headers).json()
    assert body["open_positions"] == 1
    assert body["overall"]["trades"] == 1 and body["overall"]["win_rate"] == "100.00"
    assert body["overall"]["avg_duration_seconds"] == 7200
    assert body["trades"][0]["tags"] == ["DIP"] and body["trades"][0]["pnl"] == "20.00000000"

    other = client.get(f"/api/journal/stats?portfolio_id={portfolio['id'] + 99}", headers=headers)
    assert other.status_code == 404
    no_timing = client.get("/api/journal/stats?timing=false", headers=headers).json()
    assert no_timing["overall"]["avg_duration_seconds"] is None
