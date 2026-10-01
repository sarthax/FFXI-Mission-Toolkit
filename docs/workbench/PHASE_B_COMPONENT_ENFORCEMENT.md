# Phase B — Component Contracts and Architecture Enforcement

Status: **implemented foundation; legacy inventory remains for Phase C relocation**

## What Phase B establishes

Phase B turns the adopted component boundaries into executable architecture rules before production implementations are moved again.

### Shared Core contracts

`workbench.core.contracts` defines data-oriented evidence provider protocols and the neutral `EvidenceRecord` envelope. Core owns the contract but never imports provider implementations.

Initial provider contracts:

- `CaptureEvidenceProvider`
- `ClientEvidenceProvider`
- `DevelopmentEvidenceProvider`
- `ReferenceEvidenceProvider`

These are intentionally small. Product-specific query methods belong in the owning component, not in Core.

### Component capability metadata

`workbench.core.components` defines declarative component capability metadata for:

- Core
- Client Shared
- Captures
- Validation / Packages
- Development / Research
- Editors

The registry describes capability names and optional component relationships without importing product code.

### Final component namespaces

The following final namespaces now exist so Phase C can relocate modules directly to their destination:

- `workbench.captures`
- `workbench.validation`
- `workbench.packages`
- `workbench.devtools`
- `workbench.editors`

`workbench.client` remains Client Shared.

### Architecture enforcement

`test_component_boundaries.py` enforces dependency direction for code in final component namespaces.

Current legacy placements already recorded by Phase A are not silently blessed. In particular, `workbench.core.services` is temporarily excluded because Phase A explicitly identified it as a mixed legacy namespace. Phase C must shrink that exception as services move to their final owners.

The test also verifies that Core contracts do not import product components.

### Isolation smoke tests

Each user-facing component namespace is imported in a fresh Python process and checked to ensure that unrelated product namespaces are not pulled into `sys.modules` merely by importing the component.

This is the first executable proof required for future profile-specific startup/install behavior.

## Phase C handoff

Phase C should move implementations in coherent component batches and remove corresponding legacy exceptions as each batch lands.

Recommended first batch remains the Development entity chain:

1. `lookup_entity.py`
2. `entity_profile.py`
3. related Entity Profile graph/presentation services currently under `core/services`

After each batch, architecture tests should be tightened rather than widening exceptions.
