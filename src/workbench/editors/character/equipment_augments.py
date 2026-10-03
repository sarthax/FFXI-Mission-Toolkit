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


def _latent_condition(latent_id: int, param: int, defs: dict[int, tuple[str, str]], zones: dict[int, str] | None = None) -> str:
    name, comment = defs.get(latent_id, (None, ""))
    if name is None:
        return f"Condition #{latent_id} (parameter {param})"
    head, _, ptext = comment.partition("PARAM:")
    head = head.strip(" -")
    labels = {int(k): v.strip() for k, v in re.findall(r"(\d+):\s*([A-Za-z' \-]+?)(?=\s+\d+:|,|$)", ptext)}
    if latent_id in (8, 22) and param in _JOBS:
        labels = {param: _JOBS[param]}
    if latent_id == 23 and zones and param in zones:
        labels = {param: zones[param]}
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


def _zone_names(connection) -> dict[int, str]:
    """zoneid -> readable zone name from the server's zone_settings table."""
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `zoneid`,`name` FROM `zone_settings`")
        rows = cursor.fetchall() or []
    except Exception:
        return {}
    finally:
        cursor.close()
    out = {}
    for zone_id, name in rows:
        text = str(name or "").replace("_", " ").strip()
        text = text.replace("dOria", "d'Oria")
        out[int(zone_id)] = text
    return out


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
    zones = _zone_names(connection)

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
                    bucket.append({"when": _latent_condition(int(r[3]), int(r[4]), latents, zones), "text": mod_text(int(r[1]), int(r[2]))})
                else:
                    bucket.append({"when": f"Pet: {pets.get(int(r[3]), 'Pet type ' + str(r[3]))}", "text": mod_text(int(r[1]), int(r[2]))})
    return out


_JOB_ABBR = {1: "WAR", 2: "MNK", 3: "WHM", 4: "BLM", 5: "RDM", 6: "THF", 7: "PLD", 8: "DRK", 9: "BST", 10: "BRD", 11: "RNG",
             12: "SAM", 13: "NIN", 14: "DRG", 15: "SMN", 16: "BLU", 17: "COR", 18: "PUP", 19: "DNC", 20: "SCH", 21: "GEO", 22: "RUN"}
EQUIPPABLE_LOCATIONS = (0, 8, 10, 11, 12)  # containers the core server equips from


def _jobs_text(mask: int) -> str:
    names = [abbr for job, abbr in _JOB_ABBR.items() if mask & (1 << (job - 1))]
    return "All jobs" if len(names) >= len(_JOB_ABBR) else "/".join(names)


def player_state(connection, char_id: int) -> dict[str, Any]:
    """Main job and level, which the core server checks before it lets a piece of gear stay equipped."""
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `mjob`,`mlvl`,`sjob`,`slvl` FROM `char_stats` WHERE `charid` = %s", (int(char_id),))
        row = cursor.fetchone()
    except Exception:
        row = None
    finally:
        cursor.close()
    if not row:
        return {"mjob": None, "mlvl": None, "job": None}
    return {"mjob": int(row[0]), "mlvl": int(row[1]), "job": _JOB_ABBR.get(int(row[0]), f"Job {row[0]}"),
            "sjob": int(row[2]), "slvl": int(row[3])}


def equip_block(meta: dict[str, Any] | None, player: dict[str, Any] | None) -> str | None:
    """Why the character cannot wear this gear (the server unequips it on login), or None if it can."""
    if not meta or not meta.get("slot_mask") or not player or not player.get("mjob"):
        return None
    mask = int(meta.get("jobs_mask") or 0)
    if mask and not mask & (1 << (int(player["mjob"]) - 1)):
        return f"{player['job']} cannot use this ({meta.get('jobs') or 'other jobs only'})"
    if int(meta.get("level") or 0) > int(player["mlvl"] or 0):
        return f"Needs Lv{meta['level']} (this character's {player['job']} is Lv{player['mlvl']})"
    return None


def equip_meta(connection, item_ids, player: dict[str, Any] | None = None) -> dict[int, dict[str, Any]]:
    """itemId -> {slot_mask, level, jobs, equip_block} from item_armor (weapons carry a row there too)."""
    ids = sorted({int(i) for i in item_ids if i})
    out: dict[int, dict[str, Any]] = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT `itemId`,`slot`,`level`,`jobs` FROM `item_armor` WHERE `itemId` IN ({','.join(['%s'] * len(chunk))})", tuple(chunk))
            for item_id, mask, level, jobs in cursor.fetchall() or []:
                meta = {"slot_mask": int(mask or 0), "level": int(level or 0), "jobs": _jobs_text(int(jobs or 0)), "jobs_mask": int(jobs or 0)}
                meta["equip_block"] = equip_block(meta, player)
                out[int(item_id)] = meta
        except Exception:
            pass
        finally:
            cursor.close()
    return out


def equipment_state(connection, char_id: int, root: Path | str | None = None) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `equipslotid`,`containerid`,`slotid` FROM `char_equip` WHERE `charid` = %s ORDER BY `equipslotid`", (int(char_id),))
        refs = {int(r[0]): (int(r[1]), int(r[2])) for r in cursor.fetchall() or []}
    finally:
        cursor.close()
    rows = []
    for equip_slot, slot_name in enumerate(EQUIP_SLOTS):  # slots at or above 16 (linkshell) do not hold augments
        base = {"equip_slot": equip_slot, "slot_name": slot_name, "location": None, "inventory_slot": None, "item_id": None,
                "name": None, "item_known": False, "extra_hex": None, "augments": [], "fingerprint": None, "missing_row": False,
                "empty": True}
        ref = refs.get(equip_slot)
        row = _inventory_row(connection, char_id, ref[0], ref[1]) if ref else None
        if ref and row is None:
            rows.append({**base, "location": ref[0], "inventory_slot": ref[1], "empty": False, "missing_row": True})
            continue
        if row is None or not _is_armor_or_weapon(connection, int(row["itemId"])):
            rows.append(base)
            continue
        item = _item_record(connection, int(row["itemId"]))
        extra = _extra_bytes(row.get("extra"))
        rows.append({**base, "empty": False, "location": ref[0], "inventory_slot": ref[1], "item_id": int(row["itemId"]),
                     "name": item["name"] if item else None, "item_known": item is not None, "extra_hex": extra.hex(),
                     "augments": decode_augments(extra), "fingerprint": _fingerprint(row)})
    filled = [r["item_id"] for r in rows if r["item_id"]]
    native = native_bonuses(connection, filled, root)
    cond_all = conditional_bonuses(connection, filled, root)
    player = player_state(connection, char_id)
    meta = equip_meta(connection, filled, player)
    for r in rows:
        r["native"] = native.get(r["item_id"], [])
        cond = cond_all.get(r["item_id"], {})
        r["latent"], r["pet"] = cond.get("latent", []), cond.get("pet", [])
        r.update(meta.get(r["item_id"], {"slot_mask": 0, "level": 0, "jobs": "", "jobs_mask": 0, "equip_block": None}))
    return {"char_id": int(char_id), "player": player, "slots": rows}


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
    player = player_state(connection, char_id)
    meta = equip_meta(connection, [o["item_id"] for o in out], player)
    for o in out:
        o.update(meta.get(o["item_id"], {"slot_mask": 0, "level": 0, "jobs": "", "jobs_mask": 0, "equip_block": None}))
        o["native"] = native.get(o["item_id"], [])
        o["latent"], o["pet"] = cond_all.get(o["item_id"], {}).get("latent", []), cond_all.get(o["item_id"], {}).get("pet", [])
    return {"char_id": int(char_id), "player": player, "items": out}


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


@dataclass
class EquipPlan:
    char_id: int
    equip_slot: int
    location: int | None
    slot: int | None
    item: dict[str, Any] | None
    current: tuple[int, int] | None
    moved_from: int | None
    source_fingerprint: str | None
    online: bool | None
    adapter_family: str
    issues: list[AugmentIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["slot_name"] = EQUIP_SLOTS[self.equip_slot] if 0 <= self.equip_slot < len(EQUIP_SLOTS) else None
        d["ready"] = self.ready
        return d


def _equip_refs(connection, char_id: int) -> dict[int, tuple[int, int]]:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT `equipslotid`,`containerid`,`slotid` FROM `char_equip` WHERE `charid` = %s", (int(char_id),))
        return {int(r[0]): (int(r[1]), int(r[2])) for r in cursor.fetchall() or []}
    finally:
        cursor.close()


def build_equip_plan(connection, *, char_id: int, equip_slot: int, location: int | None = None, slot: int | None = None,
                     adapter_family: str = "unknown") -> EquipPlan:
    """Plan putting the inventory row (location, slot) into an equipment slot; location/slot None empties the slot."""
    char_id, equip_slot = int(char_id), int(equip_slot)
    family = str(adapter_family or "unknown").strip().lower()
    issues: list[AugmentIssue] = []
    if not 0 <= equip_slot < len(EQUIP_SLOTS):
        issues.append(AugmentIssue("equip_slot_invalid", f"Equipment slot must be 0-{len(EQUIP_SLOTS) - 1}."))
    if family not in _VERIFIED_FAMILIES:
        issues.append(AugmentIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for writes."))
    schema = discover_character_schema(connection)
    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(AugmentIssue("character_online", "Character is online; direct equipment writes are blocked."))
    elif state.online is None:
        issues.append(AugmentIssue("online_state_unknown", "Character online state could not be verified."))
    table = schema.table("char_equip")
    if table is None or not {"charid", "slotid", "equipslotid", "containerid"}.issubset(table.column_names):
        issues.append(AugmentIssue("equip_schema_drift", "Connected char_equip schema does not match the verified core contract."))

    refs = _equip_refs(connection, char_id) if not issues else {}
    current = refs.get(equip_slot)
    item = None
    moved_from = None
    fingerprint = None
    if location is None or slot is None:
        location = slot = None
        if current is None and not issues:
            issues.append(AugmentIssue("no_change", "That slot is already empty."))
    else:
        location, slot = int(location), int(slot)
        row = _inventory_row(connection, char_id, location, slot)
        if row is None:
            issues.append(AugmentIssue("source_missing", "No inventory row exists at that location/slot."))
        else:
            fingerprint = _fingerprint(row)
            item_id = int(row.get("itemId") or 0)
            item = _item_record(connection, item_id)
            meta = equip_meta(connection, [item_id], player_state(connection, char_id)).get(item_id)
            if item is None:
                issues.append(AugmentIssue("item_unknown", f"Item ID {item_id} is not in the connected item catalog."))
            if location not in EQUIPPABLE_LOCATIONS:
                issues.append(AugmentIssue("container_not_equippable", f"{CONTAINERS.get(location, location)} items cannot be equipped directly; move the item to Inventory or a Wardrobe first."))
            if meta is None or not meta["slot_mask"]:
                issues.append(AugmentIssue("not_equippable", "This item is not armor or a weapon."))
            elif 0 <= equip_slot < len(EQUIP_SLOTS) and not meta["slot_mask"] & (1 << equip_slot):
                issues.append(AugmentIssue("wrong_slot", f"This item does not go in the {EQUIP_SLOTS[equip_slot]} slot."))
            reason = equip_block(meta, player_state(connection, char_id)) if equip_slot != -1 else None
            if reason:
                issues.append(AugmentIssue("cannot_equip", f"{reason}. The server would unequip it when the character logs in."))
            if int(row.get("bazaar") or 0):
                issues.append(AugmentIssue("bazaar_listed", "Bazaar-listed rows are protected from direct changes."))
            if current == (location, slot):
                issues.append(AugmentIssue("no_change", "That item is already equipped in this slot."))
            for other, ref in refs.items():
                if ref == (location, slot) and other != equip_slot:
                    moved_from = other  # a row cannot be worn twice, so it leaves its old slot
    return EquipPlan(char_id, equip_slot, location, slot, item, current, moved_from, fingerprint, state.online, family, issues)


def apply_equip_plan(connection, plan: EquipPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply equipment changes")
    if not plan.ready:
        raise RuntimeError("Equipment plan is not write-ready")
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
        before = _equip_refs(connection, plan.char_id)
        if before.get(plan.equip_slot) != plan.current:
            raise RuntimeError("Equipment changed since preview; preview again")
        if plan.location is not None:
            now = _inventory_row(connection, plan.char_id, plan.location, plan.slot)
            if now is None or _fingerprint(now) != plan.source_fingerprint:
                raise RuntimeError("Inventory row changed since preview; preview again")
        cursor = connection.cursor()
        try:
            for equip_slot in [plan.equip_slot] + ([plan.moved_from] if plan.moved_from is not None else []):
                cursor.execute("DELETE FROM `char_equip` WHERE `charid` = %s AND `equipslotid` = %s", (plan.char_id, equip_slot))
            if plan.location is not None:
                cursor.execute("INSERT INTO `char_equip` (`charid`,`slotid`,`equipslotid`,`containerid`) VALUES (%s,%s,%s,%s)",
                               (plan.char_id, plan.slot, plan.equip_slot, plan.location))
        finally:
            cursor.close()
        connection.commit()
        after = _equip_refs(connection, plan.char_id)
        result = {"status": "committed", "char_id": plan.char_id, "equip_slot": plan.equip_slot}
        return attach_committed_audit(
            result, operation="equipment.set", char_id=plan.char_id, adapter_family=plan.adapter_family,
            target={"table": "char_equip", "equip_slot": plan.equip_slot},
            before={str(k): list(v) for k, v in before.items()}, after={str(k): list(v) for k, v in after.items()},
            metadata={"source_fingerprint": plan.source_fingerprint}, undo_supported=False)
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
