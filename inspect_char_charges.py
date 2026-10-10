#!/usr/bin/env python3
"""Inspect charged items in a character's inventory (DSP/Topaz `char_inventory`).

Decodes the `extra` blob the way DSP's CItemUsable does:
    extra[1]    current charges
    extra[4:8]  last-use time (vana seconds, little endian)
and compares the charge byte with item_usable.maxCharges. A row whose charges < maxCharges is what
the client reports as "Partially depleted items cannot be put up for auction".

Usage (from D:\\Claude\\mission_toolkit):
    py -3 inspect_char_charges.py                      # all chars, dspdb_fresh
    py -3 inspect_char_charges.py --char Gwendy
    py -3 inspect_char_charges.py --item 13688 --item 15841
    py -3 inspect_char_charges.py --conf C:\\topaz\\conf\\map.conf
"""
from __future__ import annotations

import argparse
import re
import sys

LOCATIONS = {0: "inventory", 1: "mog safe", 2: "storage", 3: "temp", 4: "locker", 5: "satchel", 6: "sack",
             7: "case", 8: "wardrobe", 9: "safe2", 10: "wardrobe2", 11: "wardrobe3", 12: "wardrobe4"}


def read_conf(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for k in ("mysql_host", "mysql_port", "mysql_login", "mysql_password", "mysql_database"):
        m = re.search(r"^\s*" + k + r":\s*(\S+)", text, re.M)
        if not m:
            sys.exit(f"{k} not found in {path}")
        out[k] = m.group(1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conf", default=r"D:\Claude\dsp-master\conf\map_darkstar.conf")
    ap.add_argument("--char", help="character name (default: all)")
    ap.add_argument("--item", type=int, action="append", help="restrict to item id(s)")
    args = ap.parse_args()

    import mysql.connector
    c = read_conf(args.conf)
    conn = mysql.connector.connect(host=c["mysql_host"], port=int(c["mysql_port"]), user=c["mysql_login"],
                                   password=c["mysql_password"], database=c["mysql_database"])
    cur = conn.cursor()
    print(f"database: {c['mysql_database']} @ {c['mysql_host']}")

    sql = ("SELECT ch.charname, ci.location, ci.slot, ci.itemId, b.name, u.maxCharges, ci.extra "
           "FROM char_inventory ci JOIN item_usable u ON u.itemid=ci.itemId AND u.maxCharges>0 "
           "JOIN item_basic b ON b.itemid=ci.itemId JOIN chars ch ON ch.charid=ci.charid WHERE 1=1")
    params = []
    if args.char:
        sql += " AND ch.charname=%s"
        params.append(args.char)
    if args.item:
        sql += " AND ci.itemId IN (%s)" % ",".join(["%s"] * len(args.item))
        params += args.item
    cur.execute(sql + " ORDER BY ch.charname, ci.location, ci.slot", params)
    rows = cur.fetchall()
    if not rows:
        print("no charged items found")
        return
    for name, loc, slot, iid, iname, maxc, extra in rows:
        extra = bytes(extra or b"")
        cur_ch = extra[1] if len(extra) > 1 else None
        last = int.from_bytes(extra[4:8], "little") if len(extra) >= 8 else None
        if cur_ch is None:
            status = "EXTRA TOO SHORT (%d bytes) -> charges read as 0" % len(extra)
        elif cur_ch < maxc:
            status = "PARTIAL (client will refuse AH)"
        elif cur_ch > maxc:
            status = "ABOVE MAX"
        else:
            status = "ok (full)"
        print(f"{name:12} {LOCATIONS.get(loc, loc)!s:10} slot {slot:3}  {iid:5} {iname:28} "
              f"charges {cur_ch}/{maxc} lastUse {last}  extra[0:12]={extra[:12].hex()}  len={len(extra)}  {status}")


if __name__ == "__main__":
    main()
