# Feature Trace — evidence-first operator guide

Feature Trace is primarily an **implementation and dependency navigation tool**, not a dump of every catalog relationship. The October 11 [relevance audit](FEATURE_TRACE_RELEVANCE_AUDIT_2026-10-11.md) established a test protocol; its real-package execution and scored user-facing acceptance remained pending at that baseline.

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

For a coordinated real-data baseline, see [P0 issue #1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228). The three-case local campaign gate is `scripts/audit_feature_trace_campaign.py`: generate a `NOT_RUN` manifest using `--template`, collect and independently annotate real traces outside Git, then evaluate the manifest. `MEASURED_PENDING_OPERATOR_ACCEPTANCE` is an aggregate report requiring manual review, not a UI or game validation PASS.

A benchmark passing relationship counts does not prove ranking or relevance. Score real-package identity accuracy, top-result usefulness, source locator accuracy and click-through burden separately. Never call an unrun scenario “validated.”

References: `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`, `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md`.

## Wiki source-document drill-down

For a Wiki-backed subject, select the source-qualified `REFERENCE_PAGE` catalog entry and follow `HAS_SOURCE_DOCUMENT` to inspect its recorded source format, retrieval timestamp, revision and parser version. Use `DOCUMENT_FOR_REFERENCE_PAGE` to return to the page and its existing block/claim paths. Both links are provider-native navigational relationships matched on the exact `(source_id,page_id)` pair, not canonical graph assertions. Missing raw document rows yield no document link; do not infer that an absent revision or timestamp has been validated. Same-numbered pages on BGWiki and WikiWikiJP must never cross-link through the numeric page ID alone.
