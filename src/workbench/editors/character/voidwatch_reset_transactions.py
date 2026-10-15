"""Guarded one-shot Voidwatch progress reset for Character Editor (testing aid).

Clears, in a single transaction: every Stratum Abyssite + Voidstone key item (owned and seen bits in
chars.keyitems) and the Voidwatch officer/refiner charvars (VWO_TIERS, VWO_TIERS2, VWO_STOCK, VWO_STOCK_TS,
VWA0..VWA39 atmacite levels, VWA_INF1..3 infusions). Deleting the key items alone does not reset the refiner:
progress lives in those charvars. Mirrors the in-game GM command !resetvoidwatch.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from .audit import attach_committed_audit
from .packed_transactions import _chars_blob, _family, _key_item_edit
from .schema import discover_character_schema
from .session_state import detect_online_state

_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}
_KI_RE = re.compile(r"^\s*((?:[A-Z]+_STRATUM_ABYSSITE(?:_[IV]+)?)|VOIDSTONE[1-6])\s*=\s*(\d+)\s*;?", re.M)
_FIXED_VARS = ["VWO_TIERS", "VWO_TIERS2", "VWO_STOCK", "VWO_STOCK_TS", "VWA_INF1", "VWA_INF2", "VWA_INF3"]
VOIDWATCH_VARS = _FIXED_VARS + [f"VWA{i}" for i in range(40)]


@dataclass(frozen=True)
class VoidwatchResetIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class VoidwatchResetPlan:
    char_id: int
    key_items: list[dict[str, Any]]  # {name, id, owned, seen} currently set
    vars: list[dict[str, Any]]       # char_vars rows that will be deleted
    before_blob: bytes | None
    after_blob: bytes | None
    online: bool | None
    adapter_family: str
    issues: list[VoidwatchResetIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        has_work = bool(self.key_items or self.vars)
        return has_work and self.before_blob is not None and not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {"char_id": self.char_id, "key_items": self.key_items, "vars": self.vars, "online": self.online,
                "adapter_family": self.adapter_family, "issues": [asdict(i) for i in self.issues], "ready": self.ready,
                "before_sha256": sha256(self.before_blob).hexdigest() if self.before_blob is not None else None}


def voidwatch_key_item_ids(server_root: Path | str | None) -> dict[str, int]:
    if not server_root:
        return {}
    path = Path(server_root) / "scripts" / "globals" / "keyitems.lua"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return {m.group(1): int(m.group(2)) for m in _KI_RE.finditer(text)}


def _var_rows(connection, schema, char_id: int) -> list[dict[str, Any]] | None:
    table = schema.table("char_vars")
    if table is None or table.character_key is None or "varname" not in table.column_names or "value" not in table.column_names:
        return None
    marks = ",".join(["%s"] * len(VOIDWATCH_VARS))
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT `varname`, `value` FROM `char_vars` WHERE `{table.character_key}` = %s AND `varname` IN ({marks}) ORDER BY `varname`",
            (int(char_id), *VOIDWATCH_VARS),
        )
        return [{"varname": str(r[0]), "value": r[1]} for r in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def build_voidwatch_reset_plan(connection, *, char_id: int, server_root: Path | str | None, adapter_family: str = "unknown") -> VoidwatchResetPlan:
    char_id = int(char_id)
    family = _family(adapter_family)
    issues: list[VoidwatchResetIssue] = []
    schema = discover_character_schema(connection)
    if family not in _VERIFIED_FAMILIES:
        issues.append(VoidwatchResetIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for writes."))
    ids = voidwatch_key_item_ids(server_root)
    if not ids:
        issues.append(VoidwatchResetIssue("keyitems_unreadable", "Could not read scripts/globals/keyitems.lua from the server root."))
    if (schema.packed_fields or {}).get("key_items") != "chars.keyitems":
        issues.append(VoidwatchResetIssue("packed_location_unverified", "chars.keyitems was not recognised."))
    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(VoidwatchResetIssue("character_online", "Character is online; use !resetvoidwatch in-game instead."))
    elif state.online is None:
        issues.append(VoidwatchResetIssue("online_state_unknown", "Character online state could not be verified."))
    vars_rows = _var_rows(connection, schema, char_id)
    if vars_rows is None:
        issues.append(VoidwatchResetIssue("schema_unverified", "char_vars(charid, varname, value) is not available."))
        vars_rows = []
    before_blob = _chars_blob(connection, schema, char_id, "keyitems")
    after_blob = before_blob
    held: list[dict[str, Any]] = []
    if before_blob is None:
        issues.append(VoidwatchResetIssue("blob_missing", "Character has no chars.keyitems BLOB."))
    elif family in _VERIFIED_FAMILIES:
        try:
            for name, ki in sorted(ids.items(), key=lambda kv: kv[1]):
                new_blob, before, _ = _key_item_edit(after_blob, family, {"key_item_id": ki, "owned": False, "seen": False})
                if before["owned"] or before["seen"]:
                    held.append({"name": name, "id": ki, "owned": before["owned"], "seen": before["seen"]})
                    after_blob = new_blob
        except Exception as exc:  # codec / range errors
            issues.append(VoidwatchResetIssue("invalid_keyitem_edit", str(exc)))
    if not held and not vars_rows and not any(i.blocking for i in issues):
        issues.append(VoidwatchResetIssue("no_change", "No Voidwatch key items or progress variables are set."))
    return VoidwatchResetPlan(char_id, held, vars_rows, before_blob, after_blob, state.online, family, issues)


def apply_voidwatch_reset(connection, plan: VoidwatchResetPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to reset Voidwatch progress")
    if not plan.ready:
        raise RuntimeError("Voidwatch reset plan is not write-ready")
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cur = connection.cursor()
            cur.execute("START TRANSACTION")
            cur.close()
        schema = discover_character_schema(connection)
        if detect_online_state(connection, schema, plan.char_id).online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        if _chars_blob(connection, schema, plan.char_id, "keyitems") != plan.before_blob:
            raise RuntimeError("Key items changed since preview; preview again")
        if _var_rows(connection, schema, plan.char_id) != plan.vars:
            raise RuntimeError("Voidwatch variables changed since preview; preview again")
        chars, cvars = schema.table("chars"), schema.table("char_vars")
        cursor = connection.cursor()
        try:
            if plan.after_blob != plan.before_blob:
                cursor.execute(f"UPDATE `chars` SET `keyitems` = %s WHERE `{chars.character_key}` = %s LIMIT 1", (plan.after_blob, plan.char_id))
            if plan.vars:
                marks = ",".join(["%s"] * len(VOIDWATCH_VARS))
                cursor.execute(f"DELETE FROM `char_vars` WHERE `{cvars.character_key}` = %s AND `varname` IN ({marks})", (plan.char_id, *VOIDWATCH_VARS))
        finally:
            cursor.close()
        connection.commit()
        result = {"status": "committed", "char_id": plan.char_id, "key_items_cleared": len(plan.key_items), "vars_deleted": len(plan.vars)}
        return attach_committed_audit(
            result,
            operation="voidwatch.reset",
            char_id=plan.char_id,
            adapter_family=plan.adapter_family,
            target={"tables": ["chars.keyitems", "char_vars"]},
            before={"blob": plan.before_blob, "key_items": plan.key_items, "vars": plan.vars},
            after={"blob": plan.after_blob},
            undo_supported=False,
        )
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
