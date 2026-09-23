# 3D Zone Viewer / Level Editor — Project Status

_Last updated: 2026-09-22_

## Origin / goal

User's original combined ask (paraphrased): make the zone viewer and plotter more
useful for level editing, and eventually support real terrain navigation (fly-through)
instead of the current top-down-only workflow. Agreed to do this in 3 phases against
`zone_view3d.html`, informed by (not copied from) Soverance/Vanalytics' React Three
Fiber zone viewer (MIT licensed, vendored reference at
`D:\Claude\FFXI-Tools\vanalytics-full\src\Vanalytics.Web\src\components\zone\`).

## Phase 1 — spawn markers + click-to-fly camera
**Status: DONE, verified.**
File: `gui/templates/zone_view3d.html`.
- Fetches `/zoneplot/{zid}/data.json` (existing endpoint, shared with `zone_plot.html`).
- `buildSpawnMarkers()` draws mob/npc/door spawns as colored spheres, raycasting hover
  tooltip, click-to-fly camera (`flyTo()`/`flyAnim`).

## Phase 2 — time-of-day sky / height-fog / water shaders
**Status: DONE, verified.**
Same file. Procedural sky-dome `ShaderMaterial` driven by a `#tod-slider` UI control
(`getTimeOfDayParams(hour)` → `updateTimeOfDay()`), height-based fog patched into
materials via `material.onBeforeCompile` (`patchHeightFogMaterial`, handles both plain
meshes and `USE_INSTANCING`), animated water `ShaderMaterial` for water-textured meshes.

## Phase 3 — real textured zone geometry via live in-browser DAT parsing
**Status: DONE, verified end-to-end (real textures/terrain confirmed in Browser pane).**

Replaced the untextured pre-baked-OBJ-only pipeline with live parsing of the real
client MZB/MMB zone DAT, using the already-vendored `gui/static/ffxi-dat/*.js`
library (ported/built from Soverance/Vanalytics, MIT, `LICENSE-vanalytics.txt`
present) — this library was **already complete**, only needed to be called from the
browser:
- `parseZoneFile(buffer, onProgress, supplementalTextures)` → `{prefabs, instances, textures}`.
- Key files: `DatReader.js`, `DatFile.js`, `MeshParser.js`, `TextureParser.js`
  (DXT1/DXT3), `SkeletonParser.js`, `FileTableResolver.js`, `ZoneFile.js`,
  `AnimationParser.js`, `ZoneDecrypt.js`, `MzbParser.js`/`MmbParser.js`,
  `MinimapParser.js`, `ZoneScanner.js`, `index.js` (barrel export).

Server side (`gui_server.py`):
- `zones` table already had a `geometry_rom_path` column (was only used by the offline
  `build_zone_visual_cache.py` OBJ bake before this). Reused for the live-parse path.
- Reused the existing generic `/modelviewer/dat?ffxi_path=&rom_path=` endpoint
  unmodified — it already serves raw DAT bytes for any rom_path.
- `zone_view3d` route now also resolves + passes `geometry_rom_path`,
  `live_parse_available`, `ffxi_path_json` to the template.

Client side (`zone_view3d.html`):
- `buildLiveZoneGroup(zoneData)` — ported (not copy-pasted; translated to vanilla JS)
  from `ThreeZoneViewer.tsx` lines ~430-670: per-prefab `BufferGeometry`
  (position/normal/color/uv + 16/32-bit index buffer), `THREE.DataTexture` from parsed
  RGBA texture data, mirrored-instance detection via `Matrix4.determinant() < 0` +
  `cloneWithFlippedWinding`, sky/weather-mesh exclusion (`SKY_WEATHER_RE`), water-mesh
  detection (`WATER_NAME_RE`) routed to the Phase-2 water material, `InstancedMesh`
  construction per prefab group.
- Dispatch: if `LIVE_PARSE_AVAILABLE`, fetch DAT → `parseZoneFile` → `buildLiveZoneGroup`
  → `onZoneMeshReady()`; on any failure (no install configured, parse throws, empty
  result) falls back to `loadObjFallback()` (the old cached-OBJ `OBJLoader` path, now
  extracted into its own function). `onZoneMeshReady()` holds the shared
  camera-framing + capture-path-drawing logic, used by both paths.
- Verified via Browser pane: real texture names/sizes logged, real textured
  grass/dirt/rock/tree-billboard terrain screenshot confirmed, spawn markers + sky dome
  rendering correctly together, no real console errors.

## Level editing — scoped, NOT yet implemented (awaiting go-ahead)

**Key discovery**: level editing is **not a greenfield feature**. It already exists,
fully wired to the live DB, in `gui/templates/zone_plot.html` (the 2D-named but
actually-3D "Zone Plot" page) + `zone_edit.py` + routes in `gui_server.py`:

- `zone_edit.update_position(k, id, x, y, z, r, comment)` → `POST /zoneplot/edit`
- `zone_edit.update_animation(k, id, animation, animationsub, comment)` → `POST /zoneplot/animate`
- Also (grepped, confirmed wired in `zone_plot.html` JS): `/zoneplot/add`,
  `/zoneplot/delete`, `/zoneplot/backups.json`, `/zoneplot/restore`,
  `/zoneplot/{zid}/snapshot`, `/zoneplot/catalogue.json` (search source npc/mob to clone
  into a zone).
- UX already built and tuned: click-to-place (raycast → X/Y/Z + cyan preview marker),
  drag-and-drop placement from an "Add" tab asset browser (draggable rows), nudge
  buttons, animation/animationsub dropdowns with documented confirmed values, a
  corrected OrbitControls pan speed for level-editing feel
  (`panSpeed = BASE_PAN/distance`, see comment block ~line 144 in `zone_plot.html`),
  a full Backups tab (snapshot/restore/restore-exact).
- Every write auto-backs-up first and appends to `data/zoneplot_edit_log.sql`
  (`zone_edit.py`'s log target — NOT yet double-checked against the older,
  probably-superseded `zone_plot.update_position()` function in `zone_plot.py` lines
  174-201, which appears to be dead code / an earlier version now replaced by
  `zone_edit.py`. Worth a quick confirm-and-delete-dead-code pass at some point but not
  blocking.)
- `zone_plot.html` has its **own separate 3D view** already (not `zone_view3d.html`):
  uses `/zoneplot/{zid}/mesh.zmesh` + `/zoneplot/{zid}/mesh_info.json`, an on-demand
  LOD-aware mesh pipeline (`zmesh` module) — untextured `MeshStandardMaterial`, no sky,
  no water, no Phase 1-3 rendering quality.

### Decided scope (presented to user, not yet approved to start)

**Do NOT rebuild editing in `zone_view3d.html`.** Instead, port Phase 1-3's rendering
into `zone_plot.html`'s existing editor:

1. Replace `zone_plot.html`'s `loadZMesh()` untextured `.zmesh`/OBJ path with the live
   `parseZoneFile()` → `buildLiveZoneGroup()` path (reuse from `zone_view3d.html`
   nearly as-is: `buildLiveZoneGroup`, `patchHeightFogMaterial`, water/sky regexes).
   Keep the existing `.zmesh`/OBJ LOD path as fallback when no install/`geometry_rom_path`
   configured — same fallback pattern already proven working in Phase 3.
2. LOD dropdown becomes: `Full` → live parse if available, else falls back;
   `Medium/Low/Legacy OBJ` → existing `.zmesh`/OBJ pipeline unchanged. (Live-parsed
   geometry is the real mesh — no LOD levels to pick from — so no decimation work needed.)
3. `screenToWorld()`'s raycast (`ray.intersectObject(tgt, true)`) already recurses, so
   pointing `meshObj` at the new `THREE.Group` from `buildLiveZoneGroup` should just work,
   unmodified.
4. Optional/nice-to-have: port the Phase 2 time-of-day sky dome + fog into `zone_plot.html`
   too, for visual consistency. Not required for editing itself.
5. Leave `zone_view3d.html` alone as a pure visualization/review tool (capture-path
   review, spawn markers, time-of-day flythrough) — it keeps its own identity, no
   editing UI added to it.

**Explicitly out of scope for this pass**: editing the live-parsed prop/geometry
instances themselves (doors, static scenery meshes) — those aren't backed by DB rows
the way `mob_spawn_points`/`npc_list` are, so there's no `zone_edit` write path for
them today. Flagged as a possible bigger future feature (would need mapping a clicked
mesh instance back to its MZB/MMB source row and inventing an editable representation
for it) — not started, not requested yet.

## Deferred (explicitly acknowledged, not scoped in detail yet)

Real first-person/fly-through terrain navigation (WASD + pointer-lock mouselook)
to replace the current orbit/top-down-only camera model. User's own words: "At some
point I would like to do actual terrain navigation if this supports that also instead
of top down view like we have now." Reference implementation to study:
`FlyCamera` in the vendored Vanalytics tsx components (same directory as
`ThreeZoneViewer.tsx`). Not scoped in detail; user has not asked to start this yet —
they asked for level editing next.

## Next step when resuming

Get explicit go-ahead on the "Decided scope" section above, then implement steps 1-3
(4 optional) in `zone_plot.html`, verify via Browser pane the same way Phase 3 was
verified (real textures rendering, editing still functional — test a position edit
end-to-end against the live DB).

## Key files reference

| What | Path |
|---|---|
| Phase 1-3 standalone viewer | `gui/templates/zone_view3d.html` |
| Existing level editor (2D-named, actually has 3D view) | `gui/templates/zone_plot.html` |
| Live-DB write-back module | `zone_edit.py` (need to read in full — not yet done) |
| Old/likely-dead write-back fn | `zone_plot.py` lines ~174-201 (`update_position`, `EDIT_LOG`) |
| Server routes | `gui_server.py` — search `zone_view3d`, `/zoneplot/` |
| Vendored DAT parser lib | `gui/static/ffxi-dat/*.js` (from Soverance/Vanalytics, MIT) |
| Reference source (not copied, ported) | `D:\Claude\FFXI-Tools\vanalytics-full\src\Vanalytics.Web\src\components\zone\ThreeZoneViewer.tsx` (lines 430-670 = scene construction), `SpawnMarkers.tsx`, `FlyCamera` (for later terrain-nav phase) |
| Edit-log output | `data/zoneplot_edit_log.sql` |
