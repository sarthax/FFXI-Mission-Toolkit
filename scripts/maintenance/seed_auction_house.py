#!/usr/bin/env python3
"""Seed the Auction House with synthetic listings and sales for testing the AH admin visualizations.

Every generated row is tagged by a reserved fake seller-id range (SELLER_BASE..SELLER_BASE+N), so
--clear removes only seeded rows and never touches real player listings.

Usage (from repository root):
    py -3 scripts/maintenance/seed_auction_house.py --dry-run             # show the plan, write nothing
    py -3 scripts/maintenance/seed_auction_house.py                       # seed 60 items over 90 days
    py -3 scripts/maintenance/seed_auction_house.py --items 120 --days 30 --seed 7
    py -3 scripts/maintenance/seed_auction_house.py --clear               # remove seeded rows only

DB credentials come from the server's conf/map.conf (default C:\\topaz\\conf\\map.conf).
Schema is discovered with DESCRIBE, so legacy (buyer_name) and LSB-style (numeric buyer) layouts work.
"""
from __future__ import annotations

import argparse
import math
import random
import re
import sys
import time

SELLER_BASE = 990000          # fake seller/buyer char ids; real chars are far below this
FAKE_PLAYERS = 25
FIRST = ["Aldo", "Brisa", "Cato", "Dara", "Eron", "Fenn", "Gale", "Hana", "Ivor", "Jory", "Kira", "Lund", "Mira",
         "Nox", "Orin", "Pell", "Quin", "Rhea", "Soren", "Tala", "Ulric", "Vash", "Wren", "Xan", "Yara"]
# AH categories weighted toward what players actually trade (crystals, materials, meds, food, gear)
FALLBACK_ITEMS = ()  # none: items are always read from the live item_basic


def read_conf(path: str) -> dict:
    text = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for k in ("mysql_host", "mysql_port", "mysql_login", "mysql_password", "mysql_database"):
        m = re.search(r"^\s*" + k + r":\s*(\S+)", text, re.M)
        if not m:
            sys.exit(f"{k} not found in {path}")
        out[k] = m.group(1)
    return out


def connect(conf_path: str):
    import mysql.connector
    c = read_conf(conf_path)
    return mysql.connector.connect(host=c["mysql_host"], port=int(c["mysql_port"]), user=c["mysql_login"],
                                   password=c["mysql_password"], database=c["mysql_database"])


def describe(cur, table: str) -> set:
    cur.execute(f"DESCRIBE `{table}`")
    return {r[0] for r in cur.fetchall()}


def pick(cols: set, *names):
    return next((n for n in names if n in cols), None)


def column_map(cols: set) -> dict:
    return {
        "itemid": pick(cols, "itemid", "itemId", "item_id"), "stack": "stack",
        "seller": pick(cols, "seller", "seller_id", "sellerId"), "seller_name": pick(cols, "seller_name", "sellerName"),
        "date": pick(cols, "date", "list_date", "listed_at"), "price": pick(cols, "price", "asking_price"),
        "buyer_id": pick(cols, "buyer", "buyer_id", "buyerId"), "buyer_name": pick(cols, "buyer_name", "buyerName"),
        "sale": pick(cols, "sale", "sale_price"), "sell_date": pick(cols, "sell_date", "sellDate", "sold_at"),
    }


def build_players():
    names = [f"Tst{n}" for n in FIRST[:FAKE_PLAYERS]]  # <=15 chars, easy to spot
    return [(SELLER_BASE + i, nm) for i, nm in enumerate(names)]


def pick_items(cur, count: int, rng: random.Random):
    """Sample AH-listable items with a real vendor price, spread across categories."""
    cur.execute("SELECT itemid,name,stackSize,BaseSell,aH FROM item_basic WHERE aH>0 AND BaseSell>0")
    rows = cur.fetchall()
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r[4], []).append(r)
    cats = list(by_cat)
    rng.shuffle(cats)
    picked, i = [], 0
    while len(picked) < count and cats:
        cat = cats[i % len(cats)]
        pool = by_cat[cat]
        if pool:
            picked.append(pool.pop(rng.randrange(len(pool))))
        i += 1
        if i > count * 20:
            break
    return picked


def unit_price_curve(base: float, days: int, rng: random.Random):
    """Daily unit-price multiplier: mean-reverting walk around a per-item markup, plus an occasional spike."""
    mean = rng.uniform(1.3, 4.0)
    level, curve = mean, []
    for _ in range(days):
        level += (mean - level) * 0.15 + rng.gauss(0, 0.06 * mean)
        spike = rng.uniform(1.4, 2.0) if rng.random() < 0.02 else 1.0
        curve.append(max(1, int(base * max(level, 0.5) * spike)))
    return curve


def plan(cur, a: dict, args):
    rng = random.Random(args.seed)
    players = build_players()
    items = pick_items(cur, args.items, rng)
    now = int(time.time())
    rows = []  # dicts keyed by logical column
    for itemid, name, stack_size, base, _cat in items:
        stack_size = max(1, int(stack_size))
        popularity = rng.choice([0.2, 0.5, 1, 1, 2, 4])           # sales/day scale
        curve = unit_price_curve(float(base), args.days, rng)
        for d in range(args.days):                                 # d=0 oldest
            day_start = now - (args.days - d) * 86400
            n_sales = min(12, int(rng.expovariate(1 / max(popularity, 0.05)) if rng.random() < 0.7 else 0))
            for _ in range(n_sales):
                is_stack = stack_size > 1 and rng.random() < 0.3
                unit = max(1, int(curve[d] * rng.uniform(0.92, 1.08)))
                price = int(unit * stack_size * rng.uniform(0.85, 0.97)) if is_stack else unit
                listed = day_start + rng.randrange(0, 86400)
                sold = min(now - 60, listed + int(rng.expovariate(1 / 7200)) + 60)
                seller, buyer = rng.sample(players, 2)
                rows.append(dict(itemid=itemid, stack=int(is_stack), seller=seller[0], date=listed, price=price,
                                 buyer=buyer, sale=price, sell_date=sold))
        # currently active listings, priced around today's curve (a few deliberately overpriced)
        for _ in range(rng.choice([0, 1, 2, 3, 5])):
            is_stack = stack_size > 1 and rng.random() < 0.3
            unit = int(curve[-1] * rng.choice([0.9, 1.0, 1.0, 1.1, 1.6]))
            price = max(1, int(unit * stack_size * 0.93) if is_stack else unit)
            rows.append(dict(itemid=itemid, stack=int(is_stack), seller=rng.choice(players)[0],
                             date=now - rng.randrange(60, 3 * 86400), price=price, buyer=None, sale=0, sell_date=0))
    return players, items, rows


def insert(cur, a: dict, players, rows):
    names = {p[0]: p[1] for p in players}
    cols = [a["itemid"], a["stack"], a["seller"], a["date"], a["price"], a["sale"], a["sell_date"]]
    if a.get("seller_name"):
        cols.append(a["seller_name"])
    if a.get("buyer_name"):
        cols.append(a["buyer_name"])
    if a.get("buyer_id"):
        cols.append(a["buyer_id"])
    sql = f"INSERT INTO auction_house ({','.join('`'+c+'`' for c in cols)}) VALUES ({','.join(['%s']*len(cols))})"
    data = []
    for r in rows:
        v = [r["itemid"], r["stack"], r["seller"], r["date"], r["price"], r["sale"], r["sell_date"]]
        if a.get("seller_name"):
            v.append(names[r["seller"]])
        if a.get("buyer_name"):
            v.append(r["buyer"][1] if r["buyer"] else None)
        if a.get("buyer_id"):
            v.append(r["buyer"][0] if r["buyer"] else 0)
        data.append(v)
    cur.executemany(sql, data)


def plan_scenarios(cur, rng: random.Random):
    """A few deliberate market situations so the Economy queues have something real to show.

    Uses only items not already in auction_house, and only the fake-seller range (so --clear removes them):
      2 monopolised items  (one seller holds nearly all listings)
      3 stagnant items     (listings 35-70 days old, never sold)
      2 flooded items      (8 listings from many sellers, a single sale)
    """
    players = build_players()
    cur.execute("SELECT itemid,name,stackSize,BaseSell FROM item_basic WHERE aH>0 AND BaseSell>0 "
                "AND itemid NOT IN (SELECT DISTINCT itemid FROM auction_house)")
    pool = cur.fetchall()
    rng.shuffle(pool)
    now = int(time.time())
    rows, notes = [], []

    def listing(item, seller, age_days, sold_after=None, buyer=None):
        price = max(1, int(item[3] * rng.uniform(1.5, 3.0)))
        date = now - int(age_days * 86400)
        rows.append(dict(itemid=item[0], stack=0, seller=seller[0], date=date, price=price,
                         buyer=buyer, sale=price if buyer else 0, sell_date=(date + sold_after) if buyer else 0))

    for it in pool[:2]:                                   # monopolised
        owner = rng.choice(players)
        for _ in range(6):
            listing(it, owner, rng.uniform(0.1, 3))
        listing(it, rng.choice([p for p in players if p != owner]), 1)
        notes.append(f"monopolised: {it[1]} (6 of 7 listings by {owner[1]})")
    for it in pool[2:5]:                                  # stagnant
        for _ in range(rng.choice([2, 3])):
            listing(it, rng.choice(players), rng.uniform(35, 70))
        notes.append(f"stagnant: {it[1]}")
    for it in pool[5:7]:                                  # flooded
        sellers = rng.sample(players, 8)
        for s in sellers:
            listing(it, s, rng.uniform(0.2, 6))
        seller, buyer = rng.sample(players, 2)
        listing(it, seller, 4, sold_after=7200, buyer=buyer)
        notes.append(f"flooded: {it[1]} (8 listings, 1 sale)")
    return players, rows, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conf", default=r"C:\topaz\conf\map.conf")
    ap.add_argument("--items", type=int, default=60, help="distinct items to stock (default 60)")
    ap.add_argument("--days", type=int, default=90, help="days of sale history (default 90)")
    ap.add_argument("--seed", type=int, default=1234, help="RNG seed for repeatable data")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clear", action="store_true", help="delete previously seeded rows and exit")
    ap.add_argument("--scenarios", action="store_true",
                    help="add monopolised / stagnant / flooded sample items on top of existing seeded data and exit")
    args = ap.parse_args()

    conn = connect(args.conf)
    cur = conn.cursor()
    cols = describe(cur, "auction_house")
    a = column_map(cols)
    lo, hi = SELLER_BASE, SELLER_BASE + FAKE_PLAYERS - 1

    if args.clear:
        cur.execute(f"DELETE FROM auction_house WHERE `{a['seller']}` BETWEEN %s AND %s", (lo, hi))
        print(f"deleted {cur.rowcount} seeded rows")
        conn.commit()
        return

    if args.scenarios:
        players, rows, notes = plan_scenarios(cur, random.Random(args.seed))
        print(f"{len(rows)} scenario rows:\n  " + "\n  ".join(notes))
        if args.dry_run:
            print("dry run: nothing written")
            return
        insert(cur, a, players, rows)
        conn.commit()
        print("inserted. remove later with: py -3 scripts/maintenance/seed_auction_house.py --clear")
        return

    cur.execute(f"SELECT COUNT(*) FROM auction_house WHERE `{a['seller']}` BETWEEN %s AND %s", (lo, hi))
    if cur.fetchone()[0]:
        sys.exit("seeded rows already exist; run with --clear first (keeps real listings untouched)")

    players, items, rows = plan(cur, a, args)
    sold = sum(1 for r in rows if r["sell_date"])
    print(f"{len(items)} items, {len(players)} fake players ({players[0][1]}..{players[-1][1]})")
    print(f"{len(rows)} rows: {sold} completed sales over {args.days}d, {len(rows)-sold} active listings")
    print(f"schema: buyer_name={a['buyer_name']} buyer_id={a['buyer_id']} seller_name={a['seller_name']}")
    if args.dry_run:
        print("dry run: nothing written")
        return
    insert(cur, a, players, rows)
    conn.commit()
    print("inserted. remove later with: py -3 scripts/maintenance/seed_auction_house.py --clear")


if __name__ == "__main__":
    main()
