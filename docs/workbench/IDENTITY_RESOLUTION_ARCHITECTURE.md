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


## 2026-09-26 implementation milestone — installed client extraction + capture bridge

The snapshot-aware resolver now has a complete first ingestion path from an installed FFXI client.

New implementation:

- `workbench/client/identity_extract.py`
  - wraps the existing xi-tinkerer `export-dat` command;
  - copies and hashes FTABLE/VTABLE when present;
  - exports selected zone dialog/event tables;
  - records per-resource SHA-256, DAT id, zone id/key, size, and extraction failures;
  - writes one portable `identity_snapshot.json`;
  - computes a manifest-level client fingerprint;
  - does not guess the client build from DLL/file metadata; the build label is supplied explicitly and remains independently checkable against the content fingerprint.

- `workbench/client/identity_snapshot.py::ingest_client_identity_manifest`
  - registers a portable client snapshot exactly once;
  - ingests all supported zone resources under that snapshot;
  - preserves the manifest-level fingerprint instead of overwriting snapshot provenance zone-by-zone.

- `workbench/runtime/observed_transition.py`
  - now carries `client_snapshot_id` explicitly.

- `workbench/runtime/identity_bridge.py`
  - resolves a typed observed capture event from its originating client snapshot into a selected target snapshot;
  - refuses to translate `MESSAGE_OR_EVENT_ID` as EVENT/CSID until upstream packet/correlation evidence narrows the identifier type;
  - therefore preserves the raw capture value and uncertainty rather than manufacturing a target CSID.

### CLI

A client install can now be extracted with:

```text
python -m workbench.cli.client_identity_snapshot \
  --client-root "C:\\...\\FINAL FANTASY XI" \
  --xi-tinkerer "vendor\\xi-tinkerer\\target\\release\\xi-tinkerer-cli.exe" \
  --snapshot-id "client:30191204_1" \
  --build "30191204_1" \
  --output "client_snapshots\\30191204_1" \
  --zone 87:NORTH_GUSTABERG_S \
  --zone 83:ROLANBERRY_FIELDS
```

Use `--all-zones` to attempt zone IDs 0-511. Unsupported/missing exports are retained as manifest failures rather than aborting the snapshot.

The completed snapshot may also be ingested directly into a Workbench DB with:

```text
--ingest-db workbench.db
```

### Second-client workflow

When another historical client becomes available:

1. Keep the install unmodified until extraction completes.
2. Assign an explicit snapshot/build label.
3. Extract the same zone set, or use `--all-zones`.
4. Retain the generated portable snapshot directory.
5. Ingest both snapshots.
6. Run snapshot-to-snapshot EVENT identity comparison.
7. Treat `TARGET_EQUIVALENT` as an evidence-backed mapping, not a literal-id match.
8. Investigate ambiguous/source-only/target-only identities individually.
9. Use the resolved target representation when evaluating or generating server-side event code.

### Current end-to-end contract

```text
installed Retail client A
  -> portable IdentitySnapshot A
installed Retail client B
  -> portable IdentitySnapshot B

Retail capture produced by A
  -> ObservedTransition(client_snapshot_id=A, raw event id)
  -> packet/correlation typing (EVENT/CSID vs unresolved)
  -> semantic identity lookup in A
  -> target representation lookup in B
  -> EXACT / TARGET_EQUIVALENT / unresolved / ambiguous
  -> identity-closure package dimension
  -> target server implementation comparison
```

This is intentionally symmetrical: A and B can represent old/new Retail builds, server-aligned client generations, or capture/source/target combinations.


## 2026-09-26 implementation milestone — structural/composite event fingerprinting

Event identity no longer depends only on normalized dialog text.

### Event resource extraction

Installed-client snapshots now also export each zone's event DAT using the vendored
`vendor/FFXI-Resources/scripts/events/dats.yaml` zone map.

Each exported event resource retains:

- zone id/key;
- original event DAT path;
- actor/entity block id;
- event id as a snapshot-specific representation;
- block index;
- immediate-data table;
- raw event bytecode;
- resource SHA-256 and client snapshot provenance.

Alternate event resources mapped to the same zone are retained as separate resources instead of
being silently collapsed.

### Fingerprint hierarchy

`workbench/client/event_fingerprint.py` produces independent signals.

**Exact bytecode fingerprint**

```text
SHA-256(raw event bytecode)
```

This is the strongest literal equality signal but is intentionally brittle. A changed immediate
value makes this hash different even when the event remains semantically equivalent.

**Decoded structural fingerprint**

The bytecode is decoded into:

```text
opcode sequence
instruction-length sequence
event bytecode length
```

Raw event IDs, actor IDs, immediate argument values, block event count, and block-level data count
are excluded from semantic structure.

This permits an event to retain identity when:

- the event/CSID number moves;
- message IDs move;
- immediate values move;
- unrelated sibling events are added to the same actor block.

The richer vendored FFXI-EventsDump parser is used when its optional dependencies are available.
A dependency-free fallback reads the vendored opcode Python source with the standard-library AST,
including inherited `get_args()` and `calculate_length()` definitions. Variable-length opcodes
that cannot be safely decoded without executing their custom length logic cause a conservative
RAW_ONLY fallback rather than invented instruction boundaries.

**Message-reference evidence**

Decoded opcode argument definitions are inspected for message-id arguments.

Reference-table values such as `0x8000 + index` are resolved through the event block's immediate
data table before looking up the zone dialog table.

The numeric message IDs themselves are not part of semantic identity.

Instead, referenced Retail text is normalized and hashed.

Example:

```text
new client:
  event 77
  PRINT_MESSAGE 503
  text = "The same Retail line."

old client:
  event 10
  PRINT_MESSAGE References[0]
  References[0] = 500
  text = "The same Retail line."

result:
  event numeric id differs
  message numeric id differs
  opcode structure agrees
  Retail text fingerprint agrees
  => composite event identity matches
```

**Composite fingerprint**

When referenced dialog text is available:

```text
structural fingerprint
+ ordered referenced Retail-text fingerprints
= composite fingerprint
```

The composite fingerprint is preferred for EVENT semantic identity. If no resolvable message text
exists, the structural fingerprint remains the semantic basis.

### Confidence

Fingerprint comparison preserves signal strength:

| Result | Meaning | Confidence |
|---|---|---|
| `EXACT_BYTECODE` | exact raw bytecode | VERIFIED |
| `COMPOSITE_STRUCTURE_TEXT_MATCH` | decoded structure + referenced Retail text | HIGH |
| `STRUCTURE_AND_TEXT_MATCH` | decoded structure + separately supplied text evidence | HIGH |
| `STRUCTURE_MATCH` | decoded instruction shape only | HIGH |
| `COARSE_SHAPE_MATCH` | decoder unavailable; only coarse fallback shape | LOW |
| `TEXT_ONLY_MATCH` | text matches but event structure does not | LOW |
| `NO_MATCH` | no supported equivalence | UNKNOWN |

Same dialog text alone must never prove event equivalence.

### Dialog/event namespace separation

Dialog table indices are now `DIALOG_TEXT_ID` by default.

They are supporting evidence for event identity and are not silently treated as `EVENT` or
`CSID` identifiers.

### Actor-scoped capture resolution

Event DATs are actor/entity-block scoped, and the same numeric CSID may appear under multiple actors
in the same zone.

`ObservedTransition.actor_id` is therefore used to constrain the **source** event lookup when
available.

The actor id is not copied to the target snapshot. Target actor identity still requires its own
identity mapping/evidence; if multiple target event candidates remain, resolution is
`TARGET_ID_AMBIGUOUS`.



### Portable entity-role fingerprint evidence

Decoded event arguments now retain only entity references whose semantics are intrinsically portable
across client generations:

- `LOCAL_PLAYER`
- `EVENT_ENTITY`
- party-member references
- alliance-member references
- party-reference slots

These roles participate in the decoded structural fingerprint.

Ordinary raw entity/server IDs do **not** participate in the semantic hash. Two otherwise identical
events that reference different literal NPC IDs therefore remain structurally equivalent until the
separate entity identity resolver determines whether those NPC representations correspond.

Conversely, changing a semantic role such as `EVENT_ENTITY` to `LOCAL_PLAYER` changes the
event structural fingerprint.

This preserves the separation:

```text
portable semantic entity role -> event fingerprint evidence
raw actor/NPC/entity id       -> snapshot context / separate identity resolution
```

### Package confidence policy

Identity closure now accepts a minimum confidence threshold.

A mapping can be numerically resolved while still failing automatic package readiness if its
evidence confidence is below policy.

Recommended package policy for automatic event translation:

```text
minimum_confidence = HIGH
```

This allows decoded structural/composite matches while forcing RAW_ONLY, text-only, inferred, and
ambiguous mappings into manual review.

### Regression proofs

The current regression set now proves:

1. different event IDs with equivalent decoded structure;
2. changed immediate values with equivalent structure;
3. same text with different structure remains LOW-confidence only;
4. message ID drift with stable Retail text;
5. immediate-data reference resolution for message IDs;
6. unrelated actor-block growth does not change event semantic identity;
7. repeated CSID under multiple source actors is ambiguous without actor context;
8. capture/source actor context can select the correct source event;
9. duplicate semantic candidates in the target remain ambiguous rather than auto-selected.

Primary fixtures:

- `test_fixtures/test_event_fingerprint.py`
- `test_fixtures/test_event_identity_resolution.py`
- `test_fixtures/test_client_identity_extract.py`
- `test_fixtures/test_capture_identity_bridge.py`

### Next event-identity work

Before declaring identity closure complete, remaining work includes:

1. test against a real second FFXI client build;
2. add target actor/entity semantic resolution across snapshots;
3. decode variable-length event opcodes safely in the dependency-free path or preserve their
   richer-parser provenance when the full parser is available;
4. extract additional stable semantic arguments such as referenced entities/resources without
   treating their raw numeric IDs as portable;
5. feed HIGH-confidence EVENT mappings directly into Package Scope/Readiness;
6. surface source/target snapshot selection and evidence breakdown in the ID Drift GUI.
