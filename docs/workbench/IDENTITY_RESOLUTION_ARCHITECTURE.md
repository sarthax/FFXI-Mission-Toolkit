# Snapshot-Aware Identity Resolution

Status: IMPLEMENTATION STARTED  
Branch: `workbench-rework/audit-foundation`

## Purpose

The legacy **ID Drift** tool compares identifiers between selected server datasets and the currently configured FFXI client. That remains useful, but it assumes one client point in time and mainly reports literal mismatches.

The Workbench needs a stronger guarantee for packaging, capture reconstruction, and forward/backward implementation work:

> A numeric identifier is a snapshot-specific representation of a semantic identity.

The same gameplay event may use different numeric IDs in different Retail client builds or different server revisions. A package must therefore resolve identifiers for the exact **source snapshot → target snapshot** pair rather than copying a number blindly.

This architecture is intentionally bidirectional. It supports:

- modern LSB → older DSP/client;
- older DSP/client → current LSB/client;
- Retail capture → LSB;
- Retail capture → DSP/Topaz;
- client build A → client build B;
- server fork/revision A → server fork/revision B.

It is not a backport-only facility.

## Existing lineage

The current toolkit already contains useful predecessors:

- `/iddrift` categories comparing LSB and Topaz identities;
- event/CSID drift based on literal NPC-script CSIDs;
- NPC block-offset detection;
- `audit_dialog_drift.py`, which exports real dialog from the configured local FFXI install through xi-tinkerer;
- `dialog_drift_overview.py`, which detects systematic per-zone dialog offsets by normalized text matching.

Those tools become evidence producers and compatibility views. They should not be discarded.

## Core model

### IdentitySnapshot

An identity snapshot describes one concrete representation source.

Examples:

```text
client:30191204_1
client:2022-xx
retail-capture:2026-09-26:run-27
server:lsb:3747fe...
server:topaz:<revision>
server:dsp:<revision>
```

Important metadata includes:

- snapshot type: CLIENT / SERVER / CAPTURE / REFERENCE;
- family: Retail / LSB / Topaz / DSP / custom;
- version/build/revision;
- recorded/capture date;
- source location;
- deterministic fingerprint;
- optional region/language/build metadata.

Retail truth is therefore qualified as **Retail behavior for a specific build/date**, not a timeless numeric namespace.

### IdentityRecord

An identity record stores one snapshot-specific representation:

```text
snapshot
namespace
semantic identity
numeric representation
zone/context
actor/context
owner/context
content fingerprint
evidence/provenance
confidence
```

Namespaces remain distinct. Examples:

- EVENT
- CSID
- MESSAGE_ID
- DIALOG_TEXT_ID
- NPC
- MOB
- ITEM
- KEY_ITEM
- SPELL
- ABILITY
- WEAPON_SKILL
- MOB_SKILL
- STATUS_EFFECT
- PACKET_OPCODE

Do not collapse MESSAGE_ID, CSID and EVENT_RESOURCE_ID merely because they contain the same integer.

### Semantic event identity

A canonical event is not identified by its number.

Useful semantic evidence can include:

- zone;
- actor/entity;
- content owner when independently known;
- normalized dialog/event text;
- event-resource fingerprint;
- event parameter shape;
- captured start/update/finish sequence;
- referenced entities/assets;
- state effects;
- temporal/order context.

The initial implementation can use normalized dialog text as a conservative cross-build fingerprint. Stronger event-resource and capture-derived fingerprints can be added without changing the storage model.

## Resolution

Given:

```text
source snapshot
source namespace
source numeric id
source context
target snapshot
```

the resolver:

1. determines the source semantic identity;
2. finds that semantic identity in the target snapshot;
3. returns the target representation.

Possible results include:

- `EXACT` — semantic identity and number are stable;
- `TARGET_EQUIVALENT` — semantic identity matches, numeric representation drifted;
- `SOURCE_ID_UNRESOLVED`;
- `SOURCE_ID_AMBIGUOUS`;
- `TARGET_ID_UNRESOLVED`;
- `TARGET_ID_AMBIGUOUS`.

Numeric equality alone does not prove semantic equality.

## Package identity closure

Identity resolution becomes an independent package-readiness dimension.

A package may be artifact-complete but unsafe because an event, NPC, item, packet, or other required identity cannot be resolved for the selected target pair.

Conceptually:

```text
Artifact closure
Runtime/system closure
Acquisition closure
State-machine closure
Identity-resolution closure
```

`EXACT` and evidence-backed `TARGET_EQUIVALENT` mappings count as resolved.

Unresolved or ambiguous required identities produce `MANUAL_REQUIRED` or `BLOCKED` according to package policy.

## Capture chain

A captured raw event ID must be bound to the client/build that produced it.

```text
Retail capture
  ↓
capture/client snapshot identity
  ↓
raw event/message id
  ↓
ObservedTransition
  ↓
semantic event identity
  ↓
source→target identity resolver
  ↓
target client representation
  ↓
target server event/CSID implementation
  ↓
runtime replay/capture validation
```

A capture from a newer Retail client must never be assumed to contain the ID required by an older target client.

## Multi-client extraction

Old/new client installs should be treated as temporary extraction sources.

The desired workflow is:

```text
FFXI client install
  ↓
xi-tinkerer / client extraction
  ↓
portable Workbench identity snapshot
  ↓
retain snapshot/index + hashes
  ↓
compare against any later source/target
```

Once a client is indexed, the full client installation should not be required for every future comparison.

Initial extraction should prioritize:

- build/version fingerprint;
- FTABLE/VTABLE identity;
- per-zone dialog/event resources;
- event IDs/resource indices;
- normalized text fingerprints;
- provenance/hashes.

Later extraction can add deeper event-resource structure and EXE/DLL capability evidence.

## Current implementation

The foundation lives in:

`workbench/core/services/identity_resolver.py`

It currently provides:

- snapshot registration;
- namespace-neutral identity records;
- normalized dialog fingerprints;
- EVENT semantic keys that exclude numeric IDs;
- client-dialog ingestion;
- arbitrary snapshot-to-snapshot comparison;
- single-ID source→target resolution;
- persisted mapping records;
- package-facing identity-closure assessment.

Regression:

`test_fixtures/test_identity_resolver.py`

The regression proves a client-generation shift:

```text
older target: 10 / 11 / 12
newer source: 11 / 12 / 13
```

The same semantic events resolve as `TARGET_EQUIVALENT`, while an unscoped raw ID shared by multiple zones is rejected as ambiguous.

## Next implementation milestones

1. Add a portable client identity-snapshot extractor/importer around existing xi-tinkerer exports.
2. Attach capture metadata to the originating client snapshot.
3. Bridge `ObservedTransition` to semantic identity records.
4. Add stronger event fingerprints beyond dialog text.
5. Import legacy ID Drift server datasets as snapshot identity records.
6. Feed identity closure into canonical package scope/review/readiness.
7. Add GUI source/target selectors so ID Drift becomes a snapshot-pair resolver.
8. Validate against a real second FFXI client installation.
9. Add WotG25/capture proof data to exercise CSID/event resolution end to end.

## Safety rule

Never rewrite a captured or source numeric ID in place.

Always retain:

```text
raw source representation
source snapshot
semantic mapping
target representation
mapping evidence
confidence
```

That provenance is what makes an automated package auditable.
