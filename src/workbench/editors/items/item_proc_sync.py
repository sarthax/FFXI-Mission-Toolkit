"""Cross-check broken/stub item scripts against LandSandBoat and repair what LSB fully specifies.

Why this exists: LSB runs item procs from DATA (item_mods 431 type + 500 dmg + 501 chance + 950
element + 951 status + 952 power + 953 duration, handled by scripts/globals/additional_effects.lua
and the C++), so LSB has NO per-item script for these weapons. DSP runs procs from a per-item Lua
script, so a DSP weapon with mod 431 and no script silently never procs. LSB therefore can't supply
the *file*, only the *parameters* -- and only when LSB itself filled them in.

Nothing is invented: a Lua draft is generated only when every value it needs comes from LSB, and the
effect/element/sub-effect names are resolved from DSP's own status.lua/magic.lua and from patterns
that existing DSP scripts already use. Everything else is reported as "needs data" with what LSB
does and does not know.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from . import item_lsb_compare as lsbc
from . import item_summary as isum

PROC_TYPES = {1: "DAMAGE", 2: "DEBUFF", 3: "HP_HEAL", 4: "MP_HEAL", 5: "HP_DRAIN", 6: "MP_DRAIN", 7: "TP_DRAIN",
              8: "HPMP_DRAIN", 9: "HPMPTP_DRAIN", 10: "DISPEL", 11: "ABSORB_STATUS", 12: "SELF_BUFF",
              13: "DEATH", 14: "NM_SPECIFIC"}
GENERATABLE = {"DAMAGE", "DEBUFF"}
LSB_PROC_MODS = {431: "type", 500: "damage", 501: "chance", 950: "element", 951: "status", 952: "power", 953: "duration"}
# Statuses that tick in LSB's statusAttack table (scripts/globals/additional_effects.lua).
LSB_TICK = {"POISON": 3, "CHOKE": 3}
ELE_NAMES = {1: "FIRE", 2: "EARTH", 3: "WATER", 4: "WIND", 5: "ICE", 6: "LIGHTNING", 7: "LIGHT", 8: "DARK"}
SUBEFFECT_DAMAGE = {"FIRE": "SUBEFFECT_FIRE_DAMAGE", "ICE": "SUBEFFECT_ICE_DAMAGE", "WIND": "SUBEFFECT_WIND_DAMAGE",
                    "EARTH": "SUBEFFECT_EARTH_DAMAGE", "LIGHTNING": "SUBEFFECT_LIGHTNING_DAMAGE",
                    "WATER": "SUBEFFECT_WATER_DAMAGE", "LIGHT": "SUBEFFECT_LIGHT_DAMAGE", "DARK": "SUBEFFECT_DARKNESS_DAMAGE"}


def lsb_proc_data(item_id: int, lsb_root: Path | None = None) -> dict:
    """What LandSandBoat's item_mods says about this item's additional effect."""
    root = str(lsb_root or lsbc.LSB_ROOT)
    if not (Path(root) / "sql" / "item_mods.sql").is_file():
        return {"available": False}
    names, rows = lsbc._lsb_mod_names(root), lsbc._lsb_rows(root)
    out: dict = {"available": True, "in_lsb": False}
    for mid, val in rows["item_mods"].get(int(item_id), []):
        key = LSB_PROC_MODS.get(int(mid))
        if key:
            out[key] = int(val)
            out["in_lsb"] = True
    out["type_name"] = PROC_TYPES.get(out.get("type"))
    return out


def _dsp_effect_names(root: Path) -> dict:
    p = root / "scripts/globals/status.lua"
    if not p.is_file():
        return {}
    return {int(m.group(2)): m.group(1) for m in re.finditer(r"^EFFECT_(\w+)\s*=\s*(\d+)", p.read_text(errors="ignore"), re.M)}


def _dsp_subeffects(root: Path) -> set:
    p = root / "scripts/globals/status.lua"
    return set(re.findall(r"^(SUBEFFECT_\w+)\s*=", p.read_text(errors="ignore"), re.M)) if p.is_file() else set()


def _resist_precedent(root: Path) -> dict:
    """effect name -> element used by existing DSP item scripts that apply that status."""
    out: dict = {}
    d = root / "scripts/globals/items"
    for p in d.glob("*.lua") if d.is_dir() else []:
        t = p.read_text(errors="ignore")
        e = re.search(r"addStatusEffect\(\s*EFFECT_(\w+)", t)
        r = re.search(r"applyResistanceAddEffect\(\s*\w+\s*,\s*\w+\s*,\s*ELE_(\w+)", t)
        if e and r:
            out.setdefault(e.group(1), r.group(1))
    return out


def find_misnamed(root: Path, item_id: int, name: str) -> str | None:
    """A script whose '-- ID: <id>' header matches but whose filename is not the one the server loads
    (stray space, wrong case...). Returns its relative path, or None."""
    d = Path(root) / "scripts/globals/items"
    want = re.sub(r"[^a-z0-9_+]", "", name.lower())
    pat = re.compile(r"^--\s*ID:\s*%d\s*$" % int(item_id), re.M)
    for p in d.glob("*.lua") if d.is_dir() else []:
        if p.stem != want and (re.sub(r"[^a-z0-9_+]", "", p.stem.lower()) == want or pat.search(p.read_text(errors="ignore")[:400])):
            return f"scripts/globals/items/{p.name}"
    return None


def plan_item(item_id: int, name: str, root: Path, lsb_root: Path | None = None) -> dict:
    """Decide what can be done for one item. state: generate | needs-data | manual | no-lsb-data."""
    root = Path(root)
    lsb = lsb_proc_data(item_id, lsb_root)
    mis = find_misnamed(root, item_id, name)
    if mis:
        want = re.sub(r"[^a-z0-9_+]", "", name.lower())
        return {"item_id": item_id, "name": name, "lsb": lsb, "state": "misnamed", "lua": None, "missing": [],
                "resolved": {"rename_from": mis, "rename_to": f"scripts/globals/items/{want}.lua"},
                "reason": f"a script for this item exists as `{mis}` but the server looks for `{want}.lua`; rename it"}
    plan = {"item_id": item_id, "name": name, "lsb": lsb, "state": "no-lsb-data", "reason": "", "lua": None,
            "missing": [], "resolved": {}}
    if not lsb.get("available"):
        plan["reason"] = "LandSandBoat reference not found"
        return plan
    if not lsb.get("in_lsb") or "type" not in lsb:
        plan["reason"] = "LSB has no additional-effect data for this item"
        return plan
    t = lsb.get("type_name")
    if t not in GENERATABLE:
        plan["state"] = "manual"
        plan["reason"] = (f"LSB proc type {t or lsb.get('type')} is not one this tool generates; "
                          "needs a hand-written script (LSB values listed for reference)")
        return plan
    need = {"DAMAGE": ["damage", "chance", "element"], "DEBUFF": ["status", "power", "duration", "chance"]}[t]
    plan["missing"] = [k for k in need if k not in lsb]
    if plan["missing"]:
        plan["state"] = "needs-data"
        plan["reason"] = f"LSB marks this as {t} but does not supply: {', '.join(plan['missing'])}. Not guessed."
        return plan
    effects, subs = _dsp_effect_names(root), _dsp_subeffects(root)
    if t == "DAMAGE":
        ele = ELE_NAMES.get(lsb["element"])
        if not ele:
            plan.update(state="needs-data", reason=f"LSB element {lsb['element']} has no DSP ELE_ name"); return plan
        plan["resolved"] = {"element": f"ELE_{ele}", "subeffect": SUBEFFECT_DAMAGE[ele]}
        plan["lua"] = _lua_damage(item_id, name, lsb, ele)
    else:
        eff = effects.get(lsb["status"])
        if not eff:
            plan.update(state="needs-data", reason=f"LSB status id {lsb['status']} not found in DSP status.lua"); return plan
        ele = lsb.get("element") and ELE_NAMES.get(lsb["element"]) or _resist_precedent(root).get(eff)
        if not ele:
            plan.update(state="needs-data", reason=f"no resist element known for EFFECT_{eff} (LSB gives none, no DSP script applies it)")
            return plan
        sub = f"SUBEFFECT_{eff}" if f"SUBEFFECT_{eff}" in subs else "0"
        plan["resolved"] = {"effect": f"EFFECT_{eff}", "element": f"ELE_{ele}", "subeffect": sub, "tick": LSB_TICK.get(eff, 0)}
        plan["lua"] = _lua_debuff(item_id, name, lsb, eff, ele, sub)
    plan["state"] = "generate"
    plan["reason"] = "every value comes from LSB; chance/amounts are LSB's, not retail-verified on DSP"
    return plan


def _header(item_id, name, kind, lsb):
    nice = name.replace("_", " ").title()
    return (f"-----------------------------------------\n-- ID: {item_id}\n-- Item: {nice}\n-- Additional Effect: {kind}\n"
            f"-- GENERATED by the Mission Toolkit from LandSandBoat item_mods {{{', '.join(f'{k}={v}' for k, v in lsb.items() if k in LSB_PROC_MODS.values())}}}.\n"
            "-- Draft: values are LSB's and unverified on this server. Review before relying on it.\n"
            "-----------------------------------------\n"
            'require("scripts/globals/status");\nrequire("scripts/globals/magic");\nrequire("scripts/globals/msg");\n\n'
            "-----------------------------------\n-- onAdditionalEffect Action\n-----------------------------------\n\n")


def _lua_damage(item_id, name, lsb, ele):
    return _header(item_id, name, f"{ele.title()} Damage", lsb) + f"""function onAdditionalEffect(player,target,damage)
    local chance = {lsb['chance']};

    if (math.random(0,99) >= chance) then
        return 0,0,0;
    else
        local dmg = {lsb['damage']};
        local params = {{}};
        params.bonusmab = 0;
        params.includemab = false;
        dmg = addBonusesAbility(player, ELE_{ele}, target, dmg, params);
        dmg = dmg * applyResistanceAddEffect(player,target,ELE_{ele},0);
        dmg = adjustForTarget(target,dmg,ELE_{ele});
        dmg = finalMagicNonSpellAdjustments(player,target,ELE_{ele},dmg);

        local message = msgBasic.ADD_EFFECT_DMG;
        if (dmg < 0) then
            message = msgBasic.ADD_EFFECT_HEAL;
        end

        return {SUBEFFECT_DAMAGE[ele]},message,dmg;
    end
end;
"""


def _lua_debuff(item_id, name, lsb, eff, ele, sub):
    tick = LSB_TICK.get(eff, 0)
    return _header(item_id, name, eff.replace("_", " ").title(), lsb) + f"""function onAdditionalEffect(player,target,damage)
    local chance = {lsb['chance']};

    if (math.random(0,99) >= chance or applyResistanceAddEffect(player,target,ELE_{ele},0) <= 0.5) then
        return 0,0,0;
    else
        if (not target:hasStatusEffect(EFFECT_{eff})) then
            target:addStatusEffect(EFFECT_{eff}, {lsb['power']}, {tick}, {lsb['duration']});
        end
        return {sub}, msgBasic.ADD_EFFECT_STATUS, EFFECT_{eff};
    end
end;
"""


def build_report(server_root: Path | None = None, lsb_root: Path | None = None) -> dict:
    """Full script-health report with an LSB cross-check/repair plan for every broken item."""
    if server_root is None:
        from workbench.devtools.spatial import zone_plot as zone_plot
        server_root = zone_plot._server_root()
    root = Path(server_root)
    h = isum.health_report(root)
    lroot = Path(lsb_root or lsbc.LSB_ROOT)
    items = []
    for it in h["flagged_items"]:
        if it["state"] == "behavior":
            continue
        plan = plan_item(it["item_id"], it["name"], root, lroot)
        items.append({**it, "plan": {k: plan[k] for k in ("state", "reason", "missing", "resolved", "lsb")},
                      "has_draft": bool(plan["lua"]) or plan["state"] == "misnamed"})
    stubs = []
    for f in h["script_files"]:
        if f["state"] == "behavior" and not f["todo"]:
            continue
        stem = Path(f["path"]).stem
        lp = lroot / "scripts" / "items" / f"{stem}.lua"
        lstate = isum.analyze_script(lp.read_text(errors="ignore"))["state"] if lp.is_file() else "no-lsb-script"
        stubs.append({**f, "lsb_state": lstate})
    counts = {}
    for i in items:
        counts[i["plan"]["state"]] = counts.get(i["plan"]["state"], 0) + 1
    return {"server_root": str(root), "generated": time.strftime("%Y-%m-%d %H:%M"),
            "summary": {"flagged": h["flagged_counts"], "files": h["file_counts"], "orphans": len(h["orphan_files"]),
                        "repair_states": counts},
            "broken_items": items, "weak_script_files": stubs, "orphan_files": h["orphan_files"]}


def render_markdown(rep: dict) -> str:
    s = rep["summary"]
    L = ["# Item script health report", "",
         f"Generated {rep['generated']} for `{rep['server_root']}`.", "",
         "## Summary", "",
         f"- Items with a proc switch (effect 431): {sum(s['flagged'].values())} "
         f"({', '.join(f'{v} {k}' for k, v in s['flagged'].items())})",
         f"- Item script files: {sum(s['files'].values())} ({', '.join(f'{v} {k}' for k, v in s['files'].items())})",
         f"- Script files matching no item name: {s['orphans']}",
         f"- Repair plan for the broken items: {', '.join(f'{v} {k}' for k, v in s['repair_states'].items()) or 'none'}", "",
         "## Why these items never proc", "",
         "On this server an item's additional effect only runs if `scripts/globals/items/<name>.lua` defines "
         "`onAdditionalEffect`. These items have the proc switch (mod 431) set but no such script, so the "
         "switch does nothing. LandSandBoat runs the same effects from item data instead of per-item scripts, so "
         "it has no script file to copy; it only supplies parameters, and only for some items.", "",
         "## Items with a proc switch but no working script", "",
         "| Item | ID | Server state | LSB proc type | What LSB supplies | Plan |", "|---|---|---|---|---|---|"]
    for i in rep["broken_items"]:
        p = i["plan"]; l = p["lsb"]
        sup = ", ".join(f"{k}={l[k]}" for k in ("damage", "chance", "element", "status", "power", "duration") if k in l) or "nothing"
        L.append(f"| {i['name']} | {i['item_id']} | {i['state']} | {l.get('type_name') or '-'} | {sup} | **{p['state']}** — {p['reason']} |")
    L += ["", "Plan key: **generate** = a draft script can be written from LSB values; **needs-data** = LSB knows the "
          "proc type but not the numbers (get them from a retail source; nothing is guessed); **manual** = proc type this "
          "tool does not generate; **no-lsb-data** = LSB has nothing; **misnamed** = a working script exists under the wrong filename, rename it.", "",
          "## Script files that are stubs or check-only", "",
          "| File | State here | State in LSB | TODO marker |", "|---|---|---|---|"]
    for f in rep["weak_script_files"]:
        L.append(f"| `{f['path']}` | {f['state']} | {f['lsb_state']} | {'yes' if f['todo'] else ''} |")
    L += ["", "A stub that is also a stub in LSB is usually an item whose use effect is purely cosmetic or handled by "
          "the client; confirm per item before treating it as broken.", ""]
    return "\n".join(L)


def repair_item(item_id: int, server_root: Path | None = None, *, apply: bool = False,
                lsb_root: Path | None = None) -> dict:
    """Preview (default) or write the generated script. Never overwrites a script with behavior;
    a stub or check-only file is backed up first."""
    from workbench.editors.items import _editor_impl as impl
    if server_root is None:
        from workbench.devtools.spatial import zone_plot as zone_plot
        server_root = zone_plot._server_root()
    root = Path(server_root)
    db = impl._item_db(); cu = db.cursor()
    cu.execute("select name from item_basic where itemid=%s", (int(item_id),))
    row = cu.fetchone(); db.close()
    if not row:
        return {"ok": False, "error": f"item {item_id} not found"}
    name = row[0]
    sc = isum.find_script(root, name)
    if sc["exists"] and (sc["analysis"] or {}).get("state") == "behavior":
        return {"ok": False, "error": f"{sc['path']} already has behavior; refusing to overwrite", "path": sc["path"]}
    plan = plan_item(int(item_id), name, root, lsb_root)
    if plan["state"] == "misnamed":
        src, dst = root / plan["resolved"]["rename_from"], root / plan["resolved"]["rename_to"]
        if dst.exists():
            return {"ok": False, "error": f"{plan['resolved']['rename_to']} already exists"}
        res = {"ok": True, "applied": False, "path": plan["resolved"]["rename_to"], "lua": src.read_text(errors="ignore"),
               "resolved": plan["resolved"], "replaces": f"rename of {plan['resolved']['rename_from']}"}
        if apply:
            src.rename(dst); res["applied"] = True
        return res
    if not plan["lua"]:
        return {"ok": False, "error": plan["reason"], "plan_state": plan["state"]}
    rel = f"scripts/globals/items/{re.sub(r'[^a-z0-9_+]', '', name.lower())}.lua"
    dest = root / rel
    res = {"ok": True, "applied": False, "path": rel, "lua": plan["lua"], "resolved": plan["resolved"],
           "replaces": "stub/check-only file (backed up)" if dest.is_file() else "nothing (new file)"}
    if apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file():
            bak = dest.with_name(dest.name + f".bak-{time.strftime('%Y%m%d-%H%M%S')}")
            bak.write_bytes(dest.read_bytes())
            res["backup"] = str(bak.relative_to(root)).replace("\\", "/")
        dest.write_text(plan["lua"], encoding="utf-8", newline="\n")
        res["applied"] = True
    return res
