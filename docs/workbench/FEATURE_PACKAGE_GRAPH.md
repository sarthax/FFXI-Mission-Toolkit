# Feature / Package Graph Integration

`workbench.core.services.feature_package_analyzer` is the integration layer between the existing assembled-package tooling and the universal Workbench model.

It deliberately preserves the distinction:
- **Feature** = the thing being migrated or compared.
- **Package** = delivery artifact.
- **Artifact** = individual file/output.
- **Dependency** = explicit relationship supported by manifest evidence.
- **MigrationAction** = generic operation against an artifact.

`workbench.packages.migration.orchestrator` remains responsible for actual Lua/SQL conversion and package validation. The analyzer consumes its report instead of duplicating its conversion logic.

Dependency discovery is intentionally conservative. It accepts explicit `FEATURE_MANIFEST.yaml` dependencies and does not infer arbitrary `require()` relationships, because prior project analysis established that require chains can contain ambiguous cross-zone IDs.

## Graph integration

The analyzer imports its machine-readable output through `workbench.core.graph`. Generalized validation can then combine package reports, binding checks, SQL live checks, Lua sanity checks, C++ analysis, and runtime captures using the canonical Workbench records.
