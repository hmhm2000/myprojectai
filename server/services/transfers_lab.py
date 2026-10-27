"""Test view of deposits / withdrawals across exchanges - READ ONLY.

Reads the deposit / withdrawal exports from the import folder (subfolder = exchange account, ZIPs
included) and the stored trades, and shows what they would mean - nothing is written to portfolios,
positions, sales or movements (the only stored thing is the user's label of an address).

- Formats: Binance Deposit / Withdraw History (time zone in the file name), OKX deposit / withdraw
  history (first lines "UID: ..", time MM/DD/YYYY HH:MM in the zone of the file name, GMT+1), Bybit.com
  withdrawDepositHistory (UTC). Only completed operations count.
- A withdrawal and a deposit with the same TXID = a move between the user's exchanges.
- A deposit without a pair may come back from the user's own wallet: it is attributed (oldest first)
  to earlier withdrawals of the same coin to addresses not marked "foreign" - a guess, shown as such.
- Balance per exchange and coin = trades (purchases - sales, from the database) + deposits -
  withdrawals (with fees). Bybit.com uses its Funding ledger already in the database (amounts with fees);
  OKX "Transfer in / out" rows of the trading history are moves inside OKX (Funding / Earn / staking)
  and are not counted.
"""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models.imports import AccountMovement
from models.portfolio import Portfolio, Position, Sale
from models.transfers import TransferAddress
from models.user import User
from services.imports.adapters.bybit_account import STABLE
from services.imports.importer import ACCOUNTS, _load, import_entries, local_time
from services.pnl import held_quantity

ZERO = Decimal(0)
DONE = {"completed", "received", "transferred successfully", "success", "successful"}
TZ = re.compile(r"\((?:UTC|GMT)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?\)", re.I)
FORMATS = {   # file format -> columns of its header
    "binance_withdraw": {"Time", "Coin", "Network", "Amount", "Fee", "Address", "TXID", "Status"},
    "binance_deposit": {"Time", "Coin", "Network", "Amount", "Address", "TXID", "Status"},
    "okx_deposit": {"Time", "Crypto", "Deposit address", "Network", "Transaction ID", "Amount", "Status"},
    "okx_withdraw": {"Time", "Crypto", "Withdrawal address", "Network", "Transaction ID", "Amount", "Status"},
    "bybit_history": {"Date", "Type", "Asset", "Chain", "Amount", "Tx ID", "Status", "Received Address"},
}
REVERSE_DAYS = 365          # a deposit may come back from the user's wallet within this time


def _dec(value) -> Decimal:
    try:
        return Decimal(str(value).strip() or "0")
    except InvalidOperation:
        return ZERO


def _zone(name: str) -> timezone:
    match = TZ.search(name)
    if not match:
        return timezone.utc
    sign = 1 if match.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3) or 0)))


@dataclass
class Event:
    exchange: str
    kind: str                      # in | out
    time: datetime                 # local (like the rest of the app)
    coin: str
    amount: Decimal                # arrived / sent (without the fee)
    fee: Decimal
    txid: str
    address: str                   # out: destination; in: the exchange's deposit address
    network: str
    file: str
    pair: Optional["Event"] = None              # the other side of a move between exchanges
    from_wallet: list = field(default_factory=list)   # in: [(withdrawal, amount)] guessed own-wallet origin
    returned: Decimal = ZERO                    # out: part that came back to an exchange

    def out(self) -> dict:
        return {"exchange": self.exchange, "time": self.time, "coin": self.coin, "amount": self.amount,
                "fee": self.fee, "txid": self.txid, "address": self.address, "network": self.network}


def _read(entry, exchange: str) -> tuple[Optional[str], list[Event], int]:
    """(format, completed events, rows not completed) of one file; format None = not a transfer file."""
    text = entry.read_bytes().decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    for start, line in enumerate(lines[:6]):
        columns = {c.strip() for c in next(csv.reader([line]), [])}
        kind = next((k for k, need in FORMATS.items() if need <= columns
                     and not (k == "binance_deposit" and "Fee" in columns)), None)
        if kind:
            break
    else:
        return None, [], 0
    zone = timezone.utc if kind == "bybit_history" else _zone(entry.name)
    events, other = [], 0
    for row in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        if row.get("Status", "").lower() not in DONE:
            other += 1
            continue
        if kind.startswith("binance"):
            when = datetime.strptime(row["Time"], "%Y-%m-%d %H:%M:%S")
            data = (row["Coin"], row["Amount"], row.get("Fee"), row["TXID"], row["Address"], row["Network"])
            direction = "out" if kind == "binance_withdraw" else "in"
        elif kind.startswith("okx"):
            when = datetime.strptime(row["Time"], "%m/%d/%Y %H:%M")
            address = row.get("Deposit address") or row.get("Withdrawal address")
            data = (row["Crypto"], row["Amount"], row.get("Fee"), row["Transaction ID"], address, row["Network"])
            direction = "out" if kind == "okx_withdraw" else "in"
        else:
            when = datetime.strptime(row["Date"], "%Y-%m-%d %H:%M:%S")
            data = (row["Asset"], row["Amount"], None, row["Tx ID"], row["Received Address"], row["Chain"])
            direction = "in" if row["Type"].lower() == "deposit" else "out"
        coin, amount, fee, txid, address, network = data
        events.append(Event(exchange, direction, local_time(when.replace(tzinfo=zone)), coin.upper(), _dec(amount),
                            _dec(fee), txid, address, network, entry.label))
    return kind, events, other


def _trade_balances(db: Session, user: User) -> dict[tuple[str, str], Decimal]:
    """(source, coin) -> purchases - sales of the stored import trades (no transfers)."""
    out: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    mine = (Portfolio.user_id == user.id, Portfolio.kind == "import")
    for p in db.query(Position).join(Portfolio).filter(*mine):
        out[(p.source, p.symbol)] += held_quantity(p)
    groups = set()
    for s in db.query(Sale).join(Position).join(Portfolio).filter(*mine):
        out[(s.source, s.position.symbol)] -= s.quantity
        if s.group_id not in groups:
            groups.add(s.group_id)
            unallocated = _load(s.raw).get("unallocated")
            if unallocated:
                out[(s.source, s.position.symbol)] -= Decimal(unallocated)
    for m in db.query(AccountMovement).filter(AccountMovement.user_id == user.id, AccountMovement.kind == "sell_uncovered"):
        out[(m.source, m.symbol)] -= m.quantity
    return out


def overview(db: Session, user: User, prices: dict[str, Optional[Decimal]]) -> dict:
    folder = Path(settings.import_dir)
    files, events = [], []
    for entry in import_entries(folder) if folder.exists() else []:
        exchange = ACCOUNTS.get((entry.account or "").lower(), (entry.account or "?", ""))[0]
        kind, found, other = _read(entry, exchange)
        if kind:
            files.append({"file": entry.label, "exchange": exchange, "format": kind, "completed": len(found),
                          "other_status": other})
            events += found
    events.sort(key=lambda e: e.time)
    labels = {a.address: a for a in db.query(TransferAddress).filter(TransferAddress.user_id == user.id)}

    # 1. moves between exchanges: same TXID
    by_tx = defaultdict(list)
    for e in events:
        if e.txid:
            by_tx[e.txid.lower()].append(e)
    moves = []
    for same in by_tx.values():
        outs, ins = [e for e in same if e.kind == "out"], [e for e in same if e.kind == "in"]
        if outs and ins:
            o, i = outs[0], ins[0]
            o.pair, i.pair = i, o
            moves.append({"coin": o.coin, "from": o.exchange, "to": i.exchange, "sent_at": o.time, "arrived_at": i.time,
                          "sent": o.amount, "arrived": i.amount, "minutes": round((i.time - o.time).total_seconds() / 60),
                          "txid": o.txid})

    # 2. deposits without a pair: back from the user's wallet? (oldest withdrawals of the coin first)
    for deposit in (e for e in events if e.kind == "in" and e.pair is None):
        left = deposit.amount
        for w in events:
            if left <= 0 or w.time >= deposit.time:
                break
            owner = labels.get(w.address).owner if w.address in labels else None
            if (w.kind != "out" or w.pair is not None or w.coin != deposit.coin or owner == "foreign"
                    or deposit.time - w.time > timedelta(days=REVERSE_DAYS)):
                continue
            take = min(left, w.amount - w.returned)
            if take > 0:
                w.returned += take
                left -= take
                deposit.from_wallet.append((w, take))
        if left > 0 and deposit.from_wallet:          # only partly explained - keep it as external
            for w, take in deposit.from_wallet:
                w.returned -= take
            deposit.from_wallet = []

    returns = [{"coin": d.coin, "to": d.exchange, "arrived_at": d.time, "amount": d.amount,
                "from": [{"address": w.address, "exchange": w.exchange, "sent_at": w.time, "amount": take}
                         for w, take in d.from_wallet]}
               for d in events if d.kind == "in" and d.from_wallet]
    external = [d.out() for d in events if d.kind == "in" and d.pair is None and not d.from_wallet]

    # 3. withdrawal addresses (not another exchange of the user)
    addresses: dict[str, dict] = {}
    for w in (e for e in events if e.kind == "out" and e.pair is None):
        row = addresses.setdefault(w.address, {"address": w.address, "networks": set(), "exchanges": set(),
                                               "coins": defaultdict(lambda: [ZERO, ZERO, 0]), "count": 0,
                                               "first": w.time, "last": w.time})
        row["networks"].add(w.network)
        row["exchanges"].add(w.exchange)
        coin = row["coins"][w.coin]
        coin[0] += w.amount
        coin[1] += w.returned
        coin[2] += 1
        row["count"] += 1
        row["last"] = w.time
    address_list = []
    for row in sorted(addresses.values(), key=lambda r: -r["count"]):
        label = labels.get(row["address"])
        address_list.append({
            "address": row["address"], "networks": sorted(row["networks"]), "exchanges": sorted(row["exchanges"]),
            "count": row["count"], "first": row["first"], "last": row["last"],
            "owner": label.owner if label else None, "label": label.label if label else None,
            "coins": [{"coin": c, "sent": v[0], "returned": v[1], "count": v[2]} for c, v in sorted(row["coins"].items())],
        })

    # 4. balances per exchange and coin (stablecoins / fiat are not tracked here)
    trades = _trade_balances(db, user)
    flows: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    file_exchanges = {e.exchange for e in events}
    for e in events:
        if e.exchange == "bybit_com":             # its Funding ledger (with fees) is used below
            continue
        flows[(e.exchange, e.coin)][0 if e.kind == "in" else 1] += e.amount + (e.fee if e.kind == "out" else ZERO)
    for m in db.query(AccountMovement).filter(AccountMovement.user_id == user.id, AccountMovement.source == "bybit_com",
                                              AccountMovement.kind.in_(("transfer_in", "transfer_out"))):
        flows[(m.source, m.symbol)][0 if m.kind == "transfer_in" else 1] += m.quantity
    names = {p.source: p.name for p in db.query(Portfolio).filter(Portfolio.user_id == user.id, Portfolio.kind == "import")}
    balances = []
    for key in sorted(set(trades) | set(flows)):
        exchange, coin = key
        if coin in STABLE:
            continue
        traded, (deposits, withdrawals) = trades.get(key, ZERO), flows.get(key, [ZERO, ZERO])
        balance = traded + deposits - withdrawals
        price = prices.get(coin)
        balances.append({
            "exchange": exchange, "name": names.get(exchange, exchange), "coin": coin, "traded": traded,
            "deposits": deposits, "withdrawals": withdrawals, "balance": balance,
            "has_transfer_files": exchange in file_exchanges or exchange == "bybit_com",
            "value": balance * price if price is not None and balance > 0 else None,
        })

    # 5. the user's own wallets: sent there - came back to an exchange
    own = defaultdict(lambda: [ZERO, ZERO])
    for a in address_list:
        if a["owner"] == "own":
            for c in a["coins"]:
                own[c["coin"]][0] += c["sent"]
                own[c["coin"]][1] += c["returned"]
    private = [{"coin": c, "sent": s, "returned": r, "balance": s - r,
                "value": (s - r) * prices[c] if prices.get(c) is not None else None}
               for c, (s, r) in sorted(own.items()) if c not in STABLE or s - r]

    return {"files": files, "counts": {"deposits": sum(e.kind == "in" for e in events),
                                       "withdrawals": sum(e.kind == "out" for e in events)},
            "moves": sorted(moves, key=lambda m: m["sent_at"], reverse=True), "returns": returns,
            "external": external, "addresses": address_list, "balances": balances, "private": private,
            "names": names}


def set_label(db: Session, user: User, address: str, owner: Optional[str], label: Optional[str]) -> None:
    row = db.query(TransferAddress).filter(TransferAddress.user_id == user.id, TransferAddress.address == address).first()
    if row is None:
        row = TransferAddress(user_id=user.id, address=address)
        db.add(row)
    row.owner, row.label = owner, (label or "").strip() or None
    db.commit()
