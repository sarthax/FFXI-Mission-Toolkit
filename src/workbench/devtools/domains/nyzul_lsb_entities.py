"""Deterministic entity resolution for the modern LandSandBoat Nyzul adapter.

LandSandBoat intentionally resolves IDs.lua symbols such as ``GetFirstID('Mokke')``
from zone entity data instead of hard-coding numeric IDs.  The toolkit mirrors that
contract against the checked-out ``data/zones/nyzul_isle`` YAML sources so the
Nyzul editor can recover its legacy-compatible numeric view without guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MOBS_YAML = "data/zones/nyzul_isle/mobs.yaml"
NPCS_YAML = "data/zones/nyzul_isle/npcs.yaml"


@dataclass(frozen=True)
class EntityIndex:
    mobs: dict[int, str]
    npcs: dict[int, str]
    mob_ids_by_name: dict[str, tuple[int, ...]]
    npc_ids_by_name: dict[str, tuple[int, ...]]

    def name_for_mob(self, entity_id: int) -> str:
        try:
            return self.mobs[int(entity_id)]
        except KeyError as exc:
            raise ValueError(f"LSB Nyzul mob id {entity_id} is not present in {MOBS_YAML}") from exc


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"modern LSB Nyzul entity source is missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"modern LSB Nyzul entity source is not a YAML mapping: {path}")
    return data


def _reverse(index: dict[int, str]) -> dict[str, tuple[int, ...]]:
    work: dict[str, list[int]] = {}
    for entity_id, name in index.items():
        work.setdefault(name, []).append(entity_id)
    return {name: tuple(sorted(ids)) for name, ids in work.items()}


def load_entity_index(root: Path) -> EntityIndex:
    """Load the modern zone-data sources that back GetFirstID/GetTableOfIDs."""
    root = Path(root)
    mob_doc = _load_yaml(root / MOBS_YAML)
    npc_doc = _load_yaml(root / NPCS_YAML)

    spawns = mob_doc.get("spawns")
    npcs = npc_doc.get("npcs")
    if not isinstance(spawns, dict):
        raise ValueError(f"modern LSB Nyzul mob source has no 'spawns' mapping: {root / MOBS_YAML}")
    if not isinstance(npcs, dict):
        raise ValueError(f"modern LSB Nyzul NPC source has no 'npcs' mapping: {root / NPCS_YAML}")

    mob_index: dict[int, str] = {}
    for raw_id, row in spawns.items():
        if not isinstance(row, dict):
            continue
        name = row.get("template") or row.get("script")
        if name:
            mob_index[int(raw_id)] = str(name)

    npc_index: dict[int, str] = {}
    for raw_id, row in npcs.items():
        if not isinstance(row, dict):
            continue
        name = row.get("script")
        if name:
            npc_index[int(raw_id)] = str(name)

    if not mob_index:
        raise ValueError(f"modern LSB Nyzul mob source contains no named spawns: {root / MOBS_YAML}")
    if not npc_index:
        raise ValueError(f"modern LSB Nyzul NPC source contains no named NPCs: {root / NPCS_YAML}")

    return EntityIndex(
        mobs=mob_index,
        npcs=npc_index,
        mob_ids_by_name=_reverse(mob_index),
        npc_ids_by_name=_reverse(npc_index),
    )


def parse_runtime_id_defs(ids_text: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Parse only deterministic GetFirstID/GetTableOfIDs declarations from IDs.lua."""
    out: dict[str, dict[str, dict[str, Any]]] = {"mob": {}, "npc": {}}
    section_re = re.compile(r"(?m)^\s*(mob|npc)\s*=\s*\{")
    for section_match in section_re.finditer(ids_text):
        section = section_match.group(1)
        start = section_match.end() - 1
        depth = 0
        end = None
        for pos in range(start, len(ids_text)):
            depth += ids_text[pos] == "{"
            depth -= ids_text[pos] == "}"
            if depth == 0:
                end = pos + 1
                break
        if end is None:
            raise ValueError(f"unterminated {section} table in modern LSB Nyzul IDs.lua")
        body = ids_text[start:end]
        pattern = re.compile(
            r"(?m)^\s*([A-Z][A-Z0-9_]*)\s*=\s*"
            r"(GetFirstID|GetTableOfIDs)\(\s*['\"]([^'\"]+)['\"]"
            r"\s*(?:,\s*(\d+)\s*)?\)"
        )
        for key, function, name, count in pattern.findall(body):
            out[section][key] = {
                "function": function,
                "name": name,
                "count": int(count) if count else None,
            }
    return out


def resolve_runtime_ids(defs: dict[str, dict[str, dict[str, Any]]], index: EntityIndex) -> dict[str, dict[str, int | list[int]]]:
    """Resolve IDs.lua declarations using the same first/all-by-name semantics as LSB."""
    out: dict[str, dict[str, int | list[int]]] = {"mob": {}, "npc": {}}
    for section in ("mob", "npc"):
        by_name = index.mob_ids_by_name if section == "mob" else index.npc_ids_by_name
        for key, definition in defs.get(section, {}).items():
            name = str(definition["name"])
            ids = by_name.get(name, ())
            if not ids:
                raise ValueError(
                    f"cannot deterministically resolve ID.{section}.{key}: {definition['function']}({name!r}) "
                    f"has no match in modern LSB Nyzul zone data"
                )
            if definition["function"] == "GetFirstID":
                out[section][key] = ids[0]
                continue
            count = definition.get("count")
            if count is None:
                out[section][key] = list(ids)
                continue
            first = ids[0]
            expected = list(range(first, first + int(count)))
            available = (index.mobs if section == "mob" else index.npcs)
            if any(entity_id not in available for entity_id in expected):
                raise ValueError(
                    f"cannot deterministically resolve ID.{section}.{key}: requested GetTableOfIDs range "
                    f"{first}..{first + int(count) - 1} is not contiguous in modern LSB zone data"
                )
            out[section][key] = expected
    return out


def resolve_id_expression(expression: str, resolved: dict[str, dict[str, int | list[int]]]) -> int:
    """Resolve the restricted ID expressions used by current Nyzul floor_generation.lua."""
    text = expression.strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    match = re.fullmatch(r"ID\.(mob|npc)\.([A-Z][A-Z0-9_]*)(?:\s*([+-])\s*(\d+))?", text)
    if not match:
        raise ValueError(f"unsupported modern LSB Nyzul ID expression: {expression!r}")
    section, key, operator, raw_delta = match.groups()
    try:
        base = resolved[section][key]
    except KeyError as exc:
        raise ValueError(f"unresolved modern LSB Nyzul symbol: ID.{section}.{key}") from exc
    if not isinstance(base, int):
        raise ValueError(f"modern LSB Nyzul expression requires scalar ID but ID.{section}.{key} is a table")
    delta = int(raw_delta or 0)
    return base - delta if operator == "-" else base + delta


def resolve_ranges(
    ranges: dict[int, dict[str, str]], resolved: dict[str, dict[str, int | list[int]]]
) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for key, row in ranges.items():
        first_id = resolve_id_expression(row["first"], resolved)
        last_id = resolve_id_expression(row["last"], resolved)
        if last_id < first_id:
            raise ValueError(f"modern LSB Nyzul range {key} is reversed: {first_id}..{last_id}")
        out[key] = {**row, "first_id": first_id, "last_id": last_id}
    return out


def contiguous_name_groups(first_id: int, last_id: int, index: EntityIndex) -> list[dict[str, Any]]:
    """Convert a resolved contiguous mob range into legacy editor group runs."""
    groups: list[dict[str, Any]] = []
    for entity_id in range(first_id, last_id + 1):
        name = index.name_for_mob(entity_id)
        if groups and groups[-1]["name"] == name and groups[-1]["id"] + groups[-1]["count"] == entity_id:
            groups[-1]["count"] += 1
        else:
            groups.append({"id": entity_id, "count": 1, "name": name})
    return groups


def legacy_numeric_view(
    ranges: dict[str, dict[int, dict[str, Any]]],
    resolved: dict[str, dict[str, int | list[int]]],
    index: EntityIndex,
) -> dict[str, Any]:
    """Build the existing Nyzul editor's numeric collections from resolved LSB data."""
    leaders_range = ranges["enemy_leaders"].get(1)
    if not leaders_range:
        raise ValueError("modern LSB Nyzul enemy-leader range [1] is missing")
    leaders = [
        {"id": entity_id, "name": index.name_for_mob(entity_id)}
        for entity_id in range(leaders_range["first_id"], leaders_range["last_id"] + 1)
        if index.name_for_mob(entity_id) != "Qiqirn_Mine"
    ]

    groups = []
    for group_id in sorted(ranges["specified_mobs"]):
        row = ranges["specified_mobs"][group_id]
        runs = contiguous_name_groups(row["first_id"], row["last_id"], index)
        if len(runs) != 1:
            raise ValueError(
                f"modern LSB specified-mob range {group_id} maps to multiple mob names; refusing ambiguous legacy group"
            )
        groups.append(runs[0])

    families: dict[int, dict[str, Any]] = {}
    for family_id in sorted(k for k in ranges["floor_entities"] if k <= 16):
        row = ranges["floor_entities"][family_id]
        runs = contiguous_name_groups(row["first_id"], row["last_id"], index)
        families[family_id] = {
            "label": row.get("note") or ", ".join(run["name"] for run in runs),
            "groups": runs,
        }

    nm_even = [ranges["nm_even"][key]["first_id"] for key in sorted(ranges["nm_even"])]
    nm_odd = [ranges["nm_odd"][key]["first_id"] for key in sorted(ranges["nm_odd"])]

    boss_rows = [ranges["enemy_leaders"].get(40), ranges["enemy_leaders"].get(100)]
    if any(row is None for row in boss_rows):
        raise ValueError("modern LSB Nyzul boss ranges [40] and [100] are required")
    bosses: dict[str, int] = {}
    for row in boss_rows:
        assert row is not None
        for entity_id in range(row["first_id"], row["last_id"] + 1):
            name = index.name_for_mob(entity_id)
            key = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
            bosses[key] = entity_id
    for symbol in ("ARCHAIC_RAMPART_OFFSET", "DAHAK", "GEAR_OFFSET"):
        value = resolved["mob"].get(symbol)
        if isinstance(value, int):
            bosses["ARCHAIC_RAMPART" if symbol == "ARCHAIC_RAMPART_OFFSET" else symbol] = value

    required_bosses = {"ADAMANTOISE", "BEHEMOTH", "FAFNIR", "KHIMAIRA", "HYDRA", "CERBERUS", "ARCHAIC_RAMPART"}
    missing = sorted(required_bosses - bosses.keys())
    if missing:
        raise ValueError(f"modern LSB Nyzul boss mapping is incomplete: missing {', '.join(missing)}")

    return {
        "families": families,
        "leaders": leaders,
        "groups": groups,
        "nm": {"NM_EVEN": nm_even, "NM_ODD": nm_odd},
        "bosses": bosses,
    }
