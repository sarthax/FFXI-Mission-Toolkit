# Component Boundary and Product Segregation Plan

Status: **Adopted architecture direction before further root-Python relocation**

## Why this plan exists

The toolkit now serves multiple user populations whose needs overlap at the evidence layer but diverge substantially at the workflow and risk layers. Continuing the src-layout migration without defining these boundaries would risk moving modules into temporary locations and increasing cross-component coupling.

This plan therefore becomes an input to the remaining Python migration. The goal is a **modular monorepo first**, not an immediate multi-repository split. Components should be independently launchable/installable later, while continuing to share a deliberately small evidence and identity substrate.

## Product/component boundaries

### 1. Workbench Core

Shared infrastructure only. Core must remain small and non-product-specific.

Owns:

- evidence schema and logical contracts
- universal graph primitives
- provenance and source identity
- cross-source identity contracts
- common configuration/path contracts
- component/provider interfaces
- shared capability registration contracts

Core must not know about Capture UI, package workflows, editors, or any specific product shell.

Proposed shape:

```text
src/workbench/core/
  schema.py
  graph.py
  provenance.py
  identity/
  contracts/
  config/
```

### 2. Capture Workbench

Primary users: capture researchers, packet researchers, reverse-engineering/evidence users.

Owns:

- capture ingestion adapters and source manifests
- canonical packet/chat/entity/runtime observations
- Capture Data Explorer
- modular Evidence Search
- capture integrity, overlap, clock and provenance diagnostics
- packet decoding and opcode research
- PCAP/PCAPNG and lobby/world-stream research
- OCR/video/screenshot evidence alignment
- capture spatial/path reconstruction
- capture-specific correlation and Related Evidence

Proposed shape:

```text
src/workbench/captures/
  adapters/
  ingestion/
  integrity/
  correlation/
  search/
  packets/
  video/
  spatial/
  app/
```

Allowed dependencies: Core, Client Shared contracts/data readers, Reference providers where explicitly optional.

Capture must not depend on editor implementations, package migration internals, or GUI-server helper functions.

### 3. Validation and Packages

Primary users: server maintainers, migration/backport maintainers, release/package reviewers.

This is one product area with two closely related internal components.

#### Validation

Owns:

- environment/build/source comparison
- ID drift and logical schema comparison
- cross-client/server/reference validation
- live SQL/database validation
- compatibility checks
- migration readiness and validation reports
- evidence-backed contradiction/difference reporting

#### Packages

Owns:

- package assembly
- inclusion/exclusion decisions and rationale
- dependency closure
- migration/backport packaging
- proposal/package validation
- package manifests and delivery artifacts
- package-specific compatibility checks

Proposed shape:

```text
src/workbench/validation/
  environments/
  drift/
  compatibility/
  live_db/
  reports/

src/workbench/packages/
  assembly/
  dependencies/
  migration/
  validation/
  manifests/
```

Validation/Packages may consume evidence from Capture, Client Shared, Server/Development providers, and Reference providers through contracts. Those provider components must not depend back on Validation/Packages.

### 4. Development and Research Tools

Primary users: server/content developers and evidence-driven researchers asking how a feature is implemented.

Owns:

- Entity Profile
- Feature Trace and Implementation Path
- Behavior Inspector
- mission/quest extraction and dependency closure
- SQL/Lua/server implementation analysis
- Feature/Entity wiring and use-site discovery
- reference/wiki evidence workflows
- Research Sessions where they support implementation research
- source/runtime linkage and evidence dossier presentation

Proposed shape:

```text
src/workbench/devtools/
  entities/
  features/
  behavior/
  missions/
  server/
  research/
  reference/
  app/
```

Development tools should consume Capture, Client Shared and Reference evidence through provider contracts instead of importing their internal implementation modules.

### 5. Editors

Primary users: developers making intentional changes to client/server/content data.

Editors are separated because they introduce write, backup, journal and rollback risks that read-only evidence tooling does not.

Owns:

- Zone Editor
- Item Editor
- client/DAT write workflows
- editor-specific model selection and preview integration
- write journals, backups and rollback
- editing-specific validation before commit/export

Proposed shape:

```text
src/workbench/editors/
  zone/
  items/
  client/
  app/
```

Editors may use Development and Client Shared readers. Read-only components must not depend on Editors.

### 6. Client Shared

**Client Shared is not a separate end-user product.** It is the reusable read-only client evidence and decoding layer required by more than one user-facing product.

It exists because Capture, Validation, Development and Editors all need some common understanding of client data, but those products should not duplicate client parsing or depend on editor implementations.

Client Shared owns read-only capabilities such as:

- client snapshots/build fingerprints
- imported client build metadata
- ENTITY/EVENT identity extraction
- DAT inspection/parsing primitives
- model catalogs and model resolution
- binary/static inspection and indexing
- client ID/name/look/model reference data
- cross-build read-only comparison primitives
- stable client evidence/provider interfaces

It does **not** own destructive/write workflows. Item/DAT editing belongs under Editors.

Proposed shape:

```text
src/workbench/client/
  snapshots/
  identity/
  dat/
  models/
  binary/
  providers/
```

Expected consumers:

```text
Captures -------> Client Shared
Validation -----> Client Shared
Devtools -------> Client Shared
Editors --------> Client Shared
```

Client Shared should depend only on Core/runtime contracts and vendor adapters needed for reading client data.

### 7. Bootstrap and Tests

**Bootstrap / Tests is repository infrastructure, not a product component.**

The name covers two different non-product responsibilities:

#### Bootstrap / operator infrastructure

Files and workflows required to install, initialize, launch or maintain the repository itself:

- `setup.bat`
- `start.bat`
- `reset_install.bat`
- external-tool installers
- xi-tinkerer installer/bootstrap
- environment setup helpers
- package/editable-install setup
- optional component/profile launchers later

These should normally live under `scripts/bootstrap/` or remain as thin root launchers when user convenience requires it.

#### Tests / regression infrastructure

Yes: this includes the regression suite against the toolset, but it is broader than only end-to-end regression.

It includes:

- Workbench Regression jobs
- Src Layout Regression
- focused subsystem regressions
- unit tests
- integration tests
- fixture/sample datasets
- compatibility tests
- architecture/import-boundary tests
- editable-install smoke tests
- component-isolation tests
- test-only utilities

Target shape:

```text
scripts/
  bootstrap/
  maintenance/

tests/
  unit/
  integration/
  regression/
  architecture/
  fixtures/
```

The test suite should eventually prove both that the full toolkit works and that individual product profiles can operate without importing unrelated components.

## Dependency direction

The intended dependency direction is:

```text
                     +----------------+
                     | Workbench Core |
                     +----------------+
                       ^   ^   ^   ^
                       |   |   |   |
              +--------+   |   |   +---------+
              |            |   |             |
      +---------------+    |   |     +---------------+
      | Client Shared |    |   |     |   Reference   |
      +---------------+    |   |     +---------------+
          ^   ^   ^   ^    |   |             ^
          |   |   |   |    |   |             |
          |   |   |   +----|---|-------------+
          |   |   |        |   |
  +----------+ | +-----------+ +----------------+
  | Captures | | | Devtools  | | Validation /   |
  +----------+ | +-----------+ | Packages       |
               |               +----------------+
               |
           +---------+
           | Editors |
           +---------+
```

This diagram describes allowed consumption, not mandatory installation. Cross-component integration should occur through provider/contracts rather than direct imports of internal modules.

## Forbidden coupling rules

After boundary enforcement begins:

1. Core may not import any product component.
2. Client Shared may not import Editors.
3. Capture may not import Editors or package/backport internals.
4. Validation/Packages may consume Capture/Client/Development evidence through contracts, but provider components may not depend back on Validation/Packages.
5. Development tools may consume Capture/Client/Reference providers, but should not import Capture UI/routes or editor implementations.
6. Read-only components may not import write/editor implementation modules.
7. No component may import helpers from the monolithic `gui_server.py`.
8. New cross-component calls require either a Core contract/provider or an explicitly documented public component API.

## Data ownership

Do not physically split the SQLite database during this architecture phase. The evidence graph is intentionally cross-source and remains a major toolkit strength.

Instead, establish logical ownership:

```text
core / graph / identity tables   -> Core/shared
capture_*                        -> Captures
client_*                         -> Client Shared
validation_*                     -> Validation
package_*                        -> Packages
research/dev_*                   -> Development/Research
editor_*                         -> Editors where persistent editor state is needed
```

A component should write only the tables it owns except through an explicit shared API. Shared identities/evidence remain readable across installed components.

## UI/application composition

The current monolithic `gui_server.py` is the largest accidental coupling point and must be decomposed late in the migration after service boundaries are established.

Target application composition:

```python
app = create_app()
register_core(app)
register_client_shared(app)

if captures_enabled:
    register_captures(app)
if validation_enabled:
    register_validation(app)
if devtools_enabled:
    register_devtools(app)
if editors_enabled:
    register_editors(app)
```

Each product component should eventually own its own routes, templates/navigation registration, service wiring and optional dependencies.

Possible user-facing launch profiles:

```text
start-captures
start-validation
start-devtools
start-editors
start-full
```

Possible packaging profiles later:

```text
mission-toolkit[captures]
mission-toolkit[validation]
mission-toolkit[dev]
mission-toolkit[editors]
mission-toolkit[full]
```

These are target capabilities, not an immediate distribution change.

## Relationship to the src-layout migration

The remaining root-Python migration is now subordinate to this component plan.

Before relocating another root implementation, determine its final component ownership. Avoid moves such as:

```text
root -> workbench.core.services -> workbench.devtools
```

when the final boundary is already known.

Examples:

```text
lookup_entity.py        -> src/workbench/devtools/entities/lookup.py
entity_profile.py       -> src/workbench/devtools/entities/profile.py
packet_decode.py        -> src/workbench/captures/packets/decode.py
capture_backtrace.py    -> src/workbench/captures/correlation/backtrace.py
backport_package.py     -> src/workbench/packages/migration/package.py
zone_edit.py            -> src/workbench/editors/zone/editor.py
item_edit.py            -> src/workbench/editors/items/editor.py
client_binary_index.py  -> src/workbench/client/binary/index.py
```

Compatibility wrappers may remain at root when documented/operator workflows still use physical filenames.

## Execution sequence

### Phase A — Component inventory and ownership map

- Reclassify all remaining root Python files by final component.
- Reclassify existing `src/workbench` modules where current placement is broader than the new boundary.
- Identify direct cross-component imports.
- Identify routes/templates/navigation ownership.
- Identify optional dependency groups and external tools per component.
- Identify DB table ownership.

Gate: every active Python module has one owning component or is explicitly shared infrastructure.

### Phase B — Contracts and architecture enforcement

- Add Core provider/protocol contracts for cross-component evidence access.
- Add architecture tests for forbidden import directions.
- Add component capability registration.
- Add isolation smoke tests that import each component without unrelated components.

Gate: new coupling cannot silently re-enter the codebase.

### Phase C — Resume root migration by component

Recommended order:

1. Development entity chain (`lookup_entity`, `entity_profile`) after path/dependency prep.
2. Small Development server/mission analyzers.
3. Reference/Research pieces into Development where appropriate.
4. Client Shared read-only utilities.
5. Validation/Packages and migration/backport tooling.
6. Capture ingestion/protocol/OCR services.
7. Editors and client writers.
8. Bootstrap/tests relocation.
9. Settings/launch profile conversion.
10. `gui_server.py` decomposition and move last.

### Phase D — Product profiles

- Introduce capability flags/component registry.
- Produce profile-specific navigation and route registration.
- Split optional dependencies.
- Prove Capture-only, Validation-only, Development-only, Editor-only and Full profiles in CI.

### Phase E — Distribution decision

Only after isolation is proven should the project decide whether any component becomes a separate package/repository.

A repository split is not required for different user bases. Independent install/launch profiles in one repository are the preferred first outcome.

## Acceptance criteria

The segregation work is complete enough for product-profile use when:

- each module has exactly one component owner;
- Core contains no product-specific implementation;
- product components communicate across boundaries through documented APIs/providers;
- no product imports `gui_server.py` helpers;
- write/editor code is absent from Capture/Validation/Development dependency closure unless explicitly installed;
- Capture-only startup does not import package/editor modules;
- Validation-only startup does not import OCR/editor modules;
- Development-only startup can use optional Capture/Client evidence providers when present but still starts without them;
- Editor startup depends on read-only shared services but read-only profiles do not depend on Editors;
- component-specific tests and full-suite regression are green;
- the remaining src migration follows final component destinations instead of temporary intermediate locations.
