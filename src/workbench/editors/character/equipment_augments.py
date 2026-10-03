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


def _mod_names(root: Path | None) -> dict[int, tuple[str, str]]:
    """Mod id -> (enum name, the // comment after it) from the server's own modifier.h."""
    path = root / "src" / "map" / "modifier.h" if root else None
    names: dict[int, tuple[str, str]] = {}
    if path and path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^[ 	]*([A-Za-z_][A-Za-z0-9_]*)[ 	]*=[ 	]*(\d+)[ 	]*,[ 	]*(?://[ 	]*(.*))?$", text, re.M):
            names.setdefault(int(m.group(2)), (m.group(1), (m.group(3) or "").strip()))
    return names


_ACRONYM_MAX = 4
_KNOWN = {"ACC": "Accuracy", "ATT": "Attack", "DEF": "Defense", "EVA": "Evasion", "RACC": "Ranged Accuracy",
          "RATT": "Ranged Attack", "MACC": "Magic Accuracy", "MATT": "Magic Attack", "MDEF": "Magic Defense",
          "MEVA": "Magic Evasion", "FASTCAST": "Fast Cast", "CRITHITRATE": "Critical Hit Rate", "ENMITY": "Enmity"}


def _friendly(name: str | None, mod_id: int) -> str:
    """HP -> HP, DMG_RATING -> Dmg Rating (short all-caps names stay as acronyms)."""
    if not name:
        return f"Unnamed stat #{mod_id}"
    if name in _KNOWN:
        return _KNOWN[name]
    if name.endswith("RES") and len(name) > 5 and "_" not in name:
        return name[:-3].capitalize() + " Resistance"
    if "_" not in name and len(name) <= _ACRONYM_MAX:
        return name
    return " ".join(w if len(w) <= 3 and w.isupper() and len(w) < len(name) and w in {"HP", "MP", "TP", "WS", "XP"} else w.capitalize() for w in name.split("_"))


def augment_catalog(root: Path | str | None) -> dict[str, Any]:
    """augmentId -> effects, from the server checkout's ``augments.sql``."""
    root = Path(root) if root else None
    path = root / "sql" / "augments.sql" if root else None
    mods = _mod_names(root)
    try:  # item editor's enum comments; only trusted when the name matches this server's modifier.h
        from workbench.editors.items._dat_tools_impl import _explicit_mod_unit
    except Exception:
        _explicit_mod_unit = lambda _c: None
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
            raw_name, comment = mods.get(mod_id, (None, ""))
            e["effects"].append({"mod": mod_id, "mod_name": _friendly(raw_name, mod_id), "value": value,
                                 "multiplier": mult, "pet": bool(is_pet),
                                 "comment": comment or None, "unit": _explicit_mod_unit(comment) if comment else None})
    rows = [e for _, e in sorted(entries.items())]
    return {"available": bool(rows), "rows": rows}


def native_bonuses(connection, item_ids, root: Path | str | None) -> dict[int, list[dict[str, Any]]]:
    """Server-defined base stats (``item_mods``) per item, named from the server's modifier.h."""
    ids = sorted({int(i) for i in item_ids if i})
    out: dict[int, list[dict[str, Any]]] = {}
    if not ids:
        return out
    mods = _mod_names(Path(root) if root else None)
    try:
        from workbench.editors.items._dat_tools_impl import _explicit_mod_unit
    except Exception:
        _explicit_mod_unit = lambda _c: None
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT `itemId`,`modId`,`value` FROM `item_mods` WHERE `itemId` IN ({','.join(['%s'] * len(chunk))}) ORDER BY `itemId`,`modId`", tuple(chunk))
            rows = cursor.fetchall() or []
        except Exception:
            rows = []
        finally:
            cursor.close()
        for item_id, mod_id, value in rows:
            name, comment = mods.get(int(mod_id), (None, ""))
            out.setdefault(int(item_id), []).append({
                "mod": int(mod_id), "name": _friendly(name, int(mod_id)), "value": int(value),
                "comment": comment or None, "unit": _explicit_mod_unit(comment) if comment else None})
    return out


def _latent_defs(root: Path | None) -> dict[int, tuple[str, str]]:
    """Latent id -> (enum name, // comment) from the server's latent_effect.h."""
    path = root / "src" / "map" / "latent_effect.h" if root else None
    out: dict[int, tuple[str, str]] = {}
    if path and path.is_file():
        for m in re.finditer(r"^[ 	]*LATENT_([A-Z0-9_]+)[ 	]*=[ 	]*(\d+)[ 	]*,?[ 	]*(?://[ 	]*(.*))?$", path.read_text(encoding="utf-8", errors="replace"), re.M):
            out[int(m.group(2))] = (m.group(1), (m.group(3) or "").strip())
    return out


def _pet_types(root: Path | None) -> dict[int, str]:
    path = root / "src" / "map" / "modifier.h" if root else None
    out: dict[int, str] = {}
    if path and path.is_file():
        block = re.search(r"enum class PetModType\s*\{(.*?)\}", path.read_text(encoding="utf-8", errors="replace"), re.S)
        for m in re.finditer(r"([A-Za-z_]+)\s*=\s*(\d+)", block.group(1) if block else ""):
            out[int(m.group(2))] = m.group(1)
    return out


_JOBS = {1: "Warrior", 2: "Monk", 3: "White Mage", 4: "Black Mage", 5: "Red Mage", 6: "Thief", 7: "Paladin", 8: "Dark Knight",
         9: "Beastmaster", 10: "Bard", 11: "Ranger", 12: "Samurai", 13: "Ninja", 14: "Dragoon", 15: "Summoner", 16: "Blue Mage",
         17: "Corsair", 18: "Puppetmaster", 19: "Dancer", 20: "Scholar", 21: "Geomancer", 22: "Rune Fencer"}


def _latent_condition(latent_id: int, param: int, defs: dict[int, tuple[str, str]]) -> str:
    name, comment = defs.get(latent_id, (None, ""))
    if name is None:
        return f"Condition #{latent_id} (parameter {param})"
    head, _, ptext = comment.partition("PARAM:")
    head = head.strip(" -")
    labels = {int(k): v.strip() for k, v in re.findall(r"(\d+):\s*([A-Za-z' \-]+?)(?=\s+\d+:|,|$)", ptext)}
    if latent_id in (8, 22) and param in _JOBS:
        labels = {param: _JOBS[param]}
    if param in labels:
        shown = labels[param].title() if labels[param].isupper() else labels[param]
    else:
        shown = str(param)
    if not head:
        head = name.replace("_", " ").lower()
    if re.search(r"[%#]", head):
        text = re.sub(r"[%#]", lambda _m: shown + ("%" if "%" in _m.group(0) else ""), head, count=1)
    elif ptext.strip():
        text = f"{head} ({shown})"
    else:
        text = head
    text = re.sub(r"\b(hp|mp|tp)\b", lambda m: m.group(1).upper(), text)
    text = text.replace("checks if player region is under nation's control", "Region control")
    return text[:1].upper() + text[1:]


def conditional_bonuses(connection, item_ids, root: Path | str | None) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """Latent (conditional) and pet bonuses per item, from item_latents / item_mods_pet."""
    ids = sorted({int(i) for i in item_ids if i})
    out: dict[int, dict[str, list[dict[str, Any]]]] = {}
    if not ids:
        return out
    root = Path(root) if root else None
    mods = _mod_names(root)
    latents = _latent_defs(root)
    pets = _pet_types(root)

    def mod_text(mod_id: int, value: int) -> str:
        name, _ = mods.get(mod_id, (None, ""))
        return f"{_friendly(name, mod_id)} {value:+d}"

    queries = (
        ("latent", "SELECT `itemId`,`modId`,`value`,`latentId`,`latentParam` FROM `item_latents` WHERE `itemId` IN ({q}) ORDER BY `itemId`,`latentId`,`latentParam`,`modId`"),
        ("pet", "SELECT `itemId`,`modId`,`value`,`petType` FROM `item_mods_pet` WHERE `itemId` IN ({q}) ORDER BY `itemId`,`petType`,`modId`"),
    )
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        for kind, sql in queries:
            cursor = connection.cursor()
            try:
                cursor.execute(sql.format(q=",".join(["%s"] * len(chunk))), tuple(chunk))
                rows = cursor.fetchall() or []
            except Exception:
                rows = []
            finally:
                cursor.close()
            for r in rows:
                bucket = out.setdefault(int(r[0]), {"latent": [], "pet": []})[kind]
                if kind == "latent":
                    bucket.append({"when": _latent_condition(int(r[3]), int(r[4]), latents), "text": mod_text(int(r[1]), int(r[2]))})
                else:
                    bucket.append({"when": f"Pet: {pets.get(int(r[3]), 'Pet type ' + str(r[3]))}", "text": mod_text(int(r[1]), int(r[2]))})
    return out


def equipment_state(connection, char_id: int, root: Path | str | None = None) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `equipslotid`,`containerid`,`slotid` FROM `char_equip` WHERE `charid` = %s ORDER BY `equipslotid`", (int(char_id),))
        refs = cursor.fetchall() or []
    finally:
        cursor.close()
    rows = []
    for equip_slot, location, slot in refs:
        equip_slot, location, slot = int(equip_slot), int(location), int(slot)
        if equip_slot >= len(EQUIP_SLOTS):
            continue  # e.g. the linkshell slot: its extra bytes are not augments
        row = _inventory_row(connection, char_id, location, slot)
        item = _item_record(connection, int(row["itemId"])) if row else None
        if row and not _is_armor_or_weapon(connection, int(row["itemId"])):
            continue
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
    native = native_bonuses(connection, [r["item_id"] for r in rows], root)
    for r in rows:
        r["native"] = native.get(r["item_id"], [])
        cond = conditional_bonuses(connection, [r["item_id"]], root).get(r["item_id"], {}) if r["item_id"] else {}
        r["latent"], r["pet"] = cond.get("latent", []), cond.get("pet", [])
    return {"char_id": int(char_id), "slots": rows}


def inventory_augmentables(connection, char_id: int, root: Path | str | None = None) -> dict[str, Any]:
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
    native = native_bonuses(connection, [o["item_id"] for o in out], root)
    cond_all = conditional_bonuses(connection, [o["item_id"] for o in out], root)
    for o in out:
        o["native"] = native.get(o["item_id"], [])
        o["latent"], o["pet"] = cond_all.get(o["item_id"], {}).get("latent", []), cond_all.get(o["item_id"], {}).get("pet", [])
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
