# Character Editor closeout

The Character Editor is now a guarded DSP / Topaz / LandSandBoat administration surface rather than a single-schema prototype. Named server environments select the active target; native server configuration remains authoritative for database discovery.

## Guarded write surface

- Inventory: browse, add, move, quantity changes, remove, container/capacity checks, item metadata/icons where available.
- Scalar character rows: identity/profile/look/style/jobs/experience/stats/skills/points/merits/job points/unlocks/variables where the detected schema exposes verified editable columns.
- Packed progression: missions, key items, quests, Assault, Campaign, Eminence, abilities, weapon skills, titles, visited zones, and Blue Magic set state through lineage-aware codecs.
- Learned spells and blacklist entries through preview/apply transactions.
- LSB-only persistent `char_flags` / `char_history` administrative fields through an explicit allowlist.
- Every supported mutation family requires offline verification, preview/approval, stale-state checks, and audit logging. Audit Undo covers inventory, spells, blacklist, scalar rows, packed state, and LSB admin edits.

## Intentionally read-only

The following remain observation/diagnostic surfaces until their runtime ownership and write semantics are proven well enough for safe persistence edits:

- status effects and effect timers,
- recast timers,
- pet IDs, pet relationship/BLOB runtime state,
- LSB `disconnecting` / runtime session state,
- any lineage-specific or unknown schema fields that are not on an explicit edit allowlist.

These are not generic "missing editors". They are deliberately excluded from mutation because the game/server may own or rewrite the state while running.

## Safety / regression baseline

Character Editor changes have a dedicated CI workflow in addition to the normal Workbench regression. The focused gate runs both pytest-style fixtures and the repository's executable Character Editor regression scripts, including environment/profile integration.

Future Character Editor mutation work should require new evidence for the target field semantics, a lineage/schema contract, offline/stale-state guards, audit coverage, and focused regression vectors before adding it to the write capability manifest.
