# #1408 — Offline results view-model fixture contract

**Scope:** Seven deterministic characterization cases only, not a UI, wire contract, result importer, scenario editor, runtime adapter or gameplay execution. Source: #1408 Wave36 delivery contract. No actual immutable MOG-09 run artifact is bundled or verified here: `SOURCE_BACKED_RUN_UNAVAILABLE` has null identity, UNKNOWN verdict, and zero steps, **not** a fabricated historical PASS. A future owner-authorized importer must provide real evidence and revision identity before upgrading it.

`scenario_results_v2_1408.json` contains case identity, human-oriented action and expected/observed fields, separate task lifecycle and independent verdict, missing-evidence reasons, evidence refs, and source revision placeholders. `fixture://` references are **synthetic**, not external immutable production proofs. Null means not supplied or unverified, not zero or a known revision. The `synthetic:` namespace and `synthetic-` values are illustrative test identifiers, not real run IDs or cryptographic hashes.

| Fixture | Task lifecycle | Independent verdict | Interpretation |
| --- | --- | --- | --- |
| Source-backed MOG-09 unavailable | UNKNOWN | UNKNOWN | No genuine retrievable run/evidence; never invent PASS |
| Contradicted expectation | COMPLETED | FAIL | Synthetic observed value contradicts expected value |
| Missing readback | COMPLETED | UNKNOWN | Dispatch/task completion is not a gameplay verdict |
| Preflight block | NOT_STARTED | BLOCKED | No approved runner/oracle or necessary fixture |
| Cancel acknowledgement | CANCEL_REQUEST_ACCEPTED | UNKNOWN | Not terminal CANCELLED without observed terminal state |
| Conflicting provenance | COMPLETED | UNKNOWN | Preserve both conflicting synthetic receipt identities |
| Zero history | NOT_STARTED | UNKNOWN | Empty-state guidance; no imaginary run |

**Consumer contract:** Display two separate status labels, readable expected→observed step cards, original evidence refs, explicit missing evidence reason, and source/runner/revision info **only when supplied**. Never conflate synthetic receipts with authentic imports. Conflict is visible and remains UNKNOWN. Compare two runs only with stable authenticated run/attempt/revision/source identity and compatible scopes; fixture comparisons are NOT_COMPARABLE. Human-facing interface and keyboard/narrow-screen acceptance belong to later owner/UI integration, not this deliverable.

The standalone Python test checks all seven types, negative verdict mutations, cancellation semantics, missing data, no invented run/digest, and comparison refusal. It does **not** verify real Headless, DSP, actual event observation, browser accessibility, immutable hosted artifacts or approved oracles. #1406 PRODUCT NOT ACCEPTED; no merge or execution entitlement.
