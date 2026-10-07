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

`test_unified_ui_framework.py` enforces the adoption boundary. Existing pages that still extend
`base.html` directly are temporarily listed in `UI_LEGACY_TEMPLATE_ALLOWLIST.txt`. A new module
page should extend `workbench_page.html`. Adding a new legacy entry is an explicit opt-out and
requires a reason.

When a page migrates, remove it from the legacy allowlist in the same change. Migrate by workspace
and preserve route behavior, data semantics, write safety, and evidence meaning.

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
