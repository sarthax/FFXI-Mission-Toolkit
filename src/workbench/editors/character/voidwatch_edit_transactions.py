"""Granular Voidwatch editor for Character Editor: decoded state + selective add/remove.

Voidwatch progress is split between key items (chars.keyitems) and charvars read by the officer/refiner Lua:
  VWO_TIERS   paths 0-2: bit = path*4 + tier-1        VWO_TIERS2  paths 3+: bit = (path-3)*8 + tier-1
  VWO_STOCK / VWO_STOCK_TS   voidstone stock + clock   VWA<0..39> atmacite level   VWA_INF1..3 infused slot (idx+1)
This module decodes that into per-item rows and applies selective edits in one guarded transaction.
Edits: {"op":"ki","key_item_id":n,"owned":bool} | {"op":"tier","path":p,"tier":t,"done":bool} | {"op":"var","name":s,"value":n}
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from .audit import attach_committed_audit
from .packed_transactions import _chars_blob, _family, _key_item_edit
from .schema import discover_character_schema
from .session_state import detect_online_state
from .voidwatch_reset_transactions import VOIDWATCH_VARS, VoidwatchResetIssue as Issue, _VERIFIED_FAMILIES, _var_rows

_PATH_ORDER = ["CRIMSON", "INDIGO", "JADE", "WHITE", "ASHEN", "HYACINTH", "AMBER"]  # mirrors VWO.PATHS indices 0..6
_KI_RE = re.compile(r"^\s*((?:[A-Z]+_STRATUM_ABYSSITE(?:_[IV]+)?)|VOIDSTONE[1-6]|ATMACITE_OF_[A-Z_]+)\s*=\s*(\d+)\s*;?", re.M)
_ATMA_KI0, _ATMA_COUNT = 1806, 40


def _ki_table(server_root: Path | str | None) -> dict[str, int]:
    if not server_root:
        return {}
    try:
        text = (Path(server_root) / "scripts" / "globals" / "keyitems.lua").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return {m.group(1): int(m.group(2)) for m in _KI_RE.finditer(text)}


def _layout(table: dict[str, int]) -> dict[str, Any]:
    paths = []
    for p, prefix in enumerate(_PATH_ORDER):
        names = sorted((n for n in table if n.startswith(prefix + "_STRATUM_ABYSSITE")), key=lambda n: table[n])
        paths.append({"index": p, "name": prefix.title(), "tiers": [{"tier": t + 1, "name": n, "id": table[n]} for t, n in enumerate(names)]})
    stones = [{"name": f"VOIDSTONE{i}", "id": table[f"VOIDSTONE{i}"]} for i in range(1, 7) if f"VOIDSTONE{i}" in table]
    by_id = {v: k for k, v in table.items() if k.startswith("ATMACITE_OF_")}
    atma = [{"idx": i, "id": _ATMA_KI0 + i, "name": by_id.get(_ATMA_KI0 + i, f"ATMACITE_{i}")} for i in range(_ATMA_COUNT)]
    return {"paths": paths, "voidstones": stones, "atmacites": atma}


def _tier_slot(path: int, tier: int) -> tuple[str, int]:
    return ("VWO_TIERS", path * 4 + tier - 1) if path <= 2 else ("VWO_TIERS2", (path - 3) * 8 + tier - 1)


def _read_ki(blob: bytes, family: str, ki: int) -> dict[str, bool]:
    # _key_item_edit reports the pre-edit state, so a no-op-style probe edit on a throwaway copy reads it.
    _, b1, _ = _key_item_edit(blob, family, {"key_item_id": ki, "owned": True, "seen": True})
    return {"owned": bool(b1["owned"]), "seen": bool(b1["seen"])}


def voidwatch_state(connection, *, char_id: int, server_root, adapter_family: str = "unknown") -> dict[str, Any]:
    family = _family(adapter_family)
    table = _ki_table(server_root)
    layout = _layout(table)
    schema = discover_character_schema(connection)
    blob = _chars_blob(connection, schema, int(char_id), "keyitems")
    rows = _vars_all(connection, schema, int(char_id)) or {}
    state = detect_online_state(connection, schema, int(char_id))

    def ki(i: int) -> dict[str, bool]:
        return _read_ki(blob, family, i) if blob is not None and family in _VERIFIED_FAMILIES else {"owned": False, "seen": False}

    v = lambda n: int(rows.get(n, 0) or 0)  # noqa: E731
    for path in layout["paths"]:
        for t in path["tiers"]:
            t.update(ki(t["id"]))
            var, bit = _tier_slot(path["index"], t["tier"])
            t["done"] = (v(var) >> bit) & 1 == 1
    for s in layout["voidstones"]:
        s.update(ki(s["id"]))
    for a in layout["atmacites"]:
        a.update(ki(a["id"]))
        a["level"] = v(f"VWA{a['idx']}")
        a["infused_slot"] = next((s for s in (1, 2, 3) if v(f"VWA_INF{s}") == a["idx"] + 1), 0)
    layout.update({"stock": v("VWO_STOCK"), "stock_ts": v("VWO_STOCK_TS"), "tiers_raw": v("VWO_TIERS"), "tiers2_raw": v("VWO_TIERS2"),
                   "online": state.online, "char_id": int(char_id), "ready": bool(table) and blob is not None})
    return layout


def _vars_all(connection, schema, char_id: int) -> dict[str, int] | None:
    rows = _var_rows(connection, schema, char_id)
    return None if rows is None else {r["varname"]: int(r["value"] or 0) for r in rows}


def build_voidwatch_edit_plan(connection, *, char_id: int, server_root, adapter_family: str = "unknown", edits: list[dict[str, Any]]) -> dict[str, Any]:
    char_id = int(char_id)
    family = _family(adapter_family)
    issues: list[Issue] = []
    schema = discover_character_schema(connection)
    table = _ki_table(server_root)
    if family not in _VERIFIED_FAMILIES:
        issues.append(Issue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for writes."))
    if not table:
        issues.append(Issue("keyitems_unreadable", "Could not read scripts/globals/keyitems.lua from the server root."))
    if (schema.packed_fields or {}).get("key_items") != "chars.keyitems":
        issues.append(Issue("packed_location_unverified", "chars.keyitems was not recognised."))
    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(Issue("character_online", "Character is online; edits are locked until offline."))
    elif state.online is None:
        issues.append(Issue("online_state_unknown", "Character online state could not be verified."))
    before_vars = _vars_all(connection, schema, char_id)
    if before_vars is None:
        issues.append(Issue("schema_unverified", "char_vars(charid, varname, value) is not available."))
        before_vars = {}
    before_blob = _chars_blob(connection, schema, char_id, "keyitems")
    if before_blob is None:
        issues.append(Issue("blob_missing", "Character has no chars.keyitems BLOB."))
    layout = _layout(table)
    valid_ki = {t["id"] for p in layout["paths"] for t in p["tiers"]} | {s["id"] for s in layout["voidstones"]} | {a["id"] for a in layout["atmacites"]}
    after_vars, after_blob, changes = dict(before_vars), before_blob, []
    if not edits:
        issues.append(Issue("no_edits", "No edits were requested."))
    for e in edits or []:
        try:
            op = e.get("op")
            if op == "ki":
                ki = int(e["key_item_id"])
                if ki not in valid_ki:
                    raise ValueError(f"key item {ki} is not a Voidwatch key item")
                if after_blob is not None and family in _VERIFIED_FAMILIES:
                    owned = bool(e["owned"])
                    after_blob, before, after = _key_item_edit(after_blob, family, {"key_item_id": ki, "owned": owned, "seen": owned})
                    changes.append({"op": "ki", "key_item_id": ki, "before": before, "after": after})
            elif op == "tier":
                path, tier = int(e["path"]), int(e["tier"])
                if not any(p["index"] == path and any(t["tier"] == tier for t in p["tiers"]) for p in layout["paths"]):
                    raise ValueError(f"path {path} tier {tier} does not exist")
                var, bit = _tier_slot(path, tier)
                cur = after_vars.get(var, 0)
                new = (cur | (1 << bit)) if e["done"] else (cur & ~(1 << bit))
                after_vars[var] = new
                changes.append({"op": "tier", "var": var, "bit": bit, "before": cur, "after": new})
            elif op == "var":
                name, value = str(e["name"]), int(e["value"])
                if name not in VOIDWATCH_VARS or name in ("VWO_TIERS", "VWO_TIERS2"):
                    raise ValueError(f"variable {name} is not editable here")
                if not 0 <= value <= 2147483647:
                    raise ValueError(f"{name} must be 0..2147483647")
                if name.startswith("VWA_INF") and value > _ATMA_COUNT:
                    raise ValueError(f"{name} must be 0..{_ATMA_COUNT}")
                if re.fullmatch(r"VWA\d+", name) and value > 15:
                    raise ValueError(f"{name} atmacite level must be 0..15")
                changes.append({"op": "var", "var": name, "before": after_vars.get(name, 0), "after": value})
                after_vars[name] = value
            else:
                raise ValueError(f"unknown op {op!r}")
        except (KeyError, ValueError, TypeError) as exc:
            issues.append(Issue("invalid_edit", f"{e}: {exc}"))
    upserts = {k: v for k, v in after_vars.items() if v != 0 and before_vars.get(k, 0) != v}
    deletes = [k for k, v in after_vars.items() if v == 0 and k in before_vars]
    if not upserts and not deletes and after_blob == before_blob and not any(i.blocking for i in issues):
        issues.append(Issue("no_change", "Edits would not change anything."))
    plan = {"char_id": char_id, "adapter_family": family, "online": state.online, "changes": changes, "upserts": upserts, "deletes": deletes,
            "issues": [asdict(i) for i in issues], "before_vars": before_vars,
            "before_sha256": sha256(before_blob).hexdigest() if before_blob is not None else None}
    plan["ready"] = before_blob is not None and not any(i["blocking"] for i in plan["issues"])
    plan["_before_blob"], plan["_after_blob"] = before_blob, after_blob
    return plan


def apply_voidwatch_edit(connection, plan: dict[str, Any], *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to edit Voidwatch progress")
    if not plan["ready"]:
        raise RuntimeError("Voidwatch edit plan is not write-ready")
    cid = plan["char_id"]
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cur = connection.cursor(); cur.execute("START TRANSACTION"); cur.close()
        schema = discover_character_schema(connection)
        if detect_online_state(connection, schema, cid).online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        if _chars_blob(connection, schema, cid, "keyitems") != plan["_before_blob"]:
            raise RuntimeError("Key items changed since preview; preview again")
        if _vars_all(connection, schema, cid) != plan["before_vars"]:
            raise RuntimeError("Voidwatch variables changed since preview; preview again")
        chars, cv = schema.table("chars"), schema.table("char_vars")
        cursor = connection.cursor()
        try:
            if plan["_after_blob"] != plan["_before_blob"]:
                cursor.execute(f"UPDATE `chars` SET `keyitems` = %s WHERE `{chars.character_key}` = %s LIMIT 1", (plan["_after_blob"], cid))
            for name, value in plan["upserts"].items():
                if name in plan["before_vars"]:
                    cursor.execute(f"UPDATE `char_vars` SET `value` = %s WHERE `{cv.character_key}` = %s AND `varname` = %s", (value, cid, name))
                else:
                    cursor.execute(f"INSERT INTO `char_vars` (`{cv.character_key}`, `varname`, `value`) VALUES (%s, %s, %s)", (cid, name, value))
            for name in plan["deletes"]:
                cursor.execute(f"DELETE FROM `char_vars` WHERE `{cv.character_key}` = %s AND `varname` = %s", (cid, name))
        finally:
            cursor.close()
        connection.commit()
        result = {"status": "committed", "char_id": cid, "changes": len(plan["changes"]), "vars_written": len(plan["upserts"]), "vars_deleted": len(plan["deletes"])}
        return attach_committed_audit(
            result, operation="voidwatch.edit", char_id=cid, adapter_family=plan["adapter_family"],
            target={"tables": ["chars.keyitems", "char_vars"]},
            before={"blob": plan["_before_blob"], "vars": plan["before_vars"]}, after={"blob": plan["_after_blob"], "changes": plan["changes"]},
            undo_supported=False,
        )
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
