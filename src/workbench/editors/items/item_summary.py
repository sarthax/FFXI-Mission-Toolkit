"""Single source of truth for 'what does this item do'.

`describe_item(item_id)` gathers every place an item's behavior can live (item tables, mods,
pet mods, latents, weapon hit count, item script, gear sets, food/use bonuses, server-code
mentions, client description) into one plain dict. The Item Editor, character equipment,
auction house and a future item browser should all render from this, not re-derive it.

`summarize()` is pure (takes already-fetched inputs) so it can be tested without a database.
Nothing here invents meaning: unknown mods/latents are reported as unknown, and `notes`
lists suspected gaps rather than guessing fixes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

HIT_DISTRIBUTION = {
    2: {1: 55, 2: 45},
    3: {1: 30, 2: 50, 3: 20},
    4: {1: 20, 2: 30, 3: 30, 4: 20},
}
SCRIPT_HOOK_TEXT = {
    "onAdditionalEffect": "extra effect when it hits (proc)",
    "onItemUse": "what happens when the item is used",
    "onItemCheck": "extra rules for using/equipping it",
    "onEffectGain": "bonuses while its effect is active (food, medicine, buffs)",
    "onEffectLose": "removes those bonuses when the effect ends",
    "onEffectTick": "repeating effect while active",
}
SCRIPT_FLAG_NAME = "ADDITIONAL_EFFECT"  # DSP mod 431: on/off switch for onAdditionalEffect
SCRIPT_FLAG_ID = 431


def _clean_name(label: str | None, mod_id: int) -> str:
    if not label:
        return f"Unknown effect #{mod_id}"
    return re.split(r"\s+--\s+", str(label))[0].strip()


def _comment(label: str | None) -> str:
    parts = re.split(r"\s+--\s+", str(label or ""), maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


_FUNC_RE = re.compile(r"(?:^|\n)\s*(?:local\s+)?function\s+([\w.:]+)\s*\(([^)]*)\)", re.M)
_TRIVIAL_RE = re.compile(r"^(return(\s+[\w\s,.\-()]*)?|end|local\s+\w+\s*=\s*(0|nil|false|true|\{\}))$", re.I)
_TODO_RE = re.compile(r"\b(todo|stub|not implemented|placeholder|fixme)\b", re.I)
_EFFECT_RE = re.compile(r"(addStatusEffect\w*|addMod|delMod|addHP|addMP|addTP|restoreHP|restoreMP|delStatusEffect\w*|"
                        r"setPos|addItem|delItem|messageBasic|addBonusesAbility|addTPSpecial|drain\w*|"
                        r"\w*[Dd]amage\w*)\s*\(")


def _strip_comments(src: str) -> str:
    src = re.sub(r"--\[(=*)\[.*?\]\1\]", "", src, flags=re.S)
    return re.sub(r"--[^\n]*", "", src)


def analyze_script(src: str) -> dict:
    """Classify a Lua item script. Returns state in {'behavior','check-only','stub'} plus, per hook,
    how many meaningful statements it has and which game-affecting calls it makes."""
    code = _strip_comments(src)
    funcs = list(_FUNC_RE.finditer(code))
    hooks = []
    for i, m in enumerate(funcs):
        name = m.group(1).split(".")[-1].split(":")[-1]
        if not name.startswith("on"):
            continue
        end = funcs[i + 1].start() if i + 1 < len(funcs) else len(code)
        body = code[m.end():end]
        lines = [l.strip().rstrip(";") for l in body.splitlines() if l.strip()]
        meaningful = [l for l in lines if not _TRIVIAL_RE.match(l)]
        calls = sorted({c.group(1) for c in _EFFECT_RE.finditer(body)})
        hooks.append({"hook": name, "statements": len(meaningful), "effect_calls": calls,
                      "body": "\n".join(lines[:40]), "trivial": not meaningful})
    todo = bool(_TODO_RE.search(src))
    real = [h for h in hooks if not h["trivial"]]
    behavior_hooks = [h for h in real if h["hook"] != "onItemCheck"]
    if behavior_hooks:
        state = "behavior"
    elif real:
        state = "check-only"
    else:
        state = "stub"
    return {"state": state, "hooks": hooks, "todo_marker": todo,
            "behavior_hooks": [h["hook"] for h in behavior_hooks]}


def find_script(root: Path | None, internal_name: str) -> dict:
    """Locate scripts/globals/items/<name>.lua (DSP/Topaz) or scripts/items/<name>.lua (LSB)."""
    name = re.sub(r"[^a-z0-9_+]", "", (internal_name or "").lower())
    out: dict[str, Any] = {"name": name, "exists": False, "path": "", "hooks": [], "source": "", "truncated": False, "analysis": None}
    if not root or not name:
        return out
    root = Path(root)
    for rel in (f"scripts/globals/items/{name}.lua", f"scripts/items/{name}.lua"):
        p = root / rel
        if p.is_file():
            txt = p.read_text(encoding="utf-8", errors="ignore")
            out.update(exists=True, path=rel,
                       hooks=sorted(set(re.findall(r"function\s+(?:\w+[.:])?(on[A-Za-z]+)", txt))),
                       source=txt[:6000], truncated=len(txt) > 6000, analysis=analyze_script(txt))
            return out
    lsb_only = (root / "scripts/items").is_dir() and not (root / "scripts/globals/items").is_dir()
    out["path"] = f"{'scripts/items' if lsb_only else 'scripts/globals/items'}/{name}.lua"
    return out


def summarize(data: dict, *, special: dict | None = None, script: dict | None = None,
              latent_meta: dict | None = None) -> dict:
    """Pure: turn get_item() output (+ optional special-case/script lookups) into one summary."""
    server = data.get("server") or {}
    basic = server.get("item_basic") or {}
    weapon = server.get("item_weapon") or None
    equip = server.get("item_equipment") or server.get("item_armor") or None
    usable = server.get("item_usable") or None
    client = data.get("client") or {}
    special = special or {}
    script = script or {}
    latent_meta = latent_meta or {}
    notes: list[dict] = []

    bonuses, script_flag = [], None
    for m in data.get("mods") or []:
        mid = int(m["modId"])
        label = m.get("name")
        name = _clean_name(label, mid)
        if mid == SCRIPT_FLAG_ID and name.upper().startswith(SCRIPT_FLAG_NAME):
            script_flag = int(m["value"])
            continue
        bonuses.append({"mod_id": mid, "name": name, "value": m["value"],
                        "meaning": _comment(label), "known": bool(label)})
        if not label:
            notes.append({"code": "UNKNOWN_MOD", "message": f"mod {mid} has no name in the active server's enum"})

    pet_bonuses = [{"mod_id": int(m["modId"]), "name": _clean_name(m.get("name"), int(m["modId"])),
                    "value": m["value"], "pet_type": m.get("petTypeName") or f"pet type {m.get('petType')}"}
                   for m in data.get("pet_mods") or []]

    conditional = []
    for m in data.get("latents") or []:
        lid = int(m["latentId"])
        meta = latent_meta.get(lid) or latent_meta.get(str(lid)) or {}
        known = bool(m.get("latentName"))
        conditional.append({
            "mod_id": int(m["modId"]), "name": _clean_name(m.get("name"), int(m["modId"])), "value": m["value"],
            "condition_id": lid,
            "condition": _clean_name(m.get("latentName"), lid) if known else f"Unknown condition #{lid}",
            "condition_meaning": meta.get("comment") or _comment(m.get("latentName")),
            "param": m.get("latentParam"), "param_meaning": meta.get("param_semantics") or "", "known": known})
        if not known:
            notes.append({"code": "UNKNOWN_LATENT",
                          "message": f"latent condition {lid} has no name in the active server's enum"})

    combat = None
    if weapon:
        hits = int(weapon.get("hit") or 1)
        multi = None
        if hits > 1:
            multi = {"max_hits": hits, "distribution_pct": HIT_DISTRIBUTION.get(hits),
                     "text": "Occasionally attacks twice" if hits == 2 else f"Occasionally attacks up to {hits} times"}
        combat = {"damage": weapon.get("dmg"), "delay": weapon.get("delay"), "skill": weapon.get("skill"),
                  "damage_type": weapon.get("dmgType"), "max_hits": hits, "multi_hit": multi}

    scripted = None
    if script_flag is not None or script.get("exists"):
        hooks = script.get("hooks") or []
        an = script.get("analysis") or {}
        by_hook = {h["hook"]: h for h in an.get("hooks") or []}
        if not script.get("exists"):
            health = "missing"
        else:
            health = an.get("state") or "behavior"
        scripted = {"proc_switch": script_flag, "path": script.get("path"), "exists": bool(script.get("exists")),
                    "health": health, "todo_marker": bool(an.get("todo_marker")),
                    "hooks": [{"hook": h, "meaning": SCRIPT_HOOK_TEXT.get(h, "custom hook"),
                               "statements": (by_hook.get(h) or {}).get("statements"),
                               "trivial": (by_hook.get(h) or {}).get("trivial"),
                               "effect_calls": (by_hook.get(h) or {}).get("effect_calls") or [],
                               "body": (by_hook.get(h) or {}).get("body", "")} for h in hooks],
                    "has_additional_effect": "onAdditionalEffect" in hooks}
        if script_flag and not scripted["exists"]:
            notes.append({"code": "PROC_WITHOUT_SCRIPT",
                          "message": "effect 431 is set but the script file is missing, so the proc does nothing"
                                     + (f" ({script.get('path')})" if script.get("path") else "")})
        elif script_flag and not scripted["has_additional_effect"]:
            notes.append({"code": "PROC_WITHOUT_SCRIPT",
                          "message": "effect 431 is set but the script has no onAdditionalEffect hook"})
        elif health == "stub":
            notes.append({"code": "SCRIPT_STUB", "message": "script file exists but every hook is empty or only returns"})
        elif health == "check-only":
            notes.append({"code": "SCRIPT_CHECK_ONLY", "message": "script only has onItemCheck logic; no effect behavior"})
        if scripted["todo_marker"]:
            notes.append({"code": "SCRIPT_TODO", "message": "script contains a TODO/stub/placeholder marker"})

    desc = (client.get("description") or "").strip()
    low = desc.lower()
    multi_ok = bool(combat and combat["max_hits"] > 1)
    if re.search(r"attacks (twice|\w+ times)", low) and not multi_ok:
        notes.append({"code": "DESC_MULTIHIT_NOT_IN_DATA",
                      "message": "client description says it attacks multiple times but item_weapon.hit is 1"})
    if "additional effect" in low and not (scripted and (scripted["has_additional_effect"] or script_flag)):
        notes.append({"code": "DESC_PROC_NOT_IN_DATA",
                      "message": "client description mentions an additional effect but the server has no proc switch or script"})
    if re.search(r"occasionally attacks twice|double attack", low) and not multi_ok \
            and not any("DOUBLE_ATTACK" in b["name"].upper() for b in bonuses):
        notes.append({"code": "DESC_DOUBLE_ATTACK_NOT_IN_DATA",
                      "message": "client description implies double attack but no server data provides it"})

    return {
        "item_id": data.get("item_id"),
        "identity": {"name": basic.get("name"), "client_name": client.get("name"),
                     "stack": basic.get("stackSize"), "flags": client.get("flags_decoded")},
        "requirements": ({"level": equip.get("level"), "ilevel": equip.get("ilevel"),
                          "jobs": client.get("jobs_list") or equip.get("jobs"),
                          "slot": equip.get("slot"), "races": client.get("races")} if equip else None),
        "combat": combat,
        "bonuses": bonuses, "pet_bonuses": pet_bonuses, "conditional_bonuses": conditional,
        "script": scripted,
        "set_bonuses": list(special.get("gear_sets") or []),
        "effect_gain_mods": list(special.get("effect_gain_mods") or []),
        "code_references": list(special.get("code_references") or []),
        "usable": ({"valid_targets": usable.get("validTargets"), "use_delay": usable.get("useDelay"),
                    "reuse_delay": usable.get("reuseDelay"), "max_charges": usable.get("maxCharges")}
                   if usable else None),
        "client_description": desc,
        "notes": notes,
    }


def describe_item(item_id: int, *, server_root: Path | None = None) -> dict:
    """Fetch everything for one item from the live DB + active server tree and summarize it."""
    from workbench.editors.items import editor as ed
    from workbench.editors.items import _special_cases as sc

    data = ed.get_item(item_id)
    name = ((data.get("server") or {}).get("item_basic") or {}).get("name") or ""
    if server_root is None:
        try:
            from workbench.devtools.spatial import active_zone_plot as zone_plot
            server_root = zone_plot._server_root()
        except Exception:
            server_root = None
    special = sc.special_cases(server_root, int(item_id), name) if server_root else {}
    script = find_script(server_root, name)
    try:
        lmeta = ed.latent_metadata()
    except Exception:
        lmeta = {}
    return summarize(data, special=special, script=script, latent_meta=lmeta)


def summary_lines(s: dict) -> list[str]:
    """Plain-text rendering so every consumer (tooltip, CLI, chat) prints the same words."""
    out: list[str] = []
    ident = s.get("identity") or {}
    out.append(f"{ident.get('client_name') or ident.get('name')} (#{s.get('item_id')})")
    c = s.get("combat")
    if c:
        out.append(f"DMG {c['damage']}  Delay {c['delay']}")
        if c["multi_hit"]:
            out.append(c["multi_hit"]["text"])
    for b in s["bonuses"]:
        out.append(f"{b['name']} {b['value']}")
    for b in s["pet_bonuses"]:
        out.append(f"{b['pet_type']}: {b['name']} {b['value']}")
    for b in s["conditional_bonuses"]:
        param = f" ({b['param']})" if b.get("param") else ""
        out.append(f"{b['name']} {b['value']} when {b['condition']}{param}")
    sc_ = s.get("script")
    if sc_:
        out.append(f"Scripted effect [{sc_['health']}]: " + (", ".join(h["meaning"] for h in sc_["hooks"]) or "proc switch only")
                   + ("" if sc_["exists"] else " [script missing]"))
    for g in s["set_bonuses"]:
        out.append(f"Set bonus: {g.get('comment') or g.get('set_id')}")
    for m in s["effect_gain_mods"]:
        out.append(f"While active: {m.get('mod')} {m.get('value')}")
    for n in s["notes"]:
        out.append(f"! {n['message']}")
    return out


def health_report(server_root: Path | None = None) -> dict:
    """Bulk script health: (a) every item flagged with effect 431 -> is its script present / stub /
    real behavior; (b) every item script file on disk -> classified, and whether any item uses it."""
    from workbench.editors.items import _editor_impl as impl
    if server_root is None:
        from workbench.devtools.spatial import active_zone_plot as zone_plot
        server_root = zone_plot._server_root()
    root = Path(server_root)
    db = impl._item_db(); cu = db.cursor()
    cu.execute("select b.itemid, b.name, m.value from item_mods m join item_basic b on b.itemid=m.itemId where m.modId=%s",
               (SCRIPT_FLAG_ID,))
    flagged = cu.fetchall()
    cu.execute("select name from item_basic")
    all_names = {re.sub(r"[^a-z0-9_+]", "", (r[0] or "").lower()) for r in cu.fetchall()}
    db.close()

    flagged_items = []
    for iid, name, val in flagged:
        sc = find_script(root, name)
        state = "missing" if not sc["exists"] else (sc["analysis"] or {}).get("state", "behavior")
        has_add = "onAdditionalEffect" in sc["hooks"]
        if sc["exists"] and not has_add:
            state = "no-onAdditionalEffect"
        flagged_items.append({"item_id": iid, "name": name, "state": state, "path": sc["path"], "hooks": sc["hooks"]})

    files = []
    for rel in ("scripts/globals/items", "scripts/items"):
        d = root / rel
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.lua")):
            an = analyze_script(p.read_text(encoding="utf-8", errors="ignore"))
            files.append({"path": f"{rel}/{p.name}", "state": an["state"], "todo": an["todo_marker"],
                          "behavior_hooks": an["behavior_hooks"], "matches_item": p.stem.lower() in all_names})
    counts = lambda rows: {k: sum(1 for r in rows if r["state"] == k) for k in sorted({r["state"] for r in rows})}
    return {"flagged_items": flagged_items, "flagged_counts": counts(flagged_items),
            "script_files": files, "file_counts": counts(files),
            "orphan_files": [f["path"] for f in files if not f["matches_item"]]}
