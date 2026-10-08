import json
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

from config import settings
from database.db import SessionLocal
from models.portfolio import Portfolio, Position
from tests.conftest import login


def setup_portfolios(client, headers):
    """Manual portfolio with BTC (+ a sale), ETH and SPX (+ a sale), a second manual one with only BTC,
    and an import portfolio that must never be touched."""
    main = client.post("/api/portfolios", json={"name": "moje"}, headers=headers).json()["id"]
    other = client.post("/api/portfolios", json={"name": "drugi"}, headers=headers).json()["id"]

    def buy(pid, symbol):
        client.post(f"/api/portfolios/{pid}/positions", headers=headers, json={
            "symbol": symbol, "buy_price": "100", "quantity": "1", "bought_at": "2026-07-01T10:00:00"})

    for symbol in ("BTC", "ETH", "SPX"):
        buy(main, symbol)
    buy(other, "BTC")
    with SessionLocal() as db:
        ids = {p.symbol: p.id for p in db.query(Position).filter(Position.portfolio_id == main)}
        imported = Portfolio(user_id=db.get(Portfolio, main).user_id, name="OKX", kind="import", source="okx")
        db.add(imported)
        db.flush()
        db.add(Position(portfolio_id=imported.id, symbol="BTC", buy_price=D("1"), quantity=D("1"),
                        bought_at=datetime(2026, 7, 1), source="okx", external_id="1"))
        db.commit()
    for symbol in ("BTC", "SPX"):
        client.post(f"/api/portfolios/{main}/sales", headers=headers, json={
            "price": "120", "sold_at": "2026-07-02T10:00:00",
            "allocations": [{"position_id": ids[symbol], "quantity": "0.5"}]})
    return main, other


def snapshot():
    with SessionLocal() as db:
        return sorted((p.portfolio_id, p.symbol, len(p.sales)) for p in db.query(Position))


def test_dry_run_and_no_deletion_without_confirmation(client):
    headers = login(client)
    setup_portfolios(client, headers)
    before = snapshot()
    plan = client.get("/api/maintenance/manual-cleanup", headers=headers).json()
    assert (plan["positions"], plan["sales"], plan["kept_positions"], plan["kept_sales"]) == (3, 1, 1, 1)
    assert [(p["name"], p["positions"], p["empty_after"]) for p in plan["portfolios"]] == \
        [("moje", 2, False), ("drugi", 1, True)]
    assert snapshot() == before                                                  # the dry run changes nothing

    refused = client.post("/api/maintenance/manual-cleanup", headers=headers,
                          json={"confirm": False, "positions": 3, "sales": 1})
    assert refused.status_code == 400 and refused.json()["code"] == "cleanup.not_confirmed"
    stale = client.post("/api/maintenance/manual-cleanup", headers=headers,
                        json={"confirm": True, "positions": 2, "sales": 1})     # counts not from the dry run
    assert stale.status_code == 409 and stale.json()["code"] == "cleanup.plan_changed"
    assert snapshot() == before
    assert not list(Path(settings.backup_dir).glob("*.json"))                    # no backup, nothing done


def test_cleanup_keeps_only_spx_and_writes_a_backup(client):
    headers = login(client)
    setup_portfolios(client, headers)
    done = client.post("/api/maintenance/manual-cleanup", headers=headers,
                       json={"confirm": True, "positions": 3, "sales": 1}).json()
    assert (done["positions"], done["sales"], done["removed_portfolios"]) == (3, 1, [])
    with SessionLocal() as db:
        manual = db.query(Position).join(Portfolio).filter(Portfolio.kind == "manual").all()
        assert [(p.symbol, len(p.sales)) for p in manual] == [("SPX", 1)]           # SPX and its sale stay
        assert db.query(Portfolio).filter(Portfolio.kind == "manual").count() == 2  # portfolios are kept
        assert db.query(Position).filter(Position.source == "okx").count() == 1     # import untouched

    path = Path(done["backup"])
    backup = json.loads(path.read_text(encoding="utf-8"))
    assert path.name.startswith("manual-") and path.parent == Path(settings.backup_dir).resolve()
    saved = {p["name"]: sorted(x["symbol"] for x in p["positions"]) for p in backup["portfolios"]}
    assert saved == {"moje": ["BTC", "ETH", "SPX"], "drugi": ["BTC"]}               # everything, before removal
    assert any(x["sales"] for p in backup["portfolios"] for x in p["positions"] if x["symbol"] == "BTC")


def test_empty_portfolios_removed_only_on_request(client):
    headers = login(client)
    setup_portfolios(client, headers)
    done = client.post("/api/maintenance/manual-cleanup", headers=headers,
                       json={"confirm": True, "positions": 3, "sales": 1, "delete_empty_portfolios": True}).json()
    assert done["removed_portfolios"] == ["drugi"]
    with SessionLocal() as db:
        assert [p.name for p in db.query(Portfolio).order_by(Portfolio.id)] == ["moje", "OKX"]
