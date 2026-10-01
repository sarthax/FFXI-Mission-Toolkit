# Salvage Domain Pipeline

## Purpose

This domain treats Salvage as four physical Remnants zones with two implementation tracks each: Salvage I and Salvage II. The toolkit should reuse generic capture, entity, zone, SQL, Feature Trace, package, and validation services instead of creating a second Salvage-only editor stack.

The eight build targets are:

- Zhayolm Remnants I / II
- Arrapago Remnants I / II
- Bhaflau Remnants I / II
- Silver Sea Remnants I / II

LandSandBoat currently exposes the four Remnants zone structures and Salvage I instance registrations. Its `instance_list.sql` also contains commented `*_remnants_ii` placeholders, which is useful reference evidence for the I/II split but is not sufficient by itself to assert a working Salvage II implementation.

## Current toolkit readiness

### Ready now

- Capture ingestion across the supported packet/entity/action/event/chat formats.
- Canonical capture provenance and Related Evidence.
- Entity identity review against capture/server/client evidence.
- Zone Editor spatial review and editing.
- Read/compare support for `mob_spawn_points.sql`, `npc_list.sql`, `mob_groups.sql`, `mob_pools.sql`, `mob_droplist.sql`, `instance_list.sql`, and `instance_entities.sql`.
- Entity Profile diagnostics for the common `spawn exists but instance_entities registration is missing` gap.
- Event/CSID and packet investigation surfaces.
- Feature Trace / Behavior Inspector for source-level Lua dependency and hook analysis.
- Package scope/review/create and validation surfaces once a proposed implementation exists.

### Partial / next compiler work

The missing layer is a provenance-aware Salvage compiler/orchestrator. It should turn reviewed evidence into a proposed implementation package, not write directly to the target server.

1. **Entity proposal**
   - Select capture observations belonging to one Remnants implementation track.
   - Require resolved zone/entity identity.
   - Group repeated observations of the same entity and preserve source capture/row provenance.
   - Produce proposed `mob_spawn_points` / `npc_list` rows.
   - Never infer identity from name or coordinate proximity alone.

2. **Instance registration proposal**
   - Bind reviewed entities to one explicit instance ID.
   - Diff against `instance_entities.sql`.
   - Emit only missing registrations into the review package.

3. **Lua scaffold proposal**
   - Create or extend `Zone.lua`, `instances/<instance>.lua`, `mobs/<name>.lua`, and `npcs/<name>.lua` only where an implementation file is absent or an explicit package decision requests it.
   - Populate known hooks from observed/source evidence.
   - Leave unproven mechanics as TODO blocks carrying evidence references rather than inventing conditions.

4. **Telepad / door / CSID state mapping**
   - Collect observed EVENT/CSID rows and packet evidence per NPC/entity.
   - Associate only evidence-proven trigger/result pairs.
   - Model floor/path prerequisites and destinations separately from CSID identity.
   - Unobserved CSIDs and options remain unresolved.

5. **Mechanics closure**
   - Pathos restrictions and cells.
   - Starter crates.
   - floor progression and branch gates.
   - NM pop/unlock conditions.
   - boss completion and Rune of Release extraction.
   - drops/rewards.
   - Wiki information is reference/mechanics guidance; numeric IDs, positions, event IDs and server wiring require server/client/capture evidence.

6. **Validation**
   - SQL identity/duplicate checks.
   - instance registration closure.
   - Lua source/dependency closure.
   - captured entity/position/event coverage.
   - package readiness and regression tests.

## Recommended development order

Use one of the two already-built Salvage implementations as the reference truth set. Feed its captures and existing server implementation into the future compiler, require it to reconstruct a review package that matches the known implementation, then apply the same workflow to one unfinished Remnants track. This gives the compiler a measurable false-positive/false-negative target before using it across the remaining six builds.

The first compiler milestone should stop at a **reviewable proposal** containing SQL rows, Lua scaffold files, unresolved evidence gaps, and source provenance. Automatic apply should remain a later, separately approved action.
