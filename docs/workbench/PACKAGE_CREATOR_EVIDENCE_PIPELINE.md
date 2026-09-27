# Package Creator Evidence Pipeline

Status: CANONICAL DESIGN REFERENCE  
Baseline: 2026-09-26  
Scope: Packages, Captures, canonical graph, research/agent proposals, validation

## Purpose

The Package Creator exists to turn fragmented FFXI evidence into a reviewable, evidence-backed implementation or migration package without requiring the user to manually decode server source, packet logs, Retail captures, client resources, and reference material.

Its goal is not simply to collect files. It must determine whether a feature is observable, understood, implementable, viable on the selected target, complete or intentionally partial, supported by evidence, and validated against expected or observed behavior.

A dependency may be an artifact, entity, capability, acquisition path, state transition, runtime behavior, or expected behavior that is absent from the current implementation.

## Core distinction: four truth domains

The Workbench must preserve these independently.

### Expected behavior

Reference/wiki material, historical implementations, mission/quest helpers, enums, explicit requirements, and other evidence may establish what behavior is expected.

Expected behavior does not prove that the current server implements it or that a Retail capture observed it.

### Observed behavior

Retail Live Captures establish what actually occurred on a particular Retail client/server combination.

Examples include:

- entity/NPC interaction;
- packet sequences;
- event/message identifiers;
- CSIDs after semantic confirmation;
- event arguments and updates;
- item/key-item changes;
- movement and zone transitions;
- mob spawn/despawn/death;
- battle or instance entry/exit;
- timing and ordering.

A Retail capture is observational truth. It is not silently promoted to server implementation truth.

### Implemented behavior

Server/client source and data establish what the selected implementation contains:

- Lua;
- SQL/data;
- C++;
- bindings;
- enums/constants;
- build integration;
- client DAT/EXE/DLL assets and capabilities;
- persisted database state.

Source presence alone does not prove that the behavior matches Retail.

### Proposed behavior

A model, agent, or developer may propose missing implementation by synthesizing evidence.

Proposed behavior remains a proposal until deterministic verification and/or explicit human review promotes an appropriate canonical record.

## Evidence domains

The Workbench treats evidence domains independently:

- SERVER_SOURCE / SERVER_DB / SERVER_CPP
- CLIENT_DAT / CLIENT_EXE / CLIENT_DLL
- PACKET
- CAPTURE
- REFERENCE
- historical source snapshots
- DERIVED / INFERRED evidence

No evidence domain is silently promoted into another.

A wiki statement is not server truth. A Retail capture is not source truth. A server script is not proof that Retail behaved identically.

## The four permanent Package Creator closure proofs

### Medusa — cross-system/world-state closure

Medusa proves that feature closure can reach helpers, spell/skill lists, mob skills, job-special mixins, loot/items, titles/text, engine requirements, and system lifecycle behavior outside the primary entity script.

### Coiler — runtime/representation closure

Coiler proves that an inventory identity may map to a different internal identity and execute through dynamic Lua dispatch, shared behavior, C++ runtime logic, persistence, downstream consumers, conditional interactions, and reviewer-controlled acquisition paths.

### Heat Seeker — recursive acquisition/producibility closure

Heat Seeker proves that a required item is not viable merely because it exists. A selected acquisition path must recursively resolve until every prerequisite is independently obtainable and required client/runtime capability is present.

### The Will of the World — branching state-machine closure

WotG25 proves that a dependency can be a required sequence of states/events rather than a file or SQL row.

It requires representation of:

- mission and quest gates;
- OR branches;
- quest/mission variables;
- entity and zone-in triggers;
- zone/entity/content-scoped event identity;
- event arguments;
- event update/finish behavior;
- trades;
- key-item grant/require/consume/reissue lifecycle;
- timers/day gates;
- combat/battlefield/fishing/system dependencies;
- expected-but-missing implementation.

Detailed proof: `WOTG25_MISSION_PACKAGE_PROOF.md`.

## State-machine closure

State transitions are first-class dependencies.

Conceptually:

```text
State
  -> Trigger
  -> Event / interaction
  -> Preconditions
  -> Effects
  -> Next state
```

A feature is not behaviorally complete merely because all referenced files, entities, and items exist.

## Event identity

A numeric CSID/event number is not sufficient identity.

Canonical event context should preserve, where evidence permits:

```text
zone
actor/entity or zone-in source
event/csid
content owner
trigger/preconditions
event arguments
event updates
event finish behavior
state effects
evidence provenance
```

A numeric identifier remains semantically neutral until evidence proves whether it is a CSID, message ID, option, packet field, or other identifier.

## Retail Capture reconstruction loop

Captures are not merely post-implementation validators. They can provide enough observational evidence to reconstruct server behavior that is missing from the current source.

The canonical loop is:

```text
Retail Live Capture
    |
    v
Normalize observations
    |
    v
Correlate packet / event / entity / state evidence
    |
    v
ObservedTransition evidence
    |
    v
Compare against:
  - server implementation
  - client capabilities/assets
  - reference expectations
  - historical source
    |
    v
Gap / contradiction classification
    |
    +--> implementation found -> validate against observation
    |
    +--> implementation missing/partial/placeholder
             |
             v
       evidence-bounded reconstruction proposal
             |
             v
       package proposal + provenance
             |
             v
       deterministic verification / validation
             |
             v
       replay or compare against Retail behavior
             |
             v
       human review / approval
```

This closes the original Mission Toolkit loop: make behavior observable, comparative, viable, reconstructable, and verifiable without forcing the developer to manually decode every packet and log.

## ObservedTransition

The deterministic capture layer needs a generic normalized handoff record for correlated behavior.

A conceptual record contains:

```yaml
transition_id: capture-transition:...
capture_id: ...
zone: ...
actor: ...
event_identity:
  numeric_id: ...
  semantic_kind: CSID | MESSAGE_OR_EVENT_ID | ...
owner: optional feature/quest/mission/system
trigger: ...
preconditions: [...]
effects:
  - kind: ...
    subject: ...
    value: ...
evidence_ids:
  - ...
status: OBSERVED
```

The core does not need mission-specific fields. Mission plugins/analyzers may interpret generic effects such as state change, item/key-item change, entity spawn, completion, or timer behavior.

## Capture-aware implementation gap semantics

The exact canonical status names may evolve, but these distinctions must survive:

```text
IMPLEMENTED_AND_CAPTURE_OBSERVED
PLACEHOLDER_WITH_RETAIL_BEHAVIOR_AVAILABLE
PARTIAL_WITH_RETAIL_BEHAVIOR_AVAILABLE
MISSING_WITH_RETAIL_BEHAVIOR_AVAILABLE
OBSERVED_WITH_IMPLEMENTATION_UNKNOWN
MISSING_WITH_REFERENCE_ONLY
```

A missing implementation with a full Retail observation is materially different from a gap known only from a walkthrough.

Likewise, an accepted gap remains incomplete. Reviewer acceptance changes package viability/readiness policy; it does not erase completeness truth.

## Agent / LLM boundary

Deterministic tooling owns:

- capture ingestion;
- packet/event/entity extraction;
- evidence normalization;
- graph records;
- source comparison;
- gap classification;
- deterministic validators;
- package cohesion and application gates.

An LLM/agent may:

- investigate unresolved graph endpoints;
- correlate evidence;
- explain contradictions;
- infer a likely state transition;
- draft Lua/SQL/C++ changes;
- draft migration actions/package changes;
- recommend validation steps.

The governing rule is:

> The agent proposes closure. The evidence graph explains why. Deterministic tooling validates it.

Agent output never silently becomes canonical truth.

Generated proposals retain:

- source/target snapshot identity;
- capture IDs;
- supporting and contradicting evidence IDs;
- relevant packet/event/entity identities;
- inferred relationships and assumptions;
- confidence/status;
- validation requirements.

## Viability vs completeness

Viability and completeness are separate dimensions.

Examples:

- one nation branch can be viable while another is missing;
- a placeholder battlefield may be accepted temporarily;
- an acquisition path may be intentionally excluded;
- a target-equivalent representation may replace the source representation.

Human review may accept a gap.

Acceptance must not convert the gap into `COMPLETE`.

## Package pipeline

```text
Feature/root selection
 -> evidence + dependency discovery
 -> closure graph
 -> implementation comparison
 -> acquisition/state/runtime analysis
 -> unresolved gap detection
 -> capture/reference correlation
 -> reviewer scope decisions
 -> agent-assisted proposals where appropriate
 -> deterministic MigrationActions
 -> package assembly
 -> provenance/cohesion validation
 -> runtime/capture validation
 -> review
 -> approval/apply through existing safety gates
```

## Current implementation priorities

1. Add a generic `ObservedTransition` normalization/classification layer without changing existing capture ingestion formats.
2. Correlate capture event/packet/entity observations into transition evidence with provenance.
3. Add generic mission/quest state-machine extraction against the WotG25 proof.
4. Compare observed transitions with implementation and expected-reference transitions.
5. Emit explicit capture-aware implementation-gap findings.
6. Make research/agent tools consume those findings and evidence IDs rather than raw opaque logs.
7. Add proposal generation for a missing transition while preserving proposal-only authority.
8. Validate reconstructed behavior against capture observations.
9. Add a permanent capture-reconstruction regression fixture using real or deliberately synthetic, clearly labeled evidence.

## Resume here

As of 2026-09-26:

- package dependency scope review and decision ledgers exist;
- Medusa, Coiler, Heat Seeker, and WotG25 are permanent proof cases;
- recursive crafting closure exists;
- capture ingestion, packet/event graph edges, capture backtrace, and runtime validation exist;
- the evidence-aware research/proposal foundation exists;
- WotG25 exposes the need for generic state-machine/CSID analysis;
- the missing architectural seam is deterministic normalization of Retail observations into behavior/state-transition evidence that can drive gap classification and evidence-bounded reconstruction proposals.

The immediate implementation seam is therefore:

```text
capture evidence
 -> ObservedTransition
 -> implementation comparison
 -> capture-aware gap
 -> research/agent proposal
 -> deterministic validation
```

Do not bypass the canonical evidence, proposal verification, package cohesion, readiness, approval, drift, backup, journal, or rollback gates.
