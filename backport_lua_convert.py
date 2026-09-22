"""
backport_lua_convert.py -- Topaz -> DSP Lua conversion for the backport module.

Ported from D:\\Claude\\Topaz-Assault-Backport\\tools\\dsp_backport_toolkit\\convert_lua_to_dsp.py,
built during the Nyzul Isle Investigation backport package. That standalone tool remains the
canonical source for the reasoning behind each mapping (every entry in data/dsp_namespace_map.json
carries an "evidence" field citing the real DSP source file/line that confirmed it -- this module
does not re-derive anything, it only applies what's already been verified).

This does NOT try to be fully automatic for every tpz.* family. It applies only mappings the map
marks "confirmed"/"confirmed_pattern"/a documented reshape, and leaves everything else untouched
but flagged for human review -- including every "engine_gaps" and "incompatible_enums" entry, and
any tpz.* reference the map doesn't know about at all. Extend data/dsp_namespace_map.json (not this
file) when a new zone package surfaces an unmapped family -- check real DSP source the way every
existing entry was checked, don't guess a mapping in to make a flag go away.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parent / "data" / "dsp_namespace_map.json"


def load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Target-flavor fingerprinting -- added 2026-09-13 after an entire session's worth of DSP binding
# work was silently checked against D:\Claude\landsandboat-reference (LandSandBoat/server, a modern
# sol2-based fork) instead of the real production target D:\Claude\old-dsp-reference
# (DarkstarProject/darkstar, 2017-vintage, Lunar-binding-library style) -- nothing in this toolkit
# ever confirmed the configured DSP checkout actually matched what a conversion assumed. This closes
# that gap: fingerprint the real checkout by its binding-registration style before trusting `target`.
# ---------------------------------------------------------------------------
TARGET_FINGERPRINTS = {
    # (relative path to check, marker string, flavor name)
    "old_dsp_reference": ("src/map/lua/lua_baseentity.cpp", "LUNAR_DECLARE_METHOD"),
    "landsandboat": ("src/map/lua/lua_base_entity.cpp", "SOL_REGISTER"),
}


class TargetMismatchError(RuntimeError):
    """Raised when a DSP checkout's real binding style doesn't match the `target` a conversion
    was about to run with -- never silently proceed past this, it's exactly the class of mistake
    that cost an entire session's worth of rework once already."""


def detect_target_flavor(dsp_root: Path) -> str | None:
    """Returns "old_dsp_reference", "landsandboat", or None (neither fingerprint file/marker
    found -- an unrecognized or not-yet-checked-out target, not necessarily an error, but callers
    should treat None as "cannot confirm" rather than assuming either flavor)."""
    for flavor, (rel_path, marker) in TARGET_FINGERPRINTS.items():
        path = dsp_root / rel_path
        if path.exists():
            try:
                if marker in path.read_text(encoding="utf-8", errors="replace"):
                    return flavor
            except OSError:
                continue
    return None


def verify_target_or_raise(dsp_root: Path, target: str) -> None:
    """Call this before running a conversion pass against a real checkout (drivers, the GUI page)
    -- NOT called automatically inside convert() itself, since convert() operates on raw text with
    no filesystem access of its own. Raises TargetMismatchError on a confirmed mismatch; silently
    passes if the flavor can't be determined at all (missing checkout, unrecognized structure) --
    that's a different, separately-visible failure (the file read itself will fail downstream), not
    something this check should mask by being falsely confident either way."""
    detected = detect_target_flavor(dsp_root)
    if detected is not None and detected != target:
        raise TargetMismatchError(
            f"Refusing to convert: {dsp_root} fingerprints as '{detected}' "
            f"(found {TARGET_FINGERPRINTS[detected][1]} in {TARGET_FINGERPRINTS[detected][0]}), "
            f"but this conversion was about to run with target='{target}'. "
            f"Pass target='{detected}' instead, or double-check dsp_root is what you think it is."
        )


LOCAL_TABLE_DECL_RE = re.compile(r"^[ \t]*local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{\}\s*$", re.MULTILINE)
ID_REQUIRE_RE = re.compile(r'local\s+ID\s*=\s*require\("([^"]+)"\)')


def _build_simple_rules(ns_map: dict) -> list[tuple[re.Pattern, object]]:
    rules: list[tuple[re.Pattern, object]] = []

    for family, spec in ns_map.get("simple_families", {}).items():
        if family.startswith("_"):
            continue
        renames = spec.get("renames")
        prefix = spec.get("dsp_prefix")
        if renames:
            for topaz_key, dsp_name in renames.items():
                pattern = re.compile(r"\btpz\." + re.escape(family) + r"\." + re.escape(topaz_key) + r"\b")
                rules.append((pattern, dsp_name))
        if prefix is not None:
            pattern = re.compile(r"\btpz\." + re.escape(family) + r"\.([A-Za-z_][A-Za-z0-9_]*)")
            rules.append((pattern, lambda m, p=prefix: p + m.group(1)))

    reshaped = ns_map.get("reshaped_families", {})
    if "job" in reshaped:
        rules.append((re.compile(r"\btpz\.job\.([A-Za-z_][A-Za-z0-9_]*)"), lambda m: "JOBS." + m.group(1)))
    if "magic_ele" in reshaped:
        rules.append((re.compile(r"\btpz\.magic\.ele\.([A-Za-z_][A-Za-z0-9_]*)"), lambda m: "ELE_" + m.group(1)))
    if "msg_basic" in reshaped:
        msg_renames = {"SKILL_NO_EFFECT": "NO_EFFECT"}
        rules.append((
            re.compile(r"\btpz\.msg\.basic\.([A-Za-z_][A-Za-z0-9_]*)"),
            lambda m: "msgBasic." + msg_renames.get(m.group(1), m.group(1)),
        ))
    if "teleport" in reshaped:
        rules.append((re.compile(r"\btpz\.teleport\.([A-Za-z_][A-Za-z0-9_]*)"), lambda m: "TELEPORT_" + m.group(1).upper()))
    if "nyzul" in reshaped:
        rules.append((re.compile(r"\btpz\.nyzul\b"), "Nyzul"))
    if "anim_table" in reshaped:
        rules.append((re.compile(r"\btpz\.anim\b"), "xi.anim"))
    if "instance_updateInstanceTime" in reshaped:
        rules.append((re.compile(r"\btpz\.instance\.updateInstanceTime\b"), "updateInstanceTime"))
    if "path_flag" in ns_map.get("simple_families", {}):
        rules.append((re.compile(r"\btpz\.path\.flag\.([A-Za-z_][A-Za-z0-9_]*)"), lambda m: "PATHFLAG_" + m.group(1)))

    for method, spec in ns_map.get("method_renames", {}).items():
        if method.startswith("_"):
            continue
        dsp_name = spec.get("dsp_name")
        if dsp_name:
            rules.append((re.compile(r":" + re.escape(method) + r"\("), f":{dsp_name}("))

    for key, spec in ns_map.get("whole_call_renames", {}).items():
        if key.startswith("_"):
            continue
        topaz_call, dsp_call = spec.get("topaz_call"), spec.get("dsp_call")
        if topaz_call and dsp_call:
            rules.append((re.compile(re.escape(topaz_call)), dsp_call))

    # call_reshapes: a real API SHAPE difference (same function name on both sides, different real
    # argument types) -- these can't be a plain string substitution like whole_call_renames since
    # the argument itself varies per call site, so each one needs its own hand-written
    # regex-capture rule here. See data/dsp_namespace_map.json's call_reshapes._readme for why this
    # category exists and what it can't catch on its own (backport_binding_audit.py can't detect a
    # shape mismatch at all -- only a live server crash surfaced the first one, 2026-09-14).
    if "GetNPCByID_instance_arg" in ns_map.get("call_reshapes", {}):
        rules.append((
            re.compile(r"GetNPCByID\(([^,()]+),\s*instance\)"),
            lambda m: f"instance:getEntity(bit.band({m.group(1).strip()}, 0xFFF), TYPE_NPC)",
        ))

    return rules


def _convert_script_shape(text: str) -> str:
    """Topaz's entity-table pattern uses different local variable names depending on the script
    kind -- `entity` for mob/npc scripts, `instance_object` for instance scripts, occasionally
    something else. Detect the actual name from its own `local X = {}` declaration rather than
    hardcoding "entity", so instance files convert too, not just mob/npc files."""
    decls = LOCAL_TABLE_DECL_RE.findall(text)
    if not decls:
        return text
    # A file might declare more than one local table ({} ) for unrelated reasons -- only treat a
    # name as the entity-table if it also appears as `<name>.<hook> = function(` at least once,
    # confirming it's actually used as the Topaz hook-table pattern and not some other local table.
    for table_name in decls:
        hook_re = re.compile(
            r"^(?P<indent>[ \t]*)" + re.escape(table_name) + r"\.(?P<hook>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*function\s*\((?P<args>[^)]*)\)",
            re.MULTILINE,
        )
        if not hook_re.search(text):
            continue
        text = hook_re.sub(lambda m: f"{m.group('indent')}function {m.group('hook')}({m.group('args')})", text)
        # Any remaining `table_name.something(...)` (a same-table function calling a sibling hook,
        # e.g. instance_object.finishPickSetPoint(instance) from within pickSetPoint) becomes a
        # bare call too, now that the hooks themselves are bare global functions.
        text = re.sub(r"\b" + re.escape(table_name) + r"\.([A-Za-z_][A-Za-z0-9_]*)\b", r"\1", text)
        text = re.sub(r"^[ \t]*local\s+" + re.escape(table_name) + r"\s*=\s*\{\}\s*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[ \t]*return\s+" + re.escape(table_name) + r"\s*\n?", "", text, flags=re.MULTILINE)
    # Cleanup: `table_name.spawnRandomLeader = spawnRandomLeader` (exposing an already-local
    # function as a table member, e.g. for a would-be external caller) collapses to a no-op
    # self-assignment (`spawnRandomLeader = spawnRandomLeader`) once the table prefix is stripped
    # above -- harmless (valid Lua, just redundant) but safe and worth dropping outright.
    text = re.sub(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\1\s*\n", "", text, flags=re.MULTILINE)
    return text


CMDPROPS_DECL_RE = re.compile(r"^cmdprops\s*=", re.MULTILINE)


def _convert_command_shape(text: str) -> str:
    """Topaz's scripts/commands/*.lua files use bare globals (`cmdprops = {...}` / `function
    onTrigger(...) ... end`, no `return`). DSP's command_handler.cpp (confirmed by reading it
    directly: `commandTable.get<sol::optional<sol::table>>("cmdprops")` /
    `commandTable.get<sol::optional<sol::function>>("onTrigger")`) requires the file's require()
    to return a table carrying those two fields -- every real DSP command file (confirmed via
    landsandboat-reference's own scripts/commands/animatenpc.lua, gotoid.lua) uses:
        local commandObj = {}
        commandObj.cmdprops = {...}
        commandObj.onTrigger = function(...) ... end
        return commandObj
    As written, a Topaz-shaped command file would not register in DSP at all -- this is a hard
    structural requirement, not a style nuance. Only fires when a bare top-level `cmdprops =` is
    found (the unambiguous signature of this file kind); everything else (mob/npc/instance
    scripts) is untouched."""
    if not CMDPROPS_DECL_RE.search(text):
        return text

    text = re.sub(r"^cmdprops(\s*=)", r"commandObj.cmdprops\1", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"^function\s+onTrigger\s*\(", "commandObj.onTrigger = function(", text, count=1, flags=re.MULTILINE)
    # Any other bare top-level helper function (e.g. every file's own `error(player, msg)`)
    # becomes a local function, matching DSP's own real convention for the same helper.
    text = re.sub(
        r"^function\s+(?!onTrigger\b)([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"local function \1(",
        text, flags=re.MULTILINE,
    )
    text = re.sub(r"^commandObj\.cmdprops", "local commandObj = {}\ncommandObj.cmdprops", text, count=1, flags=re.MULTILINE)
    text = text.rstrip("\n") + "\n\nreturn commandObj\n"
    return text


def _convert_id_requires(text: str, id_file_hint: str | None) -> str:
    def repl(m: re.Match) -> str:
        path = m.group(1)
        if id_file_hint:
            path = re.sub(r"/IDs$", f"/{id_file_hint}", path)
        return f'require("{path}")'

    return ID_REQUIRE_RE.sub(repl, text)


def _convert_id_requires_zones_table(text: str, zone_enum: str | None) -> str:
    """shape_C (per_zone_id_file_conventions.shape_C_zones_table_global): DSP itself consumes its
    IDs.lua as `local ID = zones[xi.zone.<ZONE_ENUM>]`, not a require() returning a captured table.
    Only the require-line shape changes -- ID.text.X/ID.mob[N].X/ID.npc.X call sites are left
    completely untouched (see convert()'s docstring and dsp_namespace_map.json's shape_C entry)."""
    if not zone_enum:
        return text

    def repl(m: re.Match) -> str:
        return f"local ID = zones[xi.zone.{zone_enum}]"

    return ID_REQUIRE_RE.sub(repl, text)


def _convert_id_references(text: str, zone_table: str | None, id_shape: str | None) -> str:
    if id_shape == "zones_table":
        # No rewriting at all -- DSP's own shape_C IDs.lua already uses singular ID.text/ID.mob/
        # ID.npc, identical to Topaz's own shape, so ID.* call sites need zero changes here.
        return text
    if id_shape == "nested":
        if not zone_table:
            return text
        text = re.sub(r"\bID\.text\.", f"{zone_table}.text.", text)
        text = re.sub(r"\bID\.npc\.", f"{zone_table}.npcs.", text)
        text = re.sub(r"\bID\.mob\[", f"{zone_table}.mobs[", text)
        text = re.sub(r"\bID\.mob\.", f"{zone_table}.mobs.", text)
        # Bare whole-table references (e.g. `updateInstanceTime(instance, elapsed, ID.text)`,
        # passing the table itself as an argument, not one of its keys) -- must run AFTER the
        # dotted-key substitutions above so `ID.text.X` isn't half-matched by this broader pattern.
        text = re.sub(r"\bID\.text\b(?!\.)", f"{zone_table}.text", text)
        text = re.sub(r"\bID\.npc\b(?!\.)", f"{zone_table}.npcs", text)
        text = re.sub(r"\bID\.mob\b(?![.\[])", f"{zone_table}.mobs", text)
    elif id_shape == "flat":
        # Flat (TextIDs.lua) shape has no wrapping table at all, so no zone_table is needed here --
        # ID.text.X always becomes bare X regardless. ID.npc.*/ID.mob.* still have no established
        # DSP convention for this shape (see per_zone_id_file_conventions.shape_B_flat_bare_globals)
        # and are deliberately left alone -- they get flagged by _flag_unhandled instead.
        text = re.sub(r"\bID\.text\.([A-Za-z_][A-Za-z0-9_]*)", r"\1", text)
    return text


def _build_known_reason_patterns(ns_map: dict) -> list[dict]:
    """Every pattern _flag_unhandled checks for, each carrying WHERE it came from in the map and
    the real evidence/fix text -- so a flagged line's reason can show a human the actual citation
    (map section, source file, fix note) instead of a bare regex string. Used by both
    _flag_unhandled (for the plain-text reason list) and the GUI page (for an inline evidence
    panel next to each flagged line)."""
    patterns: list[dict] = []

    for key, spec in ns_map.get("engine_gaps", {}).items():
        if key.startswith("_"):
            continue
        topaz_ref = spec.get("topaz")
        if topaz_ref and topaz_ref.startswith("tpz."):
            patterns.append({
                "pattern": re.escape(topaz_ref.split("(")[0]),
                "section": "engine_gaps", "key": key,
                "label": f"engine gap: {topaz_ref}",
                "evidence": spec.get("status", ""), "fix": spec.get("fix", ""),
                "checked": spec.get("checked", ""),
            })

    dtf = ns_map.get("incompatible_enums", {}).get("damage_type_family")
    if dtf:
        for pat, label in [
            (r"tpz\.attackType\.", "incompatible enum: tpz.attackType.*"),
            (r"tpz\.damageType\.", "incompatible enum: tpz.damageType.*"),
            (r"[a-zA-Z_][a-zA-Z0-9_]*:takeDamage\(", "incompatible call convention: :takeDamage(...)"),
        ]:
            patterns.append({
                "pattern": pat, "section": "incompatible_enums", "key": "damage_type_family",
                "label": label, "evidence": dtf.get("warning", ""),
                "fix": dtf.get("call_convention_change", ""), "checked": dtf.get("source", ""),
            })

    for key, spec in ns_map.get("missing_lua_modules", {}).items():
        if key.startswith("_"):
            continue
        topaz_call = spec.get("topaz_call")
        if topaz_call and topaz_call.startswith("tpz."):
            patterns.append({
                "pattern": re.escape(topaz_call.split("(")[0]),
                "section": "missing_lua_modules", "key": key,
                "label": f"missing Lua module: {topaz_call}",
                "evidence": spec.get("status", ""), "fix": spec.get("fix", ""),
                "checked": spec.get("checked", ""),
            })

    return patterns


def _flag_unhandled(text: str, ns_map: dict, id_shape: str | None = None) -> tuple[str, list[dict]]:
    known = _build_known_reason_patterns(ns_map)

    lines = text.split("\n")
    out_lines = []
    flagged = []
    for lineno, line in enumerate(lines, 1):
        reasons: list[str] = []
        citations: list[dict] = []
        for entry in known:
            if re.search(entry["pattern"], line):
                reasons.append(entry["pattern"])
                citations.append(entry)
        if "tpz." in line and not reasons:
            reasons.append("unmapped tpz.* reference")
            citations.append({
                "section": None, "key": None, "label": "unmapped tpz.* reference",
                "evidence": "No entry in dsp_namespace_map.json covers this family/call at all.",
                "fix": "Check real DSP source for the equivalent, then add a new "
                       "simple_families/reshaped_families/engine_gaps/missing_lua_modules entry "
                       "with the same evidence discipline as every existing entry -- never guess.",
                "checked": "",
            })
        if id_shape != "zones_table" and re.search(r"\bID\.(text|npc|mob)\b", line):
            reasons.append("unconverted ID.* reference -- specify zone_table/id_shape")
            citations.append({
                "section": "per_zone_id_file_conventions", "key": None,
                "label": "unconverted ID.* reference",
                "evidence": "zone_table/id_shape wasn't given to convert() (or the wrapping table "
                            "name isn't known yet for this zone in DSP).",
                "fix": "Check whether scripts/zones/<Zone>/IDs.lua or TextIDs.lua already exists in "
                       "the target DSP checkout, and which shape it uses, then re-run with the "
                       "zone_table/id_shape/id_file_hint fields filled in.",
                "checked": "",
            })
        if reasons:
            indent = re.match(r"^(\s*)", line).group(1)
            out_lines.append(f"{indent}-- DSP-PORT-TODO: {'; '.join(reasons)} -- see data/dsp_namespace_map.json")
            flagged.append({"line": lineno, "text": line.strip(), "reasons": reasons, "citations": citations})
        out_lines.append(line)
    return "\n".join(out_lines), flagged


@dataclass
class ConversionResult:
    converted: str
    flagged: list[dict] = field(default_factory=list)

    def unflagged_leftovers(self) -> list[dict]:
        """Lines in `converted` that still mention `tpz.` but were NOT covered by a flag on that
        same line text, and aren't a comment-only mention. A non-empty result here means the
        namespace map/converter has a real coverage gap -- either a family that needs a new
        simple_families/reshaped_families/engine_gaps/missing_lua_modules entry, or a converter
        rule that isn't matching text it should. Used by backport_coverage_check.py to regression-
        test the map/converter against the full Topaz zone tree."""
        flagged_texts = {fl["text"] for fl in self.flagged}
        out = []
        for i, line in enumerate(self.converted.splitlines(), start=1):
            if "tpz." not in line:
                continue
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            if stripped in flagged_texts:
                continue
            out.append({"line": i, "text": stripped})
        return out


def convert(text: str, zone_table: str | None = None, id_shape: str | None = None,
            id_file_hint: str | None = None, ns_map: dict | None = None,
            target: str = "old_dsp_reference") -> ConversionResult:
    """Convert one Lua file's text from Topaz's entity-table style to DSP's global-function
    style, applying every confirmed namespace mapping in data/dsp_namespace_map.json.

    target: "old_dsp_reference" (DEFAULT, and the REAL target -- Valhalla runs
      D:\\Claude\\old-dsp-reference, DarkstarProject/darkstar 2017-vintage) or "landsandboat"
      (D:\\Claude\\landsandboat-reference, a modern sol2-based fork this project does NOT target,
      kept only for reference -- see data/dsp_namespace_map.json's _CORRECTION_NOTICE_2026-09-13).
      CRITICAL: _convert_command_shape (commandObj wrapper) and id_shape="zones_table" (the
      `zones[xi.zone.X]` wrapping-table shape) are BOTH landsandboat-only structural requirements
      that do NOT apply to old_dsp_reference -- old-dsp-reference's real commands use bare
      cmdprops/onTrigger globals (matching Topaz's own convention, confirmed via
      src/map/commandhandler.cpp), and its zone id files (where a consolidated IDs.lua exists at
      all, e.g. Periqia/Lebros_Cavern/Leujaoam_Sanctum) are bare capitalized globals consumed
      directly with NO zones[] indirection. Both are skipped by default; pass target="landsandboat"
      to restore the old (wrong-for-Valhalla) behavior for LandSandBoat-targeted work.

    zone_table: the zone's real DSP id-table global (e.g. "NyzulIsle"), if known -- see
      per_zone_id_file_conventions in the map. None leaves ID.* references untouched (and flagged).
    id_shape: "nested" (DSP wraps text/npc/mob under one zone table) or "flat" (bare globals,
      TextIDs.lua style) -- see the same map section. Required if zone_table is given.
      "zones_table" is landsandboat-only (see `target` above) and is ignored when
      target="old_dsp_reference".
    id_file_hint: "IDs" or "TextIDs" -- rewrites the require() path's trailing segment to match
      what DSP actually calls the file for this zone.

    2026-09-13 namespace full-remediation note: data/dsp_namespace_map.json's new
    "namespace_family_index_2026-09-13" section is the authoritative tpz.*/xi.* family catalogue
    for target=old_dsp_reference (supersedes simple_families/reshaped_families above for this
    target), but is NOT YET wired into this function's automatic conversion path below -- the
    families it documents as "fixed" were fixed by hand across the 8 packages' lua-dsp/ trees in
    that pass, not by re-running this converter. A future session should decide whether to extend
    _convert_simple_families()/this docstring's data-driven path to read that section directly, or
    leave per-family fixes manual (most remaining tpz.*/xi.* hits are one-off, not a repeating
    mechanical pattern this generic converter was designed for). The one exception is the
    zone-id "flat" shape (id_shape="flat", already implemented below) -- confirmed 2026-09-13 by
    reading old-dsp-reference/scripts/zones/Ilrusi_Atoll/TextIDs.lua directly to be the REAL shape
    for Ilrusi_Atoll/Mamool_Ja_Training_Grounds/Aht_Urhgan_Whitegate and mercenary_rank_promotions's
    other 6 zones -- that restructuring should use this existing "flat" path, not new tooling.

    2026-09-13 zone-shape restructuring pass (follow-up, completed): the "flat" path above was
    used AS-IS for the ID.text.X -> bare X rewrite across all 7 affected zones (Ilrusi_Atoll,
    Mamool_Ja_Training_Grounds, Aht_Urhgan_Whitegate, Bhaflau_Thickets, Mount_Zhayolm,
    Caedarva_Mire, Wajaom_Woodlands -- Al_Zahbi/Nashmau needed no changes, see
    per_zone_flat_id_shape_findings_2026-09-13 in the map). It was NOT extended for ID.mob[N].X/
    ID.npc.X: confirmed by reading real old-dsp-reference consumer files (Ilrusi_Atoll/npcs/
    Rune_of_Release.lua, Ancient_Lockbox.lua) that this shape has no shared id-table convention for
    non-text ids at all -- every real mob/npc numeric id is hardcoded as a raw literal directly in
    each consumer script. That substitution is inherently value-dependent (needs the actual old
    IDs.lua's real numeric mapping, not a generic rename), so it was done with a one-off
    per-zone script (extract name->value pairs, substitute at each call site, hand-verify every
    resulting file) rather than by extending this generic converter -- see the zone-shape
    restructuring report for the exact method. A future session doing another "flat"-shape zone
    should follow the same method, not assume this function alone suffices.
    """
    if ns_map is None:
        ns_map = load_map()

    result = _convert_script_shape(text)
    if target == "landsandboat":
        result = _convert_command_shape(result)
    if id_shape == "zones_table" and target == "landsandboat":
        result = _convert_id_requires_zones_table(result, zone_table)
    else:
        result = _convert_id_requires(result, id_file_hint)
    result = _convert_id_references(result, zone_table, id_shape)
    for pattern, repl in _build_simple_rules(ns_map):
        result = pattern.sub(repl, result)
    result, flagged = _flag_unhandled(result, ns_map, id_shape)
    return ConversionResult(converted=result, flagged=flagged)
