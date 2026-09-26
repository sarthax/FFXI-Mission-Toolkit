# Package Dependency Closure & Scope Review

## Purpose

The Packages workflow must answer four questions before a migration package is assembled:

1. What does this feature/migration depend on?
2. Why was each dependency discovered?
3. Is each dependency included, already satisfied by the target, unnecessary, explicitly excluded, or still uncertain?
4. Who/what made that decision, and what evidence/reason supports it?

Package assembly is downstream of this review. It must not silently decide that missing dependencies are safe.

## Workflow

```text
Feature / migration analysis
        ↓
MigrationAction roots
        ↓
Dependency closure discovery
        ↓
Scope Review
        ↓
Resolve questionable dependencies
        ↓
Freeze reviewed scope
        ↓
Create Package
        ↓
Review & Readiness
        ↓
Validation / future approval+apply gates
```

### 1. Migration roots

The current implementation starts with canonical `MigrationAction` records that have an `artifact_id`.
These are the migration's known package roots.

A root retains the upstream migration recommendation:

- normal actionable roots default to `INCLUDE`;
- upstream `NOT_REQUIRED` roots remain `NOT_REQUIRED` and retain their documented reason;
- blocked/failed roots remain questionable.

### 2. Transitive discovery

`workbench.migrations.package_scope.build_dependency_scope()` follows canonical outgoing graph edges from those roots.

Current dependency relationships considered by the prototype include:

- `REQUIRES`
- `IMPORTS`
- `REFERENCES`
- `USES_ID`
- `USES_PACKET`
- `USES_ENUM`
- `USES_CLIENT_CAPABILITY`
- `BINDS`
- `BUILDS_INTO`
- `CALLS`
- `IMPLEMENTED_BY`
- `HANDLED_BY`

Default UI depth is 6; the service supports a bounded maximum of 12 and a node limit to prevent unbounded traversal.

Every discovered row records:

- node ID and type;
- depth;
- parent node;
- relationship and relationship ID;
- graph status/confidence;
- evidence ID;
- source snapshot;
- artifact path/type when the node is an artifact;
- the complete first discovery path from a migration root.

### 3. Conservative default

A newly discovered transitive dependency defaults to:

`QUESTIONABLE`

Discovery does **not** mean:

- the artifact must be copied;
- the target lacks it;
- the target is equivalent;
- the dependency can be safely excluded.

Those require additional evidence or a reviewed decision.

## User decisions

User decisions are persisted separately from graph evidence in `package_scope_decisions`.

Supported decisions:

| Decision | Meaning |
| --- | --- |
| `AUTO` | Accept the current system recommendation. |
| `INCLUDE` | Keep this dependency in package scope. |
| `QUESTIONABLE` | Leave unresolved and block scope completion. |
| `TARGET_EQUIVALENT` | Reviewer asserts the target already provides equivalent behavior/data. |
| `NOT_REQUIRED` | Reviewer asserts the dependency is not semantically required for this migration. |
| `EXCLUDE` | Reviewer deliberately omits the dependency. |

`TARGET_EQUIVALENT`, `NOT_REQUIRED`, and `EXCLUDE` require an explicit reason.

Tags are independent of the decision. Examples:

- `investigate`
- `custom-server`
- `known-drift`
- `needs-runtime-test`
- `client-sensitive`
- `engine-sensitive`

Changing any decision returns the scope to `DRAFT`.

## Non-artifact dependencies

A function, binding, enum, capability, packet, entity reference, or other non-artifact node cannot be resolved merely by selecting `INCLUDE`.

If the graph has not connected that dependency to something packageable, the scope remains unresolved.

The reviewer must either:

- resolve/discover the corresponding source artifact;
- classify it as target-equivalent with a reason;
- classify it as not required with a reason;
- explicitly exclude it with a reason.

This prevents a package from appearing complete while a required engine dependency exists only as an evidence node.

## Review state and stale detection

A scope can be marked `REVIEWED` only when no questionable/unresolved nodes remain.

The reviewed state stores a SHA-256 fingerprint of:

- discovered nodes;
- graph relationships;
- confidence/status/evidence;
- source snapshots;
- recommendations;
- user decisions;
- reasons;
- tags.

If later analysis changes dependency closure or any reviewed decision, the fingerprint changes and the review becomes:

`STALE`

Package creation then returns to `REVIEW_REQUIRED`.

## Closure status

Current closure statuses:

- `COMPLETE`
- `COMPLETE_WITH_REVIEWED_EXCLUSIONS`
- `COMPLETE_WITH_USER_EXCLUSIONS`
- `MANUAL_REQUIRED`
- `BLOCKED`

Package gate statuses include:

- `READY`
- `REVIEW_REQUIRED`
- `MANUAL_REQUIRED`
- `BLOCKED`

Package creation requires the scope to be `REVIEWED`. A `READY` scope produces a normal reviewed package. A reviewed `MANUAL_REQUIRED` scope may still be assembled for inspection (for example after an explicit user `EXCLUDE`), but it cannot pass automatic apply readiness.

## Package creation behavior

Reviewed scope is embedded directly in the generated manifest.

New reviewed-scope manifests use schema 3 and include:

```text
dependency_scope
  closure_status
  package_gate
  review metadata
  counts
  discovered_count
  items[]
    node
    discovery path
    evidence
    recommendation
    user decision
    effective decision
    reason
    tags
```

For migration-root artifacts:

- `INCLUDE` keeps the original MigrationAction.
- `TARGET_EQUIVALENT`, `NOT_REQUIRED`, or `EXCLUDE` converts the package action to explicit `NOT_REQUIRED` with the reviewed reason.
- explicit `EXCLUDE` preserves user agency but makes the scope/package `MANUAL_REQUIRED`; it is not treated as evidence that the target safely satisfies the dependency.

For a newly discovered artifact explicitly marked `INCLUDE`:

- package creation adds a conservative `MANUAL_REVIEW` MigrationAction;
- it does not silently claim that a converter is safe.

The full dependency decision ledger remains in the manifest even when a dependency is not materialized.

## Apply-readiness guardrail

Schema-3 packages require:

`dependency_scope.package_gate == READY`

before `assess_apply_readiness()` can report READY.

Schema-2 packages remain supported as legacy packages so existing fixtures/workflows are not retroactively broken, but Review & Readiness warns when a package has no dependency-scope ledger.

## GUI

Packages now includes:

- **Package Library**
- **Scope Review**
- **Create Package**
- **Review & Readiness**
- **Backport Package (legacy)**

Scope Review provides:

- migration selection;
- bounded dependency depth;
- search/filtering;
- tree-like indentation by discovery depth;
- relationship/evidence/confidence visibility;
- decision override;
- reason entry;
- tagging;
- unresolved count;
- closure state;
- review freeze.

Review & Readiness shows the embedded dependency ledger for schema-3 packages.

## Critical limitation: discovery completeness

This implementation establishes the **review workflow and guardrails**. It does not by itself prove that dependency discovery is complete.

The scope can only review graph relationships that already exist.

For example, an FFXI mob may transitively require:

```text
spawn
  → group
    → pool
      → family
      → skill list
        → mob skills
      → spell list
    → drop list
      → item records
  → Lua script
    → required modules
      → Lua bindings
        → C++ functions
          → enums/constants/build targets
```

If those logical SQL or Lua/engine relationships have not been indexed into the canonical graph, the scope review cannot discover them yet.

Therefore **READY currently means the reviewed graph closure is complete, not that every possible FFXI dependency has already been proven discoverable**.

That distinction must remain visible until dependency-discovery coverage is validated.

## Next audit / proof cases

Before approval/apply UI is built, validate dependency discovery against two real cases.

### Case A — complex mob

Manually enumerate and compare Workbench discovery for:

- spawn;
- group;
- pool;
- family;
- family system;
- skill list;
- mob skills;
- spell list;
- drops;
- dropped item records;
- mob Lua;
- required Lua modules/mixins;
- Lua bindings;
- required C++ functions/enums/build targets.

Every manually identified dependency must be either:

- automatically discovered;
- represented by an explicit analyzer gap;
- deliberately unsupported with a visible reason.

### Case B — instance/mission

Use Ancient Vows or a representative Assault instance and verify:

- instance registry;
- entity membership;
- NPCs/mobs;
- all relevant mob dependency chains;
- zone/instance/mission Lua;
- globals/modules;
- IDs/constants;
- SQL membership/registry/reward data;
- bindings/C++;
- client/runtime requirements where applicable.

## Required future analyzers

Likely next implementation work:

1. logical SQL relationship closure beyond the current instance slice;
2. mob-specific logical relationships expressed generically through adapter/schema metadata;
3. static Lua `require()` / module dependency indexing;
4. Lua global/module symbol references;
5. Lua binding → C++ → enum/build-target closure;
6. target-equivalence comparison for each logical dependency;
7. explicit analyzer-gap records for dynamic/unresolvable dependencies;
8. downstream-dependency warnings when a user attempts an exclusion.

The goal is not maximum automatic inclusion. The goal is maximum **explainability, reviewer agency, and evidence-backed closure**.
