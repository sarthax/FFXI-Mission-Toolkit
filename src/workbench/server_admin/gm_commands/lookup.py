"""Read-only ID lookup against the active server checkout (never invents IDs)."""
from __future__ import annotations

import re
from pathlib import Path

KINDS = ("item", "keyitem", "title", "effect", "spell", "zone", "mob", "npc", "currency", "questlog", "missionlog")
# kind -> (relative file, regex with groups id,name). SQL rows start "(id,...'name'"; Lua "NAME = id;".
_SQL_ROW = r"VALUES \((\d+),(?:[^,']*,)*?'([^']*)'"
_SOURCES = {
    "item": ("sql/item_basic.sql", r"VALUES \((\d+),\d+,'([^']*)'"),
    "spell": ("sql/spell_list.sql", r"VALUES \((\d+),'([^']*)'"),
    "effect": ("sql/status_effects.sql", r"VALUES \((\d+),'([^']*)'"),
    "zone": ("sql/zone_settings.sql", r"VALUES \((\d+),\d+,'[^']*',\d+,'([^']*)'"),
    "npc": ("sql/npc_list.sql", r"VALUES \((\d+),'[^']*','([^']*)'"),
    "mob": ("sql/mob_spawn_points.sql", r"VALUES \((\d+),'[^']*','([^']*)'"),
    "currency": ("sql/char_points.sql", None),
    "questlog": ("scripts/globals/log_ids.lua", None),
    "missionlog": ("scripts/globals/log_ids.lua", None),
    "keyitem": ("scripts/globals/keyitems.lua", None),
    "title": ("scripts/globals/titles.lua", None),
}
_LUA = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*[;,]", re.M)
_cache: dict[tuple, tuple[float, list]] = {}


def _load(root: Path, kind: str) -> list[tuple[int, str]]:
    rel, pattern = _SOURCES[kind]
    path = root / rel
    stamp = path.stat().st_mtime
    hit = _cache.get((str(root), kind))
    if hit and hit[0] == stamp:
        return hit[1]
    text = path.read_text(encoding="utf-8", errors="replace")
    if kind == "currency":
        body = text.split("CREATE TABLE `char_points`", 1)[-1].split(") ENGINE", 1)[0]
        rows = [(n, n.replace("_", " ")) for n in re.findall(r"^\s*`([a-z_0-9]+)`", body, re.M) if n != "charid"]
    elif kind in ("questlog", "missionlog"):
        table = "QUEST_LOGS" if kind == "questlog" else "MISSION_LOGS"
        body = text.split(table + " = {", 1)[-1].split("};", 1)[0]
        rows = [(int(i), n.replace("_", " ").title()) for i, n in re.findall(r'\[(\d+)\]\s*=\s*"([A-Z_]+)"', body)]
    elif pattern is None:
        rows = [(int(i), n) for n, i in _LUA.findall(text)]
    else:
        rows = [(int(i), n) for i, n in re.findall(pattern, text)]
    if kind in ("currency", "questlog", "missionlog"):
        pass
    elif kind in ("item", "spell", "effect", "zone"):
        rows = [(i, n.replace("_", " ")) for i, n in rows]
    elif kind in ("keyitem", "title"):
        rows = [(i, n.replace("_", " ").lower()) for i, n in rows]
    _cache[(str(root), kind)] = (stamp, rows)
    return rows


def lookup(server_root: str | Path, kind: str, query: str = "", limit: int = 30) -> list[dict]:
    if kind not in KINDS:
        raise ValueError("Unknown lookup kind")
    limit = max(1, min(int(limit), 100))
    root = Path(server_root).resolve(strict=True)
    rows = _load(root, kind)
    q = query.strip().lower().replace("_", " ")
    if not q:
        hits = rows[:limit]
    elif q.isdigit():
        hits = [r for r in rows if str(r[0]).startswith(q)][:limit]
    else:
        words = q.split()
        hits = [r for r in rows if all(w in r[1].lower() for w in words)]
        hits.sort(key=lambda r: (not r[1].lower().startswith(q), len(r[1])))
        hits = hits[:limit]
    return [{"id": i, "name": n} for i, n in hits]
