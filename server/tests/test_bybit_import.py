"""Bybit spot Trade History import: fills of one order merged, fees, overlapping files without
duplicates, own "Bybit" portfolio next to OKX, files in subfolders. Rows are SPX trades in the shape
of a real export with made-up ids (no account data)."""
import shutil
from decimal import Decimal as D
from pathlib import Path

import pytest

from database.db import SessionLocal
from models.portfolio import Portfolio, Position, Sale
from models.user import User
from services.imports.adapters.bybit import BybitAdapter
from services.imports.importer import import_file
from tests.conftest import login
from tests.test_okx_import import full_name, write as write_okx

HEADER = ("Spot Pairs,Order Type,Direction,feeCoin,ExecFeeV2,Filled Value,Filled Price,Filled Quantity,Fees,"
          "Transaction ID,Order No.,Timestamp (UTC)")
ROWS = {   # Jan 19 - Mar 26: buy 500, sell 499, buy 229.56, sale in two fills (55.45 + 204.69)
    1: "SPXUSDC,LIMIT,BUY,SPX,1.25,240.85,0.4817,500.00,--,3000000000000000001, 00000001,00:01 2026-01-19",
    2: "SPXUSDC,LIMIT,SELL,USDC,0.602542,241.017,0.4830,499.00,--,3000000000000000002, 00000002,00:26 2026-01-20",
    3: "SPXUSDC,MARKET,BUY,SPX,0.5739,74.95134,0.3265,229.56,--,3000000000000000003, 00000003,07:57 2026-03-16",
    4: "SPXUSDC,LIMIT,SELL,USDC,0.039688,15.875335,0.2863,55.45,--,3000000000000000004, 00000004,22:17 2026-03-26",
    5: "SPXUSDC,LIMIT,SELL,USDC,0.146353,58.54134,0.2860,204.69,--,3000000000000000005, 00000004,22:17 2026-03-26",
}
JAN_MAR = "Bybit-Spot-TradeHistory-1766962800-1774994399.csv"    # 2025-12-29 .. 2026-03-31 (Warsaw)
JAN_FEB = "Bybit-Spot-TradeHistory-1766962800-1772319599.csv"    # 2025-12-29 .. 2026-02-28


def write(folder: Path, name: str, numbers, extra=()):
    path = folder / name
    path.write_text("\n".join([HEADER, *(ROWS[n] for n in numbers), *extra]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def user(client):
    with SessionLocal() as db:
        return db.query(User).filter(User.username == "admin").one()


def run(path, user):
    with SessionLocal() as db:
        return import_file(db, db.get(User, user.id), path)


def test_adapter_merges_fills_and_keeps_fees_like_the_form(tmp_path):
    path = write(tmp_path, JAN_MAR, range(1, 6))
    assert BybitAdapter().detect(path, path.read_text(encoding="utf-8"))
    parsed = BybitAdapter().parse(path)
    assert parsed.rows_total == 5 and parsed.rows_skipped == 0 and parsed.warnings == []
    assert [r.kind for r in parsed.records] == ["buy", "sell", "buy", "sell"]
    buy = parsed.records[0]
    assert (buy.symbol, buy.quote, buy.quantity, buy.price) == ("SPX", "USDC", D("500.00"), D("0.4817"))
    assert buy.fee_coin == D("1.25") and buy.fee_quote == 0 and buy.external_id == "00000001"
    assert buy.occurred_at.isoformat() == "2026-01-19T00:01:00+00:00"
    sale = parsed.records[3]                                     # two fills of order 00000004
    assert sale.row_count == 2 and sale.quantity == D("260.14") and sale.fee_quote == D("0.186041")
    assert sale.price == D("0.2860639463") and sale.fee_coin == 0
    start, end = parsed.period
    assert start.isoformat() == "2025-12-28T23:00:00+00:00" and end.isoformat() == "2026-03-31T22:00:00+00:00"


def test_okx_file_is_not_taken_for_bybit(tmp_path):
    path = write_okx(tmp_path, full_name(), [1])
    assert not BybitAdapter().detect(path, path.read_text(encoding="utf-8"))


def test_other_quote_and_fee_coin_are_reported(tmp_path):
    parsed = BybitAdapter().parse(write(tmp_path, JAN_MAR, [], [
        "SPXBTC,LIMIT,BUY,SPX,1,0.01,0.000005,2000,--,11,22,10:00 2026-01-05",
        "SPXUSDT,LIMIT,BUY,MNT,0.3,10,0.5,20,--,12,23,10:00 2026-01-06"]))
    assert parsed.rows_skipped == 1 and len(parsed.records) == 1
    assert [w["code"] for w in parsed.warnings] == ["unsupported_pair", "fee_other_coin"]
    assert parsed.records[0].quote == "USDT" and parsed.records[0].fee_coin == 0


def test_overlapping_files_have_no_duplicates_and_own_portfolio(tmp_path, user):
    first = run(write(tmp_path, JAN_FEB, [1, 2]), user)
    assert first.status == "imported" and first.source == "bybit" and first.rows_new == 2
    second = run(write(tmp_path, JAN_MAR, range(1, 6)), user)
    assert (second.rows_new, second.rows_unchanged, second.rows_skipped) == (3, 2, 0)
    assert run(tmp_path / JAN_MAR, user).status == "already_imported"
    with SessionLocal() as db:
        portfolio = db.query(Portfolio).filter(Portfolio.kind == "import", Portfolio.source == "bybit").one()
        assert portfolio.name == "Bybit"
        positions = db.query(Position).filter(Position.source == "bybit").all()
        assert {p.portfolio_id for p in positions} == {portfolio.id} and len(positions) == 2
        assert len({s.group_id for s in db.query(Sale).filter(Sale.source == "bybit")}) == 2
        assert db.query(Position).filter(Position.source == "okx").count() == 0


def test_folder_sync_reads_exchange_subfolders(client, user):
    headers = login(client)
    from config import settings
    folder = Path(settings.import_dir)
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "okx").mkdir(parents=True)
    (folder / "bybitEU").mkdir()
    write_okx(folder / "okx", full_name(), range(1, 8))
    write(folder / "bybitEU", JAN_MAR, range(1, 6))
    try:
        status = client.post("/api/import/sync", headers=headers).json()
        assert {r["filename"]: (r["status"], r["source"]) for r in status["last_sync"]} == {
            full_name(): ("imported", "okx"), JAN_MAR: ("imported", "bybit")}
        assert {f["filename"] for f in status["files"]} == {f"okx/{full_name()}", f"bybitEU/{JAN_MAR}"}
        assert sorted(p["name"] for p in status["portfolios"]) == ["Bybit.eu", "OKX"]
    finally:
        shutil.rmtree(folder, ignore_errors=True)
