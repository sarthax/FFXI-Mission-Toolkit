# Live entity runtime evidence — Stage 3 foundation

The read-only classifier at `src/workbench/devtools/research/entity_runtime_evidence.py`
separates **indexed configuration**, **client observation**, and **server runtime state**.

An indexed NPC/mob record, even with exact matching ID, proves only that the
configured record exists. Missing or stale Ashita observations cannot prove
despawn, hiding, or an unmet script predicate. A position discrepancy likewise
does not prove an error.

## Runtime adapter contract (not connected yet)

An authoritative adapter must supply: `source="server_runtime"`,
`zone`, exact `server_entity_id`, `instance_id`, `fresh=True`, and
a state in `active | despawned | hidden | inactive | unknown`. Only matching
zone, ID and instance produce a `runtime_reported` confidence classification.
No client slot or fuzzy name fallback is allowed.

The adapter should additionally collect sample timestamp, server build/source,
and a read-only explanation of explicit spawn predicates where available,
without running scripts or modifying state. Expire reports on disconnect,
zone/instance switch and missing data.

**Current boundary:** This is a tested classifier, not a live DSP/LSB server
runtime integration, API endpoint, or UI control. Runtime status remains
`unknown` until an independently verified server-side source is wired in.

## Timestamp-validation helper

`entity_runtime_sample.validate_runtime_sample` checks an explicitly supplied
server-origin report against a caller-supplied clock. It requires a timestamp
within the last five seconds (never future-dated), a matching instance, zone,
reported server ID, and an explicit state. `classify_supplied_sample` fails
closed to `unknown` on invalid evidence. These functions do **not** authenticate
who supplied the sample, and are **not** a connected DSP runtime adapter.
Only wire samples from a separately trusted, read-only server-side transport;
never accept arbitrary browser/client JSON as authoritative server state.
