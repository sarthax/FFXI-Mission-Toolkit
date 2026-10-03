"""Reference data for the Spells / Abilities / Traits / Mounts character pages.

Categories come from the client resources (bundled ``spell_reference.json``, keyed by the same
spell ids the server stores in ``char_spells``/``spell_list``). Which abilities and traits exist,
and their job/level, come from the selected server checkout's own ``abilities.sql``/``traits.sql``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REF = Path(__file__).with_name("spell_reference.json")

JOB_ABBR = ("WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK", "BST", "BRD", "RNG", "SAM",
            "NIN", "DRG", "SMN", "BLU", "COR", "PUP", "DNC", "SCH", "GEO", "RUN")

SPELL_CATEGORIES = (
    ("WhiteMagic", "White Magic"), ("BlackMagic", "Black Magic"), ("BardSong", "Songs"),
    ("BlueMagic", "Blue Magic"), ("SummonerPact", "Summoning"), ("Ninjutsu", "Ninjutsu"),
    ("Geomancy", "Geomancy"), ("Trust", "Trust"),
)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _title(name: str) -> str:
    return " ".join(w.capitalize() for w in str(name).replace("_", " ").split())


def _job(job_id: int) -> str:
    return JOB_ABBR[job_id - 1] if 1 <= job_id <= len(JOB_ABBR) else ""


def _insert_rows(path: Path, table: str):
    pattern = re.compile(rf"INSERT\s+INTO\s+`{table}`\s+VALUES\s*\((.*)\);", re.I)
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pattern.search(raw)
        if m:
            yield [v.strip().strip("'") for v in re.findall(r"'[^']*'|[^,]+", m.group(1))]


def spell_rows(spell_list_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach client category and per-job levels to the server's ``spell_list`` rows."""
    data = json.loads(_REF.read_text(encoding="utf-8"))
    ref, names = data["spells"], data.get("spell_names", {})
    rows = []
    on_server = set()
    for row in spell_list_rows:
        sid = int(row["spellid"])
        on_server.add(sid)
        kind, levels = ref.get(str(sid), (None, {}))
        rows.append({
            "id": sid,
            "name": _title(row.get("name", "")),
            "category": kind or "Other",
            "jobs": {_job(int(j)): lv for j, lv in levels.items() if _job(int(j))},
            "on_server": True,
        })
    # Client spells this server's spell_list lacks (e.g. Geomancy/Trust on DSP): shown, not editable.
    for sid_text, (kind, levels) in ref.items():
        if int(sid_text) not in on_server and names.get(sid_text):
            rows.append({"id": int(sid_text), "name": names[sid_text], "category": kind,
                         "jobs": {_job(int(j)): lv for j, lv in levels.items() if _job(int(j))}, "on_server": False})
    return {
        "categories": [{"key": k, "label": label} for k, label in SPELL_CATEGORIES] + [{"key": "Other", "label": "Other / unclassified"}],
        "rows": rows,
    }


def ability_rows(server_root: Path | str | None) -> dict[str, Any]:
    root = Path(server_root) if server_root else None
    path = root / "sql" / "abilities.sql" if root else None
    types = json.loads(_REF.read_text(encoding="utf-8"))["ability_types"]
    rows: list[dict[str, Any]] = []
    if path and path.is_file():
        for v in _insert_rows(path, "abilities"):
            try:
                aid, name, job, level = int(v[0]), v[1], int(v[2]), int(v[3])
            except (ValueError, IndexError):
                continue
            rows.append({"id": aid, "name": _title(name), "job": job, "job_abbr": _job(job),
                         "level": level, "type": types.get(_norm(name), "")})
    return {"available": bool(rows), "rows": rows}


def trait_rows(server_root: Path | str | None) -> dict[str, Any]:
    root = Path(server_root) if server_root else None
    path = root / "sql" / "traits.sql" if root else None
    best: dict[tuple[int, int, int], dict[str, Any]] = {}
    if path and path.is_file():
        for v in _insert_rows(path, "traits"):
            try:
                tid, name, job, level, rank = int(v[0]), v[1], int(v[2]), int(v[3]), int(v[4])
            except (ValueError, IndexError):
                continue
            key = (job, tid, rank)
            if _job(job) and (key not in best or level < best[key]["level"]):
                best[key] = {"id": tid, "name": _title(name), "job_abbr": _job(job), "job": job, "level": level, "rank": rank}
    rows = sorted(best.values(), key=lambda r: (r["job"], r["level"], r["id"]))
    return {"available": bool(rows), "rows": rows}


def mount_names() -> dict[str, str]:
    return json.loads(_REF.read_text(encoding="utf-8"))["mounts"]


def jobs_reference(server_root: Path | str | None) -> dict[str, Any]:
    """Skill names/categories (client) plus per-job skill ranks and level caps (server checkout)."""
    root = Path(server_root) if server_root else None
    skills = {k: {"name": v[0], "category": v[1]} for k, v in json.loads(_REF.read_text(encoding="utf-8")).get("skills", {}).items()}
    ranks: dict[str, dict[str, int]] = {}
    caps: dict[str, list[int]] = {}
    if root:
        rp, cp = root / "sql" / "skill_ranks.sql", root / "sql" / "skill_caps.sql"
        if rp.is_file():
            for v in _insert_rows(rp, "skill_ranks"):
                try:
                    ranks[v[0]] = {JOB_ABBR[i]: int(x) for i, x in enumerate(v[2:2 + len(JOB_ABBR)])}
                except (ValueError, IndexError):
                    continue
        if cp.is_file():
            for v in _insert_rows(cp, "skill_caps"):
                try:
                    caps[v[0]] = [int(x) for x in v[1:]]
                except ValueError:
                    continue
    return {"skills": skills, "ranks": ranks, "caps": caps, "jobs": list(JOB_ABBR)}
