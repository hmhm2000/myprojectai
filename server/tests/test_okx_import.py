"""OKX CSV import: dedupe, upsert with history, manual data kept, other sources untouched, flags,
cost methods. Rows use the BTC trades of a real export with made-up ids (no account data)."""
import json
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

import pytest

from database.db import SessionLocal
from models.imports import AccountMovement, ImportChange
from models.portfolio import Portfolio, Position, Sale
from models.user import User
from services.imports.adapters.okx import OkxAdapter
from services.imports.importer import import_file, sync_folder
from tests.conftest import login

COLUMNS = ("id,Order id,Time,Trade Type,Symbol,Action,Amount,Trading Unit,Filled Price,PnL,Fee,Fee Unit,"
           "Position Change,Position Balance,Balance Change,Balance,Balance Unit,Filled_price-USD,Pnl-USD,Fee-USD,"
           "Balance-USD,Balance_change-USD")


def spot(row_id, order, time, action, amount, price, fee, fee_unit, change, balance, unit):
    return (f"{row_id},{order},{time},Spot,BTC-USDC,{action},{amount},USDC,{price},0,{fee},{fee_unit},0,0,"
            f"{change},{balance},{unit},{price},0,0,0,0")


def fill(n, time, side, btc, price, usdc, fee, btc_balance):
    """The two rows of one fill: BTC row (id 100+n) and USDC row (id 500+n), order 1000+n."""
    order = 1000 + n
    if side == "Buy":
        return [spot(100 + n, order, time, "Buy", btc, price, f"-{fee}", "BTC", D(btc) - D(fee), btc_balance, "BTC"),
                spot(500 + n, order, time, "Sell", usdc, price, "0", "USDC", f"-{usdc}", "1000", "USDC")]
    return [spot(100 + n, order, time, "Sell", btc, price, "0", "BTC", f"-{btc}", btc_balance, "BTC"),
            spot(500 + n, order, time, "Buy", usdc, price, f"-{fee}", "USDC", D(usdc) - D(fee), "1000", "USDC")]


FILLS = {
    1: fill(1, "2026-07-20 00:12:37", "Buy", "0.00310089", "64494", "199.98879966", "0.00000310", "0.00309779"),
    2: fill(2, "2026-07-20 00:15:02", "Buy", "0.00077522", "64518.5", "50.01603157", "0.00000062", "0.00387239"),
    3: fill(3, "2026-07-20 20:23:47", "Sell", "0.00387238", "64670.5", "250.42875079", "0.25042875", "0.00000001"),
    4: fill(4, "2026-07-31 23:41:36", "Buy", "0.00159576", "62688.2", "100.03532203", "0.00000128", "0.00159449"),
    5: fill(5, "2026-08-27 15:25:14", "Buy", "0.00126921", "78766.1", "99.97072178", "0.00000127", "0.00286243"),
    6: fill(6, "2026-09-21 21:33:07", "Buy", "0.00235228", "84992.8", "199.92686358", "0.00000235", "0.00521236"),
    7: fill(7, "2026-09-23 19:29:01", "Sell", "0.00218919", "85531.9", "187.24558016", "0.18724558", "0.00302317"),
}
TRANSFER_OUT = ["108,9008,2026-09-29 05:12:11,Transfer,,Transfer out,0.0,cont,0,0,0,BTC,0,0,-0.00302317,0,BTC,0,0,0,0,"
                "-252.45932152"]


def write(folder: Path, name: str, fills, extra=()):
    rows = [r for n in fills for r in FILLS[n]] + list(extra)
    path = folder / name
    path.write_text("UID:1,Account Type:Main,Time Zone:UTC+8\n" + COLUMNS + "\n" + "\n".join(rows) + "\n",
                    encoding="utf-8")
    return path


def full_name(suffix=""):
    return f"OKX Trading History_2026-07-01~2026-10-01~UTC+8~x{suffix}.csv"


@pytest.fixture
def user(client):
    with SessionLocal() as db:
        return db.query(User).filter(User.username == "admin").one()


def run(path, user):
    with SessionLocal() as db:
        return import_file(db, db.get(User, user.id), path)


def okx_portfolio(db) -> Portfolio:
    return db.query(Portfolio).filter(Portfolio.name == "OKX").one()


def test_adapter_pairs_rows_and_converts_time(tmp_path):
    parsed = OkxAdapter().parse(write(tmp_path, full_name(), range(1, 8), TRANSFER_OUT))
    assert parsed.rows_total == 15 and parsed.rows_skipped == 0
    kinds = [r.kind for r in parsed.records]
    assert kinds.count("buy") == 5 and kinds.count("sell") == 2 and kinds.count("transfer_out") == 1
    sale = next(r for r in parsed.records if r.external_id == "107")
    assert sale.kind == "sell" and sale.fee_quote == D("0.18724558") and sale.row_count == 2
    assert sale.occurred_at.utcoffset().total_seconds() == 8 * 3600
    assert parsed.balances["BTC"] == 0


def test_same_file_twice_and_identical_content(tmp_path, user):
    first = run(write(tmp_path, full_name(), range(1, 8), TRANSFER_OUT), user)
    assert first.status == "imported" and first.rows_new == 15
    again = run(tmp_path / full_name(), user)
    assert again.status == "already_imported"
    copy = write(tmp_path, full_name("-copy"), range(1, 8), TRANSFER_OUT + [""])   # other bytes, same rows
    second = run(copy, user)
    assert (second.rows_new, second.rows_updated, second.rows_unchanged) == (0, 0, 15)


def test_overlapping_files_have_no_duplicates(tmp_path, user):
    run(write(tmp_path, "OKX Trading History_2026-07-01~2026-08-01~a.csv", [1, 2, 3, 4]), user)
    result = run(write(tmp_path, "OKX Trading History_2026-07-01~2026-10-01~b.csv", [3, 4, 5, 6, 7]), user)
    assert result.rows_new == 6 and result.rows_unchanged == 4
    with SessionLocal() as db:
        assert db.query(Position).filter(Position.source == "okx").count() == 5
        assert len({s.group_id for s in db.query(Sale).filter(Sale.source == "okx")}) == 2


def test_changed_row_updates_keeps_manual_fields_and_logs(tmp_path, client, user):
    run(write(tmp_path, full_name(), range(1, 8)), user)
    headers = login(client)
    with SessionLocal() as db:
        position = db.query(Position).filter(Position.external_id == "104").one()
        position_id, portfolio_id = position.id, position.portfolio_id
    body = {"symbol": "BTC", "buy_price": "62688.2", "quantity": "0.00159576", "fee_coin": "0.00000128",
            "bought_at": "2026-07-31T17:41:36", "entry_reason": "dip", "tags": ["RSI"]}
    assert client.put(f"/api/positions/{position_id}", json=body, headers=headers).status_code == 200
    assert client.patch(f"/api/transactions/position/{position_id}", json={"note": "moja notatka",
                        "custom_fields": {"strategia": "DCA"}}, headers=headers).status_code == 204

    corrected = [r.replace("2026-07-31 23:41:36", "2026-07-31 23:45:00") for r in FILLS[4]]
    FILLS["4c"] = corrected
    try:
        result = run(write(tmp_path, full_name("-v2"), [1, 2, 3, "4c", 5, 6, 7]), user)
    finally:
        del FILLS["4c"]
    assert result.rows_updated == 2 and result.rows_new == 0
    with SessionLocal() as db:
        position = db.get(Position, position_id)
        assert position.bought_at == datetime(2026, 7, 31, 17, 45)          # 23:45 UTC+8 = 17:45 Warsaw (CEST)
        assert position.entry_reason == "dip" and position.tags == ["RSI"] and position.note == "moja notatka"
        assert json.loads(position.custom_fields) == {"strategia": "DCA"}
        change = db.query(ImportChange).filter(ImportChange.external_id == "104").one()
        assert change.field == "occurred_at" and "23:41:36" in change.old_value and "23:45:00" in change.new_value
    items = client.get(f"/api/portfolios/{portfolio_id}/transactions", headers=headers).json()
    item = next(i for i in items if i["external_id"] == "104")
    assert item["note"] == "moja notatka" and item["changes"][0]["field"] == "occurred_at"
    assert len(item["raw_rows"]) == 2 and item["raw_rows"][0]["Order id"] == "1004"


def test_other_sources_are_never_touched(tmp_path, client, user):
    headers = login(client)
    portfolio_id = client.post("/api/portfolios", json={"name": "OKX"}, headers=headers).json()["id"]
    client.post(f"/api/portfolios/{portfolio_id}/positions", headers=headers, json={
        "symbol": "BTC", "buy_price": "50000", "quantity": "0.01", "bought_at": "2026-07-01T10:00:00"})
    with SessionLocal() as db:
        db.add(Position(portfolio_id=portfolio_id, symbol="SPX", buy_price=D("0.5"), quantity=D("100"),
                        bought_at=datetime(2026, 8, 1), source="bybit", external_id="104"))   # same id, other exchange
        db.commit()
        before = [(p.id, p.symbol, p.quantity, p.source, p.missing_in_export, len(p.sales)) for p in
                  db.query(Position).filter(Position.source != "okx")]
    run(write(tmp_path, full_name(), range(1, 8), TRANSFER_OUT), user)
    run(write(tmp_path, full_name("-later"), [1, 2, 3]), user)            # everything else "missing"
    with SessionLocal() as db:
        after = [(p.id, p.symbol, p.quantity, p.source, p.missing_in_export, len(p.sales)) for p in
                 db.query(Position).filter(Position.source != "okx")]
        assert after == before                                             # no sale assigned, no flag, no change
        assert db.query(Position).filter(Position.source == "okx").count() == 5


def test_missing_rows_are_flagged_not_deleted(tmp_path, client, user):
    run(write(tmp_path, full_name(), range(1, 8), TRANSFER_OUT), user)
    run(write(tmp_path, full_name("-v2"), [1, 2, 3, 4, 5, 6]), user)       # sale 7 and the transfer are gone
    with SessionLocal() as db:
        sale_rows = db.query(Sale).filter(Sale.external_id == "107").all()           # one sale over 3 purchases
        assert len({s.group_id for s in sale_rows}) == 1 and all(s.missing_in_export for s in sale_rows)
        assert db.query(AccountMovement).filter(AccountMovement.missing_in_export.is_(True)).count() == 1
        assert db.query(Position).filter(Position.missing_in_export.is_(True)).count() == 0
    headers = login(client)
    status = client.get("/api/import", headers=headers).json()
    missing = {(m["kind"], m["external_id"]) for m in status["missing"]}
    assert missing == {("sale", "107"), ("movement", "108")}
    sale = next(m for m in status["missing"] if m["kind"] == "sale")
    kept = client.post("/api/import/missing/keep", json={"kind": "sale", "id": sale["id"]}, headers=headers).json()
    assert [m["kind"] for m in kept["missing"]] == ["movement"]
    movement = kept["missing"][0]
    left = client.post("/api/import/missing/delete", json={"kind": "movement", "id": movement["id"]}, headers=headers)
    assert left.json()["missing"] == []


def test_duplicate_fingerprint_with_other_id_is_not_created(tmp_path, user):
    run(write(tmp_path, full_name(), [1, 2]), user)
    renumbered = [r.replace("101,1001", "901,1001").replace("501,1001", "951,1001") for r in FILLS[1]]
    FILLS["1x"] = renumbered
    try:
        result = run(write(tmp_path, full_name("-renumbered"), ["1x", 2]), user)
    finally:
        del FILLS["1x"]
    assert result.rows_new == 0 and result.rows_skipped == 2
    assert any(w["code"] == "duplicate_fingerprint" for w in result.warnings)
    with SessionLocal() as db:
        assert db.query(Position).filter(Position.source == "okx").count() == 2


def test_control_values(tmp_path, client, user):
    before_transfer = run(write(tmp_path, "OKX Trading History_2026-07-01~2026-09-24~x.csv", range(1, 8)), user)
    assert {"code": "balance_ok", "params": {"coin": "BTC", "export": "0.00302317", "computed": "0.00302317"}} \
        in before_transfer.warnings
    result = run(write(tmp_path, full_name(), range(1, 8), TRANSFER_OUT), user)
    assert {"code": "balance_ok", "params": {"coin": "BTC", "export": "0", "computed": "0"}} in result.warnings

    headers = login(client)
    with SessionLocal() as db:
        portfolio_id = okx_portfolio(db).id
    def summary(method, **query):
        url = f"/api/portfolios/{portfolio_id}/cost-summary?method={method}&symbol=BTC"
        return client.get(url + "".join(f"&{k}={v}" for k, v in query.items()), headers=headers).json()[0]

    average, fifo, lifo = summary("average"), summary("fifo"), summary("lifo")
    assert average["balance"] == 0 and average["transferred_out"] == pytest.approx(0.00302317)
    assert average["transferred_out_cost"] == pytest.approx(231.96, abs=0.01)
    assert fifo["transferred_out_cost"] == pytest.approx(253.0, abs=0.01)
    assert lifo["transferred_out_cost"] == pytest.approx(213.68, abs=0.01)
    assert fifo["realized"] == pytest.approx(40.3, abs=0.01)                 # net of fees
    assert average["realized"] == pytest.approx(19.26, abs=0.01) and lifo["realized"] == pytest.approx(0.98, abs=0.01)

    # Main view: the same model as manual entries; sales assigned FIFO -> realized like FIFO, BTC still owned
    portfolio = client.get(f"/api/portfolios/{portfolio_id}", headers=headers).json()
    btc = next(c for c in portfolio["coins"] if c["symbol"] == "BTC")
    assert float(btc["realized_pnl"]) == pytest.approx(40.31, abs=0.01)
    assert float(btc["open_quantity"]) == pytest.approx(0.00302317)


def test_unrealized_at_given_price(tmp_path, client, user):
    run(write(tmp_path, "OKX Trading History_2026-07-01~2026-09-24~x.csv", range(1, 8)), user)
    headers = login(client)
    with SessionLocal() as db:
        portfolio_id = okx_portfolio(db).id
    row = client.get(f"/api/portfolios/{portfolio_id}/cost-summary?method=average&symbol=BTC&price=100000",
                     headers=headers).json()[0]
    assert row["value"] == pytest.approx(302.317) and row["unrealized"] == pytest.approx(302.317 - 231.96, abs=0.01)


def test_folder_sync_and_status(tmp_path, client, user):
    headers = login(client)
    from config import settings
    folder = Path(settings.import_dir)
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.csv"):
        old.unlink()
    write(folder, full_name(), range(1, 8))
    (folder / "notes.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    status = client.post("/api/import/sync", headers=headers).json()
    results = {r["filename"]: r["status"] for r in status["last_sync"]}
    assert results == {full_name(): "imported", "notes.csv": "unrecognized"}
    files = {f["filename"]: f["status"] for f in status["files"]}
    assert files[full_name()] == "imported" and files["notes.csv"] == "new"
    (folder / full_name()).unlink()                                          # removing the file deletes nothing
    status = client.post("/api/import/sync", headers=headers).json()
    with SessionLocal() as db:
        assert db.query(Position).filter(Position.source == "okx").count() == 5
    assert status["history"][0]["filename"] == full_name()
