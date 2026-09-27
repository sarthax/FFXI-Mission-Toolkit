# Repository Structure Rework

## Decision
Begin the repository-structure migration **now**, but do not mass-move the existing Python tools yet.

The current root contains a large collection of mature standalone scripts. Moving all of them before their shared service boundaries are stable would create a large import/path breakage window. Use a staged migration:
1. Establish package namespaces and architectural ownership now.
2. Stabilize canonical models/services behind those namespaces.
3. Move one subsystem at a time.
4. Keep temporary compatibility shims at old root paths.
5. Remove shims after callers/tests migrate.
6. Keep data, documentation, GUI assets, and vendored tools separate from Python source.

## Target layout

```text
FFXI-Mission-Toolkit/
├── pyproject.toml
├── README.md
├── docs/
│   └── workbench/
├── workbench/
│   ├── core/
│   │   ├── schema.py
│   │   ├── graph.py
│   │   ├── provenance.py
│   │   └── services/
│   ├── analyzers/
│   │   ├── server/
│   │   ├── client/
│   │   ├── packet/
│   │   ├── capture/
│   │   └── build/
│   ├── adapters/
│   │   ├── servers/
│   │   ├── client/
│   │   ├── packet/
│   │   └── reference/
│   ├── migrations/
│   ├── runtime/
│   ├── client/
│   ├── reference/
│   └── cli/
├── data/
│   ├── indexes/
│   ├── mappings/
│   ├── fixtures/
│   └── generated/
├── gui/
├── addons/
├── plot_descriptors/
├── test_fixtures/
└── vendor/
```

## Ownership rules
- `workbench/core`: universal models and graph operations; no Assault/Nyzul/Salvage assumptions.
- `workbench/analyzers`: source-format analysis; analyzers emit canonical records.
- `workbench/adapters`: source/version-specific interpretation.
- `workbench/migrations`: transformations between source and target representations.
- `workbench/runtime`: captures and validation observations.
- `workbench/client`: DAT/EXE/DLL capabilities and client/server synchronization.
- `workbench/reference`: external/reference evidence; never silently treated as implementation truth.
- `workbench/cli`: thin command entry points only.
- `data`: generated/index/cache material, never Python implementation.
- `vendor`: third-party tools isolated from first-party code.
- `gui`: presentation/orchestration; domain logic belongs in services.

## Migration order
1. `workbench_schema.py` → `workbench/core/schema.py`
2. `workbench_graph.py` → `workbench/core/graph.py`
3. `source_snapshot.py` → `workbench/core/provenance.py`
4. Shared evidence/finding/result services
5. Server indexers and adapters
6. Packet/capture analyzers
7. Client DAT/capability tooling
8. Migration/backport tooling
9. GUI imports/orchestration
10. Remove root compatibility shims

## Compatibility policy
During migration, old root commands remain valid through thin wrappers where practical. A wrapper may import and call the new package implementation, but contains no business logic. This preserves existing workflows while new code adopts stable package imports.

## Naming policy
Use module names describing responsibility rather than historical script names. Preserve specialized legacy names only where they are user-facing entry points.

Examples:
- `feature_trace.py` → `workbench/core/services/feature_trace.py`
- `feature_checker.py` → `workbench/core/services/feature_checker.py`
- `capture_backtrace.py` → `workbench/runtime/backtrace.py`
- `capture_graph_connect.py` → `workbench/runtime/graph_connect.py`
- `lua_event_index.py` → `workbench/analyzers/server/lua_events.py`
- `workbench_connect_server.py` → `workbench/adapters/servers/graph_connect.py`

## Important constraint
Do not perform a repository-wide rename in one commit. Each subsystem migration should remain reviewable and mechanically reversible.

The structure is being introduced before the mass move so architectural cleanup does not become coupled to a giant path/import rewrite.
