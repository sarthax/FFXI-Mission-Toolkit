# Feature Trace audit: local operator run

The audit is **read-only** and does not need another capture/wiki import. Use an already indexed server checkout. Do not commit exported trace JSON, server data, or capture contents.

## 1. Run regression checks

From the repository root with the Toolkit virtual environment activated:

```powershell
python -m pytest test_fixtures/test_feature_trace_relevance_audit.py -q
```

## 1A. Exact-root read-only JSON export (new baseline collection aid)

The feature page currently renders a trace in HTML. Its specialized `/features/trace/path.json` and `/features/trace/runtime.json` diagnostics are **not** a generic full-trace JSON export. To avoid guessing a nonexistent response URL, the new CLI can reproduce a **bounded focused-mode backend trace** using existing indexed SQLite files. It does not measure which edges were actually visible in the browser on initial load; review that separately as described below.

First use the Feature Trace page to select the correct **exact canonical root ID**—for Cait Sith use the *mission*, not the same-name NPC. Do not substitute a numeric coincidence, display name, or ambiguous search match. From a terminal in the Toolkit checkout, choose a **new output path outside the Git checkout**:

```powershell
python scripts/export_feature_trace_relevance.py --case absolute-virtue --root 'EXACT-ROOT-FROM-TOOLKIT' --depth 1 --output "$env:TEMP\\trace-av.json"
python scripts/export_feature_trace_relevance.py --case wotg-cait-sith --root 'EXACT-MISSION-ROOT' --depth 1 --output "$env:TEMP\\trace-cait-sith.json"
python scripts/export_feature_trace_relevance.py --case ordinary-npc --root 'EXACT-NPC-ROOT' --depth 1 --output "$env:TEMP\\trace-npc.json"
```

Arguments `--graph-db` and `--catalog-db` can name alternate **existing** indexed databases; the defaults are the Toolkit's `workbench.db` and `ffxi_zone_database.db`. Both are opened in SQLite **read-only/query-only** mode. The exporter imports only the Feature Trace facade, not the monolithic GUI, DSP process or Ashita. It refuses missing files, an unknown or conflicting root, the wrong mission/entity root kind, duplicate audit identities, an output inside the repository, and overwriting any existing output. One- or two-hop depths only; the default is one hop with a 500-node bound.

**Privacy and evidence:** each JSON contains original local trace edges and provenance, potentially including private source/capture locators. Keep it outside Git; never post raw exports or file paths to issues. The console summary deliberately omits exact entity IDs and evidence. The exporter provides `edge_audit_ids` for annotation convenience, but **does not** identify relevant paths or infer `initial_edge_ids`. To measure first-screen precision, record the actual initial browser state and independently map that view to the exported edge IDs. If the GUI's trace mode/direction/root does not match the exporter or an edge is absent, record a blocker instead of claiming equivalence.

Use the normal annotation and score steps below with the exported JSON, and complete the three-case campaign manifest with exact Toolkit/server revisions. Even a fully scored campaign remains **MEASURED_PENDING_OPERATOR_ACCEPTANCE**, not live gameplay or GUI usability PASS.

## 2. Collect three real traces

Start the Toolkit and use the existing Feature Trace page. For each case, select the mode and root below and record the exact resolved entity/mission ID and server source revision.

| Case | Search | Mode |
| --- | --- | --- |
| Absolute Virtue | Absolute Virtue | Implementation |
| WotG Cait Sith | Cait Sith (mission), not the NPC | Mission |
| Ordinary NPC | One uniquely resolved NPC from your active server | Implementation |

Record the initially shown edges and copy/export the trace response as JSON where supported. If the UI has no JSON export, use browser developer tools > Network and save the relevant trace API response; do not guess a route or assume the API has an export button. Keep private captures outside the repository.

Before annotating, generate a manifest of actual audit IDs:

```powershell
python scripts/audit_feature_trace_relevance.py .\\av-trace.json --list-edges
```

Generate a blank annotation file (all evidence starts unreviewed):

```powershell
python scripts/audit_feature_trace_relevance.py .\av-trace.json --template > .\av-reviewed.json
```

## 3. Annotate

For each exported response containing an `edges` array, prepare a separate JSON with these **five required arrays**:

```json
{
  "initial_edge_ids": [],
  "verified_edge_ids": [],
  "relevant_edge_ids": [],
  "required_edge_ids": [],
  "locator_edge_ids": [],
  "missing_required_paths": []
}
```

Use exact unique `relationship_id`, `edge_id`, or `id` values from the response. An empty array means none are annotated; it is **not** a negative judgment. Only mark `verified_edge_ids` after checking source evidence. `relevant_edge_ids` are verified edges necessary to answer the chosen question. `required_edge_ids` are independently verified paths that should be in the first view; for missing required edges, record a concise independently verified source-backed description in `missing_required_paths` because an absent edge cannot be referenced by ID. `locator_edge_ids` have working source/row/capture locators. `initial_edge_ids` are actually visible on initial load, not every returned edge.

Feature Trace also returns read-only generated provider edges with `relationship_id: null`. The audit utility assigns these a deterministic `audit:generated:<sha256>` identity based on source, target, relationship, generator and evidence. This identity is **audit-only** and does not change canonical graph data. If two edges have indistinguishable identities, scoring fails closed. If the response lacks stable unique edge IDs, **stop and record a schema/identity blocker**. Do not invent identifiers or silently substitute list indexes.

## 4. Score

```powershell
python scripts/audit_feature_trace_relevance.py .\av-trace.json .\av-reviewed.json
```

Interpret `precision_verified_only` only together with `review_coverage`; unknown edges must not be treated as noise. `required_path_recall` includes verified missing required paths from `missing_required_paths`; avoid double-counting paths already represented by `required_edge_ids`. Record navigation steps, first-view screenshots, source locator failures and unresolved identity in the audit ledger.

## 5. Return results

For each scenario report: resolved root; initial/reviewed/relevant/irrelevant/unknown counts; absent critical edges; invalid locators; three worst distractions; whether the graph answers the question. Do not claim real-data acceptance until the operator has reviewed the actual result.

The first production fix should be an opt-in, read-only relevance projection; retain the full raw trace and distinguish source-backed implementation evidence from wiki/reference or inferred connections.

## 6. Three-case baseline campaign (P0 issue #1228)

A campaign-level gate keeps the original real-data relevance audit from being mistaken for a collection of unrelated synthetic unit tests. The runbook above remains the source of the individual edge annotations. The batch wrapper **does not run traces or examine private evidence for you**.

Generate the scaffold locally, outside the Git checkout if it will contain private paths:

```powershell
python scripts/audit_feature_trace_campaign.py --template > .\feature-trace-baseline.json
```

Initially, all three case entries are `NOT_RUN`. For each locally reviewed case, change `status` to `REVIEWED`, set `root_resolution` to `unique`, and add `resolved_root_id`, `reviewed_by`, full 40-character `toolkit_sha` and `server_sha`, an explicit `source_families` list, and `trace_json` / `annotations_json` file paths. The trace and annotations must be real observed/independently reviewed inputs; use `BLOCKED` with a reason when root resolution or source indexing is not sufficient. Do not mark a same-name Cait Sith NPC as the mission root.

Score all cases together, using exactly these case IDs and modes:

| Case ID | Mode | Root kind |
| --- | --- | --- |
| `absolute-virtue` | `implementation` | `entity` |
| `wotg-cait-sith` | `mission` | `mission` |
| `ordinary-npc` | `implementation` | `entity` |

```powershell
python scripts/audit_feature_trace_campaign.py .\feature-trace-baseline.json > .\feature-trace-redacted-scorecard.json
```

**Audit provenance integrity (current campaign gate):** `REVIEWED` campaign entries must use the versioned `feature-trace-relevance-export-v1` JSON from `scripts/export_feature_trace_relevance.py`, not an unrelated raw graph or a copied feature page response. The evaluator checks that each trace's **case ID, exact canonical root ID, root kind, mode, traversal depth/direction and bounded node budget** match the campaign; recalculates all native/generated audit edge IDs; and refuses swapped files, changed evidence, malformed exports or reusing one root across two cases. If a prior export has no versioned provenance, collect a new one rather than marking it reviewed. These automated checks **do not validate** your stated Git revisions, source-family authenticity, screenshot visibility, evidence locator correctness or gameplay behavior; verify those independently. A truncated export appears as `export_truncated: true` in the summary and must be explained in operator review.

**Outputs:** `NOT_READY` when any case is `NOT_RUN`, `BLOCKED`, or incompletely annotated. Once all three have a uniquely resolved root, source/ToolKit revisions, at least one first-visible edge, independently reviewed initial edges and a defined required-path denominator, the campaign reports `MEASURED_PENDING_OPERATOR_ACCEPTANCE`. **That is still not a PASS or a usability verdict.** The operator must independently check real implementation identities, source locators, meaningful paths, branching, and navigation screenshots before accepting the baseline and authorizing the first relevance-projection PR.

The redacted scorecard intentionally omits raw paths, reviewer names, full edge lists and free-text annotations. Store the original trace JSON, local manifests, screenshots and client/server file paths **outside Git**, and only post the aggregate findings plus revisions to [issue #1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228). The scorer and campaign evaluator do not query the local server, run gameplay, or write database records.

**Coordinator handoff:** Local Claude/operator owns the real indexed source and browser observation. Remote ChatGPT work owns offline audit tooling and the future opt-in relevance projection after the three-case measured baseline. Coordinate ownership before enabling unattended worker `ready` claims.
