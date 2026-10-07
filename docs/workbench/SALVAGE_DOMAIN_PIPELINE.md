# Salvage Domain Pipeline

## Purpose

This domain treats Salvage as four physical Remnants zones with two implementation tracks each: Salvage I and Salvage II. The toolkit should reuse generic capture, entity, zone, SQL, Feature Trace, package, and validation services instead of creating a second Salvage-only editor stack.

The eight build targets are Zhayolm, Arrapago, Bhaflau, and Silver Sea Remnants, each with I / II tracks.

LandSandBoat exposes the four Remnants zone structures and Salvage I instance registrations. Its `instance_list.sql` also contains commented `*_remnants_ii` placeholders, which is useful reference evidence for the I/II split but is not sufficient by itself to assert a working Salvage II implementation.

## Reconstruction workflow

The workflow is intentionally evidence-first:

1. **Ingest captures** with the normal Capture pipeline. Salvage should not invent a second parser stack.
2. **Build a reconstruction dossier** for one capture + Remnants zone.
3. **Review spatial/entity evidence** in Entity Profile and Zone Editor.
4. **Resolve interaction evidence** for doors, telepads, EVENT/option rows and packet observations.
5. **Compare against target/reference server state** before proposing SQL or Lua.
6. **Generate a review package**, not direct server writes.
7. **Validate closure** against the original captures and known implementation truth set.

`workbench/domains/salvage_reconstruction.py` implements the read-only dossier. The packaged Capture CLI exposes it as JSON:

```text
py -3 -m workbench.captures.cli.salvage_reconstruct <capture_id> --zone ZHAYOLM_REMNANTS
```

The dossier separates:

- capture metadata and available zones;
- observed entities with model, position, rotation and runtime fields;
- explicit door observations (`door_id` when present);
- other interactive candidates (`act_index` / `sub_kind` / door fields);
- EVENT rows by entity, opcode, event payload, option and message id;
- captured NPC movement/path coverage;
- observed player-path legs as conservative spatial-region candidates;
- entity/door overlap candidates for those observed path regions;
- observed actions, animations and messages;
- implementation-readiness states;
- unresolved evidence gaps.

Most importantly, **EVENT evidence is not automatically a telepad destination**. The dossier marks telepad/CSID mapping as partial until the event is correlated with movement/zone transition/server/reference evidence. This prevents the old workflow failure mode where an agent sees a plausible event and wires the wrong destination or state condition.

Likewise, **a player-path leg is not automatically a Salvage floor or room**. The first segmentation slice records each positioned capture path leg as an observed spatial region, calculates its X/Z envelope, and reports entities/doors that overlap that envelope. Region labels remain unresolved, and entities that overlap multiple regions remain ambiguous until door, telepad, transition, map, or other corroborating evidence establishes the actual boundary.

## Current toolkit readiness

### Ready now

- Capture ingestion across supported packet/entity/action/event/chat formats.
- Canonical capture provenance and Related Evidence.
- Salvage reconstruction dossier generation from normalized capture tables.
- Visual Salvage reconstruction workspace on the Salvage domain page.
- Conservative player-path-region segmentation foundation with unresolved floor/room semantics.
- Entity identity review against capture/server/client evidence.
- Zone Editor spatial review and editing.
- Read/compare support for `mob_spawn_points.sql`, `npc_list.sql`, `mob_groups.sql`, `mob_pools.sql`, `mob_droplist.sql`, `instance_list.sql`, and `instance_entities.sql`.
- Entity Profile diagnostics for the common `spawn exists but instance_entities registration is missing` gap.
- Event/CSID and packet investigation surfaces.
- Feature Trace / Behavior Inspector for source-level Lua dependency and hook analysis.
- Package scope/review/create and validation surfaces once a proposed implementation exists.

### Partial / next compiler work

1. **Floor/room segmentation**
   - implemented foundation: preserve parser-native player-path legs as observed spatial regions and show entity/door overlap candidates;
   - next: correlate region transitions with doors, telepads, movement discontinuities and reference-map evidence;
   - resolve ambiguous entity membership only when stronger evidence exists;
   - preserve uncertainty where a boundary cannot be established from evidence.

2. **Entity proposal**
   - group repeated observations of the same resolved entity;
   - produce `mob_spawn_points` / `npc_list` shaped proposals with provenance;
   - require explicit classification of mob vs NPC vs door/telepad before output.

3. **Instance registration proposal**
   - bind reviewed entities to one explicit instance id;
   - diff against `instance_entities.sql`;
   - emit only missing registrations into a review package.

4. **Door state model**
   - retain captured animation/status/door fields over time;
   - correlate state changes with kills, floor state, events and telepad use;
   - distinguish initial state from transition conditions.

5. **Telepad / CSID state mapping**
   - group EVENT/option/packet evidence by interactive entity;
   - correlate activation to subsequent PC path/zone/location change;
   - keep CSID identity, trigger condition and destination as three separate claims;
   - never infer an unobserved option or destination.

6. **Lua scaffold proposal**
   - create/extend `Zone.lua`, `instances/<instance>.lua`, `mobs/<name>.lua`, and `npcs/<name>.lua` only after reviewed evidence exists;
   - populate observed hooks/actions/state transitions;
   - emit TODO/evidence markers for unproven mechanics.

7. **Mechanics closure**
   - Pathos restrictions/cells;
   - starter crates;
   - floor progression and branch gates;
   - NM pop/unlock conditions;
   - boss completion and Rune of Release extraction;
   - drops/rewards.
   - BGWiki is mechanics/reference evidence only; numeric IDs, positions, event IDs and server wiring require server/client/capture evidence.

## GUI dossier

The Salvage domain workspace displays one selected capture/zone with these panels:

- **Capture set** — selected capture, zone and handoffs into Capture/Evidence Search.
- **Floor / room map** — central zone view with PC path, observed path-region envelopes, entities, doors, interactive candidates and unresolved regions.
- **Entity registry** — observed entity id/name/model/position, runtime fields and captured path coverage.
- **Floor / room candidates** — path-leg regions, bounds, overlapping entities/doors and ambiguous memberships, explicitly marked unresolved.
- **Doors** — captured identity/state-history availability without inventing transition rules.
- **Telepads / events** — entity, observed event/option and whether player-path evidence exists for later correlation.
- **Implementation gaps** — missing evidence and ambiguity that must remain unresolved.
- **Proposal** — still disabled until the review-only SQL/Lua/package compiler exists.

## Recommended truth-set development order

Use one of the two already-built Salvage implementations as the first truth set. Feed its captures into the dossier, compare the dossier against the known server implementation, and measure:

- entity roster recall;
- spawn/rotation accuracy;
- floor/room segmentation accuracy and unresolved/ambiguous region count;
- missing/extra instance registrations;
- door initial-state accuracy;
- telepad event/destination accuracy;
- mob action/Lua coverage;
- unresolved dependency count.

Then build the proposal compiler until it can reconstruct that known implementation with explicit remaining gaps. Only after that should it be used to accelerate the six unfinished builds.

Automatic apply remains a later, separately approved action.
