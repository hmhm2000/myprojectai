"""OKX "Trade Details" report: adds orders not stored yet, without touching the stored ones."""
import shutil
from decimal import Decimal as D
from pathlib import Path

from database.db import SessionLocal
from models.portfolio import Portfolio, Position, Sale
from tests.test_okx_import import TRANSFER_OUT, full_name, run, user, write  # noqa: F401

COLUMNS = ("Order ID,Trade ID,Trade Time,Instrument,Symbol,Filled Amount,Filled Amount Unit,Filled Price,"
           "Fill Price Unit,Trading Volume,Trading Volume Unit,taker/maker,Fee,Fee Unit")
NAME = "Trade Details_2026-08-02~2026-10-03~x_1.csv"
ORDERS = "Order History_2026-08-02~2026-10-03~x_1.csv"


def trade(order, trade_id, time, amount, price, volume, fee, unit, instrument="Spot", symbol="BTC-USDC"):
    return (f"{order},{trade_id},{time},{instrument},{symbol},{amount},BTC,{price},USDC,{volume},USDC,taker,"
            f"{fee},{unit}")


STORED = [trade(1005, 1, "2026-08-27 09:25:14", "0.0013", "78766.1", "99.97072178", "-0.00000127", "BTC"),
          trade(1006, 2, "2026-09-21 15:33:07", "0.0024", "84992.8", "199.92686358", "-0.00000235", "BTC"),
          trade(1007, 3, "2026-09-23 13:29:01", "0.0022", "85531.9", "187.24558016", "-0.18724558", "USDC")]


def details(folder: Path, rows, name=NAME):
    path = folder / name
    path.write_text("UID:1,Account Type:Main\n" + COLUMNS + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def folder_of(tmp_path):
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True)
    return tmp_path


def test_new_orders_are_added_with_the_exact_amount(user, tmp_path):  # noqa: F811
    folder = folder_of(tmp_path)
    run(write(folder, full_name(), range(1, 8), TRANSFER_OUT), user)
    new = [trade(2001, 4, "2026-09-30 10:00:00", "0.0001", "80000", "4.00000000", "-0.00000005", "BTC"),
           trade(2001, 5, "2026-09-30 10:00:01", "0.0001", "80000", "8.00000000", "-0.00000010", "BTC"),
           trade(2002, 6, "2026-09-30 11:00:00", "0.0001", "81000", "4.05000000", "-0.00405000", "USDC")]
    result = run(details(folder, STORED + new), user)
    assert (result.status, result.rows_new, result.rows_updated, result.rows_unchanged) == ("imported", 3, 0, 3)
    with SessionLocal() as db:
        positions = {p.external_id: p for p in db.query(Position)}
        assert positions["1005"].quantity == D("0.00126921")                    # not the rounded 0.0013
        bought = positions["2001"]
        assert (bought.quantity, bought.buy_price, bought.fee_coin) == (D("0.00015"), D("80000"), D("0.00000015"))
        assert str(bought.bought_at) == "2026-09-30 10:00:00"
        sold = db.query(Sale).filter(Sale.external_id == "2002").all()
        assert sum(s.quantity for s in sold) == D("0.00005") and sold[0].fee_quote == D("0.00405")
        assert not db.query(Position).filter(Position.missing_in_export.is_(True)).count()
        assert not db.query(Sale).filter(Sale.missing_in_export.is_(True)).count()
        assert [p.name for p in db.query(Portfolio).filter(Portfolio.kind == "import")] == ["OKX"]


def test_a_sale_with_the_fee_labelled_as_the_coin(user, tmp_path):  # noqa: F811
    folder = folder_of(tmp_path)
    run(write(folder, full_name(), range(1, 7)), user)
    wrong = trade(2003, 7, "2026-09-30 11:00:00", "0.0010", "80000", "80.00000000", "-0.08000000", "BTC")
    result = run(details(folder, [wrong]), user)
    assert result.warnings[0] == {"code": "okx_details_fee_unit", "params": {"id": "2003", "symbol": "BTC"}}
    with SessionLocal() as db:
        assert db.query(Sale).filter(Sale.external_id == "2003").count()
        assert not db.query(Position).filter(Position.external_id == "2003").count()


def test_futures_rows_and_order_history_are_reported_not_imported(user, tmp_path):  # noqa: F811
    folder = folder_of(tmp_path)
    futures = trade(2004, 8, "2026-09-30 11:00:00", "7.0", "80000", "7", "-0.02", "USDC", "Futures", "BTC-USD_UM")
    result = run(details(folder, [futures]), user)
    assert (result.rows_new, result.rows_skipped) == (0, 1)
    assert result.warnings == [{"code": "okx_details_futures_skipped", "params": {"count": 1}}]

    orders = folder / ORDERS
    orders.write_text("UID:1,Account Type:Main\nOrder ID,Order Time,Instrument,Symbol,Lvg,Side,Order Type,Order Amount,"
                      "Filled Amount,Amount Unit,Order Price,Avg. Filled Price,Price Unit,PNL,Fee,Fee Unit,Status,"
                      "Bot ID\n1,2026-09-30 11:00:00,Spot,BTC-USDC,0,Buy,MARKET,1,1,USDC,1,1,USDC,0,-1,BTC,COMPLETE,\n",
                      encoding="utf-8")
    result = run(orders, user)
    assert (result.status, result.rows_new, result.rows_skipped) == ("imported", 0, 1)
    assert result.warnings == [{"code": "okx_order_history_skipped", "params": {"count": 1}}]
