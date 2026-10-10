"""AH vs NPC-vendor price comparison (read-only).

Vendor buy prices (what an NPC charges) are scanned from the server's shop Lua scripts plus the guild_shops
table. Vendor sell value (what an NPC pays) is item_basic.BaseSell. Nothing here writes to the database.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from workbench.adapters.servers.shop_lua import numeric_item_id, parse_npc_shop_script

from .categories import category_metadata
from .schema import sellable_clause

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_SECONDS = 600
_CHUNK = 400
_MAX_ROWS = 500


_STOCK = re.compile(r"stock\s*=\s*\{(.*?)\}", re.S)


_STOCK_OPEN = re.compile(r"stock\s*=\s*\{")


def _stock_blocks(text: str) -> list[str]:
    """Bodies of every `stock = { ... }` table, brace-balanced so nested tables do not truncate the list."""
    blocks: list[str] = []
    for m in _STOCK_OPEN.finditer(text):
        depth, pos = 1, m.end()
        while pos < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[pos], 0)
            pos += 1
        blocks.append(text[m.end():pos - 1 if depth == 0 else pos])
    return blocks


def _dsp_stock_offers(text: str) -> list[tuple[int, int]]:
    """DSP static shops: `stock = {0xITEM, price[, nationflag], ...}` passed to showShop (pairs) or showNationShop (triples)."""
    stride = 3 if "showNationShop" in text and "showShop(" not in text else 2
    out: list[tuple[int, int]] = []
    for block in _stock_blocks(text):
        nums = [int(x, 16) if x.lower().startswith("0x") else int(x) for x in re.findall(r"0[xX][0-9a-fA-F]+|\d+", re.sub(r"--[^\n]*", "", block))]
        for n in range(0, len(nums) - stride + 1, stride):
            if nums[n] and nums[n + 1]:
                out.append((nums[n], nums[n + 1]))
    return out


def scan_vendor_prices(root: Path | str) -> dict[str, Any]:
    """item_id -> cheapest NPC offer found in shop scripts. Cached for a few minutes per server root."""
    key = str(root)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    zones = Path(root) / "scripts" / "zones"
    items: dict[int, dict[str, Any]] = {}
    files = unresolved = 0
    if zones.is_dir():
        for path in zones.glob("*/npcs/*.lua"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            vendor = path.stem
            offers: list[tuple[int, int]] = []
            if ".shop." in text:
                res = parse_npc_shop_script(text, source_path=str(path.relative_to(root)).replace("\\", "/"))
                shop = res.get("shop")
                if shop:
                    vendor = shop.vendor_name or vendor
                    for it in shop.items:
                        iid = numeric_item_id(it.item_literal)
                        if iid is None or not it.price:
                            unresolved += 1
                        else:
                            offers.append((iid, int(it.price)))
            elif "showShop" in text or "showNationShop" in text:
                offers = _dsp_stock_offers(text)
            if not offers:
                continue
            files += 1
            for iid, price in offers:
                cur = items.get(iid)
                if cur is None or price < cur["price"]:
                    items[iid] = {"price": price, "vendor": vendor.replace("_", " "), "zone": path.parent.parent.name, "kind": "SHOP"}
    out = {"items": items, "shops": files, "unresolved": unresolved}
    _CACHE[key] = (time.time(), out)
    return out


def _guild_prices(service) -> dict[int, dict[str, Any]]:
    cur = service.connection.cursor()
    try:
        cur.execute("SELECT `guildid`,`itemid`,`min_price` FROM `guild_shops` WHERE `min_price`>0")
        return {int(r[1]): {"price": int(r[2]), "vendor": f"Guild #{int(r[0])}", "zone": "", "kind": "GUILD"} for r in cur.fetchall() or []}
    except Exception:
        return {}
    finally:
        cur.close()


def _rows(service, sql: str, params: tuple = ()) -> list[tuple]:
    cur = service.connection.cursor()
    try:
        cur.execute(sql, params)
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def compute(service, root: Path | str, *, min_profit: int = 1, now: int | None = None) -> dict[str, Any]:
    now = int(now if now is not None else time.time())
    i, a, qn = service.schema.item_columns, service.schema.auction_columns, service.q
    min_profit = max(0, int(min_profit))
    vendors = dict(scan_vendor_prices(root)["items"])
    for iid, g in _guild_prices(service).items():
        if iid not in vendors or g["price"] < vendors[iid]["price"]:
            vendors[iid] = g
    sellable = sellable_clause(i, qn, "b")
    qty = f"(CASE WHEN ah.`{a['stack']}`>0 THEN GREATEST(b.{qn(i['stack_size'])},1) ELSE 1 END)"

    # 1) listings priced below what an NPC would pay for the same goods (buy from AH, sell to NPC)
    sql = (
        f"SELECT ah.`{a['id']}`, ah.`{a['item_id']}`, b.{qn(i['name'])}, b.{qn(i['ah_category'])}, ah.`{a['seller_id']}`, "
        f"{('ah.`' + a['seller_name'] + '`') if a.get('seller_name') else 'NULL'}, ah.`{a['listed_at']}`, ah.`{a['asking_price']}`, "
        f"ah.`{a['stack']}`, {qty}, b.`BaseSell` FROM `auction_house` ah JOIN `item_basic` b ON b.{qn(i['item_id'])}=ah.`{a['item_id']}` "
        f"WHERE ah.`{a['sale_price']}`=0 AND ah.`{a['sold_at']}`=0 AND b.`NoSale`=0 AND b.`BaseSell`>0 AND {sellable} "
        f"AND b.`BaseSell` * {qty} - ah.`{a['asking_price']}` >= %s ORDER BY (b.`BaseSell` * {qty} - ah.`{a['asking_price']}`) DESC LIMIT %s"
    )
    listings = []
    for r in _rows(service, sql, (max(1, min_profit), _MAX_ROWS)):
        q, vendor_value = int(r[9]), int(r[10]) * int(r[9])
        listings.append({
            "auction_id": int(r[0]), "item_id": int(r[1]), "item_name": str(r[2] or ""), "category_id": int(r[3] or 0),
            "category_path": category_metadata(int(r[3] or 0)).path, "seller_id": int(r[4] or 0), "seller_name": r[5],
            "listed_at": int(r[6] or 0), "asking_price": int(r[7]), "stack": bool(r[8]), "quantity": q,
            "vendor_value": vendor_value, "profit": vendor_value - int(r[7]),
        })

    # 2) items an NPC sells cheaper than the AH value (buy from NPC, post on AH)
    post = []
    ids = sorted(vendors)
    a_sql = (
        f"SELECT b.{qn(i['item_id'])}, b.{qn(i['name'])}, b.{qn(i['ah_category'])}, b.{qn(i['stack_size'])}, "
        f"(SELECT MIN(x.`{a['asking_price']}`) FROM `auction_house` x WHERE x.`{a['item_id']}`=b.{qn(i['item_id'])} AND x.`{a['sold_at']}`=0 AND x.`{a['sale_price']}`=0 AND x.`{a['stack']}`=0), "
        f"(SELECT AVG(x.`{a['sale_price']}`) FROM `auction_house` x WHERE x.`{a['item_id']}`=b.{qn(i['item_id'])} AND x.`{a['sold_at']}`>%s AND x.`{a['stack']}`=0), "
        f"(SELECT COUNT(*) FROM `auction_house` x WHERE x.`{a['item_id']}`=b.{qn(i['item_id'])} AND x.`{a['sold_at']}`>%s AND x.`{a['stack']}`=0), b.`BaseSell` "
        f"FROM `item_basic` b WHERE {sellable} AND b.{qn(i['item_id'])} IN ({{ph}})"
    )
    since = now - 30 * 86400
    for n in range(0, len(ids), _CHUNK):
        part = ids[n:n + _CHUNK]
        for r in _rows(service, a_sql.format(ph=",".join(["%s"] * len(part))), (since, since, *part)):
            iid, v = int(r[0]), vendors[int(r[0])]
            ask = None if r[4] is None else int(r[4])
            avg = None if r[5] is None else round(float(r[5]))
            ref = avg if (avg and int(r[6]) >= 2) else ask
            if not ref or ref - v["price"] < min_profit:
                continue
            post.append({
                "item_id": iid, "item_name": str(r[1] or ""), "category_id": int(r[2] or 0), "category_path": category_metadata(int(r[2] or 0)).path,
                "vendor_price": v["price"], "vendor": v["vendor"], "zone": v["zone"], "vendor_kind": v["kind"],
                "ah_low": ask, "avg_sale": avg, "sales_30d": int(r[6]), "reference": ref, "profit": ref - v["price"],
                "margin_pct": round((ref / v["price"] - 1) * 100, 1), "base_sell": int(r[7] or 0),
            })
    post.sort(key=lambda x: -x["profit"])

    # 3) data check (the price_checker rule): an NPC sells for less than any NPC pays -> infinite-gil loop
    loops = []
    for n in range(0, len(ids), _CHUNK):
        part = ids[n:n + _CHUNK]
        sql = (f"SELECT b.{qn(i['item_id'])}, b.{qn(i['name'])}, b.`BaseSell` FROM `item_basic` b "
               f"WHERE b.`NoSale`=0 AND b.`BaseSell`>0 AND b.{qn(i['item_id'])} IN ({','.join(['%s'] * len(part))})")
        for r in _rows(service, sql, tuple(part)):
            v = vendors[int(r[0])]
            if int(r[2]) > v["price"]:
                loops.append({"item_id": int(r[0]), "item_name": str(r[1] or ""), "vendor_price": v["price"], "vendor": v["vendor"],
                              "zone": v["zone"], "base_sell": int(r[2]), "profit": int(r[2]) - v["price"]})
    loops.sort(key=lambda x: -x["profit"])

    return {
        "generated_at": now, "min_profit": min_profit, "vendor_items": len(vendors), "listings": listings, "post": post[:_MAX_ROWS], "loops": loops,
        "summary": {"listing_count": len(listings), "listing_profit": sum(x["profit"] for x in listings),
                    "post_count": len(post), "loop_count": len(loops)},
    }
