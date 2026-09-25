# Feature / Package Graph Integration

`feature_package_analyzer.py` is the first integration layer between the existing assembled-package tooling and the universal Workbench model.

It deliberately preserves the distinction:
- **Feature** = the thing being migrated or compared.
- **Package** = delivery artifact.
- **Artifact** = individual file/output.
- **Dependency** = explicit relationship supported by manifest evidence.
- **MigrationAction** = generic operation against an artifact.

Existing `backport_package.py` remains responsible for actual Lua/SQL conversion and package validation. The analyzer consumes its report instead of duplicating its conversion logic.

Dependency discovery is intentionally conservative. It accepts explicit `FEATURE_MANIFEST.yaml` dependencies and does not infer arbitrary `require()` relationships, because prior project analysis established that require chains can contain ambiguous cross-zone IDs.

## Next integration

The analyzer should feed its machine-readable output into `workbench_graph.py`, then generalized validation should convert package reports, binding checks, SQL live checks, Lua sanity checks, C++ analysis, and runtime captures into a common ValidationResult model.
