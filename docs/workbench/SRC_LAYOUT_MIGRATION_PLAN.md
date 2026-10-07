# Source Layout Migration Plan and Damage Assessment

Status: PROPOSED / NO FILE MOVES PERFORMED  
Audit baseline: `main` at `f084ef782b28fc09aecd8b0f43f417e67e779631`  
Audit date: 2026-10-01

This document proposes a staged migration from the current flat repository-root Python layout to a conventional `src/` layout. It is intentionally a **migration plan**, not authorization for a single mass rename.

The current root contains **102 Python files** in addition to the already-structured `workbench/` package. Several of the largest and most central modules still live at root, including `gui_server.py` (~464 KB), `build_capture_index.py` (~209 KB), `item_dat_tools.py` (~120 KB), and `item_edit.py` (~96 KB). Root-level code also mixes application services, builders, CLI tools, tests, migration/backport utilities, client tooling, capture tooling, research helpers, editors, bootstrap/install code, and compatibility shims.

## Executive recommendation

Proceed with the migration now, but **do not combine these three changes in one step**:

1. physical relocation into `src/`,
2. Python package namespace renaming, and
3. internal module/API refactoring.

The safest first target is:

```text
src/
└── workbench/
    ├── adapters/
    ├── analyzers/
    ├── app/
    ├── captures/
    ├── cli/
    ├── client/
    ├── core/
    ├── domains/
    ├── indexing/
    ├── migrations/
    ├── packets/
    ├── plugins/
    ├── reference/
    ├── research/
    ├── runtime/
    └── spatial/
```

The existing Python package is already named `workbench`. Moving it to `src/workbench` while preserving imports such as `from workbench.core ...` greatly reduces the blast radius. A later rename from `workbench` to `mission_toolkit` may be considered separately, but it is **not part of this migration**.

## Risk rating

| Approach | Risk | Assessment |
| --- | --- | --- |
| Blind mass move of all root `.py` files | **8/10 — high** | Likely to break setup/start, imports, database/resource paths, vendored tools, tests, dynamic script invocation, and runtime write locations. |
| Staged move after path/import normalization | **3–4/10 — controlled** | Most failures become deterministic and catchable by CI plus launcher/setup smoke tests. |
| Leave layout unchanged | **Growing maintenance risk** | Root namespace continues to accumulate coupling and makes ownership, imports, testing, and future refactoring harder. |

## Why a mass move is dangerous

### 1. Module location is currently used as repository location

Many root modules use `Path(__file__).parent` (or equivalent) to locate repository resources. Examples include:

- `settings.py` → root database and configuration assumptions.
- `llm_log.py`, `id_bridge.py`, `build_wiki_index.py` → `ffxi_zone_database.db`.
- `packet_decode.py` → `vendor/Packetlyzer` and manual `sys.path` injection.
- `wiki_lookup.py`, `scrape_bg_wiki.py` → vendored wiki dumps.
- `dat_extractor_bin.py` → `vendor/dat-extractor`.
- `zmesh.py` → `gui/static/zone_visual`.
- `zone_plot.py` → `data/zoneplot_edit_log.sql`.
- `nyzul_plot.py` → `data/nyzul_exclusions.json`.
- `addon_tools.py` → root `addons/`.
- `build_plot_descriptors.py` → root `plot_descriptors/`.

If these files are moved first, they can silently point at new, wrong locations rather than fail loudly.

### 2. Root is an implicit Python import namespace

Tests and utilities frequently add the repository root to `sys.path` and then import root modules directly. Examples include direct imports of `research_gaps`, `dialog_drift_overview`, and `build_sql_index`. Production modules also modify `sys.path` for vendored code.

A `src/` layout intentionally removes this accidental import behavior, so imports must be normalized before the compatibility shims are removed.

### 3. Launchers and setup call filenames directly

`start.bat` currently runs `gui_server.py` by filename and expects `.venv` and `ffxi_zone_database.db` at repository root.

`setup.bat` directly invokes root scripts including `install_xi_tinkerer.py`, `install_external_tools.py`, `build_database.py`, `build_npc_index.py`, `build_dialog_index.py`, `ingest_global_tables.py`, and `build_capture_index.py`, and it imports root `settings` from a `python -c` command.

Those interfaces must remain valid through temporary wrappers until setup/start are migrated to package entry points.

### 4. Runtime state must not move accidentally

This migration must **not** relocate user/runtime state as a side effect. In particular, the first src-layout migration should preserve the current locations of:

- `ffxi_zone_database.db`,
- `toolkit_config.txt`,
- edit journals/backups,
- capture data,
- generated indexes/caches,
- `data/`, `addons/`, `plot_descriptors/`,
- user-selected server/client paths.

A later state-directory cleanup can be designed independently.

### 5. Stored provenance may contain source paths

The Workbench intentionally preserves source provenance. Any persisted repository-relative source paths, artifact paths, or source-location references must either remain stable or be migrated deterministically. A physical source move must never make historical evidence appear to refer to a different file silently.

---

# Proposed repository structure

```text
FFXI-Mission-Toolkit/
├── src/
│   └── workbench/
│       ├── adapters/          # existing package
│       ├── analyzers/         # existing package + server/event analysis
│       ├── app/               # web application composition / GUI server
│       ├── captures/          # ingestion, evidence correlation, OCR
│       ├── cli/               # stable command entry points
│       ├── client/            # DAT, models, binaries, item/client tools
│       ├── core/              # graph/schema/services/validation
│       ├── domains/           # Assault/Nyzul/Salvage/etc.
│       ├── indexing/          # build/index orchestration
│       ├── migrations/        # package/backport/engine migration logic
│       ├── packets/           # packet decoding/opcode tooling
│       ├── plugins/           # existing package
│       ├── reference/         # wiki/reference/dialog drift evidence
│       ├── research/          # research sessions + legacy LLM helpers
│       ├── runtime/           # connection/runtime/addon services
│       └── spatial/           # zone editors, mesh, map/position tools
├── scripts/
│   ├── bootstrap/             # install/reset repository bootstrap scripts
│   └── maintenance/           # one-off/operator utilities if not product code
├── tests/
│   ├── fixtures/
│   └── legacy/                # temporary home for current root tests
├── gui/                       # KEEP in place for first migration
│   ├── templates/
│   └── static/
├── data/                      # KEEP in place for first migration
├── docs/
├── vendor/                    # KEEP in place
├── addons/                    # KEEP in place
├── backport-workspace/        # KEEP in place until separately reviewed
├── client_probe_sets/         # data/config, not Python source
├── plot_descriptors/          # generated/reference data
├── setup.bat                  # thin root launcher
├── start.bat                  # thin root launcher
├── reset_install.bat          # thin root launcher
├── pyproject.toml             # new package/install metadata
├── requirements.txt           # retain during transition
├── README.md
└── LICENSE
```

## Package naming decision

**Phase 1 keeps the import package named `workbench`.** Existing imports already use this name extensively, and the package is internally structured. Therefore:

```text
workbench/core/...  ->  src/workbench/core/...
```

is substantially safer than simultaneously changing every import to `mission_toolkit.*`.

If a public/package namespace rename is desired, perform it only after the src migration is complete and all root compatibility modules are gone.

---

# Root Python file disposition map

The mapping below covers all **102 root-level Python files** present at the audit baseline. Destinations are the proposed **initial migration locations**; large modules may be split internally later, but splitting is deliberately not combined with relocation.

Legend:

- **L** = low relocation risk after package scaffold exists.
- **M** = moderate; imported broadly or has repository-relative assumptions.
- **H** = high; launcher/setup/runtime state or very high fan-in/fan-out.
- **Shim** = retain a temporary root wrapper until callers migrate.
- **Delete shim** = implementation is already canonical elsewhere; remove only after compatibility audit.

## Application/configuration/runtime

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `gui_server.py` | `src/workbench/app/gui_server.py` | H | **Move last. Root shim required** until `start.bat`, tests and all direct imports use package entry point. |
| `settings.py` | `src/workbench/core/settings.py` | H | First convert repository/data paths to central path service; retain root shim during transition. |
| `addon_tools.py` | `src/workbench/runtime/addon_tools.py` | M | Normalize `addons/` path first. |
| `workbench_connect.py` | `src/workbench/runtime/connect.py` | M | Preserve existing command/API surface with wrapper if externally invoked. |
| `workbench_connect_server.py` | `src/workbench/runtime/connect_server.py` | M | Same as above. |
| `mission_toolkit.py` | `src/workbench/cli/mission_toolkit.py` | M | Treat as legacy/stable CLI entry point; root wrapper during migration. |
| `salvage_reconstruct.py` | `src/workbench/cli/salvage_reconstruct.py` | M | DB path currently tied to file location; convert to path service first. |

## Canonical-core and feature services

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `entity_profile.py` | `src/workbench/core/services/entity_profile.py` | M | Move without redesign; update imports. |
| `feature_candidates.py` | `src/workbench/core/services/feature_candidates.py` | L | Package move. |
| `feature_checker.py` | `src/workbench/core/services/feature_checker.py` | M | Package move + import audit. |
| `feature_package_analyzer.py` | `src/workbench/core/services/feature_package_analyzer.py` | M | Package move + package/migration import audit. |
| `feature_trace.py` | `src/workbench/core/services/feature_trace.py` | H | High fan-in; move after package/path foundation, retain compatibility import if needed. |
| `id_bridge.py` | `src/workbench/core/services/id_bridge.py` | M | Replace root DB derivation first. |
| `lookup_entity.py` | `src/workbench/core/services/lookup_entity.py` | M | Preserve command usage through CLI/wrapper if needed. |
| `validation_pipeline.py` | `src/workbench/core/validation_pipeline.py` | M | Align with existing validation services, but do not refactor semantics during move. |

## Compatibility shims already pointing at canonical Workbench code

| Current root file | Canonical code already lives at | Risk | Proposed disposition |
| --- | --- | ---: | --- |
| `workbench_graph.py` | `workbench.core.graph` | L | **Delete shim** after direct callers are gone; do not create a second copy in `src`. |
| `workbench_schema.py` | `workbench.core.schema` | L | **Delete shim** after compatibility audit. |
| `source_snapshot.py` | `workbench.core.provenance` | L | **Delete shim** after direct callers are migrated. |
| `lua_event_index.py` | `workbench.analyzers.server.lua_events` | L | **Delete shim** after CLI/import callers migrate. |

## Capture, protocol and OCR

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `build_capture_index.py` | `src/workbench/captures/build_capture_index.py` | H | Very large/high fan-in. Preserve filename initially; root shim required because setup invokes it. Split only in later PRs. |
| `capture_backtrace.py` | `src/workbench/captures/backtrace.py` | M | Move after capture imports normalized. |
| `capture_graph_connect.py` | `src/workbench/captures/graph_connect.py` | H | Canonical graph/provenance coupling; migrate with focused regression. |
| `youtube_chat_ocr.py` | `src/workbench/captures/video_ocr.py` | H | Large module + external tools/profile/data paths; move late in capture slice. |
| `packet_decode.py` | `src/workbench/packets/decode.py` | H | Normalize Packetlyzer/vendor path and remove file-location assumption first. |
| `packet_opcode_index.py` | `src/workbench/packets/opcode_index.py` | M | Package move after decoder path foundation. |

## Client, DAT, binary, model and item tooling

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `binary_inspector.py` | `src/workbench/client/binary/inspector.py` | M | Package move. |
| `client_binary_analyze.py` | `src/workbench/client/binary/analyze.py` | M | Package move. |
| `client_binary_diff.py` | `src/workbench/client/binary/diff.py` | L | Package move. |
| `client_binary_index.py` | `src/workbench/client/binary/index.py` | M | Package move. |
| `cpp_api_index.py` | `src/workbench/client/binary/cpp_api_index.py` | M | Package move; preserve source-root assumptions. |
| `cpp_dependency_index.py` | `src/workbench/client/binary/cpp_dependency_index.py` | M | Package move. |
| `dat_extractor_bin.py` | `src/workbench/client/dat/extractor_bin.py` | H | Normalize `vendor/dat-extractor` path first. |
| `dat_inspector.py` | `src/workbench/client/dat/inspector.py` | M | Package move after DAT path service is stable. |
| `client_model_catalog.py` | `src/workbench/client/models/catalog.py` | M | Package move. |
| `client_model_resolver.py` | `src/workbench/client/models/resolver.py` | M | Package move. |
| `client_overview.py` | `src/workbench/client/overview.py` | M | Reconcile with existing `workbench/client/` code; no behavior refactor during relocation. |
| `model_schedule_dump.py` | `src/workbench/client/models/schedule_dump.py` | M | Vendor/client path audit first. |
| `model_viewer.py` | `src/workbench/client/models/viewer.py` | M | GUI/static/model path audit. |
| `mob_look_decode.py` | `src/workbench/client/models/mob_look_decode.py` | L | Package move. |
| `mob_model_tables.py` | `src/workbench/client/models/mob_model_tables.py` | L | Package move. |
| `gear_tables.py` | `src/workbench/client/items/gear_tables.py` | L | Package move. |
| `item_dat_tools.py` | `src/workbench/client/items/dat_tools.py` | H | Large/high-impact client writer; path/backup/journal tests required. |
| `item_edit.py` | `src/workbench/client/items/edit.py` | H | Large editor/write workflow; move after DAT tools and central paths. |
| `build_altana_index.py` | `src/workbench/client/models/build_altana_index.py` | M | Its output DB path must be made repository/state-root based first. |

## Server/event/mission analysis

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `explore_event.py` | `src/workbench/analyzers/server/explore_event.py` | H | Vendor/event bridge + dynamic import path; normalize before move. |
| `mission_event_reconcile.py` | `src/workbench/analyzers/server/mission_event_reconcile.py` | M | Package move. |
| `mission_graph_ingest.py` | `src/workbench/analyzers/server/mission_graph_ingest.py` | M | Canonical graph coupling; focused regression. |
| `build_condition_index.py` | `src/workbench/analyzers/server/build_condition_index.py` | M | Move with server-analysis slice. |

## Migration/backport/engine tooling

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `backport_binding_audit.py` | `src/workbench/migrations/backport/binding_audit.py` | M | Preserve CLI via wrapper if documented/external. |
| `backport_binding_index.py` | `src/workbench/migrations/backport/binding_index.py` | M | Package move. |
| `backport_convert_7_packages.py` | `src/workbench/migrations/backport/convert_7_packages.py` | M | Candidate maintenance CLI; verify still current before preserving long-term. |
| `backport_convert_gm_debug_tools.py` | `src/workbench/migrations/backport/convert_gm_debug_tools.py` | M | Same. |
| `backport_convert_nyzul_package.py` | `src/workbench/migrations/backport/convert_nyzul_package.py` | M | Same. |
| `backport_coverage_check.py` | `src/workbench/migrations/backport/coverage_check.py` | M | Package move. |
| `backport_item_audit.py` | `src/workbench/migrations/backport/item_audit.py` | M | Package move. |
| `backport_lua_convert.py` | `src/workbench/migrations/backport/lua_convert.py` | H | Existing tests and external workflows; root shim until callers updated. |
| `backport_lua_sanity_check.py` | `src/workbench/migrations/backport/lua_sanity_check.py` | M | Package move. |
| `backport_map_confidence_check.py` | `src/workbench/migrations/backport/map_confidence_check.py` | M | Package move. |
| `backport_map_lint.py` | `src/workbench/migrations/backport/map_lint.py` | M | Package move. |
| `backport_package.py` | `src/workbench/migrations/backport/package.py` | H | Package/migration core; high regression coverage. |
| `backport_sql_convert.py` | `src/workbench/migrations/backport/sql_convert.py` | H | Existing root test coverage; root shim during transition. |
| `backport_sql_live_check.py` | `src/workbench/migrations/backport/sql_live_check.py` | H | Live DB behavior; move only after configuration/path foundation. |
| `engine_change_index.py` | `src/workbench/migrations/engine/change_index.py` | M | Package move. |
| `engine_migration_compare.py` | `src/workbench/migrations/engine/compare.py` | M | Package move. |

## Reference/wiki/dialog evidence

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `audit_dialog_drift.py` | `src/workbench/reference/dialog/audit_drift.py` | M | Path/settings normalization first. |
| `dialog_drift_overview.py` | `src/workbench/reference/dialog/drift_overview.py` | M | Root tests directly import it; temporary shim. |
| `ffxiclopedia_adapter.py` | `src/workbench/reference/ffxiclopedia_adapter.py` | L | Package move. |
| `wiki_claim_compare.py` | `src/workbench/reference/wiki_claim_compare.py` | M | Package move. |
| `wiki_compile.py` | `src/workbench/reference/wiki_compile.py` | M | Package move. |
| `wiki_evidence.py` | `src/workbench/reference/wiki_evidence.py` | M | Canonical evidence coupling; focused tests. |
| `wiki_lookup.py` | `src/workbench/reference/wiki_lookup.py` | H | Normalize vendored dump path first. |
| `scrape_bg_wiki.py` | `src/workbench/reference/scrape_bg_wiki.py` | H | Network/vendor dump destination path must be centralized. |
| `build_wiki_index.py` | `src/workbench/indexing/build_wiki_index.py` | H | Root DB + vendor paths; root shim while setup/home rebuild actions migrate. |

## Research and legacy LLM helpers

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `llm_client.py` | `src/workbench/research/legacy_llm/client.py` | M | Preserve existing behavior; do not conflate with ResearchSession provider refactor. |
| `llm_db_tools.py` | `src/workbench/research/legacy_llm/db_tools.py` | M | DB path audit. |
| `llm_log.py` | `src/workbench/research/legacy_llm/log.py` | H | Root DB path must be normalized first. |
| `research_gaps.py` | `src/workbench/research/gaps.py` | M | Root test imports directly; compatibility shim or test migration. |

## Spatial/editor/domain helpers

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `zone_plot.py` | `src/workbench/spatial/zone_plot.py` | H | DB/settings/data edit-log path + editor API; move late in spatial slice. |
| `zone_edit.py` | `src/workbench/spatial/zone_edit.py` | H | Large editor/write workflow; preserve backups/journals. |
| `zmesh.py` | `src/workbench/spatial/zmesh.py` | H | Normalize `gui/static/zone_visual` path first. |
| `zone_animation_meta.py` | `src/workbench/spatial/zone_animation_meta.py` | M | Client/model path audit. |
| `build_zone_topdown.py` | `src/workbench/spatial/build_zone_topdown.py` | M | Output/cache location must be explicit. |
| `build_zone_visual_cache.py` | `src/workbench/spatial/build_zone_visual_cache.py` | H | Mesh/cache/vendor path + GUI route callers. |
| `build_plot_descriptors.py` | `src/workbench/spatial/build_plot_descriptors.py` | M | Normalize `plot_descriptors/` output path. |
| `fix_zone_door_props.py` | `src/workbench/spatial/fix_zone_door_props.py` | M | Determine whether product tool or maintenance-only before final placement. |
| `pull_mob_positions.py` | `src/workbench/spatial/pull_mob_positions.py` | M | Determine whether product tool or maintenance-only; DB/server path audit. |
| `nyzul_plot.py` | `src/workbench/domains/nyzul_plot.py` | H | Normalize data path; retain domain semantics outside generic spatial core. |

## General indexing/build orchestration

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `build_database.py` | `src/workbench/indexing/build_database.py` | H | Setup invokes directly; root shim required until setup CLI migration. |
| `build_dialog_index.py` | `src/workbench/indexing/build_dialog_index.py` | H | Same. |
| `build_dsp_index.py` | `src/workbench/indexing/build_dsp_index.py` | M | Package move after path/config service. |
| `build_integration_index.py` | `src/workbench/indexing/build_integration_index.py` | M | Package move. |
| `build_lsb_index.py` | `src/workbench/indexing/build_lsb_index.py` | H | Source-root/vendor path assumptions; home rebuild callers. |
| `build_npc_index.py` | `src/workbench/indexing/build_npc_index.py` | H | Setup invokes directly; root shim. |
| `build_sql_index.py` | `src/workbench/indexing/build_sql_index.py` | H | Widely imported by tests/services; shim + import migration. |
| `build_topaz_index.py` | `src/workbench/indexing/build_topaz_index.py` | M | Server path/config audit. |
| `ingest_global_tables.py` | `src/workbench/indexing/ingest_global_tables.py` | H | Setup invokes directly; root shim. |

## Bootstrap/install scripts: move outside `src`

These are repository bootstrap/operator scripts, not application libraries. They should not become importable package modules merely to clear the root.

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `install_external_tools.py` | `scripts/bootstrap/install_external_tools.py` | H | Keep root wrapper or update `setup.bat` in same PR. Paths must resolve from repository root, not script directory. |
| `install_xi_tinkerer.py` | `scripts/bootstrap/install_xi_tinkerer.py` | H | Same. |
| `reset_install.py` | `scripts/bootstrap/reset_install.py` | H | `reset_install.bat` must be updated atomically; distribution cleanup paths need central root resolution. |

## Root tests: move to `tests/`, not `src`

| Current root file | Proposed destination | Risk | Transition |
| --- | --- | ---: | --- |
| `tests/legacy/test_backport_lua_convert.py` | `tests/legacy/tests/legacy/test_backport_lua_convert.py` | M | Remove repo-root import dependence as migration modules move. |
| `tests/legacy/test_backport_sql_convert.py` | `tests/legacy/tests/legacy/test_backport_sql_convert.py` | M | Same. |
| `tests/legacy/test_capture_ingestion.py` | `tests/legacy/tests/legacy/test_capture_ingestion.py` | M | Align with capture package imports. |

`test_fixtures/` should eventually become `tests/fixtures/`, but that directory move should occur only after the production package is stable. Mixing a full test-tree rename into the first source move would create unnecessary review noise.

---

# Non-Python root items: initial disposition

The src migration should **not** sweep unrelated artifacts into new locations at the same time.

| Current item | Initial action |
| --- | --- |
| `.github/`, `.claude/` | Keep at root. |
| `README.md`, `LICENSE` | Keep at root. |
| `setup.bat`, `start.bat`, `reset_install.bat` | Keep as thin root launchers; update internals incrementally. |
| `requirements.txt` | Keep during transition; add `pyproject.toml` rather than replacing dependency workflow immediately. |
| `gui/` | Keep templates/static assets in place for first migration; central path service locates them. |
| `data/` | Keep in place. |
| `vendor/` | Keep in place. |
| `addons/` | Keep in place. |
| `backport-workspace/` | Keep in place pending separate archival/current-use review. |
| `client_probe_sets/` | Keep as data/config. |
| `plot_descriptors/` | Keep as generated/reference data. |
| `appraisal_item_id_xref.csv`, `appraisal_pools_with_item_ids.csv` | Keep initially; later consider `data/reference/appraisal/`. |
| `uncharted90_names.txt` | Keep initially; later classify/reference-data cleanup. |
| `mission_toolkit_gui_artifact.html` | Review separately for archive/deprecation; do not bury under `src`. |
| runtime DB/config files | Preserve existing locations through the entire source-layout migration. |

---

# Required foundation before the first code move

## A. Central repository/path service

Introduce one canonical module, proposed as:

```text
src/workbench/runtime/paths.py
```

Before files physically move, it should expose at minimum:

```text
REPO_ROOT
SRC_ROOT
GUI_ROOT
DATA_ROOT
VENDOR_ROOT
ADDONS_ROOT
PLOT_DESCRIPTORS_ROOT
DATABASE_PATH
CONFIG_PATH
```

It should resolve the repository root independently of the importing module's physical location.

**Gate:** production code may use `Path(__file__)` for assets that truly belong to that Python package, but not as shorthand for repository root.

## B. Packaging scaffold

Add `pyproject.toml` with a conventional src-layout package configuration and install the project into `.venv` in editable mode.

Desired behavior:

```text
python -c "import workbench"
```

must succeed from outside the repository root after editable installation.

This is the proof that imports no longer depend on current working directory or root `sys.path` injection.

## C. Stable CLI entry points

Long-term setup/launch code should call package entry points rather than physical filenames, for example:

```text
python -m workbench.app.gui_server
python -m workbench.indexing.build_database
python -m workbench.captures.build_capture_index
```

Console-script aliases can be added later, but `python -m` is sufficient to remove filename-location coupling.

---

# Damage/risk matrix

| Failure class | Likelihood in blind move | Impact | Required mitigation |
| --- | ---: | ---: | --- |
| Database silently created/opened in wrong directory | High | Critical | Central `DATABASE_PATH`; regression asserting exact path. |
| `setup.bat`/`start.bat` cannot find scripts | Certain | Critical | Temporary root wrappers; migrate launchers only after package entry points work. |
| Import failures / duplicate module identities | High | High | Editable src package; absolute `workbench.*` imports; eliminate root `sys.path` hacks. |
| Vendor tools no longer found | High | High | Central `VENDOR_ROOT`; explicit vendor adapter paths. |
| GUI templates/static/cache paths break | Medium-high | High | Central `GUI_ROOT`; web smoke tests. |
| Edit journals/backups written into `src/` | Medium-high | Critical | Central state/data roots; writer regression tests. |
| Capture source/provenance paths drift | Medium | High | Preserve repository-relative canonical path mapping or explicit migration. |
| Dynamic subprocess/script invocation fails | Medium-high | High | Inventory string-based `.py` invocation; replace with `-m`/callable APIs. |
| Tests pass only from repo root | High | High | Run import/test smoke from a different CWD. |
| CI path filters miss moved files | Medium | High | Update `.github/workflows/*` path filters in the same phase as moves. |
| User/external scripts invoking old filenames break | Medium | Medium-high | Compatibility shims for documented/common entry points for at least one migration cycle. |
| Git history becomes hard to review | Medium | Medium | Keep relocation PRs behavior-neutral; no large refactor/rename in same commit. |

---

# Migration phases and acceptance gates

## Phase 0 — Freeze and dependency inventory

**No code moves.**

- Search all source/tests/docs/batch/workflows for direct root-module imports.
- Search all string/subprocess references to `*.py` filenames.
- Search all `Path(__file__)`, `os.getcwd()`, relative open/write, and CWD-sensitive paths.
- Enumerate CI path filters.
- Identify persisted source-path formats in DB/evidence records.
- Mark each root file as active product code, compatibility shim, bootstrap script, test, generated helper, or deprecation candidate.

**Gate:** machine-readable inventory checked into docs/data or generated by a deterministic audit script.

## Phase 1 — Path normalization

**Still no broad physical move.**

- Add canonical path service.
- Convert repository-root/resource assumptions to canonical paths.
- Add tests proving DB/data/vendor/gui/addons paths remain exactly where expected.
- Add a test that runs key imports from a non-repository current working directory.

**Gate:** full Workbench regression green; `start.bat` smoke and setup/build dry-run paths unchanged.

## Phase 2 — `src/` packaging foundation

- Add `pyproject.toml`.
- Establish `src/workbench` package.
- Move the existing `workbench/` tree to `src/workbench/` **without renaming package namespace**.
- Install editable package in setup/CI.
- Update tests to import installed package rather than insert repository root into `sys.path`.

**Gate:** existing `workbench.*` import paths remain valid and full CI is green.

## Phase 3 — Low/moderate-risk service modules

Move cohesive groups with no launcher dependence first:

- reference/wiki helpers,
- research helpers,
- client binary/model read-only helpers,
- core feature/entity services,
- engine comparison helpers.

Use root compatibility shims only where a real caller remains.

**Gate:** no new root-to-root production imports are permitted.

## Phase 4 — Capture and protocol modules

- Move packet decoder/opcode code after vendor paths are canonical.
- Move capture graph/backtrace services.
- Move `build_capture_index.py` last within this phase, retaining root shim until setup is updated.
- Move video/OCR after external-tool/profile paths are proven.

**Gate:** capture ingestion matrix, exact provenance, Evidence Search, packet decode and OCR regressions green.

## Phase 5 — Client write/editor modules

- Move `item_dat_tools.py`, `item_edit.py`, DAT inspector/extractor, model tooling.
- Preserve exact backup/journal/fingerprint/rollback locations.

**Gate:** read/write/rollback focused tests green; no client write path changes except Python module location.

## Phase 6 — Migration/backport modules

- Move active backport/migration code into `src/workbench/migrations/backport/`.
- Move root converter tests under `tests/`.
- Decide whether one-off conversion scripts remain supported CLI commands or become `scripts/maintenance/`.

**Gate:** Lua/SQL converter regressions and package/migration regressions green.

## Phase 7 — Spatial/editors/domains

- Move Zone Editor backend helpers, mesh/cache helpers, Nyzul-specific plotting, position tools.
- Keep GUI templates/static and `data/` physically unchanged.

**Gate:** Zone Editor, 2D/3D viewer, Nyzul and domain regressions green; edit logs/backups unchanged.

## Phase 8 — Builders/bootstrap/launchers

- Move general builders to `src/workbench/indexing/`.
- Move install/reset Python scripts to `scripts/bootstrap/`.
- Change `setup.bat` to package/module entry points.
- Remove builder root wrappers only after setup/home rebuild actions have migrated.

**Gate:** fresh-environment setup smoke, rebuild actions, and start smoke all pass.

## Phase 9 — Web application move

Move `gui_server.py` last to `src/workbench/app/gui_server.py`.

Keep a tiny root `gui_server.py` wrapper for one transition cycle if needed, then change `start.bat` to:

```text
python -m workbench.app.gui_server
```

**Gate:** complete GUI route regression and full Workbench CI green.

## Phase 10 — Root cleanup

- Remove compatibility shims with zero callers.
- Move root tests into `tests/`.
- Add a CI guard prohibiting new root-level `.py` files except an explicit allowlist (ideally empty).
- Review non-Python root artifacts separately.

**Gate:** root contains project metadata/launchers/directories, not application implementation modules.

---

# Recommended PR decomposition

Do not make one 100-file rename PR. A practical sequence is approximately:

1. **Path service + path regressions**
2. **`pyproject.toml` + editable install + move existing `workbench/` → `src/workbench/`**
3. **Core/reference/research low-risk root modules**
4. **Client read-only/model/binary modules**
5. **Capture/packet/OCR modules**
6. **Migration/backport modules**
7. **Spatial/editor/domain modules**
8. **Client write/item modules**
9. **Index/build modules + setup/bootstrap migration**
10. **`gui_server.py` + start launcher**
11. **Tests/shim/root cleanup + CI root-layout guard**

Each PR should be behavior-neutral as much as possible: relocate + import/path fixes + tests, not feature development.

---

# Compatibility policy

Temporary root wrappers are acceptable during migration, but they must be explicit and short-lived.

Example:

```python
# gui_server.py -- temporary compatibility entry point
from workbench.app.gui_server import main

if __name__ == "__main__":
    raise SystemExit(main())
```

Rules:

- A wrapper contains no business logic.
- It includes a removal note/phase.
- New code must not import the wrapper.
- CI should track remaining wrapper callers.
- Wrappers are deleted in Phase 10 when caller count reaches zero.

Existing compatibility files such as `workbench_graph.py`, `workbench_schema.py`, `source_snapshot.py`, and `lua_event_index.py` demonstrate that this pattern is already used in the repository; these should be retired rather than copied into the new package.

---

# Rollback strategy

Each migration PR must be independently revertible.

- Do not migrate runtime data in the same commits as source relocation.
- Do not perform schema migrations solely because code moved.
- Preserve root wrappers until the corresponding launcher/import callers are proven migrated.
- Keep compatibility at module boundaries, not duplicate implementations.
- If a phase fails after merge, revert that phase rather than partially restoring individual files.

Because Git records file content rather than directory identity, rename-heavy commits are recoverable, but reviewability is best when each PR changes one subsystem at a time.

---

# Definition of done

The src-layout migration is complete when all of the following are true:

- [ ] `src/workbench/` contains the production Python package.
- [ ] No production behavior depends on repository root being present in `sys.path`.
- [ ] No production module uses its own `__file__` directory when it actually means repository/data/vendor/gui root.
- [ ] `setup.bat` and `start.bat` invoke package/module entry points rather than implementation filenames.
- [ ] Runtime DB/config/data/cache/journal locations are unchanged unless separately migrated and documented.
- [ ] `gui_server.py` implementation lives under `src/`; any root wrapper is removed or intentionally documented.
- [ ] Root compatibility shims have zero callers and are removed.
- [ ] Root tests are under `tests/`.
- [ ] CI runs successfully from the installed src-layout package.
- [ ] A CI guard rejects new root-level production `.py` files.
- [ ] README/SETUP/developer docs describe the src layout.
- [ ] Full Workbench regression is green after final cleanup.

## Decision

**Proceed, but begin with Phase 0/1 rather than file moves.** The root layout is now a material maintenance liability, and the current Workbench architecture is stable enough to migrate. The highest-value first implementation PR is the canonical repository/path service plus regression coverage; once that is green, the physical move can begin in bounded subsystem slices.