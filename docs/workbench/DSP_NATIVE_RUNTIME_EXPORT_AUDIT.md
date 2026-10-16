# DSP native entity runtime exporter: verified source audit

Status: **source mapping complete; native exporter not yet implemented or deployed**.

Source examined: `sarthax/Topaz-to-Valhalla`, branch `release`, not a verified checkout of the running DSP server. Do not assume this exact fork's APIs exist unchanged on the deployed server.

## Verified source hooks

| Source file | Direct finding | Integration consequence |
| --- | --- | --- |
| `src/map/zone.h` | `CZone::ForEachMob(std::function<void(CMobEntity*)>)`, `ForEachNpc(std::function<void(CNpcEntity*)>)` | These are candidate read-only enumeration points |
| `src/map/zone.cpp` | `ForEachMob` enumerates `m_zoneEntities->m_mobList`; `ForEachNpc` enumerates `m_npcList` | They enumerate loaded entity objects, **not** proof of actual spawning |
| `src/map/zone.cpp` | `ForEachMobInstance(CBaseEntity*, ...)` currently iterates the same `m_mobList` with no visible instance filter in the examined body | Do **not** infer instance identity from this method name |
| `src/map/zone.h` | `GetEntity(uint16 targid, uint8 filter=-1)` notes that it ignores instances | Do not use this lookup alone for authoritative per-instance status |
| `src/map/entities/baseentity.h` | `CBaseEntity::id` is the global identifier; `targid` is zone-local; `status` uses `STATUS_TYPE`; `loc.zone` holds the zone | Export global ID, never equate client slot or `targid` to server entity ID |
| `src/map/entities/baseentity.h` | `STATUS_TYPE` includes `NORMAL=0`, `MOB=1`, `DISAPPEAR=2`, `INVISIBLE=3`, `CUTSCENE_ONLY=6`, `SHUTDOWN=20` | Report raw state separately; do not automatically equate `DISAPPEAR` with a permanent despawn |
| `src/map/entities/mobentity.h` | `ROAMFLAG_AMBUSH`, `ROAMFLAG_STEALTH`, `SPECIALFLAG_HIDDEN` are declared | These are *potential* behavior flags, not sufficient to establish the current hidden/conditional state |

## Read-only native integration contract

1. Obtain the **deployed** server's map-thread API version and build identity; do not assume source parity with the archived release branch.
2. Implement a bounded on-map-thread sampling callback, not cross-thread traversal of live entity lists.
3. Export observed entity ID, zone ID, verified instance identity, raw status, position, monotonic/UTC collection time, and diagnostic source/build. Make distinctions between **loaded object**, **currently active**, **client-visible**, and **spawn eligible**.
4. Only emit `source: server_runtime` and classified `state` after confirming that status/visibility predicates on this server actually justify the label; otherwise report `unknown` with raw fields.
5. Never claim instance-scoped confidence without independently validated instance membership. In particular, the inspected `ForEachMobInstance` implementation cannot provide that confidence by itself.
6. Use an operator-restricted snapshot directory and atomic replacement; the Toolkit's existing `RuntimeSnapshotSpool`, `TrustedRuntimeProvider`, and timestamp validation can consume the result.
7. Do not enumerate a full instance indefinitely each tick. Bound interval and entity count, measure overhead, and avoid server-side mutators or scripts.
8. Add native tests for multi-instance duplicate local IDs, nonspawned-but-loaded mobs, hidden/cutscene NPCs, transitions and partially constructed/destructing actors. Require production developer-server validation before calling the feed authoritative.

## Blocking gap

No native DSP runtime producer, build-tested map-server modification, or verified instance accessor has been established in this audit. The Toolkit's Stage 3 transport is ready, but runtime labels must remain **unknown** until the native producer has been reviewed and deployed. Static SQL and Ashita telemetry must not be promoted to server runtime evidence.
