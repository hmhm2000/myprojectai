"""Bybit.com account statements (ledger CSVs in ZIPs): spot from the UTA ledger, deposits / withdrawals
from the Funding ledger, account chosen by the subfolder. Rows have the shape of a real export with
made-up values (no account data)."""
import shutil
import zipfile
from decimal import Decimal as D
from pathlib import Path

import pytest

from database.db import SessionLocal
from models.imports import AccountMovement
from models.portfolio import Portfolio, Position, Sale
from models.user import User
from services.imports.adapters.bybit_account import BybitAccountAdapter
from services.imports.importer import ImportEntry, import_file, sync_folder

UID = "UID: 1,Company Name: ,Country: "
UTA_HEADER = ("Uid,Currency,Contract,Type,Direction,Quantity,Position,Filled Price,Funding,Fee Paid,Cash Flow,Change,"
              "Wallet Balance,Action,Time(UTC)")
FUND_HEADER = "Uid,Date & Time(UTC),Coin,QTY,Type,Account Balance,Description"


def uta(currency, contract, kind, side, qty, price, fee, balance, action, time, position="0"):
    return f"1,{currency},{contract},{kind},{side},{qty},{position},{price},0,{fee},{qty},{qty},{balance},{action},{time}"


UTA_ROWS = [   # newest first, like the export
    # sale of 300 SOL-like coin "ABC" in two fills of the same second (fee in USDT)
    uta("USDT", "ABCUSDT", "TRADE", "SELL", "100", "0.5", "-0.1", "1150", "--", "2025-03-02 10:00:00"),
    uta("ABC", "ABCUSDT", "TRADE", "SELL", "-200", "0.5", "0", "100", "--", "2025-03-02 10:00:00"),
    uta("USDT", "ABCUSDT", "TRADE", "SELL", "40", "0.4", "-0.04", "1050", "--", "2025-03-02 10:00:00"),
    uta("ABC", "ABCUSDT", "TRADE", "SELL", "-100", "0.4", "0", "300", "--", "2025-03-02 10:00:00"),
    # perpetual: open / funding / close - not spot
    uta("USDT", "BTCUSDT", "TRADE", "SELL", "0.003", "65940", "-0.1", "1010", "CLOSE", "2025-02-19 13:43:11"),
    uta("USDT", "BTCUSDT", "SETTLEMENT", "BUY", "--", "--", "0", "1010", "SETTLEMENT", "2025-02-19 08:00:00", "0.003"),
    uta("USDT", "BTCUSDT", "TRADE", "BUY", "0.003", "66843", "-0.11", "1010", "OPEN", "2025-02-19 06:00:00", "0.003"),
    # stablecoin swap
    uta("USDT", "USDCUSDT", "TRADE", "BUY", "-100.07", "1.0007", "0", "1010", "--", "2025-02-10 09:00:00"),
    uta("USDC", "USDCUSDT", "TRADE", "BUY", "100", "1.0007", "0", "100", "--", "2025-02-10 09:00:00"),
    # purchase of 400 ABC (fee in the coin)
    uta("ABC", "ABCUSDT", "TRADE", "BUY", "400", "0.25", "-0.4", "399.6", "--", "2025-02-01 12:00:00"),
    uta("USDT", "ABCUSDT", "TRADE", "BUY", "-100", "0.25", "0", "1110", "--", "2025-02-01 12:00:00"),
    # transfer from the Funding account - internal
    "1,USDT,,TRANSFER_IN,--,0,0,0,0,0,1210,1210,1210,--,2025-01-31 10:00:00",
]
FUND_ROWS = [
    "1,2025-03-01 08:00:00,ABC,-50,Withdraw,0,Withdrawal",
    "1,2025-01-30 10:00:00,USDT,-1210,Transfer out,0,Transfer to Unified Trading Account",
    "1,2025-01-30 09:00:00,ABC,100,Deposit,100,Deposit",
    "1,2025-01-29 09:00:00,USDT,1210,Deposit,1210,Deposit",
]
UTA_NAME = "AssetChangeDetails_uta_1_20250101_20251231_0.csv"
FUND_NAME = "AssetChangeDetails_fund_1_20250101_20251231_0.csv"


def write(folder: Path, name: str, header: str, rows) -> Path:
    path = folder / name
    path.write_text("\n".join([UID, header, *rows]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def user(client):
    with SessionLocal() as db:
        return db.query(User).filter(User.username == "admin").one()


def run(path, user, account="bybitCOM"):
    with SessionLocal() as db:
        return import_file(db, db.get(User, user.id), ImportEntry(path, path.name, account))


def test_uta_ledger_spot_fills_fees_and_skipped_rows(tmp_path):
    parsed = BybitAccountAdapter().parse(write(tmp_path, UTA_NAME, UTA_HEADER, UTA_ROWS))
    records = {r.kind: r for r in parsed.records}
    assert sorted(records) == ["buy", "conversion", "sell"] and parsed.kinds == {"buy", "sell", "conversion"}
    buy, sale = records["buy"], records["sell"]
    assert (buy.symbol, buy.quote, buy.quantity, buy.price, buy.fee_coin) == ("ABC", "USDT", D(400), D("0.25"), D("0.4"))
    assert sale.quantity == D(300) and sale.row_count == 4 and sale.fee_quote == D("0.14") and sale.fee_coin == 0
    assert sale.price == D("0.4666666667") and sale.external_id == "ABCUSDT:sell:2025-03-02 10:00:00"
    assert records["conversion"].symbol == "USDC"
    codes = {w["code"]: w["params"] for w in parsed.warnings}
    assert codes == {"futures_not_imported": {"count": 3}, "internal_transfers_skipped": {"count": 1}}
    assert parsed.balances["ABC"] == D(100) and parsed.rows_skipped == 4


def test_balance_after_fills_of_one_second_in_any_order(tmp_path):
    swapped = [UTA_ROWS[2], UTA_ROWS[3], UTA_ROWS[0], UTA_ROWS[1], *UTA_ROWS[4:]]   # 300 -> 100 listed first
    parsed = BybitAccountAdapter().parse(write(tmp_path, UTA_NAME, UTA_HEADER, swapped))
    assert parsed.balances["ABC"] == D(100)


def test_fund_ledger_gives_transfers_only(tmp_path):
    parsed = BybitAccountAdapter().parse(write(tmp_path, FUND_NAME, FUND_HEADER, FUND_ROWS))
    assert sorted((r.kind, r.symbol, r.quantity) for r in parsed.records) == [
        ("transfer_in", "ABC", D(100)), ("transfer_in", "USDT", D(1210)), ("transfer_out", "ABC", D(50))]
    assert parsed.kinds == {"transfer_in", "transfer_out"} and parsed.rows_skipped == 1


def test_account_from_folder_and_no_false_missing(tmp_path, user):
    fund = run(write(tmp_path, FUND_NAME, FUND_HEADER, FUND_ROWS), user)
    spot = run(write(tmp_path, UTA_NAME, UTA_HEADER, UTA_ROWS), user)
    assert fund.source == spot.source == "bybit_com"
    # 400 bought + 100 deposited - 50 withdrawn: the sale of 300 is covered by the purchase
    assert not [w for w in spot.warnings if w["code"] in ("sale_uncovered", "sale_from_transfer")]
    again = run(write(tmp_path, "AssetChangeDetails_fund_1_20250101_20251231_1.csv", FUND_HEADER,
                      FUND_ROWS + [""]), user)              # other bytes, same rows
    assert again.rows_unchanged == 3
    with SessionLocal() as db:
        portfolio = db.query(Portfolio).filter(Portfolio.source == "bybit_com").one()
        assert portfolio.name == "Bybit.com"
        assert db.query(Position).filter(Position.missing_in_export.is_(True)).count() == 0
        assert db.query(Sale).filter(Sale.source == "bybit_com").count() == 1
        kinds = sorted(m.kind for m in db.query(AccountMovement).filter(AccountMovement.source == "bybit_com"))
        assert kinds == ["conversion", "transfer_in", "transfer_in", "transfer_out"]


SALE_200 = UTA_ROWS[:2]                                   # 200 ABC sold on 2025-03-02, no purchase


@pytest.mark.parametrize("deposits, code", [
    (["1,2025-01-30 09:00:00,ABC,100,Deposit,100,Deposit"], "sale_uncovered"),          # only 100 came in
    (["1,2025-01-30 09:00:00,ABC,100,Deposit,100,Deposit",
      "1,2025-01-20 09:00:00,ABC,150,Deposit,150,Deposit"], "sale_from_transfer"),     # 250 came in
])
def test_sale_of_deposited_coins(tmp_path, user, deposits, code):
    run(write(tmp_path, FUND_NAME, FUND_HEADER, deposits), user)
    result = run(write(tmp_path, UTA_NAME, UTA_HEADER, SALE_200), user)
    assert [w["code"] for w in result.warnings if w["code"].startswith("sale_")] == [code]
    with SessionLocal() as db:                            # no purchase to assign it to either way
        assert db.query(AccountMovement).filter(AccountMovement.kind == "sell_uncovered").count() == 1


def test_zip_members_in_account_folders(client, user):
    from config import settings
    folder = Path(settings.import_dir)
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "bybitCOM").mkdir(parents=True)
    with zipfile.ZipFile(folder / "bybitCOM" / "export.zip", "w") as archive:
        archive.writestr(f"statements/{UTA_NAME}", "\n".join([UID, UTA_HEADER, *UTA_ROWS]) + "\n")
        archive.writestr(f"statements/{FUND_NAME}", "\n".join([UID, FUND_HEADER, *FUND_ROWS]) + "\n")
    try:
        with SessionLocal() as db:
            results = sync_folder(db, db.get(User, user.id))
            again = sync_folder(db, db.get(User, user.id))
        assert [(r.filename, r.status, r.source) for r in results] == [
            (FUND_NAME, "imported", "bybit_com"), (UTA_NAME, "imported", "bybit_com")]
        assert {r.status for r in again} == {"already_imported"}
    finally:
        shutil.rmtree(folder, ignore_errors=True)
