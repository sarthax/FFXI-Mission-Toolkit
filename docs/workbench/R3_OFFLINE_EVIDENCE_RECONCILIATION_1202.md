# R3 #1202 — Offline evidence reconciliation (bounded implementation slice)

**Status:** GitHub-only, untrusted synthetic fixture adapter, **NOT** the XIHeadless #105 protocol; not a live importer, not a durable evidence index, not a new authorization or normative result oracle. This change adds two standalone files plus its test workflow and this explanatory document. Existing `feature_testing.importer.import_report`, `results.py`, v1 SQLite schema, existing API/routes, GUI, published specs and observed records remain untouched.

## Why this slice exists

Existing Toolkit import accepts only `{"schema_version":1,"results":[...]}`, with 10 exact row fields, known catalog case, UTC timestamp, 40-character Git SHAs and the v1 verdict enum `PASS|FAIL|BLOCKED|SKIPPED`. `UNKNOWN` is **not** representable in v1; its insert-only primary key is `(run_id,case_id,stage)` and repeat import currently raises SQLite IntegrityError. Do **not** change this established behavior to claim #1202 is fully released.

XIHeadless [#105](https://github.com/sarthax/xiheadless-dsp/issues/105) remains an **unapproved draft**. Its proposed request, execution, attempt, supervised task operation, per-action operation IDs, digest/manifest versions and oracle authority require owner decision. The offline receipt shape below is a **Toolkit-local fixture/adapter contract**, not a competing #105 wire version or compatibility certification. No transport conversion or operator token is implemented.

## Internal synthetic fixture shape

`format: "toolkit-offline-receipt/1"` has bounded `run_id`, `execution_id`, positive `attempt`, `operation_id`, immutable `receipt_id`, `feature_id`, `case_id`, `definition_revision`, separate `phase` (`PARTIAL|TERMINAL`) and `operation_state` (`accepted|running|completed|failed|cancelled|interrupted`). It has `evidence_complete` boolean, `reported_verdict` producer claim, `missing_artifacts[]`, `provenance` with original opaque reference and **source_authenticated=false, oracle_approved=false**, a bounded JSON `evidence` object and `evidence_digest`. Digest is lower-case SHA-256 of locally canonicalized **submitted JSON**; matching it only checks internal integrity, **not physical artifact bytes, Headless producer authenticity, or valid gameplay**. Original receipts are retained as independent deep copies.

`OfflineEvidenceLedger` has only in-memory, per-process state. `ingest`, `ingest_many` and `snapshot` perform **no database, filesystem, network, Headless, GM, client or execution actions**. An exact immutable receipt replay yields `NO_CHANGE`, an original record yields `FIRST_SEEN`, subsequent distinct partial `PARTIAL_UPDATED`, and separate terminal evidence after partial `PARTIAL_TO_TERMINAL`. Exact receipt-id reuse with changed data/digest yields `BLOCKED/IDENTITY_DIGEST_CONFLICT`. Distinct terminal digests, late partial after terminal, changed attempt definition, unsupported versions/states, altered digest claims, duplicate evidence with changed receipt ID, unapproved source/oracle authority and malformed JSON all fail closed; an `ingest_many` batch is atomic in memory. Terminal receipt does not erase partial receipts. Two operation IDs under one run/execution/attempt remain distinct.

**Important:** `phase=TERMINAL` only records a terminal lifecycle receipt. `evidence_complete=true` is still an unverified producer claim. Even a reported `PASS` and completed task results in `authoritative_gameplay_verdict=UNKNOWN`, `v1_import_eligible=false`. Cancelled, interrupted, failed or terminal-incomplete receipts never become PASS because of absent artifacts, missing cleanup or status alone. Reconciled snapshots retain producer-reported verdict, missing-artifact references and original provenance without granting independent authority.

## Scoped CI / acceptance

`.github/workflows/r3-offline-evidence-reconciliation.yml` runs new synthetic partial/replay/conflict/atomicity/version tests **together with the unchanged existing `test_feature_testing_importer.py`** to verify the old v1 duplicate rejection and valid v1 import remain exactly as before. No tests depend on live source bytes, DSP schema, packet tools or Headless operation sessions.

**Deliberate blockers to a real release:**

1. **No durable idempotency or cross-process restart.** The in-memory ledger is an offline regression primitive; it does not satisfy atomic durable SQLite/Persisted DB attempts, migrations, retention, storage collision recovery or multiwriter locks. Do not use in production or claim the full story's durable import acceptance.
2. **No #105/#110 agreed wire/identity contract.** All field IDs/format here are isolated synthetic fixtures; sign off run, execution, task-operation, action-operation, positive attempt and stable receipt identity, digest/version semantics before any conversion or transport ingestion.
3. **No #1198 oracle/authority approval.** No real observed PASS/FAIL authentication, no untrusted Headless result coercion, no guessed 40-character DSP/Toolkit/Headless SHA, no v1 projection.
4. **No authorized local import acceptance.** Owner/local agent must later demonstrate an approved and sanitized supervised XIHeadless evidence bundle under #47/#49/#55/#105/#110/#111/#112 with independent client/server/source/cleanup evidence, durable receipt persistence, replay/id-conflict rejection across restarts and actual v1 compatibility. Without those gates report `BLOCKED/NOT_RUN`.

**Next owner:** Toolkit #1202 implementation owner retains this branch for review fixes. Upstream #105 owners decide protocol identities; Toolkit #1198 signs oracle provenance; independent reviewer checks exact new HEAD CI; local operator validates the future persisted version. Never merge this as an approved live importer or enable gameplay/production without additional owner authorization.
