# Feature Catalog v1

The Feature Catalog is the structured inventory of **what the Toolkit exposes**. It is deliberately distinct from the Roadmap (remaining development and validation) and Help (usage instructions).

## Canonical data

`feature_catalog/features.json` is the curated v1 source. Each record has a stable `id`, `module`, `name`, `summary`, primary `route`, `help` route, `implementation` status and independent `validation` status.

Implementation statuses: `implemented`, `partial`, `research`, `planned`.
Validation statuses: `unverified`, `operator_reported`, `tested`.

A route or source reference does not establish runtime acceptance. The first twelve records are a Help-derived seed, **not** an exhaustive module or subfeature census. The catalog is separate from Feature Trace's graph schema.

## GUI

`/feature-catalog` renders searchable/filterable records. Help and Roadmap link to it. The current navigation does not yet include a dedicated sidebar entry; the catalog is reachable from Help and Roadmap.

## Adding a feature

1. Add a unique slug to `feature_catalog/features.json` with a grounded route and Help destination.
2. State implementation and validation separately; use `unverified` unless reproducible acceptance evidence exists.
3. Run `python test_fixtures/test_feature_catalog.py` and `python test_fixtures/test_help_route_inventory.py`.
4. Keep the Roadmap limited to work remaining and link it to the corresponding capability when appropriate.

## Next milestones

- Reconcile **all** Help sections, sidebar pages and route inventory against the catalog; classify module versus subfeature granularity.
- Add explicit provenance references to merged PRs and source/test evidence for every capability.
- Add automated drift reporting (uncataloged routes, missing Help, outdated descriptions) without treating every API endpoint as a user-facing feature.
- Introduce dedicated sidebar navigation and optional graph linkage after the catalog passes acceptance.

This v1 does not scrape Help automatically or declare every route to be a capability.
