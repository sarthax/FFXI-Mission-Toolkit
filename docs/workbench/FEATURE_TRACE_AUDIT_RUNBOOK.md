# Feature Trace audit: local operator run

The audit is **read-only** and does not need another capture/wiki import. Use an already indexed server checkout. Do not commit exported trace JSON, server data, or capture contents.

## 1. Run regression checks

From the repository root with the Toolkit virtual environment activated:

```powershell
python -m pytest test_fixtures/test_feature_trace_relevance_audit.py -q
```

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
