"""External reference catalogue (items_external) matching for the Item Browser.

This is the feature of the retired /items page: match each server item to the external catalogue by
normalized name (lowercase letters and digits only, the same norm_name build_database.py stores) and
report whether the ids agree.  status: matched (same id), drift (name matches, id differs),
ours_only (no catalogue entry), external_only (catalogue entry the server lacks).
"""
import re
import time

_cache = {"t": 0, "idx": None}


def norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def _index(con):
    """{norm_name: [ext ids]}, {ext id: name}; cached briefly because it is ~29k rows."""
    if _cache["idx"] is not None and time.time() - _cache["t"] < 300:
        return _cache["idx"]
    by_norm, names = {}, {}
    for r in con.execute("select id, name, norm_name from items_external"):
        by_norm.setdefault(r["norm_name"], []).append(r["id"]); names[r["id"]] = r["name"]
    _cache["idx"], _cache["t"] = (by_norm, names), time.time()
    return _cache["idx"]


def status_of(itemid, name, con):
    by_norm, _ = _index(con)
    ids = by_norm.get(norm(name), [])
    if not ids:
        return "ours_only", []
    return ("matched" if itemid in ids else "drift"), ids


def annotate(items, con):
    """Add ref_status / ref_ids to each browse row (in place)."""
    for it in items:
        it["ref_status"], it["ref_ids"] = status_of(it["itemid"], it["name"], con)
    return items


def external_only(con, live_names, q="", limit=60, offset=0):
    """Catalogue entries whose normalized name matches no server item."""
    by_norm, names = _index(con)
    live = {norm(n) for n in live_names}
    qn = norm(q)
    rows = sorted((i, n) for i, n in names.items() if norm(n) not in live and (not qn or qn in norm(n) or qn == str(i)))
    page = rows[offset:offset + limit]
    return len(rows), [{"itemid": None, "ext_id": i, "name": n, "type_name": "reference only", "ref_status": "external_only", "ref_ids": [i],
                        "jobs": [], "slots": [], "ah_name": "", "level": None, "skill_name": "", "dmg": None, "delay": None,
                        "rare": False, "ex": False} for i, n in page]


def counts(con, live_rows):
    """Summary counts for the status filter: live_rows = [(itemid, name)]."""
    c = {"matched": 0, "drift": 0, "ours_only": 0}
    for iid, n in live_rows:
        c[status_of(iid, n, con)[0]] += 1
    by_norm, names = _index(con)
    live = {norm(n) for _, n in live_rows}
    c["external_only"] = sum(1 for n in names.values() if norm(n) not in live)
    return c


def reference(con, itemid, name, external_detail_fn, topaz=False):
    """Detail for one item: catalogue matches (with description/type/targets) and the Topaz match."""
    status, ids = status_of(itemid, name, con)
    _, names = _index(con)
    out = {"status": status, "matches": []}
    for i in ids[:6]:
        d = external_detail_fn(i) or {}
        desc = (d.get("description") or {}).get("english") if isinstance(d.get("description"), dict) else None
        out["matches"].append({"id": i, "name": names.get(i), "type": d.get("type"), "stack_size": d.get("stack_size"),
                               "flags": d.get("flags"), "targets": d.get("targets"), "description": desc})
    if topaz:
        row = con.execute("select itemid, name from topaz_item_basic where norm_name=?", (norm(name),)).fetchone()
        out["topaz"] = {"itemid": row["itemid"], "name": row["name"], "drift": row["itemid"] != itemid} if row else None
    return out
