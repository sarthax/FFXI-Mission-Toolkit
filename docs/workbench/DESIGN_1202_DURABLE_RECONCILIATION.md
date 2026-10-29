# Design (draft, for review): durable reconciliation store and v1 import path (#1202)

Status: DRAFT. Reviewed 2026-10-29: tables go in the EXISTING results DB (not a separate file); the Phase B binding record is owned by XIHeadless; Phase A approved and implemented (offline_receipt_store.py). Reject-audit table dropped for simplicity. No code is part of this document. Nothing here is approved or implemented.
Scope: connect `OfflineEvidenceLedger` (PR #1399) to durable storage and to the v1 importer.
Gate (#1197): no live wiring, and no dependence on the unapproved `xi-test-execution/1.0.0-draft.1` contract
beyond synthetic fixtures, until shared contract review and supervised XIHeadless #47 acceptance.

## 1. Where things stand

| Piece | Today |
|---|---|
| `offline_evidence_reconciliation.py` | Pure, in-memory, per-session. Classifies receipts (FIRST_SEEN, PARTIAL_UPDATED, PARTIAL_TO_TERMINAL, NO_CHANGE) or blocks them. `durable: False`, `v1_import_eligible: False`, verdict always `UNKNOWN`. |
| `importer.py` + `results.py` | Trusted local importer. Report schema v1, rows keyed `(run_id, case_id, stage)`, verdicts PASS/FAIL/BLOCKED/SKIPPED/UNKNOWN, one SQLite transaction per report, append-only, no public write route. |
| `run_outcome.py` | Read-only description of stored results; never issues a verdict. |

The two sides share no identity: ledger keys are `(run_id, execution_id, attempt)`; v1 keys are
`(run_id, case_id, stage)`. A receipt has no `case_id`/`stage`/commit SHAs, so it cannot be turned into a v1 row by field copying.
That gap is the real design problem.

## 2. Principles (carried over, not new)

1. The reconciliation core stays pure. Persistence wraps it; it does not get a DB handle.
2. Receipts are never authoritative. `source_authenticated` and `oracle_approved` stay False in this phase, so the verdict stays UNKNOWN.
3. Nothing is inferred. Missing data stays absent or UNKNOWN. Cancelled, failed or interrupted never becomes PASS.
4. Append-only. Corrections are new rows, never updates of old evidence.
5. No new write route, no network, no packets, no executor duplication.

## 3. Proposed layers

```
receipt(s) -> [validate + reconcile: existing pure core]
           -> [ReceiptStore: durable, append-only, own SQLite file]   (Phase A)
           -> [promotion gate: explicit, operator-run]                (Phase B, blocked)
           -> [v1 importer: existing validate_report/import_report]
```

### Phase A: durable receipt store (buildable offline)

New module `offline_receipt_store.py` and a separate SQLite file (default next to the feature-testing DB, path required to be absolute, same rule as the importer). It is deliberately NOT the `feature_test_results` table: that table means "imported evidence a human can read as a result", and a receipt is not that.

Tables:

- `offline_receipts`: `receipt_id` (PK), `run_id`, `execution_id`, `attempt`, `phase` (PARTIAL/TERMINAL), `operation_state`, `evidence_sha256`, `receipt_json` (canonical), `ingested_at`, `outcome` (the ledger classification at ingest).
  - UNIQUE `(run_id, execution_id, attempt, receipt_id)`.
  - UNIQUE `(run_id, execution_id, attempt)` WHERE `phase='TERMINAL'`, so a second terminal for an attempt cannot exist at the DB level (backs TERMINAL_IMMUTABLE).
  - UNIQUE `(evidence_sha256)` is NOT enforced; the ledger rule DUPLICATE_DIGEST_DIFFERENT_RECEIPT stays in code, because a SQL constraint cannot express "same digest, different receipt id within one attempt".
- `offline_receipt_blocks`: rejected receipts (reason code, digest, truncated reason, time). Optional, so rejects are auditable. Never stores the rejected body beyond its digest and size, to avoid persisting untrusted payloads.
- `schema_meta`: single row holding the store format version (`toolkit-offline-receipt-store/1`).

Behaviour:

- `ingest_many` loads existing rows for the affected attempts into a fresh `OfflineEvidenceLedger`, runs the existing atomic classification, and writes only when the whole batch is accepted, inside one `BEGIN IMMEDIATE` transaction. Same all-or-nothing contract as today.
- Replay of an identical receipt is NO_CHANGE and writes nothing (idempotent across processes and restarts, which is the missing property).
- Process restart reproduces the same snapshot: the ledger is rebuilt from rows, not trusted from a cache.
- Tamper check on read: recompute each stored digest; a mismatch surfaces as a store-integrity error and refuses to build a snapshot, rather than silently reconciling bad data.
- `snapshot` keeps `v1_import_eligible: False` and verdict UNKNOWN. Only `durable` flips to True.

Tests (synthetic, tmp_path only): replay across a reopen; conflict across a reopen; partial then terminal across a reopen; second terminal rejected at DB level even if the Python check is bypassed; atomic batch rollback leaves no rows; integrity failure on edited row; no writes to `feature_test_results`; the existing 17 ledger tests remain unchanged and green.

### Phase B: promotion to v1 (design only, blocked on #47 / contract approval)

A receipt can never be promoted by the store itself. Promotion is a separate, explicit, operator-invoked step that produces a normal v1 report file, which then goes through the unchanged `validate_report` and `import_report`. This keeps one door into `feature_test_results`.

Mapping rules (proposed):

| Receipt state | v1 result |
|---|---|
| Any non-authenticated receipt (this phase: all) | none. Not promoted. Remains UNKNOWN in the receipt store. |
| TERMINAL completed, source authenticated AND oracle approved | eligible: v1 row whose verdict comes from the oracle's assertions, never from the receipt state. |
| TERMINAL failed | v1 `BLOCKED` with `reason_class` `ENVIRONMENT` or `OTHER`, never `FAIL` (a failed operation is not a failed behaviour check). |
| TERMINAL cancelled / interrupted | v1 `UNKNOWN`, never `PASS`. |
| PARTIAL only | none. |

Missing for a v1 row, which receipts do not carry: `case_id`, `feature_id`, `stage`, the three commit SHAs, `observed_at`. These must come from an operator-supplied or runner-supplied binding record, validated against the catalog; they are not guessed. This binding record is the main open design item (see section 5).

Safety properties to preserve: PASS still requires `assertions` and `observations` in evidence; `import_context` stays importer-only; `reason_class` stays optional and validated; the importer's duplicate-identity rule `(run_id, case_id, stage)` continues to apply, so promoting the same attempt twice is rejected rather than duplicated.

## 4. Compatibility with the XIHeadless draft contract

- Phase A depends only on the Toolkit's own `toolkit-offline-receipt/1` format, which the #1487 mirrored fixtures already exercise. No dependence on live XIHeadless behaviour.
- Fixtures stay `synthetic: true` and are not valid direct v1 reports; the store must refuse to treat them as authenticated.
- If the draft contract changes, only the receipt validator changes; the store keeps the canonical receipt bytes, so older rows stay verifiable under the old format version.

## 5. Open questions for review

1. Store location and lifecycle: separate SQLite file (proposed) vs extra tables in the existing results DB. Separate keeps "evidence" and "receipts" from being confused; costs one more file to back up.
2. Retention: keep rejects as digest-only rows (proposed), or not record them at all?
3. Binding record for Phase B (`case_id`/`feature_id`/`stage`/SHAs): who produces it, and in what file? Probably XIHeadless, so this needs the shared contract review. I do not want to define it unilaterally.
4. Is a failed operation always BLOCKED, or can some failures legitimately be FAIL once an oracle exists? Proposed answer: BLOCKED until the oracle contract says otherwise.
5. Should Phase B be an offline CLI only, or ever an HTTP route? Proposed: CLI only, consistent with "no public write route".
6. Do you want Phase A built now (it is fully offline and independent of #47), with Phase B left as this document only?

## 6. Proposed sequencing

1. Review this document (you).
2. Phase A as one PR: store + tests, no change to the importer, ledger or routes.
3. Phase B stays a design until XIHeadless #47 is accepted and the binding record is agreed.

Not in scope: live ingestion, XIHeadless calls, authentication of receipts, any change to verdict semantics.
