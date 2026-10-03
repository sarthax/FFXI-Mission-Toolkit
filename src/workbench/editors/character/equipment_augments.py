"""Equipped-item view and per-character augment editing (core server contract only).

Core DSP/Topaz/LSB store a character's own item modifiers in ``char_inventory.extra`` (24 bytes).
For armor/weapons the four augment slots are little-endian u16 words at byte ``2 + 2 * slot``:
the low 11 bits are an ``augments.augmentId`` and the top 5 bits are an additive value (0-31)
(``CItemArmor::setAugment``). The ``augments`` table maps an id to the modifier it grants. Nothing
else in ``extra`` is touched, and nothing server-branch specific (path/trial/reforge data) is decoded.
This is separate from the Items editor, which changes the item definition for every copy of the item.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .adapters.inventory import inspect_inventory_contract
from .audit import attach_committed_audit
from .inventory_slots import CONTAINERS
from .inventory_management import _fingerprint, _inventory_row, _item_record
from .schema import discover_character_schema
from .session_state import detect_online_state

EQUIP_SLOTS = ("Main", "Sub", "Ranged", "Ammo", "Head", "Body", "Hands", "Legs", "Feet", "Neck", "Waist", "Ear 1", "Ear 2", "Ring 1", "Ring 2", "Back")
AUGMENT_SLOTS = 4
EXTRA_BYTES = 24
_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}


def _extra_bytes(value: Any) -> bytes:
    raw = bytes(value) if value is not None else b""
    return raw.ljust(EXTRA_BYTES, b"\x00")[:EXTRA_BYTES]


def decode_augments(extra: Any) -> list[dict[str, int]]:
    raw = _extra_bytes(extra)
    out = []
    for slot in range(AUGMENT_SLOTS):
        word = raw[2 + 2 * slot] | (raw[3 + 2 * slot] << 8)
        out.append({"slot": slot, "id": word & 0x7FF, "value": word >> 11})
    return out


def encode_augments(extra: Any, augments: list[tuple[int, int]]) -> bytes:
    raw = bytearray(_extra_bytes(extra))
    for slot, (aug_id, value) in enumerate(augments[:AUGMENT_SLOTS]):
        word = (int(aug_id) & 0x7FF) | ((int(value) & 0x1F) << 11)
        raw[2 + 2 * slot], raw[3 + 2 * slot] = word & 0xFF, word >> 8
    if any(aug_id for aug_id, _ in augments):
        raw[0] |= 0x02   # same flag bytes the core sets when it adds an augment
        raw[1] |= 0x03
    return bytes(raw)


def _mod_names(root: Path | None) -> dict[int, str]:
    path = root / "src" / "map" / "modifier.h" if root else None
    names: dict[int, str] = {}
    if path and path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*,", text, re.M):
            names.setdefault(int(m.group(2)), m.group(1))
    return names


def augment_catalog(root: Path | str | None) -> dict[str, Any]:
    """augmentId -> effects, from the server checkout's ``augments.sql``."""
    root = Path(root) if root else None
    path = root / "sql" / "augments.sql" if root else None
    mods = _mod_names(root)
    entries: dict[int, dict[str, Any]] = {}
    if path and path.is_file():
        pat = re.compile(r"VALUES\s*\(([^)]*)\)", re.I)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "INSERT" not in line.upper():
                continue
            m = pat.search(line)
            if not m:
                continue
            try:
                aug_id, mult, mod_id, value, is_pet, _pet_type = [int(x) for x in m.group(1).split(",")]
            except ValueError:
                continue
            e = entries.setdefault(aug_id, {"id": aug_id, "effects": []})
            e["effects"].append({"mod": mod_id, "mod_name": mods.get(mod_id, f"Mod {mod_id}"), "value": value,
                                 "multiplier": mult, "pet": bool(is_pet)})
    rows = [e for _, e in sorted(entries.items())]
    return {"available": bool(rows), "rows": rows}


def equipment_state(connection, char_id: int) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `equipslotid`,`containerid`,`slotid` FROM `char_equip` WHERE `charid` = %s ORDER BY `equipslotid`", (int(char_id),))
        refs = cursor.fetchall() or []
    finally:
        cursor.close()
    rows = []
    for equip_slot, location, slot in refs:
        equip_slot, location, slot = int(equip_slot), int(location), int(slot)
        row = _inventory_row(connection, char_id, location, slot)
        item = _item_record(connection, int(row["itemId"])) if row else None
        extra = _extra_bytes(row.get("extra")) if row else b""
        rows.append({
            "equip_slot": equip_slot,
            "slot_name": EQUIP_SLOTS[equip_slot] if equip_slot < len(EQUIP_SLOTS) else f"Slot {equip_slot}",
            "location": location, "inventory_slot": slot,
            "item_id": int(row["itemId"]) if row else None,
            "name": item["name"] if item else None,
            "item_known": item is not None,
            "extra_hex": extra.hex() if row else None,
            "augments": decode_augments(extra) if row else [],
            "fingerprint": _fingerprint(row) if row else None,
            "missing_row": row is None,
        })
    return {"char_id": int(char_id), "slots": rows}


def inventory_augmentables(connection, char_id: int) -> dict[str, Any]:
    """Armor/weapon rows in every container (Temporary Items excluded), with decoded augments."""
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `location`,`slot`,`itemId`,`extra` FROM `char_inventory` WHERE `charid` = %s AND `location` <> 3 ORDER BY `location`,`slot`", (int(char_id),))
        rows = cursor.fetchall() or []
    finally:
        cursor.close()
    ids = sorted({int(r[2]) for r in rows if int(r[2])})
    gear: set[int] = set()
    for table in ("item_armor", "item_equipment", "item_weapon"):
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            cursor = connection.cursor()
            try:
                cursor.execute(f"SELECT `itemId` FROM `{table}` WHERE `itemId` IN ({','.join(['%s'] * len(chunk))})", tuple(chunk))
                gear.update(int(r[0]) for r in cursor.fetchall() or [])
            except Exception:
                pass
            finally:
                cursor.close()
    names: dict[int, Any] = {}
    out = []
    for location, slot, item_id, extra in rows:
        item_id = int(item_id)
        if item_id not in gear:
            continue
        if item_id not in names:
            rec = _item_record(connection, item_id)
            names[item_id] = rec["name"] if rec else None
        raw = _extra_bytes(extra)
        out.append({"location": int(location), "container": CONTAINERS.get(int(location), f"Container {location}"),
                    "inventory_slot": int(slot), "item_id": item_id, "name": names[item_id],
                    "extra_hex": raw.hex(), "augments": decode_augments(raw)})
    return {"char_id": int(char_id), "items": out}


@dataclass(frozen=True)
class AugmentIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class AugmentPlan:
    char_id: int
    location: int
    slot: int
    augments: list[tuple[int, int]]
    source: dict[str, Any] | None
    source_fingerprint: str | None
    item: dict[str, Any] | None
    extra_before: str | None
    extra_after: str | None
    online: bool | None
    adapter_family: str
    issues: list[AugmentIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.source is not None and self.source_fingerprint is not None and not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id, "location": self.location, "slot": self.slot,
            "augments": [{"id": a, "value": v} for a, v in self.augments],
            "item": self.item, "source_fingerprint": self.source_fingerprint,
            "extra_before": self.extra_before, "extra_after": self.extra_after,
            "online": self.online, "adapter_family": self.adapter_family,
            "issues": [asdict(i) for i in self.issues], "ready": self.ready,
        }


def _is_armor_or_weapon(connection, item_id: int) -> bool:
    for table in ("item_armor", "item_equipment", "item_weapon"):
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT 1 FROM `{table}` WHERE `itemId` = %s LIMIT 1", (int(item_id),))
            if cursor.fetchone():
                return True
        except Exception:
            pass
        finally:
            cursor.close()
    return False


def _augment_known(connection, aug_id: int) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM `augments` WHERE `augmentId` = %s LIMIT 1", (int(aug_id),))
        return cursor.fetchone() is not None
    except Exception:
        return False
    finally:
        cursor.close()


def build_augment_plan(connection, *, char_id: int, location: int, slot: int, augments: list[dict[str, Any]],
                       adapter_family: str = "unknown") -> AugmentPlan:
    char_id, location, slot = int(char_id), int(location), int(slot)
    family = str(adapter_family or "unknown").strip().lower()
    issues: list[AugmentIssue] = []
    pairs: list[tuple[int, int]] = []
    if len(augments) != AUGMENT_SLOTS:
        issues.append(AugmentIssue("augment_count", f"Exactly {AUGMENT_SLOTS} augment slots are required (use id 0 for an empty slot)."))
    for a in augments[:AUGMENT_SLOTS]:
        aug_id, value = int(a.get("id") or 0), int(a.get("value") or 0)
        if not 0 <= aug_id <= 0x7FF:
            issues.append(AugmentIssue("augment_id_range", f"Augment id {aug_id} is outside 0-2047."))
        if not 0 <= value <= 0x1F:
            issues.append(AugmentIssue("augment_value_range", f"Augment value {value} is outside 0-31."))
        pairs.append((aug_id, value))
    if family not in _VERIFIED_FAMILIES:
        issues.append(AugmentIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for writes."))

    schema = discover_character_schema(connection)
    contract = inspect_inventory_contract(schema, family)
    if not contract.basic_insert_verified:
        issues.append(AugmentIssue("inventory_schema_drift", "Connected char_inventory schema does not match the verified core contract."))
    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(AugmentIssue("character_online", "Character is online; direct item writes are blocked."))
    elif state.online is None:
        issues.append(AugmentIssue("online_state_unknown", "Character online state could not be verified."))

    source = _inventory_row(connection, char_id, location, slot) if contract.basic_insert_verified else None
    item = None
    extra_before = extra_after = None
    if source is None:
        issues.append(AugmentIssue("source_missing", "No inventory row exists at that location/slot."))
    else:
        item = _item_record(connection, int(source.get("itemId") or 0))
        if item is None:
            issues.append(AugmentIssue("item_unknown", f"Item ID {source.get('itemId')} is not in the connected item catalog."))
        if not _is_armor_or_weapon(connection, int(source.get("itemId") or 0)):
            issues.append(AugmentIssue("not_augmentable", "Only armor and weapon rows carry the core augment layout."))
        if location == 3:
            issues.append(AugmentIssue("temporary_items_runtime", "Temporary Items are runtime-managed."))
        for aug_id, _ in pairs:
            if aug_id and not _augment_known(connection, aug_id):
                issues.append(AugmentIssue("augment_unknown", f"Augment id {aug_id} is not in the server's augments table."))
        extra_before = _extra_bytes(source.get("extra")).hex()
        if len(pairs) == AUGMENT_SLOTS:
            extra_after = encode_augments(source.get("extra"), pairs).hex()
            if extra_after == extra_before:
                issues.append(AugmentIssue("no_change", "Augments already match the stored values."))
    return AugmentPlan(char_id, location, slot, pairs, source, _fingerprint(source) if source else None, item,
                       extra_before, extra_after, state.online, family, issues)


def apply_augment_plan(connection, plan: AugmentPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply augment changes")
    if not plan.ready or plan.source is None or plan.extra_after is None:
        raise RuntimeError("Augment plan is not write-ready")
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cursor = connection.cursor()
            try:
                cursor.execute("START TRANSACTION")
            finally:
                cursor.close()
        schema = discover_character_schema(connection)
        if detect_online_state(connection, schema, plan.char_id).online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        now = _inventory_row(connection, plan.char_id, plan.location, plan.slot)
        if now is None or _fingerprint(now) != plan.source_fingerprint:
            raise RuntimeError("Inventory row changed since preview; preview again")
        new_extra = bytes.fromhex(plan.extra_after)
        cursor = connection.cursor()
        try:
            cursor.execute("UPDATE `char_inventory` SET `extra` = %s WHERE `charid` = %s AND `location` = %s AND `slot` = %s",
                           (new_extra, plan.char_id, plan.location, plan.slot))
            if getattr(cursor, "rowcount", 1) != 1:
                raise RuntimeError("Augment update did not change exactly one row")
        finally:
            cursor.close()
        connection.commit()
        after = dict(now)
        after["extra"] = new_extra
        result = {"status": "committed", "char_id": plan.char_id, "location": plan.location, "slot": plan.slot,
                  "item_id": int(now.get("itemId") or 0)}
        return attach_committed_audit(
            result, operation="inventory.augment", char_id=plan.char_id, adapter_family=plan.adapter_family,
            target={"table": "char_inventory", "source_location": plan.location, "source_slot": plan.slot,
                    "item_id": int(now.get("itemId") or 0)},
            before=now, after=after, metadata={"source_fingerprint": plan.source_fingerprint}, undo_supported=True)
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
