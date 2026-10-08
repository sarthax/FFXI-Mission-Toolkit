# Workbench UI Framework

This is the shared module-layout layer above `base.html`. The global shell remains responsible for
navigation, theme, and workspace context; `workbench_page.html` owns page-level composition and
geometry.

## Canonical page archetypes

- **browser** — search/filter controls plus result list/table and pagination.
- **detail** — identity/summary header plus evidence or detail sections.
- **workbench** — navigator plus primary working surface plus optional inspector.
- **editor** — navigator/editable surface/properties/actions; write capability must remain explicit.
- **dashboard** — status/KPI/action strip plus panels or tables.

Every unified page declares one archetype through `page_archetype`. Feature-specific surfaces may
still implement specialized canvas, graph, packet-byte, or economy layouts inside `page_body`;
the wrapper standardizes the outer geometry rather than flattening specialized behavior.

## Wrapper blocks

`gui/templates/workbench_page.html` provides:

- `page_width`: `fluid` (default), `reading`, or `narrow`;
- `page_class`: feature-specific class hook;
- `page_back`, `page_heading`, `page_identity`, `page_subtitle`;
- `page_status`, `page_actions`, and `page_help`;
- `page_notices`;
- `page_body`.

Use `wb-readonly-badge` or `wb-write-badge` when capability/safety state belongs in the page header.

## Shared geometry

The shell defines Workbench tokens for page padding, section/panel gaps, toolbar/control height,
table density, sidebar sizes, inspector width, and content widths. Reusable layout primitives are:

- `wb-layout-one`;
- `wb-layout-two` (navigator + workspace);
- `wb-layout-three` (navigator + workspace + inspector);
- `wb-pane` and `wb-inspector`;
- `wb-filter-row`;
- `wb-empty`, `wb-loading`, and `wb-error`.

Do not add page-local `main { padding: ... }`, arbitrary global max-widths, or new sidebar/control
dimensions when a Workbench token or primitive expresses the same geometry.

## Migration and enforcement

`test_unified_ui_framework.py` enforces the adoption boundary. The workspace-by-workspace migration
is complete and `UI_LEGACY_TEMPLATE_ALLOWLIST.txt` is intentionally empty of pending templates.
All current module pages use the shared Workbench page contract.

New module pages must extend `workbench_page.html`. Reintroducing a legacy allowlist entry is an
explicit exception that requires a documented reason in the PR. Preserve route behavior, data
semantics, write safety, evidence meaning, and specialized inner layouts when extending the shared
framework.

Foundation adopters:

- `sql.html` — Browser;
- `validation_dashboard.html` — Dashboard;
- `research_evidence.html` — Detail.

Completed workspace migrations:

- **Research** — Sessions (Browser), Contradictions (Browser), Gaps (Dashboard), Session Detail (Workbench), and Evidence (Detail).
- **Validation** — Dashboard (Dashboard), Runs (Browser), Run Detail (Detail), and Live Target (Workbench, read-only).
- **Packages** — Library (Browser), Scope Review (Workbench), Create Package (Editor; package-files-only write boundary), and Review & Readiness (Detail, read-only).
- **Backport** — Package Workflow (Editor; package-workspace writes only), Lua Converter (Editor), SQL Converter (Editor), and Binding Reference (Browser).
- **ID Drift** — Overview (Dashboard) and Category Detail (Browser).
- **LLM** — Assistant (Workbench; draft-output boundary) and Call Detail (Detail, read-only).
- **Events / CSID** — Browser (Browser) and Event Detail (Detail).
- **Wiki Compiler** — Evidence compilation and comparison workspace (Workbench).
- **Capture Path Plots** — Single Path and All Paths (Workbench; specialized visualization geometry preserved).
- **Client Overview** — Installed-client fingerprint and build identity comparison (Dashboard).
- **Binary Inspector** — PE/binary evidence inspection and probe workflow (Workbench; inspection read-only, explicit probe-save write action preserved).
- **Behavior Inspector** — Lua behavior/evidence graph and source drill-down (Workbench).
- **Dialog Drift** — Cross-zone dialog offset/status overview (Dashboard, read-only).
- **Zone Dialog Drift** — Per-zone wired-comment versus client-dialog report (Detail, read-only).
- **Roadmap** — Reconciled project status and historical roadmap (Dashboard).
- **Help** — Workbench usage guide and evidence-boundary reference (Detail, reading width).
- **System confirmations** — Backup delete/restore and source rebuild confirmations (Editor, narrow; explicit destructive/write status), plus shutdown/restart status (Detail, narrow).
- **Entity Gaps** — Zero-position/unregistered diagnostic browser (Browser, read-only).
- **Key Items** — Client/server readiness and capture-evidence browser (Browser, read-only).
- **Assault Missions** — Mission text and observed implementation-coverage browser (Browser).
- **Zones Browser** — Zone/content-tag entity browser (Browser, read-only).
- **Dialog Browser** — Client dialog search/browse with drift, CSID, capture, and implementation evidence (Browser; specialized result geometry preserved).
- **Domains Index** — Domain implementation inventory and editor coverage (Dashboard, read-only).
- **Feature Checker** — Capability-requirement evidence evaluator with separate implementation and validation dimensions (Workbench, read-only).
- **Packet Tools** — Manual packet decoder and opcode browser (Workbench; capture-native provenance guidance preserved).
- **Assault Domain** — Assault-specific development/validation landing workspace (Dashboard).
- **Message-ID Shift Master** — Evidence-derived packet-message/dialog-index shift ranges with explicit rebuild write boundary (Workbench, reading width).
- **Capture Delete Confirmation** — Capture-owned-row deletion review with explicit permanent-delete boundary (Editor, narrow).
- **Capture Help** — Supported ingestion formats, packet convergence, evidence provenance, and adapter-gap reference (Detail, wide, read-only).
- **Capture Add Files** — Capture evidence upload/ingestion surface with individual-file and directory-preserving workflows (Editor, write boundary explicit).
- **New Capture** — Capture metadata/classification creation form (Editor, reading width).
- **Capture Source Evidence** — Exact source locator/hash/row provenance dossier (Detail, read-only).
- **Capture Bulk Ingest** — Directory scan/plan/run workflow with explicit scan-versus-ingest boundary and disk safeguards (Editor).
- **Capture Bulk Ingest Job** — Active/completed bulk-ingest progress, failure, source-sheet, and cancellation detail (Detail).
- **Capture Metadata Import** — CSV validation/apply workflow for capture source information with explicit overwrite control (Editor, reading width).
- **Capture Review Queue** — Quarantine/review decision workbench for missing, duplicate, failed, and unverified capture data (Workbench; write boundary explicit).
- **Related Capture Evidence** — Deterministic provenance/packet/entity/item/chat relationship dossier (Detail, read-only).
- **Capture / Video Alignment** — Landmark-based clock alignment, packet correlation, anchors, and key-evidence workspace with explicit mutation boundaries (Workbench).
- **Capture Evidence Search** — Cross-capture modular evidence discovery and drill-down surface (Browser, read-only).
- **Captures** — Typed/tagged capture library with filtering, review-state visibility, and administration entry points (Browser).
- **Capture Detail** — Capture dossier spanning integrity, metadata, provenance, derived views, and maintenance actions (Detail).
- **Capture Packet Browser** — Filterable canonical raw-packet browser with contextual viewer/manual-decoder handoff (Browser, read-only).
- **Capture Packet Viewer** — Contextual decoded-field/raw-byte/provenance/correlation inspector with specialized two-pane packet layout (Workbench, wide, read-only).
- **Capture Data Explorer** — Normalized dataset browser exposing curated fields plus complete raw-row/provenance detail (Browser, read-only).
- **Capture Timeline** — Source-specific event/battle/key-item/item/dialog timeline workbench preserving separate chronology and confidence semantics (Workbench, read-only).
- **Manual Packet Viewer / Decoder** — Wide manual/bulk raw-packet decode workbench preserving byte coverage and source-adapter evidence (Workbench, read-only).
- **Entity Lookup** — Canonical entity-index search and candidate browser (Browser, read-only).
- **Entity Detail** — Evidence-backed entity dossier bridging SQL, Lua, Feature Trace, client, capture, event/dialog, wiki, relationship, and provenance evidence (Detail, read-only).
- **Item Browser** — Faceted item catalogue/search with reference drift comparison and editor/AH handoff (Browser, read-only).
- **Item Script Health** — Active-server script audit, LSB cross-check, repair preview, and explicit confirmed repair-write workflow (Workbench; write boundary explicit).
- **Feature Trace** — Canonical graph/evidence traversal and implementation-path diagnostics (Workbench, read-only).
- **Home / Data & Tools** — Toolkit data-source health dashboard with explicit rebuild/install action boundary (Dashboard).
- **Domain Detail** — Domain-specific implementation/evidence dossier with specialized embedded read-only workspaces (Detail).
- **Model Viewer** — Full-width client DAT/model inspection workspace with preserved specialized renderer layout (Workbench, read-only).
- **DAT Inspector** — Client resource identification/structure/parser workbench with downstream handoffs (Workbench, read-only).
- **3D Zone Viewer** — Full-width client zone visual/capture overlay viewer with explicit derived-mesh cache build boundary (Workbench).
- **YouTube Chat OCR** — OCR run/prerequisite dashboard for video evidence ingestion with explicit local-file/tool writes (Workbench).
- **OCR Run** — Video crop/extraction/layout/OCR/matching/capture-conversion workspace with explicit write actions (Workbench).
- **Settings** — Shared environment/branding/path/write-gate/LLM/backup/server configuration workspace with explicit mutation boundary (Workbench).
- **Character Editor** — Adapter-aware character/inventory editor with offline/capability safety gates and preview/confirm writes (Editor).
- **Item Editor** — Live server/client item editor with preview/apply batching, DAT synchronization, backup, SQL journaling, and session history controls (Editor).
- **Zone Editor** — Full-width server/client spatial editor with entity/path/navmesh tooling, cache operations, and preserved save/undo/redo controls (Editor).
- **Nyzul Isle Layout Editor** — Full-width lineage-aware floor-generation/spatial editor with optional navmesh evidence and persistent exclusion controls (Editor).
- **Synth & Crafting** — Full-width recipe browser/audit/health/compare/economy/editor/export console with explicit mixed read/write boundary (Workbench).
- **Auction House Activity** — Read-only executor/replay/reward activity ledger (Workbench).
- **Auction House Economy Intelligence** — Full-width analytical economy workspace with explicit toolkit-local snapshot-recording boundary (Workbench).
- **Auction House Help & Status** — Capability/safety/operations reference for Auction House workflows (Detail-like Workbench, read-only).
- **Auction House Reward History** — Read-only reward campaign/outcome history with retry preview handoff (Workbench).
- **Auction House Administration** — Readiness/economy/listing overview with preview/validation-only controls and guarded-tool handoffs (Workbench).
- **Auction House Console** — Full-width operational hub with guarded Test-only mutation workflows and fail-closed safety gates (Workbench).
- **Auction House Presets** — Reusable cleanup/seeding configuration workspace; writes toolkit preset state but never authorization (Workbench).
- **Auction House Cleanup** — Preview-token-bound stale/targeted listing cleanup with guarded Test-only Admin Buy/Return execution (Editor).
- **Auction House Listing Manager** — Exact listing browser/admin surface with guarded single/batch DSP/Topaz Test writes (Editor).
- **Auction House Seeder** — Test-only player-backed listing and market-history/scenario seeding workspace with readiness/confirmation safeguards (Editor).
