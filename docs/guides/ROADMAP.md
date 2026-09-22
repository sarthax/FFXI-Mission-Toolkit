# Mission Toolkit — Roadmap

No prior phased plan document existed for this project (checked `mission_toolkit/` for any
`*plan*`/`*PHASE*` file and found none) — this is the first one, written 2026-09-06 to capture
what's done and lay out what's next per the user's request to track future feature phases.

## Completed

- **2026-09-21: Zone Plot (`zone_plot.py`/`zone_edit.py`/`gui/templates/zone_plot.html`) — server-
  agnostic live level editor, Add-tab UX overhaul, and a zone-switch rendering race fix.** Zone
  Plot (View/Edit/Add/Backups on `/zoneplot`) draws every mob/NPC/door spawn row of a zone from
  the *live* server DB over the real client mesh + navmesh, and can add/move/delete rows straight
  against MariaDB with an auto-backup per edit. It was hardcoded to `C:\topaz`; this pass made it
  target either Topaz or a real DSP checkout (`old-dsp-reference`), picked per-request via a new
  `zoneplot_server` setting so switching servers takes effect immediately, no restart:
  - `zone_plot._db()`/`_server_root()`/`_conf_path()` resolve the live DB from either server's conf
    file (Topaz `conf/map.conf` vs DSP `conf/map_darkstar.conf` — same `key: value` line format).
  - Real schema drift handled explicitly rather than assumed away: DSP's `mob_groups` has no
    `name` column at all (group identity is `poolid`-only) — `zone_data()`, `zone_edit.catalogue()`,
    and `zone_edit.add_entity()` all needed a schema-detection fallback to DSP's `mob_spawn_points.
    mobname` instead. DSP's `instance_list` also has no reliable "which zone does this instance run
    in" column (`entrance_zone` means *enter from*, not *runs in* — e.g. Nyzul Isle enters from
    zone 72 but runs in 77) — fixed by deriving each instance's real zone from decoding one of its
    own `instance_entities` ids (`((id-16777216)>>12)&511`), the same formula already used for
    `mob_spawn_points`/`npc_list` zone filtering, instead of trusting either column name.
  - Add tab reworked per user feedback that it was "cumbersome": a persistent cyan Three.js marker
    now shows exactly where a click or drag-and-drop set the pending X/Y/Z (previously nothing
    visually confirmed a drop landed), clicking anywhere in the viewport sets position without a
    separate "enable placement" checkbox, a continuous cursor-coordinate readout appears on hover
    over empty mesh/navmesh, and adding an entity now flies the camera to and selects it instead of
    leaving the view unchanged.
  - Fixed a real rendering race: `loadNav()` ran un-awaited with no staleness check, so switching
    zones while a slow `navmesh.bin` fetch for the *previous* zone was still in flight would apply
    late and silently overlay that old zone's navmesh onto the new one — including a "no nav" zone
    that should have shown none at all. Fixed with a `loadGen` generation counter threaded through
    every async step of `loadZone()` (`data.json`, `computeReach()`, `loadZMesh()`, `loadNav()`);
    each discards its own result if the user has since switched zone/instance away from it.
  - Fixed OrbitControls' default right-drag pan, which scales the pan offset by camera-target
    distance (its normal, intentional perspective-camera behavior) — at a close zoom that distance
    is tiny, so a full drag barely moved anything ("zoom is inversely proportional to how much the
    map moves" per report). Countered by setting `controls.panSpeed = BASE_PAN/distance` at the
    start of each drag, canceling that built-in scaling so pan covers roughly the same world-space
    distance regardless of zoom level. Also raised `zoomSpeed` (1 → 2.5) and lowered `minDistance`/
    camera near-plane (0.1 → 0.05/0.01) — zooming in on a large zone needed many scroll ticks and
    could start clipping into the near plane before getting close, which read as a hard zoom cap.

- **2026-09-15: content-duplication checking, closing a real gap id-collision checking left open**
  — a real incident (`D:\Claude\Topaz-Assault-Backport\reports\dsp_repair_2026-09-15\
  INCIDENT_REPORT.md`) showed multiple Topaz→DSP backport passes, run at different times, each
  minting a FRESH, genuinely-unused `groupid` for `mob_groups` content a prior pass had already
  backported. Every pass used a numeric range that was genuinely free, so the existing
  `check_id_collisions()` reported "clear" every single time — it structurally cannot catch "this
  content already exists under a different id," only "this exact id is taken." 195 live rows ended
  up silently pulling wrong loot as a result (the live-wired duplicate used a raw, unconverted
  `dropid` that collided with unrelated DSP-native content, while the correctly-remapped duplicate
  from an earlier pass sat orphaned with zero spawns). Repaired live (195 rows fixed, 270 harmless
  duplicates cleaned up, verified `0` live-wrong-loot cases remain) and closed at the tooling level:
  - `backport_sql_convert.py`: new `CONTENT_KEY_COLUMNS` map (currently `mob_groups` →
    `(poolid, zoneid)`, its real identity per `dsp_sql_schema_map.json`'s own composite-PK note)
    and `check_content_duplication()`, the offline (indexed-snapshot) counterpart to
    `check_id_collisions()`.
  - `backport_sql_live_check.py`: `check_live_content_duplication()` (classifies each match by real
    live impact — `harmless` / `live_conflict` / `orphaned` / `ambiguous`, using a real
    `mob_spawn_points` join, not just presence/absence) and a new `--scan-duplicates TABLE` flag
    for a standalone, periodic full-DB health check independent of any candidate package.
  - `backport_package.py`: wired into the existing `run_id_collision_checks()`/`build_report()`
    flow automatically for any table in `CONTENT_KEY_COLUMNS` — a duplicate now fails the overall
    "Clean" verdict the same way a real id-collision already did.
  - GUI: both `/backport/sql-convert` and `/backport/package` now render a "Content-duplication
    check" section alongside the existing id-collision section.
  - Validated end-to-end against the real live DSP database, not just the offline snapshot: the
    live scan correctly reports `0` live-wrong-loot cases post-repair (distinguishing the 27
    remaining duplicate `(poolid, zoneid)` pairs as legitimate same-poolid-different-in-world-name
    variants, a real, common FFXI pattern — not a bug), and re-running the full package check
    against `nyzul_isle_investigation` correctly flags that re-applying it today would recreate the
    incident (97 of 112 content keys already exist live).

- **2026-09-08: dedicated `.venv` for this toolkit's Python dependencies** — real incident, not
  precautionary: `luaparser>=4.0` (needed by `xi-events-py`'s event decompiler) permanently pins
  `antlr4-python3-runtime==4.13.2` — confirmed every `luaparser` release since 4.0 pins the exact
  same version, no compatible alternative exists — which silently broke `omegaconf` (a real,
  unrelated package pinned to `antlr4-python3-runtime==4.9.*`) the first time this was installed
  straight into a shared system Python. `setup.bat`/`start.bat` now create and use a dedicated
  `.venv/` for every Python invocation, so this toolkit's own dependencies can never conflict with
  anything else already on a user's machine again. `reset_install.py`/`DIST_PACKAGING.md` updated
  to treat `.venv/` as regenerable (strip + recreate), same as the other fetched data. Also fixed a
  real bug this surfaced in `reset_install.py` itself: its `__pycache__` scan was separately
  listing 100+ nested cache dirs already inside `.venv` (or any other whole-directory strip
  target) as their own redundant entries, instead of recognizing they're already covered.
- **2026-09-08: LSB-primary core module + Topaz/DSP backport module** (see `CORE_AGNOSTIC_DESIGN.md`
  for the full design and phasing). The toolkit's default target flipped from Topaz-primary to
  LSB-primary, with Topaz/DSP demoted to an optional backport module:
  - Phase 1: `build_sql_index.py` rewritten to parse the bundled LandSandBoat checkout instead of a
    Topaz server (`sql_*` table names/shapes kept identical so no core-module page's queries needed
    to change, just their real underlying data source).
  - Phase 2: new `build_topaz_index.py`, structurally parallel to `build_dsp_index.py`, giving the
    backport module its own `topaz_*` tables.
  - Phase 3: ID Drift's diff direction flipped (Topaz/DSP vs. LSB as baseline, not the reverse); its
    nav entry now gated behind a real `backport_enabled()` check (a real Topaz/DSP checkout present
    on disk, not just a saved setting string).
  - Phase 4: `setup.bat` un-hardcoded (LandSandBoat fetch now required/reordered before it's needed;
    Topaz path now optional/skippable), homepage stat-row labels corrected.
  - Follow-up: `build_database.py` had its own separate, previously-missed hardcoded Topaz path —
    `items_ours`/`keyitems_ours` now genuinely read LSB's own `item_basic.sql`/
    `scripts/enum/key_item.lua` (`xi.keyItem`). Added `topaz_keyitems` so the backport module keeps
    real keyitem-drift coverage (parallel to the existing `topaz_item_basic`). Fixed two comparison
    panels that had silently started comparing LSB against itself once the primary source changed
    underneath them without their own update: the Item Browser's `/items/{id}` detail page's
    "backport source" panel (was showing LSB data twice under two different labels; now shows real
    Topaz data, gated behind `backport_enabled()`) and ID Drift's item/keyitem categories (now join
    `topaz_item_basic`/`topaz_keyitems` instead of `items_ours`/`keyitems_ours`).
  - Real verified drift found once the fix was in place: 58 real Topaz-vs-LSB item id mismatches
    (e.g. Almace 20653→19458, Armageddon 21264→19469 — relic weapons with genuinely different ids
    between forks), confirming the comparison was actually broken before (silently 0 results) and
    is now surfacing real data.
- **2026-09-08: Capture ingestion, format coverage + regression fixtures**
  - Real **CapLog** parser built — a merged multi-addon session-log format, confirmed directly
    against the real Windower addon source (`reference_addons/wiggo-addons-1/capture/*.lua`), not
    guessed from samples. Extracts ID-View events, HP-Track kills, and genuinely unique in-game
    chat/system text (item drops, mission announcements, combat log — not carried by any other
    capture format) into their real home tables (`capture_events`, `capture_hp_events`, and a new
    `capture_caplog_chat` table), with a fixed seq offset (`CAPLOG_SEQ_BASE`) so it can never
    collide with the same zone's data already ingested from a sibling standalone file in the same
    capture — verified live against a real capture bundle that has both.
  - Three more real capturer-layout variants fixed: `npclogger/logs/` missing the optional capturer
    subfolder its `tables/`/`database/` siblings already had; flat `eventview/raw.log`/`simple.log`
    and `packetviewer/full.log`/`incoming.log`/`outgoing.log` combined-session dumps now recognized
    as real, deliberately-unattributable duplicates (reported "ok, not ingested" rather than a false
    "not a recognized capture-log format" failure).
  - A real double-processing bug fixed: `ingest_eventview`'s dispatch pattern
    (`EventView/<capturer>/<Zone>.log`) was too broad and also matched
    `eventview/simple/<Zone>.log`/`eventview/raw/<Zone>.log` (treating "simple"/"raw" as if they
    were a capturer name), silently running the same file through the wrong parser a second time —
    showed up as a confusing duplicate "0 rows" entry right after a real successful import.
  - A real silent-zero bug fixed in `ingest_hptrack`: it only ever tried the older `Defeated
    <name>: X~YHP` line shape. A real, common newer HPTrack version writes `[HP Track] Killed <id>
    (<name>): X~YHP` instead — confirmed both shapes are genuinely real (57 vs. 80 files sampled
    across the capture corpus, not one replacing the other) — every real hptrack file in the newer
    format was silently returning 0 real kills until this fix.
  - A real third CapLog variant built: a titlecase `CapLog/` folder (not lowercase `caplog/`),
    confirmed across 88 real captures from a "Thris" capturer, carrying a genuinely different
    `[EView]` packet-block shape (short time-only header + a separate comma-separated field line)
    from the other CapLog variant's single-line `[Tag] message` shape — same real EventView packet
    taxonomy `ingest_eventview` already knows (`CEventPacket`, `GP_SERV_COMMAND_EVENTNUM`, etc.),
    routed into the same `capture_eventview` table. A third regression fixture
    (`thris_ilrusi_atoll/`) added alongside it.
  - A zip-directory-entry bug fixed: `Source`'s `.zip` branch was including zip's own directory
    entries (real zero-content records ending in `/`) in its file listing, alongside the `.7z`/
    folder branches which already filtered to real files only — a real 25-entry capture zip had
    exactly 15 such directory entries, all misreported as "failed" imports.
  - Permanent regression-test fixtures added (`test_fixtures/captures/`, `test_capture_ingestion.py`)
    — two real, trimmed-of-nothing capturer trees (Foxmulder- and Tacocat-style layouts) with a
    standalone test script (no pytest dependency) that fails loudly on any unexpected format
    failure, so a fix for one capturer's layout can't silently re-break another's the way
    `npclogger/logs/` regressed before this.
  - A conservative content-sniffing fallback: a file matching no known path pattern now gets its
    content checked against a short list of already-proven format signatures (never used to attempt
    real ingestion, only diagnostics) — upgrades a bare "not a recognized capture-log format" into
    "content looks like a real X, may need a parser added or an existing one's path pattern updated."
  - **Capture Query & Export**: a general ad-hoc search page (`/captures/query`) across every real
    `capture_*` table (not just a capture's own summarized/truncated detail view), filterable by
    table/capture id/text, with a CSV export of the current filtered result set
    (`/captures/query.csv`). A capture's own detail page gained a one-click "export all data (.zip)"
    link (`/captures/{id}/export.zip`) — one CSV per `capture_*` table that actually has rows for
    that capture, empty tables skipped rather than shipped blank.
  - Add Files page's two upload options relabeled and visually separated ("Option A — pick
    individual files" vs. "Option B — pick a whole folder, use this one if unsure") — previously two
    identical unlabeled "Choose Files" buttons with only a bare "or" between them.
  - `reset_install.py`/`reset_install.bat` added — strips an install back to source-only (database,
    backups, generated reports, and the three re-fetchable checkouts: LandSandBoat, FFXI-DATS,
    FFXI-Resources-dist) for testing `setup.bat` from scratch, matching `DIST_PACKAGING.md`'s
    confirmed strip list exactly. Dry-run by default; requires `--i-am-sure` to actually delete
    (same double-confirmation convention `build_database.py --wipe-everything` already uses), backs
    up the DB first unless told not to, and never touches `test_fixtures/` or any hand-authored
    source file.
  - `addon_tools.py` added — packages real, already-fetched data one install has (e.g. the real
    BG-Wiki page dump, ~19MB/47,608 pages) into a small, checksummed, portable `.zip` under
    `addons/` that another install can extract via `py -3 addon_tools.py install <name>` instead of
    regenerating it the slow way (a real network scrape, in BG-Wiki's case). Verifies a real sha256
    per file on install, refuses to silently overwrite a destination file with different real
    content unless `--force`, and skips cleanly (no-op) when the destination already matches.
    Complements `install_external_tools.py` (which fetches from a known public URL) rather than
    replacing it — this is for real local data with no public single-file source to re-fetch from.
- **2026-09-12: Backport module — Topaz→DSP Lua converter, namespace map, and coverage regression
  check** (see `STRESS_TEST_FINDINGS.md`):
  - `backport_lua_convert.py` + `data/dsp_namespace_map.json` — a config-driven Topaz→DSP Lua
    converter, live at `/backport/lua-convert` (gated behind `backport_enabled()`, same as ID
    Drift). Applies every namespace mapping confirmed against real DSP source (simple prefix
    families, reshaped tables, incompatible-enum name-maps, method/whole-call renames, script-shape
    conversion, per-zone ID-file conventions) and explicitly flags anything unmapped or a known
    engine gap for human review rather than guessing a conversion. Homed here (superseding an
    earlier standalone tool in `Topaz-Assault-Backport/tools/dsp_backport_toolkit/`, now marked
    `SUPERSEDED.md`) per the user's direction to build on this toolkit's existing multi-codebase
    (DSP/Topaz/LSB) infrastructure instead of a one-off script.
  - Proven against a real production package: the full **Nyzul Isle Investigation** backport — 194
    files converted mechanically with zero unexpected flags, 10 more requiring hand judgment and
    fully documented (`MERGE_DECISIONS.md`), surfacing two real bugs in the process (a live
    undeclared-`party` global in DSP's own shipped `_20m.lua`, silently skipping all party-member
    instance entry; and an operator-precedence regression in Topaz's own independent rewrite of the
    same file, deliberately not ported).
  - `backport_coverage_check.py` — turned a manual one-off 6-zone stress test into a permanent
    regression check: runs the converter against every real `.lua` file under the actual Topaz
    checkout's `scripts/zones/` tree (`--zone` to scope, `--report` for a Markdown report), and
    reports any line whose converted output still mentions `tpz.` without being covered by a flag
    (`ConversionResult.unflagged_leftovers()` in `backport_lua_convert.py`) — a real coverage gap,
    not a cosmetic one. The first manual run (6 zones outside Nyzul) found 97 such gaps; each was
    fixed with the same evidence-checked discipline as every other map entry (new `mobMod`/
    `animation`/`objType`/`path_flag` families, the missing physical half of the
    attackType/damageType incompatible-enum map, a real new engine gap `MOBMOD_NO_REST`, and a new
    `missing_lua_modules` map section for genuinely-absent-but-portable Lua dependencies, as
    distinct from a true C++ `engine_gaps` entry). Re-run against the **full 290-zone tree (9,380
    files): zero unflagged gaps.**
  - `assault_lockbox.lua` (one of the `missing_lua_modules` findings — the shared Ancient Lockbox
    open/roll/give logic used by Lebros Cavern, Mamool Ja Training Grounds, and Periqia) ported to
    `Topaz-Assault-Backport/dsp-shared-globals/assault_lockbox.lua` — every DSP API call it makes
    confirmed present with an identical signature before porting. Only the shared roller function
    is centralized; each zone's own calling script and per-mission reward tables are NOT — a
    correction from the user after an earlier over-broad suggestion, now recorded as a standing
    rule (`[[topaz_dsp_no_central_lockbox]]` memory). The other `missing_lua_modules` finding,
    `caskets.lua`, turned out on inspection to have zero real Assault callers at all across the
    whole zone tree — every hit is either the unrelated general open-world Treasure Casket system
    or a comment-only mention — documented as out of scope rather than porting an unused ~990-line
    module.
  - `test_backport_lua_convert.py` — a permanent, pytest-free regression suite (16 test functions,
    matching this project's existing `test_capture_ingestion.py` convention) against small
    hand-written snippets, one per converter code path (each `simple_families`/`reshaped_families`
    shape, incompatible-enum flagging, `missing_lua_modules` flagging, method/whole-call renames,
    both script-shape regression guards, both ID-shape conventions, the generic unmapped-reference
    fallback, `ConversionResult.unflagged_leftovers()`). Checks converter MECHANICS on fixed inputs
    (fast, catches a regex regression immediately), complementing rather than replacing
    `backport_coverage_check.py` (which checks coverage against real, changing Topaz source).
  - `backport_map_confidence_check.py` — a decay check for `confirmed_pattern` map entries (an
    entry marked this way was only spot-checked on 2-3 members when written, with the rest assumed
    to follow the same prefix pattern). Scans every real `tpz.<family>.<KEY>` actually used
    anywhere in the Topaz checkout, then checks whether the mapped DSP identifier for that specific
    KEY exists anywhere in real DSP source — a name-existence check, not a value check, meant to be
    paired with `backport_coverage_check.py` and a manual value spot-check. First run found real
    decay: 2 more genuinely-missing `mobMod` members (`NO_AGGRO`, `NO_LINK`, beyond the
    already-known `CHECK_AS_NM`/`NO_REST`) and one more missing `effectFlag` member (`EMPATHY`,
    beyond the already-known `INFLUENCE`/`OFFLINE_TICK`/`AURA`) — both added as new `engine_gaps`
    entries. Also surfaced a much larger, expected decay area: 69 of 469 real `tpz.mod.*` members
    used anywhere in Topaz have no matching identifier in this DSP snapshot at all (an older/smaller
    `MOD_` enum missing many newer roll/augment/job-trait modifiers) — documented as a known large
    gap area in the map rather than individually engine-gap'd member-by-member.
  - GUI page (`/backport/lua-convert`) now surfaces each flagged line's real evidence/fix/checked
    citation inline instead of a bare regex string — refactored `_flag_unhandled` to carry
    provenance (which map section/key each pattern came from) through to the flag record, so a user
    of the page sees the same reasoning a map author would have to go dig up manually before.
  - **SQL backport tooling** — `backport_sql_convert.py` + `data/dsp_sql_schema_map.json`, with a
    live GUI page at `/backport/sql-convert` (same gate as the Lua converter). Converts Topaz
    `INSERT INTO` statements to DSP's real column order/shape per table, and — the more valuable
    half — checks every row's id against DSP's REAL, already-indexed data
    (`ffxi_zone_database.db`'s `dsp_*` tables from `build_dsp_index.py`), classifying each
    collision as "same entity already present" (safe) vs. "real collision, different entity"
    (needs a human decision), rather than a bare id-overlap count. Proven against the real Nyzul
    package (`ID_COLLISION_REPORT.md`): found that DSP's `mob_groups` primary key is server-global
    (not per-zone like Topaz's), meaning **all 100** of the package's groupids collided with
    unrelated existing DSP zones — and, by actually comparing item rows rather than just id
    numbers, that **all 59** `mob_droplist` dropIds collided too (Topaz's dropId 15 drops a
      Nyzul-specific item; DSP's existing dropId 15 belongs to an unrelated mob entirely). Both
    renumbered into confirmed-free blocks above this DSP snapshot's real max, with every
    downstream reference (`mob_spawn_points.groupid`, `mob_groups.dropid`) updated to match.
    10-test regression suite (`test_backport_sql_convert.py`), matching the Lua converter's
    testing discipline.
  - `backport_sql_live_check.py` — a live-MySQL counterpart to the snapshot-based checker above,
    for DSP_TRANSITION_PLAN.md task 4 (`[NEEDS DBA/ADMIN]`, live Valhalla-target DB access we don't
    have). Runs the exact same same-entity-vs-real-collision classification against a REAL live
    database instead of the indexed snapshot -- read-only (`SELECT` only, never writes), ready to
    hand to whoever has that access with zero setup beyond one pip install. Full handoff writeup in
    `LIVE_DB_COLLISION_CHECK.md` alongside the Nyzul package.
- **2026-09-13: Target-codebase correction, backport audit toolchain, and a real local DSP server**:
  - **Root-cause correction**: discovered every prior DSP binding/conversion check in this project
    had been verified against `landsandboat-reference` (LandSandBoat/server, modern sol2-based
    `SOL_REGISTER` style) instead of `old-dsp-reference` (DarkstarProject/darkstar, 2017-vintage
    Lunar-binding-library `LUNAR_DECLARE_METHOD` style) — the actual real production target. Full
    re-audit and fix pass run against the correct codebase; the mistake is now structurally
    impossible to repeat silently: `backport_lua_convert.py` gained `TARGET_FINGERPRINTS`/
    `detect_target_flavor()`/`verify_target_or_raise()`, and `/backport/lua-convert` shows a live
    fingerprint-mismatch warning banner comparing the configured DSP checkout against the selected
    conversion target.
  - **New audit tools**: `backport_lua_sanity_check.py` (Lua syntax + cross-references
    `local ID = <Global>` usage against real `<Global> = {` declarations in the same package —
    catches the "declared `zones[X]`, consumed as bare `X`" bug class); `backport_binding_audit.py`
    (extracts every `:method(` call from a package and checks it against real DSP source across
    ALL `src/map/lua/*.cpp` binding files, not just `lua_baseentity.cpp`); `backport_map_lint.py`
    (enforces every `dsp_namespace_map.json` entry cites real evidence/source, not an unverified
    guess); `backport_binding_index.py` (full Topaz-vs-DSP binding inventory, 673 vs. 600 names,
    classified exact/case-only/topaz-only via `--diff`).
  - **Binding Reference page** (`/backport/bindings`) — dedicated browse/search page over that full
    binding inventory (731 rows: 535 exact, 15 confirmed renames, 123 topaz-only gaps needing a
    look, 58 DSP-only), cross-referenced against `dsp_namespace_map.json`'s confirmed renames with
    inline evidence, searchable by name and filterable by match status. Tabbed alongside the Lua
    Converter page (`/backport/lua-convert`) so a name can be looked up outside a conversion run,
    not just flagged mid-conversion. Nav entry added under Backport.
  - **Real bugs found and fixed** by the new tooling plus manual re-verification: `isEngaged`/
    `forceRespawn` (new C++ additions — the AI container already tracked engagement/could be forced
    to respawn, just never exposed to Lua), `setAnimationSub`/`getAnimationSub` unified to
    `AnimationSub(value)`, `delEffectFlag`→`unsetFlag`, `setSpeed`/`setBaseSpeed`/`getSpeed` unified
    to `speed(value)`, `showText()` extended with a new optional 7th `showName` bool arg, `setName`/
    `checkNavPath`/`checkNavPosition` added as new C++. Each real engine addition has its own
    `dsp-engine-changes/<name>/README.md` + real `.diff` in `Topaz-Assault-Backport`.
  - **`goToEntity` — real cross-process gap, later resolved with new engine plumbing** (same day):
    initially documented as a genuine unfixable limitation (needs a dedicated inter-process message
    type this DSP snapshot's `MSGSERVTYPE` enum had no equivalent for). Once the local DSP server
    (below) gave real build/test access, actually built it: `MSG_SEND_TO_ENTITY` added to
    `src/common/mmo.h`, `CLuaBaseEntity::goToEntity()` added/registered (same name/signature as
    Topaz), and the real two-hop message.cpp/message_server.cpp routing ported byte-for-byte from
    Topaz's own protocol. Verified live in-game for both a same-zone and a **cross-zone** target
    (the scenario that was actually broken) — no errors, correct warp both times. A stale, wrong
    `method_renames` entry (`goToEntity`→`gotoEntity`, left over from the pre-correction
    landsandboat-checked pass) that would have silently broken any real use of the new binding was
    also found and removed while updating the map.
  - **`addCharVar`/CharVar "gap" was a false negative**: an earlier grep for the literal substring
    "charvar" found nothing; the real mechanism is `getVar`/`setVar`/`addVar` (backed by a real
    `char_vars` SQL table, same semantics). Closed the gap, unblocking 4 previously-stuck package
    functions; `backport_binding_audit.py` now reports 0 missing bindings across all 8 packages.
  - **`tpz.besieged.*` ported** to old-dsp-reference's real `scripts/globals/besieged.lua` as bare
    globals (this codebase predates Topaz's own `tpz.*` namespacing) — rank badges, promotion
    points/cap, `canPromote`/`promoteRank`/`capPromotionPoints`/`warhorseHoofprintTrigger`, adapted
    away from a runtime zone-text-lookup pattern that doesn't exist in this codebase.
  - **A real local DSP server, built and verified running** — fully separate from `C:\topaz` (own
    `dspdb` MariaDB database, same MariaDB instance). Full build-chain diagnosis: VS2017 v141
    toolset install, Windows SDK version override, and three real build-environment bugs, each
    given its own `dsp-engine-changes/<name>/README.md` + real `.diff` in `Topaz-Assault-Backport`
    (same documentation convention as every gameplay-facing engine change, even though none of
    these three affect Lua-visible behavior): a real MSVC v141 toolset internal-compiler bug in
    `automaton_controller.cpp`'s `std::stable_sort` on a `pair<SpellID,int16>` instantiation,
    worked around with `std::sort` (`automaton_stable_sort_toolset_bug/` — tie-order on this fixed
    6-element list isn't gameplay-critical); a missing `#include "mob_modifier.h"` in
    `packet_system.cpp` left over from an earlier session's `check_as_nm` patch, which added the
    enum but never the include (`packet_system_missing_include/`); and a PostBuildEvent
    (`get_git_ver_win.bat`) invocation that failed under MSBuild's spawned child shell two
    different ways (`git` unresolved, then the wrapper script itself unresolved) — fixed with a
    fully-qualified `call "$(OutDir)get_git_ver_win.bat"` command instead of
    `cd $(OutDir) && get_git_ver_win.bat`, plus a `where git`-with-fallback rewrite of the script
    itself (`postbuild_git_ver_fix/`). All three real server executables
    (`DSConnect-server_64.exe`/`DSGame-server_64.exe`/`DSSearch-server_64.exe`) build clean and
    start clean (login/map/search all report "ready to work" against real `dspdb` data). Ports
    kept identical to Topaz's own (54xxx) rather than offset, since the two are never run
    simultaneously — `start_dsp_server.bat`/`stop_dsp_server.bat` at the repo root. This is now the
    standing baseline server for backport testing going forward.
- **Core GUI**: FastAPI+SQLite local server, Dialog Search, Browse by Zone, Zero-Position/
  Unregistered, SQL Index, Events/CSIDs, Assault Missions, Key Items, Item Browser, Entity Lookup,
  Wiki Compiler, Packet Decoder.
- **ID Drift**: LSB-vs-Topaz cross-referencing (19 categories), extended to old-DSP as a real 4th
  data source (`build_dsp_index.py`) — configurable via Settings, matches LSB's schema-difference
  handling (item_armor rename, mob_groups name-via-pool-join, no `@variable` usage, heavy
  trailing-comment prevalence).
- **Guardrails**: `safe_rebuild()` consolidation (CLI/GUI share one path), automatic backups before
  any rebuild, dual-flag (`--wipe-everything --i-am-sure`) requirement for a full wipe, backup
  create/restore/delete UI with double-confirmation pages, configurable retention count.
- **Captures pipeline**:
  - Folder upload support (not just zip/individual files) — a directory picker reconstructs the
    real relative-path tree server-side and ingests it through the same `Source`/
    `ingest_from_source` path a zip gets, so PathLog CSVs and other folder-context-dependent
    formats work identically either way.
  - Real per-file pass/fail reporting on every zip/folder upload (was previously one opaque
    bundle-wide summary) — matched-but-broken files report the real exception instead of aborting
    the whole batch, unmatched files are named explicitly, known-benign extras (manifest.txt,
    Thumbs.db) are distinguished from real failures.
  - Extended `eventview`'s ingest pattern to match a capturer-nested folder layout
    (`eventview/<capturer>/simple/<zone>.log`), recovering real event data that was previously
    silently dropped for at least one real capture (Bhaflau Remnants — 112 rows).
  - **Items Obtained bug fixed**: the capture timeline's Items tab was pulling from an overly
    broad opcode category (full-inventory-sync dumps, Synth/Auction/Currency noise) AND opcode
    0x020 itself had a corrupted field definition in `packetlyzer_db.xml` (two conflicting field
    layouts concatenated into one packet block) causing item ids/quantities to decode as garbage.
    Both fixed; validated by bulk-ingesting 147 real Assault/Salvage capture zips (225 captures,
    264,479+ item-attribute rows, zero decode errors, zero unresolved item ids beyond the expected
    "empty slot" sentinel).
  - **Packet opcode audit**: same duplicate-field corruption pattern found and fixed in 33 more
    opcodes (0x00B, 0x015, 0x017, 0x01D, 0x01E, 0x029, 0x02B, 0x02D, 0x038, 0x039, 0x041, 0x043,
    0x047, 0x04C, 0x04E, 0x05A, 0x05B, 0x063, 0x06F, 0x070, 0x079, 0x083, 0x085, 0x086, 0x0C4,
    0x0CA, 0x0CC, 0x0D3, 0x0DC, 0x0E1, 0x0E2, 0x0E4, 0x0F4, 0x110, 0x113, 0x0FA), each verified
    against real LandSandBoat struct source and, where real capture data existed, decode-validated.
    Two opcodes (0x00A Zone In, 0x0B4 Config) remain genuinely unresolved — see Known Gaps below.
- **2026-09-14: `backport_package.py` — end-to-end package backport orchestrator, plus a bundled
  turnkey `backport-workspace/` scaffold**:
  - Chains together every already-built per-file/per-table backport tool into one run over a whole
    package folder instead of four separate manual invocations: converts every `.lua` file
    (`backport_lua_convert.py`) and every `.sql` file (`backport_sql_convert.py`), then runs the
    binding audit, the Lua sanity check, and the SQL id-collision check (against real indexed DSP
    data) over the whole converted result, and writes one consolidated `BACKPORT_REPORT.md`.
    `--verify-only` re-runs just the 3 checks against an already-converted `lua-dsp/` without
    re-converting.
  - Validated against a real, large package (`nyzul_isle_investigation`, 10 SQL tables + dozens of
    Lua files): correctly reproduced the already-known `mob_groups`/`mob_skill_lists` server-global
    id-collision findings from the original Nyzul backport, and surfaced genuine new
    case-mismatch collisions (`Friars_Lantern`/`Friar_s_Lantern`, `Puk`/`Puk_WW`,
    `homing_missile`/`pw_homing_missile`) in the same single-report run.
  - Explicit, documented non-goals (see the script's own docstring): does not auto-discover which
    files belong to a mission across zone/npc/mob/ability layers (a harder problem this project
    already tried and rejected automating once, per `package_mission.py`'s own docstring) --
    operates on a package folder someone has already assembled. Does not auto-detect per-file
    zone-table/id-shape for multi-zone packages -- one `--zone-table`/`--id-shape` setting applies
    to the whole run, same as manually repeating the GUI converter's settings per file.
  - New `backport-workspace/` folder bundled into the repo (real `mission-packages/<name>/{lua,
    lua-dsp}`, `dsp-engine-changes/<name>/{README,.diff}`, `reports/` shapes, one small real
    already-verified example package, zero real Assault project content) -- `settings.
    get_backport_root()` now defaults to it instead of returning `None`, so the `--all-packages`
    CLI tools (and `backport_package.py`) work turnkey on a fresh clone with zero configuration.

## Known Gaps (blocked on real data, not effort)

- **0x00A (Zone In)**: three conflicting field fragments in one packet block. Structural
  recomputation from the real struct disagrees with the existing (community-sourced) offsets by a
  consistent +4 bytes partway through — can't resolve which is right without a real decoded 0x00A
  sample to arbitrate. No such sample exists in the current capture corpus.
- **0x0B4 (Config)**: the real struct's trailing fields (GmLevel, PartyLanguages, a 3-byte
  unknown) aren't represented in the XML at all past the already-fixed bitfield block. Same
  problem — needs a real sample, not a guess.
- User will gather more/different real captures later specifically to unblock these two.

## Future Phases (requested 2026-09-06, not yet started)

1. **Video linking, timestamp alignment, and possible transcription** — associate a capture with
   a recorded video of the same session, align capture-log timestamps to video timeline position,
   and investigate automatic transcription of in-game or voice audio for searchability.
2. **Online hosting and access** — move the toolkit (or a read-only view of it) from local-only to
   something reachable remotely, with whatever auth/access-control that implies.
3. **Auto-ingestion pipeline from a Windower or Ashita addon** — a live capture path that pushes
   data into this toolkit directly from an in-game addon, instead of the current
   capture-then-zip-then-upload flow.
4. **Workflow for completing requests for missing data from a capture** — a way to flag "this
   capture is missing X" and track that request through to being filled (presumably by a future
   capture or manual entry), rather than the gap just sitting silently.
5. **Pipeline from a capture to an output format for external development of the data into a
   private server** — e.g. capture → structured SQL/Lua ready to hand to a Topaz/LSB-style
   codebase, closing the loop from "recorded a real session" to "usable server data."
6. **Checklist on captures for missing details based on tags/categories** — given a capture's
   content_type/tags, surface what's typically expected for that kind of capture and what's
   actually present, so gaps are visible without manually knowing what "complete" looks like.
7. **Ability to flag missing or invalid data in captures** — explicit user-facing markers on a
   capture (or a specific row/section within it) distinct from the automatic per-file ingest
   status already built this session, for cases a human needs to call out that automation can't
   detect on its own.

These are recorded here as scope, not yet scoped into concrete implementation steps — each will
need its own design pass (data model, UI surface, and for #1/#3 in particular, real external
tooling/format decisions) before implementation starts.

8. **FFXIDB.com as a real drop-rate source** — added 2026-09-07 after live-testing it during the
   Arrapago Remnants Salvage cell-drop audit. URL pattern: `ffxidb.com/zones/<zoneid>/<mob-slug>`
   (slug = lowercase, spaces to hyphens, apostrophes dropped — e.g. "Draugar's Wyvern" ->
   `draugars-wyvern`; zone-index page `ffxidb.com/zones/<zoneid>/` lists every real slug for that
   zone, use it instead of guessing a slug). No search-by-mob API found — direct zone/mob URL
   editing is the only confirmed access path so far. Each mob page's drop table has a **TH0
   column specifically** (real measured drop-rate percentage with no Treasure Hunter effect —
   use this one, not the blended "average rate" column, for normal-player-accurate rates) —
   confirmed real, measured data (tens of thousands of sample kills per mob in the cases checked),
   meaningfully more precise than BG Wiki's simple "here's what it drops" tables (which don't give
   rates at all, and in at least one case — Qiqirn Astrologer — omitted a real item, Cotton Coin
   Purse, entirely). Rates can exceed 100% (e.g. 232.3%) — real per-kill drop count can be >1, not
   a data error. Adopted as the primary drop-rate source for all future Salvage (and likely other
   real-drop-table) build-out, superseding a flat "guaranteed/5%" placeholder assumption used
   earlier in this same audit before FFXIDB was found — confirmed against real per-item rates
   instead. Not yet wired into the toolkit itself (still a manual WebFetch-per-mob-page workflow)
   — a future toolkit integration (scrape/cache real drop tables keyed by zone+mob, expose in the
   GUI) would remove the need to hand-fetch each page.
