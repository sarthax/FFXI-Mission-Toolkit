"""Inventory DSP GM Lua commands without executing Lua or sending game commands.

The command catalog is descriptive, not authorization. The server's actual GM
permission checks remain authoritative. Commands default to manual-only.
"""
from __future__ import annotations

import re
from pathlib import Path

_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{0,63}\Z")
_META = re.compile(r"--\s*(?:func|desc)\s*:\s*(.*)", re.I)
_PERMISSION = re.compile(r"\bpermission\s*=\s*(\d+)")
_PARAMETERS = re.compile(r'\bparameters\s*=\s*["\']([^"\']*)["\']')
_READ_ONLY = frozenset({"getmobaction", "checklocalvar"})
_MAX_FILE = 64 * 1024
_USAGE = re.compile(r"""[\"']!([a-zA-Z0-9_]+)((?:\s+[<{][^>}\"']*[>}])*)""")
_TOKEN = re.compile(r"([<{])([^>}]*)[>}]")

CATEGORIES = ["Items & Currency", "Key Items, Quests & Missions", "Character", "Spells & Effects",
              "Movement & Zones", "Mobs & NPCs", "Assault & Instances", "Server & World",
              "Diagnostics & Dev"]
_CATEGORY_NAMES = {
    "Items & Currency": "additem giveitem delitem hasitem addtempitem addtreasure addcurrency delcurrency "
        "givegil takegil setgil addassaultpoints addnyzultokens salvagedrinks addlights resetlights showlights ah",
    "Key Items, Quests & Missions": "addkeyitem delkeyitem haskeyitem addquest delquest checkquest completequest "
        "addmission delmission checkmission completemission resetlcquest checkvar setplayervar checklocalvar setlocalvar",
    "Character": "changejob changesjob setplayerlevel givexp takexp cp setmerits hp mp tp pettp title setmentor "
        "capskill capallskills setplayermodel setplayernation cnation costume animation godmode godmode1 petgodmode "
        "hide togglegm promote resetmercrank reset raise setflag jail pardon moghancement garden astraria chocobo resetvoidwatch",
    "Spells & Effects": "addspell delspell addallspells addeffect deleffect addallattachments addallmaps",
    "Movement & Zones": "pos goto bring zone gotoentity gotoinstid homepoint return posfix speed wallhack where "
        "logpos getid release logoff send",
    "Mobs & NPCs": "spawnmob mobhere npchere despawnmob setmobflags mobsub npcsub animatenpc animatesubnpc "
        "getmobaction mobskilldiag getmod",
    "Assault & Instances": "wa warpassault setstage testmine nyzuldebug nyzulflorlayout nyzulnavsweep adddynatime",
    "Server & World": "setweather timeoffset setmusic updateconquest updateservermessage reloadglobal revision",
    "Diagnostics & Dev": "cs cs2 inject injectaction messagebasic messagespecial entityvisual fourccanim exec "
        "checknav navdebug showhelper",
}
_CATEGORY = {n: c for c, names in _CATEGORY_NAMES.items() for n in names.split()}
_KIND_WORDS = (("keyitem", ("key item", "keyitem")), ("item", ("item",)), ("title", ("title",)),
               ("effect", ("effect",)), ("spell", ("spell",)), ("zone", ("zone",)),
               ("mob", ("mob",)), ("npc", ("npc",)))


def _lookup_kind(label: str, name: str) -> str | None:
    low = label.lower()
    if "currency" in low:
        return "currency"
    if low in ("questid", "missionid"):
        return low[:-2]
    if low == "logid":
        return "missionlog" if "mission" in name else "questlog"
    if name in ("hasitem", "delitem", "additem", "giveitem", "addtempitem", "addtreasure") and "item" in low:
        return "item"
    for kind, words in _KIND_WORDS:
        if any(w in low for w in words):
            return kind
    return None


_RANGE = re.compile(r"([A-Za-z_]\w*)\s*<\s*(-?\d+)\s+or\s+\1\s*>\s*(-?\d+)")
_BETWEEN = re.compile(r"between (-?\d+) and (-?\d+)", re.I)
_ERRMSG = re.compile(r"error\(\s*player\s*,\s*\"([^\"]{6,160})\"")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _attach_hints(source: str, params: list[dict]) -> None:
    """Add range/hint to a param when the command's own validation names it. Never guesses."""
    ranges = {_norm(v): (int(lo), int(hi)) for v, lo, hi in _RANGE.findall(source)}
    errors = _ERRMSG.findall(source)
    for p in params:
        key = _norm(p["label"])
        if key in ranges:
            p["min"], p["max"] = ranges[key]
        for msg in errors:
            low = _norm(msg)
            if key and key in low and not msg.lower().startswith(("you must", "usage")) and re.search(r"\bmust\b|\buse\b|\d", msg, re.I):
                p["hint"] = " ".join(msg.split())
                b = _BETWEEN.search(msg)
                if b and "min" not in p:
                    p["min"], p["max"] = int(b.group(1)), int(b.group(2))
                break


def _usage_params(name: str, source: str, types: str | None) -> tuple[str, list[dict]]:
    """Usage text from the command's own help line; params as {label, required, type, lookup}."""
    for m in _USAGE.finditer(source):
        if m.group(1).lower() == name and m.group(2).strip():
            usage = "!" + name + " " + " ".join(m.group(2).split())
            out = []
            for i, t in enumerate(_TOKEN.finditer(m.group(2))):
                out.append({"label": t.group(2).strip(), "required": t.group(1) == "<",
                            "type": (types or "")[i:i + 1] or "s",
                            "lookup": _lookup_kind(t.group(2), name)})
            return usage, out
    out = [{"label": "arg%d" % (i + 1), "required": False, "type": c, "lookup": None}
           for i, c in enumerate(types or "")]
    return "!" + name + "".join(" {%s}" % p["label"] for p in out), out


def catalog_commands(server_root: str | Path, *, limit: int = 512) -> list[dict]:
    """Read a configured local server checkout's scripts/commands directory."""
    if type(limit) is not int or not 1 <= limit <= 1024:
        raise ValueError("Invalid catalog size limit")
    root = Path(server_root).resolve(strict=True)
    directory = root / "scripts" / "commands"
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Server checkout has no trusted command directory")
    records = []
    for path in sorted(directory.glob("*.lua")):
        if len(records) >= limit:
            break
        if path.is_symlink() or not _NAME.fullmatch(path.stem):
            continue
        try:
            if path.stat().st_size > _MAX_FILE:
                continue
            source = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        labels = {}
        for line in source.splitlines()[:35]:
            m = _META.match(line.strip())
            if m:
                value = m.group(1).strip()[:240]
                key = "function" if "func:" in line.lower() else "description"
                labels[key] = value
        permission = _PERMISSION.search(source)
        params = _PARAMETERS.search(source)
        name = path.stem.lower()
        usage, plist = _usage_params(name, source, params.group(1) if params else None)
        _attach_hints(source, plist)
        records.append({
            "name": name,
            "command": "!" + name,
            "description": labels.get("description", ""),
            "permission": int(permission.group(1)) if permission else None,
            "parameters": params.group(1) if params else None,
            "category": _CATEGORY.get(name, "Other"),
            "usage": usage,
            "params": plist,
            "classification": "diagnostic_candidate" if name in _READ_ONLY else "unreviewed",
            "execution_enabled": False,
            "source_path": "scripts/commands/" + path.name,
        })
    return records


def command_preview(record: dict, arguments: list[str] | None = None) -> str:
    """Build a copy-only preview. No transport or execution exists here."""
    name = record.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("Invalid command name")
    arguments = arguments or []
    if len(arguments) > 8 or any(not isinstance(a, str) or not a or
       len(a) > 128 or any(c in a for c in "\r\n\x00") for a in arguments):
        raise ValueError("Invalid command arguments")
    return "!" + name + (" " + " ".join(arguments) if arguments else "")
