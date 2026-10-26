"""Futures positions rebuilt from fills: chaining fills of one second, funding, USDC settlement,
copy trading, the API view and that fills stay out of the transaction list."""
from datetime import datetime
from decimal import Decimal as D

from database.db import SessionLocal
from models.portfolio import Portfolio
from services.futures import Fill, build_positions
from services.imports.adapters.bybit_account import BybitAccountAdapter
from tests.conftest import login
from tests.test_bybit_account_import import UTA_HEADER, run, user, write  # noqa: F401  (user: fixture)

T = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def fill(n, time, action, side, qty, position, pnl="0", fee="0", funding="0", price="100", account="uta"):
    return "uta", Fill(id=n, time=T(time), account=account, contract="BTCUSDT", action=action, side=side,
                       quantity=D(qty), price=None if action == "funding" else D(price),
                       position=None if position is None else D(position), pnl=D(pnl), fee=D(fee),
                       funding=D(funding), liquidation=False, quote="USDT")


def test_fills_of_one_second_are_chained_by_size():
    # close to 0 and a new open in the same second, stored in the "wrong" order (open first)
    fills = [
        fill(1, "2025-01-01 10:00:00", "open", "long", "2", "2", fee="0.2"),
        fill(2, "2025-01-01 12:00:00", "open", "long", "1", "1", fee="0.1"),      # new position, listed first
        fill(3, "2025-01-01 12:00:00", "close", "long", "2", "0", pnl="5", fee="0.2"),
        fill(4, "2025-01-01 16:00:00", "funding", "long", "1", "1", funding="-0.05"),
        fill(5, "2025-01-01 18:00:00", "close", "long", "1", "0", pnl="-1", fee="0.1", price="99"),
    ]
    first, second = build_positions(fills)
    assert (first.opened, first.closed, first.pnl, first.fees, first.net) == (D(2), D(2), D(5), D("0.4"), D("4.6"))
    assert first.closed_at == T("2025-01-01 12:00:00") and not first.is_open
    assert second.opened_at == T("2025-01-01 12:00:00") and second.funding == D("-0.05")
    assert second.net == D("-1.25") and second.out()["exit_price"] == D(99)


def test_sizes_without_position_column_and_open_position():
    fills = [fill(1, "2025-01-01 10:00:00", "open", "short", "3", None, account="okx"),
             fill(2, "2025-01-01 11:00:00", "close", "short", "1", None, pnl="2", account="okx"),
             fill(3, "2025-01-01 12:00:00", "funding", "long", "0", None, funding="0.3", account="okx")]
    [position] = build_positions(fills)
    assert position.is_open and position.size == D(2) and position.funding == D("0.3")   # funding finds the short
    assert position.out()["status"] == "open" and position.out()["closed_at"] is None


def test_uta_perp_rows_and_usdc_settlement(tmp_path):
    rows = [
        # settlement of a USDC contract: Cash Flow 2 (settled PnL), Funding -0.03, Change 1.97
        "1,USDC,BTCPERP,SETTLEMENT,BUY,--,0.003,--,-0.03,0,2,1.97,101.97,SETTLEMENT,2025-01-02 08:00:00",
        "1,USDT,ETHUSDT,TRADE,BUY,0.07,0,3000,0,-0.1,-1.6,-1.7,1000,CLOSE,2025-01-02 07:00:00",
        "1,USDT,ETHUSDT,TRADE,SELL,0.07,-0.07,3000,0,-0.1,0,-0.1,1001.7,OPEN,2025-01-02 06:00:00",
        "1,USDC,BTCPERP,TRADE,BUY,0.003,0.003,90000,0,-0.05,0,-0.05,100,OPEN,2025-01-01 20:00:00",
    ]
    parsed = BybitAccountAdapter().parse(write(tmp_path, "AssetChangeDetails_uta_1_20250101_20251231_0.csv",
                                               UTA_HEADER, rows))
    fills = {(r.symbol, r.futures["action"]): r.futures for r in parsed.records}
    assert fills[("ETHUSDT", "open")]["side"] == fills[("ETHUSDT", "close")]["side"] == "short"
    assert fills[("ETHUSDT", "close")]["pnl"] == "-1.6" and fills[("ETHUSDT", "close")]["fee"] == "0.1"
    settlement = fills[("BTCPERP", "funding")]
    assert (settlement["pnl"], settlement["funding"], settlement["side"], settlement["quote"]) == (
        "2", "-0.03", "long", "USDC")


def test_copytrading_rows(tmp_path):
    header = ("Uid,Time,Currency,Contract,Type,Direction,Quantity,Position,Filled Price,Funding,Fee Paid,Cash Flow,"
              "Change,Wallet Balance,Fee Rate,Trade ID,Order ID")
    rows = [   # one trader's close split into two copy orders (same Trade ID), a funding fee, an open
        "1,2024-12-09 13:56:30,USDT,XUSDT,Trade,Close Long,10,1.1,0.4,0,0.002,0.5,0.498,10,0.00055,T2,O2",
        "1,2024-12-09 13:56:30,USDT,XUSDT,Trade,Close Long,10,1.1,0.4,0,0.002,0.5,0.498,10,0.00055,T2,O3",
        "1,2024-12-09 08:00:00,USDT,XUSDT,Funding fee,Open Long,20,20,0.38,0,0.01,0,-0.01,9,0,F1,",
        "1,2024-12-09 07:00:00,USDT,XUSDT,Trade,Open Long,20,20,0.35,0,0.004,0,-0.004,9,0.00055,T1,O1",
        "1,2024-12-09 06:00:00,USDT,,Pre-deduction return,,,,,0,0,1,1,9,0,,",
    ]
    parsed = BybitAccountAdapter().parse(write(tmp_path, "AssetChangeDetails_copytrading_1_20240101_20241231_0.csv",
                                               header, rows))
    assert len(parsed.records) == 4 and len({r.external_id for r in parsed.records}) == 4
    [position] = build_positions([("bybit_com", Fill(
        id=i, time=r.occurred_at.replace(tzinfo=None), account=r.futures["account"], contract=r.symbol,
        action=r.futures["action"], side=r.futures["side"], quantity=r.quantity, price=r.price, position=None,
        pnl=D(r.futures["pnl"]), fee=D(r.futures["fee"]), funding=D(r.futures["funding"]), liquidation=False,
        quote="USDT")) for i, r in enumerate(parsed.records)])
    assert not position.is_open and position.net == D("0.498") * 2 - D("0.01") - D("0.004")


def test_api_view_and_fills_not_in_transactions(tmp_path, client, user):
    rows = ["1,USDT,ETHUSDT,TRADE,BUY,0.07,0,3000,0,-0.1,-1.6,-1.7,1000,CLOSE,2025-01-02 07:00:00",
            "1,USDT,ETHUSDT,TRADE,SELL,0.07,-0.07,3000,0,-0.1,0,-0.1,1001.7,OPEN,2025-01-02 06:00:00"]
    run(write(tmp_path, "AssetChangeDetails_uta_1_20250101_20251231_0.csv", UTA_HEADER, rows), user)
    headers = login(client)
    with SessionLocal() as db:
        portfolio_id = db.query(Portfolio).filter(Portfolio.source == "bybit_com").one().id
    view = client.get(f"/api/portfolios/{portfolio_id}/futures", headers=headers).json()
    assert view["summary"]["closed"] == 1 and round(view["summary"]["net"], 8) == -1.8
    [position] = view["positions"]
    assert position["side"] == "short" and position["account"] == "uta" and len(position["fills"]) == 2
    assert view["by"]["contract"][0]["key"] == "ETHUSDT"
    assert client.get(f"/api/portfolios/{portfolio_id}/transactions", headers=headers).json() == []
