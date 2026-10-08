"""Gated live edits for Voidwatch NM rows (mob_groups / mob_pools / mob_spawn_points).

Whitelisted columns only, typed and range-checked, parameterized SQL, before/after captured and logged. The caller must pass the
same Test-profile write gate used by the other server-admin editors. Drops live in NM Lua, not the database, so they are not here.
"""
from __future__ import annotations

import datetime
import json

from workbench.runtime.paths import REPO_ROOT
from workbench.server_admin.synth import recipes as R

LOG = REPO_ROOT / "data" / "voidwatch" / "edit_log.jsonl"

# table -> (key column, {column: (min, max)})
SPEC = {
    "mob_groups": ("groupid", {"HP": (0, 99999999), "MP": (0, 9999999), "minLevel": (1, 255), "maxLevel": (1, 255), "respawntime": (0, 86400 * 30)}),
    "mob_pools": ("poolid", {"mJob": (0, 22), "sJob": (0, 22), "cmbDelay": (0, 9999), "cmbDmgMult": (0, 9999), "aggro": (0, 1), "true_detection": (0, 1),
                             "links": (0, 1), "skill_list_id": (0, 65535), "spellList": (0, 65535)}),
    "mob_spawn_points": ("mobid", {"pos_x": (-9999, 9999), "pos_y": (-9999, 9999), "pos_z": (-9999, 9999), "pos_rot": (0, 255)}),
}


class EditError(ValueError):
    pass


def plan(conn, table: str, key, changes: dict) -> dict:
    if table not in SPEC:
        raise EditError(f"Table {table!r} is not editable here")
    kcol, cols = SPEC[table]
    if not changes:
        raise EditError("No changes given")
    try:
        key = int(key)
    except (TypeError, ValueError):
        raise EditError("Row key must be an integer")
    clean = {}
    for c, v in changes.items():
        if c not in cols:
            raise EditError(f"Column {c!r} is not editable on {table}")
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise EditError(f"{c}: {v!r} is not a number")
        lo, hi = cols[c]
        if not lo <= f <= hi:
            raise EditError(f"{c}: {v} outside {lo}..{hi}")
        clean[c] = int(f) if table != "mob_spawn_points" or c == "pos_rot" else f
    rows = R._rows(conn, "SELECT " + ",".join(f"`{c}`" for c in clean) + f" FROM `{table}` WHERE `{kcol}`=%s", (key,))
    if not rows:
        raise EditError(f"{table}.{kcol}={key} not found")
    before = dict(zip(clean, rows[0]))
    warnings = []
    if table == "mob_groups":
        cur = R._rows(conn, "SELECT minLevel,maxLevel FROM mob_groups WHERE groupid=%s", (key,))[0]
        lo = clean.get("minLevel", cur[0]); hi = clean.get("maxLevel", cur[1])
        if lo > hi:
            raise EditError("minLevel is above maxLevel")
    if table == "mob_pools":
        for col, tbl, idcol in (("skill_list_id", "mob_skill_lists", "skill_list_id"), ("spellList", "mob_spell_lists", "spell_list_id")):
            if col in clean and clean[col]:
                if not R._rows(conn, f"SELECT 1 FROM {tbl} WHERE {idcol}=%s LIMIT 1", (clean[col],)):
                    raise EditError(f"{col}={clean[col]} does not exist in {tbl}")
                n = R._rows(conn, f"SELECT COUNT(*) FROM mob_pools WHERE {col}=%s AND poolid<>%s", (clean[col], key))[0][0]
                if n:
                    warnings.append(f"{col} {clean[col]} is shared by {n} other pool(s); they are unaffected (only this pool is repointed).")
    if table == "mob_spawn_points":
        cur = R._rows(conn, "SELECT pos_x,pos_y,pos_z FROM mob_spawn_points WHERE mobid=%s", (key,))[0]
        pos = [clean.get("pos_x", cur[0]), clean.get("pos_y", cur[1]), clean.get("pos_z", cur[2])]
        if not any(pos):
            raise EditError("Position (0,0,0) is refused: the instance loader silently skips zero-position spawns")
        warnings.append("Run !checknav x y z against the live navmesh before trusting a new coordinate (Y axis is inverted).")
    sql = f"UPDATE `{table}` SET " + ", ".join(f"`{c}`={v}" for c, v in clean.items()) + f" WHERE `{kcol}`={key};"
    return {"table": table, "key_col": kcol, "key": key, "changes": clean, "before": before, "sql": sql, "warnings": warnings}


def apply(conn, p: dict, who: str = "") -> int:
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE `{p['table']}` SET " + ",".join(f"`{c}`=%s" for c in p["changes"]) + f" WHERE `{p['key_col']}`=%s", (*p["changes"].values(), p["key"]))
        n = cur.rowcount
        conn.commit()
    finally:
        cur.close()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), "by": who, "table": p["table"], "key": p["key"], "before": p["before"],
                             "after": p["changes"], "sql": p["sql"], "rows": n}, default=str) + "\n")
    return int(n)
