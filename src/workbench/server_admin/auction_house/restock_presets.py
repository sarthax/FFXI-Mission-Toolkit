"""Restock presets: a saved item-selection + pricing recipe that resolves to Restock table rows.

A preset never stores authorization. Resolving only reads; the Restock tab still previews and the
guarded executor still requires the typed confirmation.
"""
from __future__ import annotations

from .schema import sellable_clause

import time
from typing import Any

MAX_ITEMS = 50
DEFAULT_SELLER_ID = 990100
DEFAULT_SELLER_NAME = "AHRestock"
VIRTUAL_SELLER_RANGE = (990000, 990999)   # reserved for synthetic sellers that have no chars row

RESTOCK_FIELDS = {
    "description", "category_ids", "min_level", "max_level", "name_contains", "rare_only", "no_activity_days",
    "price_source", "price", "price_mult", "fallback_mult", "target", "max_items", "stack_mode", "seller_ids",
    "item_ids", "exclude_item_ids",
}
_PRICE_SOURCES = {"market", "fixed", "base_sell"}
_STACK_MODES = {"single", "stack"}


def normalize_restock_config(config: dict[str, Any]) -> dict[str, Any]:
    from .presets import PresetError
    out = {k: v for k, v in config.items() if v not in (None, "", [])}
    cats = out.get("category_ids") or []
    out["category_ids"] = sorted({int(x) for x in cats if int(x) > 0})
    for key in ("min_level", "max_level", "no_activity_days", "target", "max_items", "price"):
        if key in out:
            out[key] = int(out[key])
    for key in ("price_mult", "fallback_mult"):
        if key in out:
            out[key] = float(out[key])
            if out[key] <= 0:
                raise PresetError(f"{key} must be positive")
    if "min_level" in out and "max_level" in out and out["min_level"] > out["max_level"]:
        raise PresetError("min_level cannot exceed max_level")
    if out.get("no_activity_days", 0) < 0:
        raise PresetError("no_activity_days cannot be negative")
    out["rare_only"] = bool(out.get("rare_only"))
    out["price_source"] = str(out.get("price_source") or "market").lower()
    if out["price_source"] not in _PRICE_SOURCES:
        raise PresetError("price_source must be market, fixed or base_sell")
    if out["price_source"] == "fixed" and int(out.get("price") or 0) <= 0:
        raise PresetError("A fixed price source needs a positive price")
    out["target"] = max(1, min(int(out.get("target") or 3), 99))
    out["max_items"] = max(1, min(int(out.get("max_items") or MAX_ITEMS), MAX_ITEMS))
    mode = str(out.get("stack_mode") or "single").lower()
    if mode not in _STACK_MODES:
        raise PresetError("stack_mode must be single or stack")
    out["stack_mode"] = mode
    out["item_ids"] = sorted({int(x) for x in (out.get("item_ids") or []) if int(x) > 0})
    out["exclude_item_ids"] = sorted({int(x) for x in (out.get("exclude_item_ids") or []) if int(x) > 0})
    out["seller_ids"] = sorted({int(x) for x in (out.get("seller_ids") or []) if int(x) > 0})
    if "name_contains" in out:
        out["name_contains"] = str(out["name_contains"]).strip()
    if "description" in out:
        out["description"] = str(out["description"]).strip()[:300]
    has_scope = out["category_ids"] or "min_level" in out or "max_level" in out or out.get("name_contains") or out["rare_only"] or out["item_ids"]
    if not has_scope:
        raise PresetError("Pick at least one filter: a category, a level range, a name, specific items, or rare-only")
    return out


def resolve_items(service, config: dict[str, Any], *, now: int | None = None) -> dict[str, Any]:
    """Turn a restock preset config into Restock table entries using live data."""
    cfg = normalize_restock_config(dict(config))
    i, a, qn = service.schema.item_columns, service.schema.auction_columns, service.q
    now = int(now if now is not None else time.time())
    level_filter = "min_level" in cfg or "max_level" in cfg
    where, params = [], []
    if cfg["category_ids"]:
        where.append(f"b.{qn(i['ah_category'])} IN ({','.join(['%s'] * len(cfg['category_ids']))})")
        params += cfg["category_ids"]
    if level_filter:
        where.append("lv.level IS NOT NULL AND lv.level > 0")
        if "min_level" in cfg:
            where.append("lv.level >= %s"); params.append(cfg["min_level"])
        if "max_level" in cfg:
            where.append("lv.level <= %s"); params.append(cfg["max_level"])
    if cfg.get("name_contains"):
        where.append(f"b.{qn(i['name'])} LIKE %s"); params.append("%" + cfg["name_contains"].replace(" ", "_") + "%")
    if cfg["rare_only"]:
        if not i.get("flags"):
            raise ValueError("This schema has no item flags column, so rare-only cannot be applied")
        where.append(f"(b.{qn(i['flags'])} & 32768) > 0")
    if "no_activity_days" in cfg:
        where.append("(st.last_activity IS NULL OR st.last_activity < %s)")
        params.append(now - cfg["no_activity_days"] * 86400)
    id_col = f"b.{qn(i['item_id'])}"
    if cfg["item_ids"]:
        # explicit items are added on top of whatever the filters match
        extra = f"{id_col} IN ({','.join(['%s'] * len(cfg['item_ids']))})"
        where = [f"(({' AND '.join(where)}) OR {extra})" if where else extra]
        params += cfg["item_ids"]
    where.insert(0, sellable_clause(i, qn, "b"))
    if cfg["exclude_item_ids"]:
        where.append(f"{id_col} NOT IN ({','.join(['%s'] * len(cfg['exclude_item_ids']))})")
        params += cfg["exclude_item_ids"]
    base_sell = "b.`BaseSell`"
    sql = (
        f"SELECT b.{qn(i['item_id'])}, b.{qn(i['name'])}, b.{qn(i['stack_size'])}, b.{qn(i['ah_category'])}, {base_sell}, "
        "lv.level, st.avg_sale, st.last_activity "
        "FROM `item_basic` b LEFT JOIN `item_armor` lv ON lv.`itemId`=b." + qn(i['item_id']) + " "
        f"LEFT JOIN (SELECT `{a['item_id']}` AS iid, AVG(CASE WHEN `{a['sold_at']}`>0 THEN `{a['sale_price']}` END) AS avg_sale, "
        f"MAX(GREATEST(`{a['listed_at']}`, `{a['sold_at']}`)) AS last_activity FROM `auction_house` GROUP BY `{a['item_id']}`) st "
        f"ON st.iid=b.{qn(i['item_id'])} WHERE {' AND '.join(where)} ORDER BY b.{qn(i['name'])} LIMIT %s"
    )
    cur = service.connection.cursor()
    try:
        cur.execute(sql, tuple(params + [cfg["max_items"] + 200]))
        rows = list(cur.fetchall() or [])
    finally:
        cur.close()

    entries, skipped = [], []
    for item_id, name, stack_size, category, base, level, avg_sale, _last in rows:
        base, stack_size = int(base or 0), max(1, int(stack_size or 1))
        src = cfg["price_source"]
        if src == "fixed":
            price = cfg["price"]
        elif src == "base_sell":
            price = round(base * cfg.get("price_mult", 1.0))
        else:
            price = round(float(avg_sale) * cfg.get("price_mult", 1.0)) if avg_sale else round(base * cfg.get("fallback_mult", 1.5))
        if price <= 0:
            skipped.append({"item_id": int(item_id), "item_name": str(name or ""), "reason": "no price (no sales and no base value)"})
            continue
        stack = cfg["stack_mode"] == "stack" and stack_size > 1
        if cfg["stack_mode"] == "stack" and stack_size <= 1:
            skipped.append({"item_id": int(item_id), "item_name": str(name or ""), "reason": "cannot be listed as a stack"})
            continue
        entries.append({"item_id": int(item_id), "item_name": str(name or ""), "target": cfg["target"], "price": int(price), "stack": stack,
                        "level": None if level is None else int(level), "category_id": int(category or 0)})
    matched = len(entries) + len(skipped)
    return {"entries": entries[:cfg["max_items"]], "skipped": skipped, "matched": matched,
            "truncated": len(entries) > cfg["max_items"], "matched_capped": len(rows) >= cfg["max_items"] + 200, "config": cfg}


def _r(name, description, **cfg):
    return {"name": name, "kind": "restock", "config": dict(description=description, **cfg)}


# Category ids come from categories.py (the client's AH menu). Level ranges use item_armor.level, which also
# holds weapon levels in this schema.
BUILTIN_RESTOCK_PRESETS = [
    _r("Gear: level 1-10", "Weapons and armor usable at level 10 or below.", category_ids=list(range(1, 27)), min_level=1, max_level=10, target=2, max_items=50),
    _r("Gear: level 11-20", "Weapons and armor for levels 11-20.", category_ids=list(range(1, 27)), min_level=11, max_level=20, target=2, max_items=50),
    _r("Gear: level 21-30", "Weapons and armor for levels 21-30.", category_ids=list(range(1, 27)), min_level=21, max_level=30, target=2, max_items=50),
    _r("Gear: level 31-50", "Weapons and armor for levels 31-50.", category_ids=list(range(1, 27)), min_level=31, max_level=50, target=2, max_items=50),
    _r("Pet supplies", "Pet food and other pet items.", category_ids=[48], target=5, max_items=50),
    _r("Food: meals", "Cooked meals of every type.", category_ids=[52, 53, 54, 55, 56, 57, 58], target=4, max_items=50),
    _r("Food: fish and ingredients", "Fish and cooking ingredients.", category_ids=[51, 59], target=5, max_items=50),
    _r("Crystals", "Elemental crystals; listed as stacks.", category_ids=[35], target=5, stack_mode="stack", max_items=50),
    _r("Crafting materials", "Smithing, goldsmithing, clothcraft, leathercraft, bonecraft, woodworking and alchemy supplies.", category_ids=[38, 39, 40, 41, 42, 43, 44, 63], target=4, max_items=50),
    _r("Medicines and ninja tools", "Potions, ethers, status cures and ninjutsu tools.", category_ids=[33, 49], target=5, max_items=50),
    _r("Scrolls", "White, black, summoning, ninjutsu, song and geomancy scrolls.", category_ids=[28, 29, 30, 31, 32, 45], target=2, max_items=50),
    _r("Rare items with no activity (60 days)", "Rare items that nobody has listed or bought in 60 days. Prices come from base value when no sale exists.",
       category_ids=list(range(1, 27)) + [33, 34, 46], rare_only=True, no_activity_days=60, target=1, max_items=50, price_source="market", fallback_mult=3.0),
    _r("Dead stock: anything idle 90 days", "Any item without a listing or sale in 90 days, across common categories.",
       category_ids=list(range(28, 35)) + list(range(38, 46)), no_activity_days=90, target=1, max_items=50),
]

BUILTIN_CLEANUP_PRESETS = [
    {"name": "Stale 30 days: return", "kind": "cleanup", "config": {"description": "Listings older than 30 days go back to the seller.", "min_age_days": 30, "default_action": "return_to_seller", "limit": 100}},
    {"name": "Stale 90 days: return", "kind": "cleanup", "config": {"description": "Listings older than 90 days go back to the seller.", "min_age_days": 90, "default_action": "return_to_seller", "limit": 100}},
    {"name": "Stale 180 days: admin buy", "kind": "cleanup", "config": {"description": "Very old listings are bought out and removed.", "min_age_days": 180, "default_action": "admin_buy", "limit": 100}},
    {"name": "Cheap clutter: under 200g, 14 days", "kind": "cleanup", "config": {"description": "Low-value listings that have sat for two weeks.", "max_price": 200, "min_age_days": 14, "default_action": "admin_buy", "limit": 100}},
    {"name": "Expensive and idle: over 1,000,000g, 30 days", "kind": "cleanup", "config": {"description": "High-priced listings that are not selling.", "min_price": 1000000, "min_age_days": 30, "default_action": "return_to_seller", "limit": 100}},
    {"name": "Below vendor value: admin buy", "kind": "cleanup", "since": 2, "config": {"description": "Listings priced under what an NPC pays for the item. Buys them out so nobody can flip them to a vendor.", "max_vendor_ratio": 1.0, "default_action": "admin_buy", "limit": 100}},
    {"name": "Below vendor value: return", "kind": "cleanup", "since": 2, "config": {"description": "Listings priced under NPC buy-back value go back to the seller to be relisted.", "max_vendor_ratio": 1.0, "default_action": "return_to_seller", "limit": 100}},
]
