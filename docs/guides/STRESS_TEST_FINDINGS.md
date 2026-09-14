# Stress Test: Converter/Namespace-Map Coverage Outside the Nyzul Package

Per request, ran `backport_lua_convert.py` against every `.lua` file in 6 Assault zones the Nyzul
Isle Investigation package never touched, to find gaps the Nyzul-only dataset couldn't surface:

- Bhaflau_Remnants
- Ilrusi_Atoll
- Lebros_Cavern
- Leujaoam_Sanctum
- Mamool_Ja_Training_Grounds
- Periqia

**377 files processed.** Before this pass, 97 lines carried a leftover `tpz.*` reference the
converter silently failed to flag (a real gap — an unflagged leftover means a human reviewer has no
signal that line needs attention). After the fixes below: **0 unflagged leftovers.** Every remaining
`tpz.*` reference in the converted output is one the converter deliberately flags for human review
(genuine engine gaps, missing Lua modules, or the intentionally-manual `attackType`/`damageType`
call-convention rewrite).

## Real gaps found and fixed in `data/dsp_namespace_map.json`

1. **`tpz.mobMod.*` was never added as a family at all** (only individual members like
   `CHECK_AS_NM` were documented as gaps). Spot-checked 10 members against
   `src/map/mob_modifier.h` — all matched (`SIGHT_RANGE=4`, `NO_DESPAWN=17`, `ROAM_DISTANCE=31`,
   etc). Added as `simple_families.mobMod` (prefix `MOBMOD_`). Found one more real engine gap in
   the process: `MOBMOD_NO_REST` doesn't exist in DSP at all (`Lebros_Cavern/mobs/Brittle_Rock.lua`).

2. **`tpz.animation.*`, `tpz.objType.*`** — never mapped. Confirmed exact matches
   (`ANIMATION_OPEN_DOOR=8`, `TYPE_PC=0x01`, etc, all bare globals in DSP vs Topaz's tables).

3. **`tpz.inventoryLocation.*`** — the map only had the `tpz.inv` alias, not the unaliased spelling
   Topaz itself defines it under (`tpz.inv = tpz.inventoryLocation`). A real zone file
   (`Ilrusi_Atoll/instances/apkallu_seizure.lua`) used the unaliased form and went unflagged.

4. **`tpz.path.flag.*`** — never mapped (nested two levels, needed a reshaped-family rule, not a
   simple prefix). Confirmed against `src/map/ai/helpers/pathfind.h`: `PATHFLAG_RUN=1`,
   `WALLHACK=2`, `REVERSE=4`, plus `SCRIPT=8`/`SLIDE=0x10` that Topaz's own `tpz.path.flag` table
   *doesn't even define* — this reconfirms the already-known live Topaz bug where
   `tpz.path.flag.SCRIPT` is `nil` (see `[[topaz_pathto_wallhack_default]]` memory), found again
   independently via `Ilrusi_Atoll/npcs/QiqirnDiver_Common.lua` and
   `Lebros_Cavern/npcs/Lebros_Apkallu.lua`.

5. **`incompatible_enums.damage_type_family` was missing its entire PHYSICAL half.** Only the
   elemental/MAGICAL name-map existed. Real call sites
   (`Lebros_Cavern/mobs/Qiqirn_Mine.lua`) use `tpz.attackType.PHYSICAL`/`tpz.damageType.NONE`, which
   the map had no entry for at all. Confirmed against `scripts/globals/monstertpmoves.lua`: DSP's
   physical damage names don't even share Topaz's spelling (`MOBPARAM_SLASH` not `SLASHING`,
   `MOBPARAM_PIERCE` not `PIERCING`, `MOBPARAM_H2H` not `HTH`). Added the full name_map.
   `tpz.damageType.ELEMENTAL` (a generic/unused Topaz value per its own source comment) has no DSP
   equivalent at all and is left flagged rather than guessed.

6. **New `missing_lua_modules` section** — 4 genuinely-absent Topaz modules/functions found by
   this test, none with a DSP equivalent anywhere (confirmed by file search, not just grep):
   `tpz.caskets.*`, `tpz.assault.chestTrigger` (used by an `Ancient_Lockbox.lua` npc script that
   repeats across at least 3 non-Nyzul Assault zones), `tpz.besieged.capPromotionPoints`, and
   `tpz.battlefield.HandleLootRolls`. These aren't C++ engine gaps — they're portable Lua the
   converter should never guess at, only flag. See the section's own notes for what each needs.

## Converter code fix

`_build_simple_rules` only auto-applies a `simple_families` entry when the Topaz path is exactly
`tpz.<family>.<KEY>` — a nested path like `tpz.path.flag.<KEY>` needs its own rule (same pattern
already used for `job`/`magic_ele`/etc). Added one for `path_flag`. Also extended
`_flag_unhandled` to read `missing_lua_modules` the same way it already reads `engine_gaps`, so
those get a clear flag reason instead of falling through to the generic "unmapped tpz.* reference".

## What this validates

The map/converter built against a single mission's dataset generalizes well — most families
(`status`, `effect`, `zone`, `slot`, `mod`, `title`, `ki`, `job`, `magic_ele`, `msg_basic`,
`teleport`) needed zero changes across 377 files from 6 unrelated zones. The gaps found were exactly
the kind the design anticipated (new families never exercised by Nyzul, e.g. door animations,
path-walking flags, physical damage types) rather than anything wrong with the existing entries.

**Not done as part of this pass** (out of scope for a coverage stress test, not attempted): actually
porting/writing the 4 `missing_lua_modules` files, or resolving `capPromotionPoints`/`chestTrigger`
into real DSP additions. Flagged and documented for whenever a package that needs them gets built.

Correction from the user after this was first written: files like `Ancient_Lockbox.lua` that repeat
across multiple zones and call the same missing DSP function (`tpz.assault.chestTrigger`) are NOT
centralizable — each copy carries its own zone/mission-specific local values (item tables, rewards,
instance IDs). The missing DSP-side function itself can still be documented as one shared gap, but
every calling zone's own script still needs individual porting.

## Follow-up: `backport_coverage_check.py` (full-tree regression check)

Turned the manual 6-zone stress test into a permanent tool: `backport_coverage_check.py` runs the
converter against every `.lua` file under the real Topaz checkout (`--zone` to scope it, `--report`
to write a Markdown report). Ran it against the FULL `scripts/zones/` tree (all 290 zones, not just
Assault ones): **9,380 files processed, 0 unflagged gaps.** `data/dsp_namespace_map.json` and the
converter now have full coverage for every zone Topaz ships, not just the ones checked by hand.

The ~12k "unmapped tpz.* reference" flags are expected and out of scope, not gaps: sampling them
shows they're almost entirely non-Assault systems this map was never meant to cover (quest/mission
IDs, Regime, Conquest, HELM, Abyssea, Homepoint, etc). Re-run this tool (no args) any time
`dsp_namespace_map.json` or `backport_lua_convert.py` changes, to confirm a change didn't
regress coverage on real files.

