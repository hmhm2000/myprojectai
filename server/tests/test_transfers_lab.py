"""Test view of transfers: files read from the account folders, TXID moves, returns from own wallets,
balances, address labels - and that nothing in the portfolios changes."""
import shutil
from decimal import Decimal as D
from pathlib import Path

import pytest

from config import settings
from database.db import SessionLocal
from models.imports import AccountMovement
from models.portfolio import Position, Sale
from tests.conftest import login
from tests.test_binance_import import HEADER as TRADES_HEADER, user  # noqa: F401  (user: fixture)
from tests.test_bybit_account_import import run

BINANCE_TRADES = "Binance-Spot-Trade-History-202610271452(UTC+1)-part1-of1.csv"
BINANCE_OUT = ("Binance-Withdraw-History-202610271512(UTC+1)-part1-of1.csv",
               "Time,Coin,Network,Amount,Fee,Address,TXID,Status",
               ["2026-07-15 14:42:12,SOL,SOL,1.5,0.001,OKXADDR,tx-sol,Completed",            # -> OKX
                "2026-06-29 10:00:00,SHIB,ETH,1000,0,0xOWN,tx-shib,Completed",               # -> own wallet
                "2026-06-29 11:00:00,ETH,ETH,0.1,0.0001,0xFOREIGN,tx-eth,Completed",
                "2026-06-30 11:00:00,ETH,ETH,9,0,0xFAILED,tx-x,Cancelled"])
BINANCE_IN = ("Binance-Deposit-History-202610271519(UTC+1)-part1-of1.csv",
              "Time,Coin,Network,Amount,Address,TXID,Status",
              ["2024-11-21 21:38:01,ETH,ETH,0.5,0xBINANCE,tx-zonda,Completed"])
OKX_IN = ("OKX_deposit_history_20261027163045(GMT+1)_x.csv",
          "Time,Crypto,Deposit address,Network,Transaction ID,Amount,Status",
          ["07/15/2026 14:42,SOL,OKXADDR,Solana,tx-sol,1.5,Received",
           "07/16/2026 10:00,SHIB,0xOKX,ERC20,tx-back,1000,Received"])                      # back from 0xOWN


@pytest.fixture
def folder():
    root = Path(settings.import_dir)
    shutil.rmtree(root, ignore_errors=True)
    for sub in ("binance", "okx"):
        (root / sub).mkdir(parents=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def write(path: Path, header: str, rows, first: str = "") -> Path:
    path.write_text((first + "\n\n" if first else "") + "\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_overview_and_labels(folder, client, user):
    trades = write(folder / "binance" / BINANCE_TRADES, TRADES_HEADER.lstrip("﻿"),
                   ["1,2026-06-01 10:00:00,SOLUSDT,BUY,150,1.6SOL,240USDT,0.0016SOL,,",
                    "2,2026-06-01 10:00:00,SHIBUSDT,BUY,0.00001,1000SHIB,0.01USDT,0SHIB,,"])
    run(trades, user, account="binance")
    write(folder / "binance" / BINANCE_OUT[0], *BINANCE_OUT[1:])
    write(folder / "binance" / BINANCE_IN[0], *BINANCE_IN[1:])
    write(folder / "okx" / OKX_IN[0], *OKX_IN[1:], first="UID: 1,Account type: Main,Time: 10/27/2026 16:30")
    with SessionLocal() as db:
        before = (db.query(Position).count(), db.query(Sale).count(), db.query(AccountMovement).count())

    headers = login(client)
    view = client.get("/api/transfers-lab", headers=headers).json()
    assert view["counts"] == {"deposits": 3, "withdrawals": 3}                 # the cancelled one is left out
    assert [(m["coin"], m["from"], m["to"], m["minutes"]) for m in view["moves"]] == [("SOL", "binance", "okx", 0)]
    [back] = view["returns"]
    assert (back["coin"], back["to"], back["from"][0]["address"]) == ("SHIB", "okx", "0xOWN")
    assert [(d["exchange"], d["coin"]) for d in view["external"]] == [("binance", "ETH")]
    balances = {(b["exchange"], b["coin"]): b for b in view["balances"]}
    # SOL: bought 1.6 - fee 0.0016, sent 1.5 + fee 0.001 -> 0.0974 left; arrived 1.5 on OKX
    assert D(str(balances[("binance", "SOL")]["balance"])) == D("0.0974")
    assert D(str(balances[("okx", "SOL")]["balance"])) == D("1.5")
    assert {a["address"] for a in view["addresses"]} == {"0xOWN", "0xFOREIGN"}
    assert view["private"] == []

    assert client.put("/api/transfers-lab/address", headers=headers,
                      json={"address": "0xOWN", "owner": "own", "label": "MetaMask"}).status_code == 204
    view = client.get("/api/transfers-lab", headers=headers).json()
    own = next(a for a in view["addresses"] if a["address"] == "0xOWN")
    assert (own["owner"], own["label"]) == ("own", "MetaMask")
    assert [(p["coin"], p["balance"]) for p in view["private"]] == [("SHIB", 0)]   # sent 1000, all came back
    with SessionLocal() as db:                                                       # read only
        assert (db.query(Position).count(), db.query(Sale).count(), db.query(AccountMovement).count()) == before
