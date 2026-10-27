"""Binance spot Trade History import: units glued to numbers, fills of one order merged (identical
rows included), fees, conversions, a coin bought for fiat, time zone from the file name, own portfolio
and no duplicates from overlapping files. Rows have the shape of a real export with made-up values."""
from decimal import Decimal as D

from database.db import SessionLocal
from models.imports import AccountMovement
from models.portfolio import Portfolio, Position, Sale
from services.imports.adapters.binance import BinanceAdapter
from tests.test_bybit_account_import import run, user  # noqa: F401  (user: fixture)

HEADER = "﻿Order No,Time,Pair,Side,Price,Executed,Amount,Fee,AOR Conversion Pair,AOR Conversion Rate"
ROWS = [
    "105,2026-06-25 14:57:44,ETHUSDC,SELL,1800,0.05ETH,90USDC,0.09USDC,,",
    "104,2026-06-20 10:00:00,1INCHUSDT,BUY,0.25,40.51INCH,10.1275USDT,0.041INCH,,",            # fee 0.04 1INCH
    "103,2026-06-15 16:29:02,ETHUSDC,BUY,1500,0.1ETH,150USDC,0.0001ETH,,",
    "103,2026-06-15 16:29:02,ETHUSDC,BUY,1500,0.1ETH,150USDC,0.0001ETH,,",       # identical fill - real
    "103,2026-06-15 16:29:02,ETHUSDC,BUY,1510,0.05ETH,75.5USDC,0.00005ETH,,",
    "102,2026-06-10 09:00:00,USDCUSDT,SELL,1.0003,50USDC,50.015USDT,0BNB,,",
    "101,2024-11-21 13:59:07,ETHPLN,BUY,13600,0.2ETH,2720PLN,0.0002ETH,,",
    "100,2024-11-21 13:22:08,USDTPLN,BUY,4.0,100USDT,400PLN,0.1USDT,,",
]
NAME = "Binance-Spot-Trade-History-202610271452(UTC+1)-part1-of1.csv"


def write(folder, name, rows):
    path = folder / name
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def test_units_fills_fees_and_fiat(tmp_path):
    parsed = BinanceAdapter().parse(write(tmp_path, NAME, ROWS))
    records = {r.external_id: r for r in parsed.records}
    assert parsed.rows_total == 8 and parsed.rows_skipped == 0
    buy = records["103"]
    assert (buy.symbol, buy.quote, buy.kind, buy.row_count) == ("ETH", "USDC", "buy", 3)
    assert buy.quantity == D("0.25") and buy.fee_coin == D("0.00025") and buy.price == D("1502")
    assert buy.occurred_at.isoformat() == "2026-06-15T16:29:02+01:00"
    assert (records["105"].kind, records["105"].fee_quote, records["105"].fee_coin) == ("sell", D("0.09"), 0)
    inch = records["104"]
    assert (inch.symbol, inch.quantity, inch.fee_coin) == ("1INCH", D("40.5"), D("0.04"))
    assert records["102"].kind == records["100"].kind == "conversion"
    fiat = records["101"]                                    # 13600 PLN / 4.0 PLN per USDT
    assert (fiat.symbol, fiat.kind, fiat.quote, fiat.price) == ("ETH", "buy", "USDT", D(3400))
    assert [w["code"] for w in parsed.warnings] == ["fiat_converted"]


def test_own_portfolio_and_overlapping_files(tmp_path, user):
    first = run(write(tmp_path, NAME, ROWS[2:]), user, account="binance")
    assert first.source == "binance" and first.rows_new == 6
    later = run(write(tmp_path, "Binance-Spot-Trade-History-202611011200(UTC+1)-part1-of1.csv", ROWS), user,
                account="binance")
    assert (later.rows_new, later.rows_unchanged, later.rows_skipped) == (2, 6, 0)
    with SessionLocal() as db:
        assert db.query(Portfolio).filter(Portfolio.source == "binance").one().name == "Binance"
        assert db.query(Position).filter(Position.source == "binance").count() == 3      # ETH x2, 1INCH
        assert len({s.group_id for s in db.query(Sale).filter(Sale.source == "binance")}) == 1
        assert db.query(AccountMovement).filter(AccountMovement.kind == "conversion").count() == 2


def test_shorter_exports_never_duplicate_or_cut_orders(tmp_path, user):
    """Full history, then "last month" (cuts order 103: only its last fill), then full again."""
    run(write(tmp_path, NAME, ROWS), user, account="binance")
    month = run(write(tmp_path, "Binance-Spot-Trade-History-202611271200(UTC+1)-part1-of1.csv",
                      [ROWS[0], ROWS[4]]), user, account="binance")
    assert (month.rows_new, month.rows_updated, month.rows_unchanged) == (0, 0, 2)
    assert [w["code"] for w in month.warnings] == ["partial_order_kept"]
    again = run(write(tmp_path, "Binance-Spot-Trade-History-202612011200(UTC+1)-part1-of1.csv", ROWS + [""]),
                user, account="binance")
    assert (again.rows_new, again.rows_updated) == (0, 0)
    with SessionLocal() as db:
        eth = db.query(Position).filter(Position.source == "binance", Position.symbol == "ETH").all()
        assert sorted(p.quantity for p in eth) == [D("0.2"), D("0.25")]      # ETHPLN 0.2, order 103 in full
