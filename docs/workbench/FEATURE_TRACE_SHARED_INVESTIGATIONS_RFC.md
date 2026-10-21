# Shared Trace Investigations — persistence and rehydration RFC v0

**Status: PROPOSAL / NOT APPROVED / NO SERVER WRITES IMPLEMENTED**  
**Date:** 2026-10-20  
**Tracker:** [#1235](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1235)  
**Related:** Feature Trace relevance gate [#1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228), guided authoring [#1208](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1208).

## 1. Why this is a separate contract

Feature Trace now has URL-only bounded breadcrumbs, explicit browser-local named views (PR #1236), and separately opted-in one-slot recovery drafts (PR #1237). These preserve **selection/navigation**, not source truth. Neither localStorage format is a server investigation schema, authenticated user identity, graph snapshot, or validated implementation path.

A *shared investigation* is an operator-owned notebook of questions, selections, optional annotation, and explicit references to indexed evidence. It must survive Workbench restarts and eventually permit links from Feature Trace, Behavior Trace and Character Mission/Quest Progression **without copying raw canonical graph contents into a second source of truth**.

This RFC proposes a future contract and gates. It does not authorize a database migration, API, authentication bypass, automatic browser upload, local client read/write, DSP write, model tool action, or claim that any trace is verified. Relevance-ranked first-screen presentation remains blocked on the independent real three-case audit in #1228.

### Existing contracts to keep distinct

| Existing feature | Actual role | Must not be inferred |
| --- | --- | --- |
| `gui/static/feature_trace_local_saves.js` | Browser-local, explicit same-origin read-only navigation URL bookmarks | Cross-machine synchronization, immutable evidence, account authorization |
| Feature Trace URL breadcrumb history | Up to eight previous node selections, branch-pruned by navigation | Semantic path, verified edge chain |
| `src/workbench/research/session.py` `ResearchSessionStore` | Persistent model/research tool calls, proposals, permission-profile metadata and replay | Human operator's shared navigation notebook or an already suitable ACL |
| Canonical graph, provider/index/evidence records | Actual source and provenance lookup | Automatically trusted behavior, stable identity across revisions |

Existing `ResearchSessionStore` records include provider/model and verification lifecycle. **Do not overload** research-session IDs or add navigation JSON into existing research tables without separate compatibility review; the proposed storage should have its own named namespace, lifecycle, audit and permissions.

## 2. Required ownership and security decisions — blocking

Before any server-side write PR, the maintainer must document and approve:

1. **Principal:** how a request is bound to an authenticated human/workspace principal in the actual Workbench deployment. A browser-origin check, loopback address, source repository identity, LLM permission profile, or character name is *not* an authentication/authorization solution. If the host has no suitable principal and CSRF controls, stay browser-local and **do not expose shared write endpoints**.
2. **Deployment boundary:** single-user workstation state vs shared Workbench server; permitted database location, backup/export, permissions, file locking, and treatment of multiple simultaneous browser sessions.
3. **API safety:** authenticated owner-scoped access to each record, CSRF protections for browser write requests, same-origin enforcement, capped payloads and fields, audited write policy, and no LLM/MCP or headless caller write permission by default.
4. **Retention/privacy:** expiration/delete policy, backups and purge behavior, treatment of names/notes containing sensitive text, whether encryption at rest is required, and whether export/import is permitted. Never store account passwords, private capture bodies, full source files, raw packet payloads or session tokens.
5. **Canonical index identity:** exact graph/source revision token available at save time, including what the UI can reliably obtain if the graph metadata omits a server SHA. If absent, mark provenance **UNKNOWN** rather than inventing a fingerprint.

Explicit reviewer signoff on these decisions is required before implementing the storage schema or enabling shared create/update/delete.

## 3. Proposed versioned record (not deployed)

The following is illustrative JSON data, **not an active API response**. Identifiers are synthetic.

```json
{
  "schema": "workbench.investigation.v1-proposed",
  "investigation_id": "synthetic:investigation-1",
  "owner_principal": "synthetic:principal-1",
  "title": "Synthetic investigation",
  "note": "Review exact source mapping",
  "created_at": "2026-10-20T00:00:00Z",
  "updated_at": "2026-10-20T00:00:00Z",
  "record_version": 1,
  "forked_from": null,
  "surface": "feature_trace",
  "subject": {
    "root_id": "synthetic:canonical-root",
    "root_namespace": "synthetic:graph-namespace",
    "source_family": "synthetic:server-family"
  },
  "view": {
    "question_mode": "implementation",
    "depth": 2,
    "direction": "both",
    "selected_node_id": "synthetic:canonical-root",
    "selection_history": ["synthetic:prior-node"]
  },
  "pins": [],
  "provenance": {
    "toolkit_commit": null,
    "server_commit": null,
    "graph_revision": null,
    "catalog_revision": null,
    "source_snapshot_ids": []
  }
}
```

**Field constraints (proposed):**

- `schema` is required and exact; unknown versions are read-only/unsupported until migrated explicitly. Unknown fields must not become executable instructions.
- `investigation_id` is server-generated and immutable; `owner_principal` is assigned by the authenticated server, **never trusted from client input**. `record_version` is an optimistic-concurrency revision, not a source revision.
- Title (≤80 characters), note (≤240) and bounded UI annotations are user-entered and must be escaped on render. Any larger attachment/evidence copy is outside v1.
- `surface` starts with a registered enum such as `feature_trace`, `behavior_trace`, `character_progression`; the latter two require independent adapter/ID-contract reviews before enablement.
- Node/root IDs must be exact, namespaced, bounded, validated against the source namespace. Display names alone and same-number client/NPC/mission IDs do not resolve identity.
- `selection_history` contains up to eight validated **navigation selections**, not edge identities. Default depth bounds follow the reviewed surface; no arbitrary query/body persistence.
- `pins`, if later enabled, refer to **exact indexed edge/evidence identifiers** and store an explicit user annotation plus source version metadata. Pins cannot create a canonical edge or change its status. A reference whose identity is ambiguous or invalid is unresolved; it cannot silently point to a replacement.
- Every source revision value is either an exact observed locator/version or `null` (UNKNOWN). `toolkit_commit` is not interchangeable with DSP SHA or a graph refresh watermark.
- A shared investigation can be copied as a *fork* with a new ID/version and explicit parent reference, never by mutating the source record.

## 4. Proposed read/write lifecycle (not implemented)

| Operation | Required checks | Failure |
| --- | --- | --- |
| List/open | Authenticated owner or approved workspace ACL; bounded pagination, no public enumeration | Deny unknown owner and absent identity |
| Create | Opt-in explicit action; strict schema, resolved exact subject/root and payload cap; assign owner server-side | No save on ambiguity/unavailable index or missing authorization |
| Update | Owner authorization; immutable ID/owner; `If-Match` or equivalent expected record version | `409`/conflict on stale writer, never last-write-wins silently |
| Fork | Owner access to source; new ID and version; preserve referenced source versions and provenance | No clone of hidden data across principals |
| Delete | Explicit confirmation/authorized mutation, sensible backup/retention policy | No silent delete or implicit auto-cleanup |
| Rehydrate | Read-only, validate current graph and source identities against pinned versions; return diagnostics | Never rewrite the stored evidence/selection on read |

Proposed UI actions are **Save investigation**, **Resume**, **Fork**, **Review changes**, and **Delete** with visible owner and source-revision context. No implicit upload of existing localStorage views, and no automatic server write on navigation, refresh, graph indexing, or bot activity.

### Conflict and transaction semantics

Use one transaction per state mutation. `record_version` must advance on a successful update; competing updates with an older version fail without partial save. Server-side owner/ACL filters must be part of the data-access operation rather than a purely cosmetic UI check. A deletion/re-save race cannot resurrect a record with a reused ID. Only canonical source/evidence tables remain authoritative.

## 5. Rehydration and source-change diagnostics

On resume, re-run read-only lookup against **current** configured source/index and report both the saved and current revisions. A case cannot be called CURRENT based only on matching display names or unchanged UI options.

Proposed per-reference outcomes:

- `CURRENT` — exact namespace, node/edge identity and required provenance match an indexed record, with enough source revision metadata to support this judgment.
- `CHANGED` — exact identity still resolves, but a pinned source/edge/version digest differs.
- `MISSING` — previously referenced exact node/evidence identifier is absent from the available current index.
- `AMBIGUOUS` — multiple candidates or namespace conflicts; **do not guess or coalesce** them.
- `UNKNOWN` — missing revision, source/index unavailable or insufficient evidence to compare.

Compare pinned edge references using an explicit tuple that captures at least the source namespace, source-node ID, recorded relationship, target-node ID, evidence/source identity, and source revision where available. Never infer equality from visual adjacency, display text, row number alone, or a breadcrumb. For truncated graph results, show `UNKNOWN` for unvisited references, not `MISSING`.

**Two independent views:** the saved *navigation intention* and current *evidence resolution*. Present changed/missing references in the UI with current source drill-downs, but never mutate a previous saved pin by opening it. User approval is required to update saved references to a new version. Unknown source revisions block any verified-replay or authoritative path badge.

## 6. Migration of browser-local views (separate opt-in)

Do not auto-read/upload `ffxi.feature-trace.local-saves.v1` or `ffxi.feature-trace.local-draft.v1`. A future **Import browser view** UI must:

1. Require explicit user action, read existing local data through its **current strict validator**, and show a preview of only name/note/navigation fields.
2. Resolve current exact subject before offering a shared record. Unresolved, stale or unknown source revision is displayed as unverified, not repaired by a same-name lookup.
3. Obtain authentication/authorization and retention notice, then require an explicit second save confirmation.
4. Leave the browser-local original untouched until the user chooses to delete it separately. Failure must not destroy the original.
5. Refuse foreign origin, unsupported schema, unknown mode, oversized data, malformed trail, duplicate IDs or credential-like fields without silently trimming or migrating them.

No source data or notes should be sent to a cross-project connector or external model as part of this workflow by default.

## 7. Minimum offline and live acceptance matrix

Offline synthetic, deterministic contracts required before a storage implementation may merge:

- v1/vUnknown/corrupt/oversize input; arbitrary HTML/JS in title/note; invalid namespace and same-name/different-family roots; missing graph/index provenance.
- Two principals cannot list/read/fork/update/delete each other's private investigations; unauthenticated and CSRF-bearing writes fail; read-only model/MCP callers remain unable to mutate.
- Create/open/update/delete and two competing writer revisions; failed mutation leaves DB unchanged; import failure leaves localStorage untouched.
- `CURRENT`/`CHANGED`/`MISSING`/`AMBIGUOUS`/`UNKNOWN` with synthetic index revisions, truncation, stale edge, exact source locator and same numeric IDs in distinct namespaces.
- Fork preserves ancestry but not write-through; saved breadcrumbs never acquire canonical-edge status; no automatic promotion of AI/model-generated assertions.
- Restart/persistence, backups and schema-migration rollback with an explicitly disposable local store.

Local owner/Claude acceptance (after implementation) must additionally exercise a disposable Workbench checkout, restart, two browsers/authorized principals if supported, source-index refresh, stale ID/edge reporting, and explicit deletion. This does not require connecting to live gameplay or writing DSP. **No such tests have run as part of this design RFC.**

## 8. Implementation gates / handoff

1. **G0 — this RFC:** agree on principal/ACL, storage location, CSRF, retention and revision token. No code/DB writes.
2. **G1 — isolated repository and migrations:** separate investigation store, bounded schema, auth-aware read-only list/get initially, safe migration/backup rollback tests. Keep routes disabled if deployment identity is unresolved.
3. **G2 — explicit owner-scoped CRUD:** guarded UI/API writes with optimistic concurrency, opt-in import preview, delete and audit. Never access DSP mutation paths.
4. **G3 — rehydration:** revision-aware current-index comparison, diagnostics and explicit stale-pin review/fork.
5. **G4 — cross-tool adapters:** Behavior Trace and Character progression only after their exact identity/selector contracts and read-only handoffs are independently reviewed.

**Open decisions:** actual Workbench principal/authn mechanism, deployment sharing policy, database namespace/path and backup policy, source revision digest schema, whether notes/pins require additional privacy controls, and adapter identities for Behavior Trace/Character progression. Until resolved, #1235 remains open and persistent shared investigations remain **NOT IMPLEMENTED**.
