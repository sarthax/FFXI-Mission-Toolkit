#!/usr/bin/env python3
"""Build the hand-off package of item-script repairs.

Output (default D:\\Claude\\Item-Script-Repairs):
  README.md, REPORT.md, manifest.json
  ready/scripts/globals/items/*.lua   drop-in files; every value sourced (see header + manifest)
  ready/RENAMES.txt                   misnamed files to rename
  needs-values/*.lua.template         effect pre-wired, magnitudes blank (no source has them)
  stubs.md                            verdict on each of the 29 stub files
  apply.py                            copies ready/ into a server tree (backs up, never clobbers behavior)

Nothing here is invented: values come from LandSandBoat data or the BG Wiki dump; anything that neither
source states is left blank and listed in manifest.json under "missing".
"""
import json
import re
import sys
from pathlib import Path

from workbench.runtime.legacy_settings import get_dsp_root
from workbench.runtime.paths import REPO_ROOT
from workbench.editors.items import item_proc_sync as ps
from workbench.editors.items import item_summary as isum

ROOT = REPO_ROOT
DSP = get_dsp_root() or Path(r"D:\Claude\dsp-master")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\Claude\Item-Script-Repairs")

# Template specs: what the wiki confirms (effect/element) and what no source supplies (missing).
# kind: dmg(element) | status(EFFECT, ele) | drain(HP) | other
SPECS = {
    19196: dict(kind="dmg", ele="DARK", wiki="Additional effect: Darkness damage"),
    19296: dict(kind="dmg", ele="FIRE", wiki="Additional effect: Fire damage"),
    20609: dict(kind="dmg", ele="WIND", wiki="Additional effect: Wind damage"),
    21102: dict(kind="dmg", ele="EARTH", wiki="Additional effect: Earth damage"),
    21166: dict(kind="dmg", ele="LIGHTNING", wiki="Additional effect: Lightning damage"),
    17069: dict(kind="status", eff="FLASH", ele="LIGHT", wiki="Additional effect: Flash"),
    19140: dict(kind="status", eff="WEIGHT", ele="WIND",
                wiki="Additional effect: Gravity (user-confirmed; Gravity is EFFECT_WEIGHT in DSP, as spells/gravity.lua uses)"),
    21166 + 0: None,
    19316: dict(kind="status", eff="ADDLE", ele="WIND", wiki='Additional effect: Addle (also enhances "Resist Slow")'),
    19261: dict(kind="status", eff="CURSE_I", ele="DARK",
                wiki="Additional effect: Curse. Curse gives HP -12.5% and lasts 10-30 seconds (confirm CURSE_I vs CURSE_II power)"),
    18785: dict(kind="drain", wiki="Additional effect: HP Drain"),
    18810: dict(kind="drain", chance=1,
                wiki="Additional effect: HP drain. User observation: ~1% proc (about 1 in 25 hits), drained 34 HP and 43 HP on the two procs seen (2 samples, no range known)"),
    20904: dict(kind="drain", wiki="Additional effect: HP drain"),
    20611: dict(kind="drain", wiki="Additional effect: HP Drain"),
    20612: dict(kind="drain", wiki="Additional effect: HP Drain"),
    16504: dict(kind="other", wiki='Additional effect: Haste on self, full 3-minute duration after it procs. Needs a self-buff script (no precedent generated).'),
    18784: dict(kind="multi", wiki=("Additional effect: Poison, Paralyze, or Bind. User report: proc rate is very high and several "
                "of the three often land on one mob. Afflictions ignore enemy resistance and immunity. NOTE: a Lua script can skip the "
                "resistance roll but cannot skip immunity (enforced in C++ StatusEffectContainer::CanGainStatusEffect); that needs an engine change.")),

}
OOS = {}  # item id -> level, for items above the server cap (90)
SPECS = {k: v for k, v in SPECS.items() if v}
FIELDS = {"multi": ["chance (per status)", "power and duration per status"], "dmg": ["chance", "damage"], "status": ["chance", "power", "duration"], "drain": ["chance", "drain amount"],
          "other": ["see note"]}
TWILIGHT = 19132
EREBUS = 19315
EREBUS_LUA = """-----------------------------------------
-- ID: 19315
-- Item: Erebus's Lance
-- Additional Effect vs. Empty: damage varies with current TP
-- Source: user-supplied wiki notes -- activates on ~5% of melee hits (Enlight animation = light damage),
--         damage = current TP / 14 (about 9-70 below 1000 TP, about 194-210 at 3000 TP).
-- ASSUMPTION: no resistance/MAB adjustment is applied (the formula is a flat TP/14).
-----------------------------------------
require("scripts/globals/status");
require("scripts/globals/magic");
require("scripts/globals/msg");

-----------------------------------
-- onAdditionalEffect Action
-----------------------------------

function onAdditionalEffect(player,target,damage)
    if (target:getSystem() ~= SYSTEM_EMPTY or math.random(0,99) >= 5) then
        return 0,0,0;
    end

    local dmg = math.floor(player:getTP() / 14);
    if (dmg <= 0) then
        return 0,0,0;
    end

    return SUBEFFECT_LIGHT_DAMAGE, msgBasic.ADD_EFFECT_DMG, dmg;
end;
"""

STUB_VERDICT = {
    "cosmetic": "Intentional. Fireworks/fans/bells/masques only play a client-side animation or nothing; LandSandBoat's file is the same empty stub. No repair.",
}
STUB_SPECIAL = {
    "flask_of_muting_potion": "Unknown behavior. Wiki says only 'A powerful silencing potion enhanced with anima', valid target Self, no numbers. Do not guess; needs retail capture/data.",
    "ramblers_cloak": "Not a script problem. Its STR+5 latent is already data (item_latents 11312, TP>=100%). The 'cannot equip headgear' restriction is not implemented in any DSP data; stub file is harmless.",
    "twilight_cloak": "Working as designed. onItemCheck grants/removes the 'Impact' spell on equip; check-only is the correct shape for that mechanism.",
}


def lua_template(item_id, name, spec, lsb):
    nice = name.replace("_", " ").title()
    fields = FIELDS[spec["kind"]]
    if "chance" in spec:
        fields = [f for f in fields if f != "chance"]
    head = (f"-- ID: {item_id}\n-- Item: {nice}\n-- TEMPLATE, NOT LOADABLE: fill the blanks, rename to {name}.lua\n"
            f"-- Wiki: {spec['wiki']}\n-- Blank because no source states them: {', '.join(fields)}\n"
            f"-- LSB data for this item: {lsb or 'none'}\n")
    if spec["kind"] == "dmg":
        e = spec["ele"]
        body = ps._lua_damage(item_id, name, {"chance": "<CHANCE>", "damage": "<DAMAGE>", "type": 1}, e)
    elif spec["kind"] == "status":
        eff, e = spec["eff"], spec["ele"]
        body = ps._lua_debuff(item_id, name, {"chance": "<CHANCE>", "power": "<POWER>", "duration": "<DURATION>",
                                              "status": 0}, eff, e, "0")
    elif spec["kind"] == "multi":
        body = ps._header(item_id, name, "Poison / Paralyze / Bind", {}) + (
            "function onAdditionalEffect(player,target,damage)\n"
            "    -- Each status rolls independently so several can land on one mob. Resistance is NOT rolled (afflictions ignore it).\n"
            "    local applied, last = 0, nil;\n"
            "    local list = {\n"
            "        {EFFECT_POISON,    SUBEFFECT_POISON,    <POISON_CHANCE>, <POISON_POWER>, <POISON_DURATION>},\n"
            "        {EFFECT_PARALYSIS, SUBEFFECT_PARALYSIS, <PARA_CHANCE>,   <PARA_POWER>,   <PARA_DURATION>},\n"
            "        {EFFECT_BIND,      0 --[[no SUBEFFECT_BIND constant in DSP status.lua; confirm animation id]], <BIND_CHANCE>,   <BIND_POWER>,   <BIND_DURATION>},\n"
            "    };\n"
            "    for _, e in ipairs(list) do\n"
            "        if (math.random(0,99) < e[3] and not target:hasStatusEffect(e[1])) then\n"
            "            if (target:addStatusEffect(e[1], e[4], 0, e[5])) then applied = applied + 1; last = e; end\n"
            "        end\n"
            "    end\n"
            "    if (applied == 0) then return 0,0,0; end\n"
            "    return last[2], msgBasic.ADD_EFFECT_STATUS, last[1];\n"
            "end;\n")
    elif spec["kind"] == "drain":
        body = ps._header(item_id, name, "HP Drain", {}) + (
            "function onAdditionalEffect(player,target,damage)\n    local chance = " + str(spec.get("chance", "<CHANCE>")) + ";\n\n"
            "    if (math.random(0,99) >= chance or target:isUndead()) then\n        return 0,0,0;\n    else\n"
            "        local drain = <DRAIN>;\n        local params = {};\n        params.bonusmab = 0;\n"
            "        params.includemab = false;\n        drain = drain * applyResistanceAddEffect(player,target,ELE_DARK,0);\n"
            "        drain = adjustForTarget(target,drain,ELE_DARK);\n"
            "        drain = finalMagicNonSpellAdjustments(player,target,ELE_DARK,drain);\n"
            "        if (drain > target:getHP()) then drain = target:getHP(); end\n"
            "        target:addHP(-drain);\n"
            "        return SUBEFFECT_HP_DRAIN, msgBasic.ADD_EFFECT_HP_DRAIN, player:addHP(drain);\n    end\nend;\n")
    else:
        body = "-- (no generated body: see Wiki note above)\n"
    return "".join("-- " + l + "\n" if not l.startswith("--") else l + "\n" for l in head.splitlines()) + "\n" + body


TWILIGHT_LUA = """-----------------------------------------
-- ID: 19132
-- Item: Twilight Knife
-- Additional Effect: HP, MP or TP Drain
-- Source: BG Wiki -- "5% activation. Activation distribution for HP/MP/TP is 45:45:10.
--         For a max of 45 HP, 45 MP or 10 TP."
-- ASSUMPTION (not stated by any source): the HP/MP amount is uniform 1..45. Verify against retail.
-----------------------------------------
require("scripts/globals/status");
require("scripts/globals/magic");
require("scripts/globals/msg");

-----------------------------------
-- onAdditionalEffect Action
-----------------------------------

function onAdditionalEffect(player,target,damage)
    if (math.random(0,99) >= 5) then
        return 0,0,0;
    end

    local roll = math.random(1,100);
    local params = {};
    params.bonusmab = 0;
    params.includemab = false;

    if (roll <= 45) then -- HP drain
        local drain = math.random(1,45);
        drain = drain * applyResistanceAddEffect(player,target,ELE_DARK,0);
        drain = adjustForTarget(target,drain,ELE_DARK);
        drain = finalMagicNonSpellAdjustments(player,target,ELE_DARK,drain);
        drain = math.min(drain, target:getHP());
        target:addHP(-drain);
        return SUBEFFECT_HP_DRAIN, msgBasic.ADD_EFFECT_HP_DRAIN, player:addHP(drain);
    elseif (roll <= 90) then -- MP drain
        local drain = math.random(1,45);
        drain = drain * applyResistanceAddEffect(player,target,ELE_DARK,0);
        drain = adjustForTarget(target,drain,ELE_DARK);
        drain = finalMagicNonSpellAdjustments(player,target,ELE_DARK,drain);
        drain = math.min(drain, target:getMP());
        target:addMP(-drain);
        return SUBEFFECT_MP_DRAIN, msgBasic.ADD_EFFECT_MP_DRAIN, player:addMP(drain);
    else -- TP drain
        local drain = math.min(10, target:getTP());
        target:addTP(-drain);
        player:addTP(drain);
        return SUBEFFECT_TP_DRAIN, msgBasic.ADD_EFFECT_TP_DRAIN, drain;
    end
end;
"""

APPLY_PY = '''#!/usr/bin/env python3
"""Apply the ready/ repairs to a DSP server tree: python apply.py <server_root> [--dry-run]
Existing scripts that contain behavior are never overwritten; stubs are backed up as .bak-<time>."""
import re, shutil, sys, time
from pathlib import Path
here = Path(__file__).parent
root = Path(sys.argv[1]); dry = "--dry-run" in sys.argv
stamp = time.strftime("%Y%m%d-%H%M%S")
def has_behavior(t):
    t = re.sub(r"--[^\\n]*", "", t)
    return bool(re.search(r"function\\s+on(AdditionalEffect|ItemUse|EffectGain)\\b[^\\n]*\\n\\s*(?!end)\\S", t))
for src in sorted((here / "ready").rglob("*.lua")):
    rel = src.relative_to(here / "ready"); dst = root / rel
    if dst.exists():
        if has_behavior(dst.read_text(errors="ignore")):
            print("SKIP (already has behavior)", rel); continue
        print("REPLACE stub", rel, "(backup)")
        if not dry: shutil.copy2(dst, dst.with_name(dst.name + ".bak-" + stamp))
    else:
        print("ADD", rel)
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
for line in (here / "ready" / "RENAMES.txt").read_text().splitlines():
    if "->" not in line or line.startswith("#"): continue
    a, b = [x.strip() for x in line.split("->")]
    pa, pb = root / a, root / b
    if pa.exists() and not pb.exists():
        print("RENAME", a, "->", b)
        if not dry: pa.rename(pb)
    else:
        print("SKIP rename", a, "(source missing or target exists)")
print("Done. Restart the map server to load the scripts.")
'''


def main():
    rep = ps.build_report(DSP)
    from workbench.editors.items import _editor_impl as impl
    _db = impl._item_db()
    cu = _db.cursor()
    cu.execute("select itemid, level from item_equipment where level > 90")
    OOS.update({i: l for i, l in cu.fetchall()})
    for old in (OUT / "needs-values").glob("*.template"):
        old.unlink()
    for old in (OUT / "ready/scripts/globals/items").glob("*.lua"):
        old.unlink()
    (OUT / "ready/scripts/globals/items").mkdir(parents=True, exist_ok=True)
    (OUT / "needs-values").mkdir(parents=True, exist_ok=True)
    manifest = {"out_of_scope": [], "ready": [], "renames": [], "needs_values": [], "no_data": [], "stubs": []}
    renames = ["# old path -> new path (relative to server root)"]
    for it in rep["broken_items"]:
        iid, name, plan = it["item_id"], it["name"], it["plan"]
        lsb = {k: v for k, v in plan["lsb"].items() if k in ps.LSB_PROC_MODS.values()}
        if plan["state"] == "misnamed":
            r = plan["resolved"]
            renames.append(f"{r['rename_from']} -> {r['rename_to']}")
            manifest["renames"].append({"id": iid, "name": name, **r})
        elif iid in OOS:
            manifest["out_of_scope"].append({"id": iid, "name": name, "level": OOS[iid]})
        elif iid == EREBUS:
            (OUT / f"ready/scripts/globals/items/{name}.lua").write_text(EREBUS_LUA, newline=chr(10))
            manifest["ready"].append({"id": iid, "name": name, "source": "user-supplied wiki formula (5%, TP/14, Empty only)", "assumption": "no resistance/MAB adjustment"})
        elif iid == TWILIGHT:
            (OUT / f"ready/scripts/globals/items/{name}.lua").write_text(TWILIGHT_LUA, newline="\n")
            manifest["ready"].append({"id": iid, "name": name, "source": "BG Wiki", "assumption": "HP/MP amount uniform 1..45"})
        elif plan["state"] == "generate":
            lua = ps.plan_item(iid, name, DSP)["lua"]
            (OUT / f"ready/scripts/globals/items/{name}.lua").write_text(lua, newline="\n")
            manifest["ready"].append({"id": iid, "name": name, "source": "LandSandBoat item_mods (chance/damage), element confirmed by BG Wiki", "lsb": lsb})
        elif iid in SPECS:
            sp = SPECS[iid]
            (OUT / f"needs-values/{name}.lua.template").write_text(lua_template(iid, name, sp, lsb or None), newline="\n")
            manifest["needs_values"].append({"id": iid, "name": name, "kind": sp["kind"], "wiki": sp["wiki"],
                                             "missing": FIELDS[sp["kind"]], "lsb": lsb})
        else:
            manifest["no_data"].append({"id": iid, "name": name, "lsb": lsb})
    (OUT / "ready/RENAMES.txt").write_text("\n".join(renames) + "\n")
    # stubs
    lines = ["# The 29 stub script files", "", "A stub is an empty `onItemUse`/`onItemCheck`. Most are correct as stubs.", ""]
    cos, special = [], []
    for f in rep["weak_script_files"]:
        stem = Path(f["path"]).stem
        if f["state"] not in ("stub", "check-only"):
            continue
        if stem in STUB_SPECIAL:
            special.append((stem, STUB_SPECIAL[stem]))
        else:
            cos.append(stem)
        manifest["stubs"].append({"file": f["path"], "verdict": "special" if stem in STUB_SPECIAL else "cosmetic-intentional"})
    lines += [f"## Intentional, no repair needed ({len(cos)})", "", STUB_VERDICT["cosmetic"], "", ", ".join(f"`{c}`" for c in cos), "",
              f"## Individually reviewed ({len(special)})", ""]
    lines += [f"- **{n}**: {v}" for n, v in special]
    (OUT / "stubs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "apply.py").write_text(APPLY_PY, newline="\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (OUT / "REPORT.md").write_text(ps.render_markdown(rep) + STATUS_SECTION.format(
        ready=", ".join(f"{m['name']}" for m in manifest["ready"]),
        oos=", ".join(f"{m['name']} (L{m['level']})" for m in manifest["out_of_scope"]),
        tpl=", ".join(m["name"] for m in manifest["needs_values"])), encoding="utf-8")
    (OUT / "README.md").write_text(README.format(r=len(manifest["ready"]), n=len(manifest["renames"]),
                                                 t=len(manifest["needs_values"]), d=len(manifest["no_data"]), s=len(cos),
                                                 sp=len(special)), encoding="utf-8")
    print({k: len(v) for k, v in manifest.items()})


STATUS_SECTION = """
## Resolution status (final)

Valhalla is capped at level 90, so items above 90 were not worked on.

- **Ready to apply:** {ready}, plus the `poison_kukri _+1.lua` rename (a complete script saved with a stray space in the filename).
- **Out of scope (level above 90):** {oos}.
- **Awaiting numbers, effect already wired (templates):** {tpl}.
- **Stubs:** 27 of the 29 are intentionally empty (fireworks, fans, bells, masques); Twilight Cloak is working as designed; Rambler's Cloak's latent is already data; Flask of Muting Potion's behavior is unknown. See `stubs.md`.

### Source and assumption notes
- Erebus's Lance: 5% of hits, Empty-system targets only, damage = floor(TP / 14), light animation. Source: user-supplied wiki notes. No resistance or magic-attack-bonus adjustment is applied; TP is read when the proc fires.
- Twilight Knife: 5% activation, HP/MP/TP split 45:45:10, maximums 45/45/10 (BG Wiki). Assumption: HP and MP amounts are uniform from 1 to 45.
- Holy Sword and Holy Sword +1: chance and damage are LandSandBoat's, element confirmed by the wiki. Not retail-verified on this server.
- Mantodea Harpe: "Gravity" is `EFFECT_WEIGHT` in DSP (as `spells/gravity.lua` uses). Chance, power and duration are still needed.
- Cadushi Grip: chance set to 1% from a player observation (about 1 proc in 25 hits). Two observed drains (34 and 43 HP) are not enough to define a range, so the amount is blank.
- Metasoma Katars: the three statuses roll independently so several can land on one mob, with no resistance roll. Ignoring immunity cannot be done from Lua (it is enforced in C++ `StatusEffectContainer`) and would need an engine change. DSP has no `SUBEFFECT_BIND` constant, so the animation id for Bind needs confirming.
- LandSandBoat's data for several of these items is only a placeholder proc type with no numbers, so it is not evidence of the real effect.
- Twilight Knife's DSP data has Quad Attack 10 where the wiki says +3% (a separate data question).
"""

README = """# Item script repair package

Fixes for weapons whose additional effect (mod 431) never procs on the DSP/Valhalla server because the
per-item Lua script is missing, misnamed or a stub. See REPORT.md for the full table.

| Folder / file | Count | What it is |
|---|---|---|
| `ready/` (lua) | {r} | Drop-in scripts. Every value is sourced; assumptions are written in each file's header and in manifest.json. |
| `ready/RENAMES.txt` | {n} | Working script saved under the wrong filename; rename only. |
| `needs-values/` | {t} | Effect and element confirmed by BG Wiki, chance/amount blank because neither LandSandBoat nor the wiki states them. Not loadable until filled. |
| `manifest.json` | | `out_of_scope` lists items above level 90 (server cap), not worked on. |
| | | `no_data` lists {d} item(s) with no source at all. |
| `stubs.md` | | Verdict on the 29 stub files: {s} are intentionally empty (fireworks, fans), {sp} reviewed individually. |

## Apply
```
python apply.py <server_root> --dry-run
python apply.py <server_root>
```
Then restart the map server. Existing scripts with behavior are never overwritten; stubs are backed up.

## Caveats
- LandSandBoat marks several of these as plain DAMAGE with no numbers (a placeholder), so it is not evidence of the real effect; the wiki is.
- Generated values are LSB's or the wiki's and are not retail-verified on this server. Test in game.
- Twilight Knife's DSP data has Quad Attack 10 where the wiki says +3% (separate data question).
"""

if __name__ == "__main__":
    main()
