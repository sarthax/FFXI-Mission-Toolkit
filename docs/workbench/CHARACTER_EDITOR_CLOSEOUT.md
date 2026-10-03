# Character Editor closeout

Status: **mature guarded administration surface**  
Last reconciled: **2026-10-03**

The Character Editor now supports DSP / Topaz / LandSandBoat through named server environments and lineage-aware schema/codec adapters. It is no longer a single-schema prototype.

Settings owns server-environment management. The Character Editor shows the active target and consumes that profile; native server configuration remains authoritative for database discovery and credentials.

## Current user experience

- Sticky character header and category tabs.
- Sticky changed-fields apply bar.
- Dense field grids with friendly labels and units.
- Dropdowns for known enums such as nation/race/jobs where the schema supports them.
- Field filtering, hide-zero, changed-only views, pagination, and tab counts.
- Raw/physical storage is collapsed behind Advanced presentation when a semantic editor exists.
- Current/owned/learned/set state is prioritized by default for large catalogs, with Browse All available where appropriate.
- Inventory is organized by storage container, uses compact rows/icons, and only loads icons for opened containers.

## Server environment behavior

- Named profiles can represent Live/Test/Dev/Backup/Other environments across LSB/Topaz/DSP/custom forks.
- The active profile is the authoritative admin target.
- Profiles are managed under Settings, not inside Character Editor.
- DSP/Topaz config selection accepts server root, `conf`, or native `map*.conf` and normalizes to the server root.
- LSB settings inputs are likewise normalized to the canonical checkout root.
- Passwords are never copied into profile metadata; database credentials are read from native server configuration.
- LIVE-target actions retain explicit safety warnings/confirmation behavior.

## Guarded write surface

### Inventory

- Browse all persistent containers exposed by the connected schema.
- Add item to directly verifiable persistent containers.
- Move item between supported containers.
- Change quantity with stack-limit validation.
- Remove item.
- Equipped, bazaar-listed, Temporary Item, and otherwise runtime-sensitive rows remain protected where direct mutation would be unsafe.
- Preview/apply uses source-row fingerprints so stale inventory state is rejected.

### Scalar state

Verified editable character/job/stat/skill/point fields can be updated when the adapter proves the physical table/column and write semantics. Unknown lineage fields remain read-only.

### Packed progression / unlock state

Lineage-aware codecs support guarded edits for the verified families implemented by the connected adapter, including:

- Missions
- Key Items
- Quests
- Assault
- Campaign
- Eminence
- Abilities
- Weapon Skills
- Titles
- Visited Zones
- Blue Magic set state

Mission/key-item catalogs are resolved from the selected checkout rather than assuming modern LSB IDs/names.

### Spells / blacklist

- Learn/unlearn spell operations use guarded preview/apply transactions.
- Blacklist add/remove uses the same safety/audit model.

### Merits

The semantic merit view is lineage-aware:

- current LSB structured merit metadata is used when present;
- legacy DSP merit definitions are reconstructed from the checkout's own `sql/merits.sql` plus merit header/C++ definitions;
- category, name, rank/cap, cost, jobs, and effect metadata are displayed without substituting another server family's values.

Raw rows remain available below the semantic presentation for evidence/debugging.

### LSB administrative fields

Verified persistent `char_flags` / `char_history` administrative fields are available only under explicit LSB allowlists. They are not generalized to DSP/Topaz without equivalent schema evidence.

## Mission / quest State Surface integration

Character Editor integrates Feature Trace's read-only State Surface analysis for mission/quest progression.

For a selected mission/quest it can show source-evidenced references to:

- character variables,
- key items,
- items,
- mission/quest state,
- events/CSIDs,
- titles,
- gil/fame,
- relevant hooks and source lines.

Current character state is overlaid where the storage semantics are known. Literal charvar guards can be evaluated and surfaced as matching/mismatching. State Surface remains evidence-first: static source references do not prove runtime ordering or helper-generated dynamic state.

Trace actions can hand off to existing Key Items, Variables, Inventory, and Unlocks editors. Expensive source scanning is opt-in rather than part of normal tab load.

## Safety model

Every supported mutation family is expected to preserve these boundaries:

1. exact lineage/schema detection,
2. character offline verification,
3. preview before apply,
4. explicit user approval,
5. stale-state recheck/fingerprint,
6. transaction-time validation,
7. commit/rollback semantics,
8. audit recording,
9. Undo support where a safe inverse operation is proven.

Read connections use autocommit so preview/read operations do not leave an implicit MySQL transaction that conflicts with later explicit write transactions.

## Audit / Undo

Committed inventory, spell, blacklist, scalar, packed-state, and supported LSB-admin mutations are journaled. Undo restores only the state owned by the original audited operation and re-runs lineage/schema/offline/stale-state safety checks.

Audit persistence is post-commit and non-throwing: a journal I/O failure must not falsely report that a database commit rolled back.

## Intentionally read-only

The following remain observation/diagnostic surfaces until runtime ownership and persistence semantics are proven well enough for safe edits:

- status effects and effect timers,
- recast timers,
- pet IDs and pet relationship/runtime BLOB state,
- LSB disconnecting/runtime session state,
- unknown or fork-specific fields not on an explicit edit allowlist.

These are not generic unfinished editors. The server/game may own or rewrite this state while running.

## Client item cache

Character inventory uses the shared client item DAT cache for names/icons where client data is available.

- Default behavior is lazy: the first request parses/extracts the item asset and persists it.
- Settings offers **Build all item DAT cache** for an optional one-time prebuild.
- Parsed item metadata is stored in SQLite; icons are normal PNG files.
- Cache entries are scoped by client install/snapshot identity and validated against source DAT size/mtime.
- Clearing the cache simply returns the system to lazy extraction.
- Closed inventory containers do not receive icon URLs until opened, reducing initial request volume.

## Regression baseline

Character Editor changes have a dedicated CI workflow in addition to Workbench regression. Coverage includes backend services, transaction safety, codecs, route registration, environment/profile integration, GUI assets, semantic catalogs, State Surface integration, and executable regression scripts.

Future Character Editor mutation work should require new evidence for target-field semantics, a lineage/schema contract, offline/stale-state guards, audit coverage, and focused regression vectors before it is advertised as writable.
