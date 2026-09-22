#!/usr/bin/env python3
"""
test_backport_lua_convert.py -- regression test for backport_lua_convert.py, so a change to the
converter's regex rules (or to data/dsp_namespace_map.json's shape) can't silently break a family
that was already working. This is NOT a substitute for backport_coverage_check.py (which validates
coverage against real Topaz source) -- this checks the converter's MECHANICS against small, fixed,
hand-written snippets, one per code path, so a future regex change gets caught immediately instead
of waiting for the next coverage run to notice.

No pytest dependency, matching this project's existing test_capture_ingestion.py convention.

Usage:
    py -3 test_backport_lua_convert.py
"""
from __future__ import annotations

import sys

import backport_lua_convert as blc

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  [ok] {name}")
    else:
        print(f"  [FAIL] {name}  {detail}")
        FAILURES.append(name)


def test_simple_prefix_family():
    print("simple_families (prefix substitution, e.g. status/slot/effect)")
    ns_map = blc.load_map()
    src = 'npc:setStatus(tpz.status.NORMAL)\nmob:addStatusEffect(tpz.effect.STUN)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("tpz.status.NORMAL -> STATUS_NORMAL", "STATUS_NORMAL" in res.converted, res.converted)
    check("tpz.effect.STUN -> EFFECT_STUN", "EFFECT_STUN" in res.converted, res.converted)
    check("no leftover tpz. references", "tpz." not in res.converted.replace(
        "-- DSP-PORT-TODO", ""), res.converted)


def test_simple_family_with_renames():
    print("simple_families with explicit renames (inv: TEMPITEMS -> LOC_TEMPITEMS)")
    ns_map = blc.load_map()
    src = 'player:hasItem(id, tpz.inv.TEMPITEMS)\nplayer:hasItem(id2, tpz.inventoryLocation.TEMPITEMS)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("tpz.inv.TEMPITEMS -> LOC_TEMPITEMS", res.converted.count("LOC_TEMPITEMS") == 2, res.converted)
    check("no leftover tpz.inv/inventoryLocation", "tpz.inv" not in res.converted, res.converted)


def test_reshaped_family_job():
    print("reshaped_families (job -> JOBS.X)")
    ns_map = blc.load_map()
    src = 'if player:getMainJob() == tpz.job.COR then\nend\n'
    res = blc.convert(src, ns_map=ns_map)
    check("tpz.job.COR -> JOBS.COR", "JOBS.COR" in res.converted, res.converted)


def test_reshaped_family_path_flag():
    print("reshaped_families (path_flag -> bare PATHFLAG_X, nested 2 levels deep)")
    ns_map = blc.load_map()
    src = 'npc:pathTo(x, y, z, tpz.path.flag.RUN + tpz.path.flag.WALLHACK)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("tpz.path.flag.RUN -> PATHFLAG_RUN", "PATHFLAG_RUN" in res.converted, res.converted)
    check("tpz.path.flag.WALLHACK -> PATHFLAG_WALLHACK", "PATHFLAG_WALLHACK" in res.converted, res.converted)
    check("no leftover tpz.path.flag", "tpz.path.flag" not in res.converted, res.converted)


def test_msg_basic_rename():
    print("reshaped_families (msg_basic table + one real key rename)")
    ns_map = blc.load_map()
    src = 'skill:setMsg(tpz.msg.basic.SKILL_NO_EFFECT)\nskill:setMsg(tpz.msg.basic.MISS)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("SKILL_NO_EFFECT renamed to msgBasic.NO_EFFECT", "msgBasic.NO_EFFECT" in res.converted, res.converted)
    check("MISS keeps its name under msgBasic", "msgBasic.MISS" in res.converted, res.converted)


def test_incompatible_enum_flagged_not_converted():
    print("incompatible_enums (attackType/damageType/takeDamage -- must NEVER auto-convert)")
    ns_map = blc.load_map()
    src = 'target:takeDamage(dmg, mob, tpz.attackType.MAGICAL, tpz.damageType.LIGHTNING)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("attackType left untouched (flagged, not silently rewritten)",
          "tpz.attackType.MAGICAL" in res.converted, res.converted)
    check("damageType left untouched (flagged, not silently rewritten)",
          "tpz.damageType.LIGHTNING" in res.converted, res.converted)
    check("takeDamage call itself flagged", any(
        "takeDamage" in r["text"] for r in res.flagged), res.flagged)
    check("exactly one flagged line for the call", len(res.flagged) == 1, res.flagged)


def test_missing_lua_modules_flagged():
    print("missing_lua_modules (e.g. besieged.capPromotionPoints -- flagged, not guessed)")
    ns_map = blc.load_map()
    src = 'tpz.besieged.capPromotionPoints(v, currentPromotion)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("capPromotionPoints left untouched", "tpz.besieged.capPromotionPoints" in res.converted, res.converted)
    check("flagged with a specific reason (not the generic fallback)",
          any("capPromotionPoints" in reason for fl in res.flagged for reason in fl["reasons"]),
          res.flagged)


def test_whole_call_rename():
    print("whole_call_renames (besieged.getAssaultRank -> getMercenaryRank, assault.chestTrigger -> AssaultLockbox.chestTrigger)")
    ns_map = blc.load_map()
    src = 'local rank = tpz.besieged.getAssaultRank(player)\ntpz.assault.chestTrigger(player, npc, a, b, c, d)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("getAssaultRank -> getMercenaryRank", "getMercenaryRank(player)" in res.converted, res.converted)
    check("chestTrigger -> AssaultLockbox.chestTrigger",
          "AssaultLockbox.chestTrigger(player, npc, a, b, c, d)" in res.converted, res.converted)
    check("no leftover tpz. call sites", not res.unflagged_leftovers(), res.unflagged_leftovers())


def test_method_rename():
    print("method_renames (getCharVar/setCharVar -> getVar/setVar)")
    ns_map = blc.load_map()
    src = 'local v = player:getCharVar("x")\nplayer:setCharVar("x", 1)\n'
    res = blc.convert(src, ns_map=ns_map)
    check("getCharVar -> getVar", ":getVar(" in res.converted, res.converted)
    check("setCharVar -> setVar", ":setVar(" in res.converted, res.converted)


def test_script_shape_entity_table():
    print("script_shape (entity-table style -> bare global functions, hardcoded-name regression guard)")
    ns_map = blc.load_map()
    src = (
        'local entity = {}\n\n'
        'entity.onTrigger = function(player, npc)\n'
        '    entity.helper(npc)\n'
        'end\n\n'
        'entity.helper = function(npc)\n'
        'end\n\n'
        'return entity\n'
    )
    res = blc.convert(src, ns_map=ns_map)
    check("entity.onTrigger -> bare function onTrigger", "function onTrigger(player, npc)" in res.converted, res.converted)
    check("entity.helper(npc) call site -> bare helper(npc)", "helper(npc)" in res.converted and "entity.helper(npc)" not in res.converted, res.converted)
    check("local entity = {} declaration dropped", "local entity = {}" not in res.converted, res.converted)
    check("trailing return entity dropped", "return entity" not in res.converted, res.converted)


def test_script_shape_non_entity_table_name():
    print("script_shape (a DIFFERENT local table name than 'entity', e.g. instance_object -- regression guard for the hardcoded-name bug fixed 2026-09)")
    ns_map = blc.load_map()
    src = (
        'local instance_object = {}\n\n'
        'instance_object.onInstanceCreated = function(instance)\n'
        '    instance_object.spawnLeader(instance)\n'
        'end\n\n'
        'instance_object.spawnLeader = function(instance)\n'
        'end\n\n'
        'instance_object.spawnLeader = spawnLeader\n\n'
        'return instance_object\n'
    )
    res = blc.convert(src, ns_map=ns_map)
    check("instance_object.onInstanceCreated -> bare function", "function onInstanceCreated(instance)" in res.converted, res.converted)
    check("instance_object.spawnLeader(instance) call -> bare spawnLeader(instance)",
          "spawnLeader(instance)" in res.converted and "instance_object.spawnLeader(instance)" not in res.converted, res.converted)
    check("no-op self-assignment (spawnLeader = spawnLeader) dropped",
          "spawnLeader = spawnLeader" not in res.converted, res.converted)
    check("local instance_object = {} declaration dropped", "local instance_object = {}" not in res.converted, res.converted)


def test_script_shape_unrelated_local_table_left_alone():
    print("script_shape (a local table that ISN'T the entity-hook pattern must be left untouched)")
    ns_map = blc.load_map()
    src = (
        'local lookup = {}\n'
        'lookup[1] = "a"\n\n'
        'function onTrigger(player, npc)\n'
        'end\n'
    )
    res = blc.convert(src, ns_map=ns_map)
    check("unrelated 'local lookup = {}' preserved (not a hook table)",
          "local lookup = {}" in res.converted, res.converted)


def test_id_references_nested_shape():
    print("per_zone_id_file_conventions (nested shape, e.g. Nyzul_Isle/IDs.lua)")
    ns_map = blc.load_map()
    src = (
        'local ID = require("scripts/zones/Nyzul_Isle/IDs")\n'
        'player:messageSpecial(ID.text.SOME_MESSAGE)\n'
        'local npcId = ID.npc.SOME_NPC\n'
        'local mobId = ID.mob[1]\n'
    )
    res = blc.convert(src, zone_table="NyzulIsle", id_shape="nested", ns_map=ns_map)
    check("require() has no local capture", "local ID = require" not in res.converted, res.converted)
    check("require() targets the same IDs file", 'require("scripts/zones/Nyzul_Isle/IDs")' in res.converted, res.converted)
    check("ID.text.X -> NyzulIsle.text.X", "NyzulIsle.text.SOME_MESSAGE" in res.converted, res.converted)
    check("ID.npc.X -> NyzulIsle.npcs.X (pluralized)", "NyzulIsle.npcs.SOME_NPC" in res.converted, res.converted)
    check("ID.mob[N] -> NyzulIsle.mobs[N] (pluralized)", "NyzulIsle.mobs[1]" in res.converted, res.converted)
    check("no leftover bare ID. references", "ID." not in res.converted, res.converted)


def test_id_references_flat_shape():
    print("per_zone_id_file_conventions (flat shape, e.g. Alzadaal_Undersea_Ruins/TextIDs.lua -- no zone_table needed)")
    ns_map = blc.load_map()
    src = (
        'local ID = require("scripts/zones/Alzadaal_Undersea_Ruins/IDs")\n'
        'player:messageSpecial(ID.text.SOME_MESSAGE)\n'
    )
    res = blc.convert(src, zone_table=None, id_shape="flat", id_file_hint="TextIDs", ns_map=ns_map)
    check("require() rewritten to TextIDs, no local capture",
          'require("scripts/zones/Alzadaal_Undersea_Ruins/TextIDs")' in res.converted
          and "local ID" not in res.converted, res.converted)
    check("ID.text.X -> bare X (flat shape needs no zone_table -- regression guard for the "
          "early-return bug fixed 2026-09)", "SOME_MESSAGE" in res.converted and "ID.text" not in res.converted,
          res.converted)


def test_unmapped_reference_flagged():
    print("generic fallback (a real tpz.* family the map doesn't know about at all)")
    ns_map = blc.load_map()
    src = 'local x = tpz.totallyMadeUpFamily.SOMETHING\n'
    res = blc.convert(src, ns_map=ns_map)
    check("unmapped reference is flagged, not silently dropped or guessed",
          any("unmapped tpz.* reference" in reason for fl in res.flagged for reason in fl["reasons"]),
          res.flagged)
    check("original tpz. text preserved verbatim next to the flag",
          "tpz.totallyMadeUpFamily.SOMETHING" in res.converted, res.converted)


def test_unflagged_leftovers_empty_on_clean_conversion():
    print("ConversionResult.unflagged_leftovers() -- must be empty when every tpz. mention is either converted or flagged")
    ns_map = blc.load_map()
    src = (
        'require("scripts/globals/status")    -- comment mentioning tpz.status, not a real reference\n'
        'npc:setStatus(tpz.status.NORMAL)\n'
        'tpz.besieged.capPromotionPoints(v, 1)\n'
    )
    res = blc.convert(src, ns_map=ns_map)
    check("comment-only tpz. mention is not treated as a gap", not res.unflagged_leftovers(), res.unflagged_leftovers())


TESTS = [
    test_simple_prefix_family,
    test_simple_family_with_renames,
    test_reshaped_family_job,
    test_reshaped_family_path_flag,
    test_msg_basic_rename,
    test_incompatible_enum_flagged_not_converted,
    test_missing_lua_modules_flagged,
    test_whole_call_rename,
    test_method_rename,
    test_script_shape_entity_table,
    test_script_shape_non_entity_table_name,
    test_script_shape_unrelated_local_table_left_alone,
    test_id_references_nested_shape,
    test_id_references_flat_shape,
    test_unmapped_reference_flagged,
    test_unflagged_leftovers_empty_on_clean_conversion,
]


def main():
    for t in TESTS:
        t()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {', '.join(FAILURES)}")
        sys.exit(1)
    print(f"All {len(TESTS)} test functions passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
