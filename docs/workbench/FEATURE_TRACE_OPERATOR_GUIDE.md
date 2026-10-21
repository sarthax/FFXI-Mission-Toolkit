# Feature Trace — evidence-first operator guide

Feature Trace is primarily an **implementation and dependency navigation tool**, not a dump of every catalog relationship. The October 11 [relevance audit](FEATURE_TRACE_RELEVANCE_AUDIT_2026-10-11.md) established a test protocol; its real-package execution and scored user-facing acceptance remained pending at that baseline.

## Provider evidence presentation correction (October 20)

Focused-mode generated provider relationships now carry their actual `from_node`, `to_node` and source-recorded traversal depth into the Relationships table. A missing provider depth remains unknown (shown as a dash), not a fabricated hop. Provider-generated edges are visibly marked **read-only** with their generator and up to three escaped source-evidence summaries; persisted canonical edges retain their evidence ID/link separately. The Runtime relationship section presents a count/inspection handoff instead of an empty per-edge table because the indexed runtime hierarchy intentionally retains summary groups, not expanded raw packet rows.

This is a **rendering/interpretation fix**, not a relevance-ranker change, new identity closure, successful source-locator validation or real DSP acceptance. The baseline under [P0 #1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228) remains NOT RUN until a local reviewer returns actual three-case observations.

## Browser-local named investigation views — first save/resume phase (October 20)

When Feature Trace resolves an exact root, the **Named investigation views** section lets the operator enter a name and optional note, then **Save this view locally**. Each explicit save retains the resolved root, selected Question mode, hop depth, traversal direction, and bounded preceding-node trail as a validated, same-origin Feature Trace URL. Open **Resume / delete saved views** to reopen the current indexed trace or delete a saved view. Saving another name for the same root permits a local fork without overwriting the original.

The save list is stored **only in the current browser profile's localStorage**, up to 20 records. It is not available on other machines or browsers, and clearing site data deletes it. No raw Lua/SQL, packets, edges, evidence bodies, character/account data or graph snapshots are saved by this feature. No server-side database or live client is written. Saves are **explicit**—there is no automatic draft recovery yet. Storage restrictions, a corrupt browser record or quota exhaustion cause an error instead of a misleading success message.

**Acceptance boundary:** Resuming re-executes Feature Trace from a saved navigation URL; the bookmarked root or relationships might have changed or vanished. This phase does not pin an authoritative source revision or verify evidence staleness; an on-page warning instructs the operator to recheck the actual indexed source, identity and locator. It is not backend-persisted research, automatic recovery, multi-browser sync, or the cross-tool Feature/Behavior/Character saved investigation model. That future work is tracked at [#1235](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1235); first-screen relevance and real-data acceptance remain [#1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228).

## Bounded investigation trail (October 20)

Feature Trace now displays an **Investigation trail** above the Evidence Dossier when a root resolves. It records up to eight previous root selections **in the URL only**, so the operator can follow indexed canonical/provider links and click an earlier breadcrumb to backtrack. The selected question, depth and traversal direction are preserved, and **Clear trail for this root** starts over without changing the resolved root. An existing URL can be shared/reopened with its trail intact.

**Evidence boundary:** These are *browser selections*, not a verified graph path, identity equivalence, runtime evidence, or proof of causal behavior. Source-locator and mission-transition correctness still require independent inspection. The URL trail is intentionally bounded and validated as untrusted input; malformed entries reset the navigation trail rather than erroring or manufacturing relationships. It does not write to SQLite, store drafts locally, or provide named/saved investigations. **Persistent saved investigations and stale-evidence rehydration remain future work**, separate from the relevance-ranked default gated by [P0 issue #1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228).

## Question-first navigation (October 20)

The Feature Trace search form now has a **Question** selector. It exposes existing focused trace modes without requiring a typed `@mode` prefix: Implementation, Mission, Triggers, Effects, Dependencies, Runtime, Identity, Diagnosis and All Evidence. The default **All recorded (legacy)** deliberately preserves the historical unfiltered trace, while explicit questions use the previously implemented focused-mode evidence/filter contract. Choosing a mode does **not** itself validate relevance, runtime behavior or absence of missing paths.

The selected question, depth and traversal direction carry through node, provider, and relationship links, so following an implementation path does not silently reset the investigation. The focus notice includes an explicit **open All recorded (legacy)** link to compare excluded/peripheral material without changing stored evidence. Existing `@mission <root>` style searches remain supported: the query prefix becomes the selected visible question and is removed from the search text. Explicit dropdown selection overrides a conflicting legacy prefix. Invalid selectors revert to the unchanged legacy mode rather than selecting another question.

This is a discoverability and navigation milestone, **not** the future relevance-first projection. Before changing the default or claiming useful first-screen ranking, complete the locally reviewed Absolute Virtue, WotG Cait Sith and ordinary NPC scorecards on [P0 issue #1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228).

## Recommended workflow
1. Start with one concrete question (e.g. “what controls this NM behavior?” or “what gates this mission?”).
2. Search Feature Trace by a specific ID/name, verify the selected root's source family and exact identity. Do not collapse ambiguous NPC/spawn/group/pool IDs into one object.
3. Inspect the first directly relevant evidence paths: source Lua/SQL, source line or row, spawn/group/pool linkage, event/CSID and prerequisites as appropriate. Expand peripheral providers only on demand.
4. Open the Evidence Dossier and drill into runtime/validation/character/client evidence when it answers the question. Distinguish provider-native relationships from independently recorded canonical graph edges.
5. For Lua behavior use Behavior Inspector: start with readable trigger → requirements → actions/events → results, then drill into the technical graph for exact guards, callbacks, named state and helper provenance.
6. Record wrong or missing paths, unrelated result noise, absent source locators and ambiguous identities as findings rather than filling gaps with unverified wiki claims.

## Acceptance cases
- **Absolute Virtue:** trace resolved identity, spawn/group/pool and important Lua behavior, not every unrelated obtainability or wiki association.
- **WotG Cait Sith:** show initiator, gates, state changes and next actionable evidence without drowning in all same-zone NPCs.
- **Ordinary NPC:** recover onTrigger/onTrade semantics and source lines before generic zone-wide context.

**Baseline integrity:** the campaign evaluator requires an exact versioned backend export for each reviewed case and rejects mismatched roots/modes or evidence IDs. Keep source SHA and browser first-view annotations independently reviewed; passing export checks does not imply the graph is relevant or locally accepted.

**Audit collection help:** `scripts/export_feature_trace_relevance.py` exports the current backend's exact-root focused trace to a **new file outside Git** using read-only SQLite. Use only after selecting a uniquely resolved canonical root in the page. The export is not the first-screen GUI view; identify actually visible edges independently before scoring. See [the local audit runbook](FEATURE_TRACE_AUDIT_RUNBOOK.md) for commands and safety limits.

For a coordinated real-data baseline, see [P0 issue #1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228). The three-case local campaign gate is `scripts/audit_feature_trace_campaign.py`: generate a `NOT_RUN` manifest using `--template`, collect and independently annotate real traces outside Git, then evaluate the manifest. `MEASURED_PENDING_OPERATOR_ACCEPTANCE` is an aggregate report requiring manual review, not a UI or game validation PASS.

A benchmark passing relationship counts does not prove ranking or relevance. Score real-package identity accuracy, top-result usefulness, source locator accuracy and click-through burden separately. Never call an unrun scenario “validated.”

References: `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`, `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md`.

## Wiki source-document drill-down

For a Wiki-backed subject, select the source-qualified `REFERENCE_PAGE` catalog entry and follow `HAS_SOURCE_DOCUMENT` to inspect its recorded source format, retrieval timestamp, revision and parser version. Use `DOCUMENT_FOR_REFERENCE_PAGE` to return to the page and its existing block/claim paths. Both links are provider-native navigational relationships matched on the exact `(source_id,page_id)` pair, not canonical graph assertions. Missing raw document rows yield no document link; do not infer that an absent revision or timestamp has been validated. Same-numbered pages on BGWiki and WikiWikiJP must never cross-link through the numeric page ID alone.
