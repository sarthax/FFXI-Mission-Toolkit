# Feature Catalog — Operator Reference and Maintenance

The Feature Catalog is the structured inventory of **what the Toolkit exposes**. It is deliberately distinct from the Roadmap (remaining development and validation) and Help (usage instructions).

## Current catalog snapshot (October 19, 2026)

The current curated inventory contains **96 capabilities**, including **48 child capabilities**, across modules. Of these, **74** are labelled implemented and **22** partial. Validation is **95 unverified**, **1 operator-reported**, and **0 tested**. All 96 have either a contextual Help section or a module-specific Help link; **31** have implementation references and **17** have named automated-test references. These are catalog counts, not assertions of comprehensive coverage or live runtime acceptance. Recalculate from `feature_catalog/features.json` rather than treating this paragraph as an evergreen dashboard.

## How operators should read each entry

- **Purpose:** what the capability is intended to help inspect or perform; a concise summary is not proof of behavior.
- **Operator workflow:** a starting sequence and navigational advice, with full procedural detail in the linked Help section.
- **Documented subfunctions:** entries linked by `parent_id`; absence of children means not yet documented, not necessarily absent.
- **Implementation references:** checked-in code pointers for deeper inspection, not a demonstration that the feature works live.
- **Regression references:** named offline tests applicable to the capability. An empty list means specific test evidence has not been attached, not that no tests exist.
- **Limitations and validation:** assumptions and interpretation warnings. `unverified` remains the default without independent runtime evidence.

The detail page displays missing implementation/test links explicitly rather than hiding the evidence section. A reference's presence must not silently promote validation status.

## Documentation upkeep

When editing capabilities, keep `purpose`, `how_to_use` and `caveat` specific to the user workflow and avoid rephrasing the summary three times. Split genuinely distinct operator subfunctions into child entries when evidence supports them. Prefer verified paths and narrowly applicable tests; leave mappings absent when unresolved. Check links and focused regressions before merging. Historical checkpoints below document earlier development passes, **not current totals**.

## Canonical data

`feature_catalog/features.json` is the curated v1 source. Subfeatures use an optional `parent_id` pointing to an existing module record. The loader rejects duplicate IDs, missing parents and direct self-parenting. Parent records and child records may share a module route because a dedicated subfeature deep-link is not always available.\n\nEach record has a stable `id`, `module`, `name`, `summary`, primary `route`, `help` route, `implementation` status and independent `validation` status.

Implementation statuses: `implemented`, `partial`, `research`, `planned`.
Validation statuses: `unverified`, `operator_reported`, `tested`.

A route or source reference does not establish runtime acceptance. The inventory began as a Help-derived seed, **not** an exhaustive module or subfeature census. The catalog is separate from Feature Trace's graph schema.

## GUI

`/feature-catalog` renders searchable/filterable records. Help and Roadmap link to it. The catalog is listed in the Home / Project shell navigation and linked from Help and Roadmap.

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

## Coverage diagnostics

The Catalog page now shows an expandable **Coverage audit**. `workbench.core.services.feature_catalog_audit.audit_catalog()` compares global Help's static links to catalog routes and the maintained GET-route inventories, with explicit exceptions for the three mounted module routes. It reports unlisted Help destinations, unresolved catalog destinations, and entries lacking independent runtime validation. The test fails when global Help adds a module link without a catalog entry. This is **link-level coverage**, not an exhaustive audit of subfeatures, service methods or live behavior.

## Initial subfeature coverage

The first expansion adds 18 Help-documented subfeatures across Auction House, Live Client, Feature Trace, Wiki and Key Items. These entries are manually curated from operator-facing descriptions, not inferred from every API endpoint. The catalog remains incomplete for other large modules, and all newly added child records retain `unverified` runtime acceptance until evidence is recorded.

## Source-route expansion (October 18)

Twenty additional operator-facing pages were added from the maintained GET route inventory, bringing the curated inventory to 56 records at that historical checkpoint. These include missions, Assault, Nyzul, zones, client inspection, retail versions, dialog, capture search/query, migration converters, package review and validation runs. Static catalog route references were checked against the maintained route inventories; the Workbench regression workflow now runs `test_fixtures/test_feature_catalog.py` and triggers when `feature_catalog/**` changes. This still does not verify that the pages render in a configured Windows/DSP installation, or that every UI operation works.

## Active-page coverage gate

The coverage audit also compares catalog destinations with the maintained GET-route inventories' static `role: page` entries. It excludes root/Help/Roadmap/Catalog and parameterized paths; uncataloged `LEGACY` or `MERGE` disposition pages are reported separately rather than treated as active feature gaps. The regression fixture requires zero uncataloged active static pages. At the October 18 source-level checkpoint, 75 curated records cover the static active page inventory, with `/items` and `/backport/package` retained as uncataloged legacy/merge-target routes. This is not full dynamic-router, subfeature, browser-rendering, or Windows/DSP runtime acceptance.

## CI validation checkpoint

The initial Workbench Regression run failed in the newly added catalog smoke test because the test incorrectly assumed the query `binary` would match only one record. As the inventory grew, multiple valid records matched. The test now asserts inclusion of Binary Inspector rather than exclusive equality. That historical failure was fixed; later Workbench Regression runs passed. This does not constitute local Windows/browser acceptance.

## Quality and validation audit — October 19, 2026

At that historical checkpoint, the curated inventory had **85 records**, comprising **38 subfeatures**; **67** are labelled implemented and **18** partial. Validation remains independent: **84 unverified**, **1 operator-reported**, **0 tested**. These numbers described the catalog labels at that checkpoint, not runtime capability. Refer to the current snapshot above for the latest counts.

The Coverage audit now displays module and subfeature totals, per-status counts, and missing purpose/usage/caveat fields. CI asserts status accounting against the actual JSON, rather than pinning record counts likely to change. UI-control inventory remains sampled and is not a claim of complete subfunction coverage. The next content-oriented slice is to attach real source/test references and review module-by-module whether key GUI actions have corresponding guided subfunction entries; runtime validation requires a separate observed acceptance record.

## Feature Testing and Wiki/Trace crosswalk — October 19, 2026

The next source-grounded expansion adds six curated capabilities: a parent Feature Testing & Validation entry, three operator-facing testing subfunctions (guided scenario builder, imported run inspector, read-only Supervisor investigation), a Feature Trace Wiki provenance drill-down, and exact Wiki page/section navigation. The catalog now has **91 entries**, subject to merge and CI. The existing `/feature-testing` mounted router is explicitly accounted for in source-route diagnostics rather than inventing a static endpoint in the maintained host route map.

All six new records remain **unverified** for local runtime acceptance. The descriptions distinguish design-only tests from supported execution and Wiki source evidence from verified DSP gameplay behavior. Subsequent work should inspect each major module's controls and functions against the curated catalog and attach independently reviewable source/test evidence, rather than automatically converting all endpoints to capabilities.

## Key Items and Validation operator function crosswalk (October 19)

Five additional guided subfunctions are proposed: Key Item lineage comparison, Lua operation dependencies, evidence handoff, validation run history, and live target validation. The inventory will reach **96 curated records** if this PR merges. Each new entry separates its purpose, operator steps and limitations, and retains `unverified` runtime validation. Key Item inspector labels and operation controls are checked in the curated template audit; Validation is grounded in existing `/validation/runs` and `/validation/live-target` routes. This is a documentation and route-contract expansion, not a claim that the user's live server or test harness has been exercised.

## Source/test provenance crosswalk (October 19)

A focused subset of Feature Trace, Feature Testing and Key Items records now carries `source_refs` and `test_refs` pointing to checked-in files. The loader verifies that paths exist and rejects invalid references; the detail view displays these under **Source and regression references**. These are implementation and offline-test pointers only: they do **not** upgrade a record to `tested` or prove live DSP, client, or GUI acceptance. More modules will be mapped in later slices.

## Contextual Help deep links — October 19

Twenty-two existing capabilities in Feature Trace/Behavior Inspector, Wiki, Key Items, Feature Testing and Validation now point to anchored in-app guidance rather than generic `/help`. Each anchor covers a bounded operator workflow and explicitly states the distinction between source references, design-only plans and observed validation. The catalog regression confirms that every referenced Help anchor is present. This is a navigation and documentation improvement, not a runtime validation claim.

## Help-link coverage diagnostic (October 19)

The Catalog coverage panel now counts and classifies each record by its Help destination: a contextual `/help#section` link, a direct module-specific Help route, or a generic `/help` link. The audit also groups generic destinations by module with links to their exact catalog entries for targeted documentation work. Regression compares these counts to live `features.json`; it does not hardcode an expected number of contextual links. This is link-depth coverage only, not a quality or runtime-acceptance score.

## Client Research contextual Help (October 19)

Sixteen Binary Inspector, Retail Version and client-asset research entries now point to three grounded Help sections. The documentation covers PE evidence, version/probe comparisons, manifest and selective download planning, and DAT/model/dialog research, while explicitly distinguishing artifact/source inspection from the running client's behavior. Existing Help anchor and route inventory regression contracts apply. This does not change runtime validation labels.

## Capture workflow Help links (October 19)

Twelve Captures records now deep-link to operator Help for browsing/search/path projection, ingestion and metadata, review/zone evidence, and video OCR. These preserve provenance and distinguish session observations from verified server behavior. Link/anchor checks remain part of the Feature Catalog regression suite, and none of the entries is promoted to runtime-tested.

## Migration Help deep links (October 19)

Eight Migration entries now point to focused operator guidance on ID drift, Lua/SQL/binding conversion, and package generation/scope/review. The instructions distinguish read-only investigation and generated plans from authorized apply operations. Runtime validation status remains unchanged; existing Help fragment and route-inventory smoke tests cover the destinations.

## Research & Evidence contextual Help — October 19

Six remaining Research & Evidence entries now link to sections for scoped research sessions and evidence, gaps and contradictory claims, and Feature Checker/LLM-assisted research. Guidance keeps source identity, indexing gaps and independent runtime acceptance separate. Existing catalog and Help route regressions validate navigation.

## Live Client contextual Help — October 19

Five Live Client catalog functions now deep-link to bridge connection/observation, entity and movement telemetry, or live 3D viewing guidance. This clarifies client-observed data versus DSP spawn records, sampling gaps, and source freshness; no gameplay/runtime validation status changes.

## Server Data contextual Help — October 19

Four Server Data catalog entries now link to specific instructions for entity lookup, read-only SQL browsing, dialog source references, and event IDs. The guidance requires DSP profile/zone/source identity and distinguishes indexed or configured data from observed runtime behavior. Existing Help link tests cover anchor and route integrity; no runtime statuses or database permissions change.

## Help quality and evidence crosswalk (October 19)

The catalog now audits each module's entry count, generic Help destinations, missing purpose/how-to/caveat details, and attached source/test reference counts. A separate provenance gap inventory flags features lacking either source or test pointers. These are *static triage indicators*, not independent judgments of instruction accuracy, full functional coverage, or DSP/runtime acceptance. Review representative workflows and evidence manually before promoting validation status. The PR is independent of pending Captures, Migration, Research, Live Client and Server Data Help PRs.

## Source provenance pilot: Captures, Live Client, Server Data

The Capture Browser, Live Client bridge and Server Data entity/SQL browser entries now carry inspected repository GUI source pointers. Live Client bridge entries also cite an existing protocol regression. No tests are attached to the entity/SQL browser entries without verified matching tests. Presence of code and passing protocol regression do not establish operator or gameplay acceptance. This pilot is independent of the pending Help quality audit and documentation branches.

## Contextual Help completion — October 19

The final 14 generic Help destinations now point to focused operator guidance for configuration and synthesis, items, progression, zones and validation history. The catalog regression explicitly rejects generic `/help` destinations and checks contextual anchors. These links improve navigation and workflow descriptions; they are not a substitute for independent instruction review, implementation provenance or live DSP/client testing.

## Focused source-provenance follow-up (October 19)

Verified GUI implementation pointers were added for Capture Search, Capture Review, Wiki browsing, Wiki exact-source navigation, and Feature Trace runtime drill-down. The Wiki exact-source link contract also has a narrowly applicable dossier regression reference. Capture Search/Review remain without named test references because merely having an implementation template is not test coverage. Remaining Research and Migration references require a separate source-to-handler crosswalk; no references were fabricated. Local runtime validation remains unverified.

## Research and Migration provenance crosswalk (October 19)

The catalog now references checked-in GUI and selected service implementations for Research sessions, contradictions, evidence browsing, ID Drift, package review/scope/create, Lua and SQL conversion, and bindings. Named regression pointers are limited to the existing research-session GUI test and Lua/SQL converter tests; other entries deliberately retain missing-test status. Static references demonstrate traceability, not passing local client/server workflows or runtime acceptance.

## Functional guidance review — prioritized operators (October 19)

The Feature Trace, Live Client, Wiki, Zone Editor, Lua Converter and SQL Converter catalog entries now describe concrete starting controls and review steps instead of only a generic opening sequence. These are read-only documentation refinements, with regression assertions for key instructions. Feature Trace branch/provider controls, bridge setup previews and read-only checks, Wiki sync/snapshot validation, and converter option/collision checks were inspected in checked-in templates. Zone Editor instructions deliberately remain cautious because this pass did not establish the exact current template backing the registered route. Do not promote runtime validation status on the strength of GUI text or offline tests.

## Operator-workflow review: Captures, Research and Migration (October 19)

The Capture Browser/Search/Review, Research Sessions/Evidence, ID Drift and package create/review catalog descriptions now identify practical controls and evidence handoffs. Search results and parser suggestions retain original capture provenance; reviews must inspect dependency ledgers and missing/skipped artifacts before promotion. These are static operator guidance updates grounded in the checked-in templates where available, not runtime acceptance. Research evidence and ID Drift descriptions remain cautious about assuming a particular data source or result was verified.

## Large-batch subfunction workflow review (October 19)

Twenty-two child-capability operator workflows were expanded across Live Client (4), Wiki (3), Captures (8), Retail Versions (4), and Feature Testing (3). Each now directs operators to specific input and review steps and distinguishes evidence from inference or actual execution. The changes are documentation-only and do not claim that controls were exercised against a live Windows client, DSP server, or locally held retail/capture files. Checked-in GUI controls were sampled for representative parent tools; individual behavior and input availability remain subject to local acceptance. The regression checks stable review concepts and keeps runtime validation separate.

## Subfunction consistency pass: Auction House, Key Items, Trace and Validation

Seventeen remaining priority child workflows were revised to identify operator selection, evidence checks and explicit review boundaries: eight Auction House, four Key Item, three Feature Trace and two Validation functions. Existing status labels and references are unchanged. The guidance is source-oriented and does not assert that live server changes, scheduled rewards, key-item transitions or validation checks were run. Exact behavior still requires an authorized local operator and captured evidence.

## Documentation accuracy audit — staged implementation

The catalog's **Documentation accuracy triage** panel now consumes `audit_documentation()` from `src/workbench/core/services/feature_catalog_documentation_audit.py`. It is reproducible from checked-in catalog records and the conservative GUI control inventory, without invoking routes or changing server data.

1. **Static triage (implemented):** report entries with absent source/test mappings, missing purpose/workflow/caveat fields or those fields duplicating the summary. Keep each finding tied to a stable catalog ID. GUI controls are explicitly labelled `needs_review`, *not* automatically classified as missing documentation.
2. **Handler and workflow verification (next stage):** select a bounded list of GUI candidates, inspect real handler bindings, inputs, outputs, error paths and guardrails; mark findings as confirmed mismatch, documentation omission, supported or unresolved with source references. Avoid inferred route-to-handler matches.
3. **Corrections and independent acceptance (next stage):** update grounded catalog prose and tests, attach source/test references, and record local operator validation separately. Never upgrade a runtime status merely because static CI passes.

The panel displays static findings and a pointer to the existing automatic GUI inventory. Template scans have a cap and miss dynamic Jinja-generated controls. Missing test mappings do not establish that tests are absent; they indicate that applicable regression evidence has not been attached.

## Source-backed GUI review cases — stage 2

The catalog now tracks five curated template-only findings in `feature_catalog/documentation_review_cases.json`: the package review filter, Feature Testing run filter and builder plan, and Lua/SQL converter forms. Their markers are asserted against checked-in templates and shown in the audit UI. All are explicitly `template_verified_handler_unverified`. This is evidence of a rendered-form source definition, **not** proof that a handler works, accepts specific inputs, or ran in a live server environment. Source-to-handler checks, negative/error paths and operator acceptance remain further review stages.

## Handler source crosswalk — stage 3

Five previously template-only controls now have checked-in handler references: package review GET (`packages_review`), Feature Testing GET dashboard (`dashboard`), GET test builder plan (`test_builder_plan`), Lua converter POST (`lua_convert_submit`) and SQL converter POST (`sql_convert_submit`). The audit asserts literal template and handler symbols and exposes their source paths. The converter handlers return transformed text and warnings; the SQL converter may inspect indexed data for collisions or duplication. These source observations do **not** verify a live client, local database, permissions, target server writes or end-to-end error handling. Further review should bind complete parameter/error contracts and independent operator acceptance evidence.

## Behavioral source contracts — stage 4

The five curated handler review cases now document observed HTTP method, input names, returned fields, error/uncertainty notes and a bounded behavior class. Package and Feature Testing filters are read-only history/review; the test builder plan is design-only; Lua conversion produces a preview; SQL conversion may read a configured index for collision/duplication checks. These are source-level interpretations, checked by literal source markers to detect drift. They do not establish that errors or authorization were exercised end-to-end, nor permit execution against live targets. Investigate any failed marker manually before changing documentation or validation statuses.

## Documentation discrepancy detection — stage 5

Five reviewed GUI-to-handler contracts now carry explicit, case-specific documentation checks. The audit compares required operator terms against the relevant catalog purpose, workflow or caveat, and reports missing terms as **reviewable documentation gaps**, not runtime defects. Corrections clarify read-only package review, filter limitations for test history, test plan versus guarded execution, preview-only Lua conversion, and index-reading (but not database-writing) SQL conversion. CI asserts no discrepancies in these curated cases. This is a bounded contract/content check, not a semantic guarantee of all code paths; further expansion requires independently verified handler behavior and error cases.

## Expanded behavioral reviews — Package Scope and Capture Search

Two more source-backed audit cases cover Package Scope GET filtering and cross-capture Search GET across event and packet modes. The Package Scope page contains separate POST decision/review forms; the documented GET filter must not imply those operations are executed. Capture Search results depend on available indexed recordings. Curated documentation contract checks protect these boundaries, while handler-symbol checks remain static source drift guards rather than runtime execution tests.

## Higher-risk source contracts — guarded enqueue and package creation (October 20)

Two additional source-backed review cases extend the audit to operations that initiate work. The Feature Testing POST launch requires operator authorization and explicit approval before enqueueing; a QUEUED result is not a test verdict. Package creation POST requires a canonical graph, migration actions and reviewed dependency scope before materializing a package candidate; it does not deploy to the server. These boundaries are documented in the operator catalog and checked by static handler-marker assertions. They have **not** been exercised against a configured runtime. The form's visible presence is not authorization, and failing a source-marker check must be investigated rather than bypassed.

## Administrative preview and scope-state audit — October 20

Three additional source reviews cover the two package-scope POST actions and the Auction House admin listing preview. Scope decision POST saves a node decision and resets its review to DRAFT; scope review POST checks closure before recording REVIEWED. Both update Workbench graph review state and must not be described as GET-only or as target server deployment. The Auction House listing-preview handler performs SELECT-only snapshot lookups, not a listing mutation. The AH UI panel and handler were observed separately; the static marker does not prove the exact frontend-to-endpoint binding. All three remain runtime unverified, with explicit source markers and discrepancy checks.

## Auction House purchase-preview source review — October 20

Two additional reviewed routes cover the purchase/cleanup preview and the lineage-specific validation preview. Both are POST routes for read-only/SELECT-only inspection; neither posts an auction, completes a purchase or authorizes a mutation. Missing/invalid inputs and unavailable environments have distinct error paths. The Auction House preview panel and handlers are currently verified separately, not as a proven frontend-to-endpoint binding. Recovery-journal language now emphasizes diagnosis and independent idempotency checks instead of implied retries. No administrative operation or live server action was executed.
