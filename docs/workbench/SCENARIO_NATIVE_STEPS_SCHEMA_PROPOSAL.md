# Saved typed steps — draft schema proposal (#1411)

**Status: APPROVED by the owner on 2026-10-28 (all six recommendations accepted) and IMPLEMENTED. This document is kept as
the design record; the "Outcome" section at the end says what shipped and where it differs from the proposal.**

## Why
The owner direction (2026-10-28) is that the Toolkit owns the whole path: author a scenario, publish it, run it
through XIHeadless, and review results (the "Scenario Test Hub" mockups: Create, Drafts, Test Catalog, Preflight &
Run, Run Results). Today the typed step builder (#1447, #1448, #1449) keeps its steps only in the browser; they can
be exported or imported as native Headless JSON but are not saved with a draft. Saving them is the first schema
change on that path.

## What exists, and the constraints it puts on the change
- Drafts are rows in `test_spec_drafts` (revisioned; a save needs the expected revision). Each draft is the whole
  specification as JSON, **capped at 32,768 bytes**, and must stay `design_only` with `runner: unassigned`.
- `validate_spec` rejects any top-level field it does not know, and any unknown field inside a step.
- Canonical `steps` must cite Toolkit readbacks (`client_bag`, `db_bag`, ...). Typed steps are Headless actions and
  checks (`zone`, `hpp`, `event_active`, ...), so they cannot be stored as canonical steps; they are a parallel list.
- `base_spec_sha256` hashes every field except `contract_v2`. A new top-level field would change the hash and make
  any draft with recorded v2 fingerprints report `base specification SHA-256 mismatch` after a step is added.
- A typical native step is about 111 bytes; 50 steps add roughly 6 KB to a draft.

## Proposed field
One optional top-level field, `native_steps`, on the draft/specification:

```json
"native_steps": {
  "library_version": 1,
  "steps": [
    {"name": "talk to guide", "do": {"talk_npc": 17719298}, "expect": {"event_active": true},
     "note": "npc_id from DSP catalog sql/npc_list.sql; not verified for this zone or client"}
  ]
}
```

- `library_version` ties the steps to the typed action library they were validated against (today: `1`), so a later
  library can re-check older drafts instead of guessing.
- `steps`: 1 to **50** entries. `name` is 1 to 100 characters and unique within the list. `do` and `expect`
  each hold exactly one native key and value (see Decision 1 for whether a step may have only one side). `note` is
  optional, at most 300 characters, and is where catalog or import provenance goes. No other fields are allowed;
  nothing is trimmed or ignored on save.
- **Validation on save** reuses the typed action library (`review_native_steps`): every step must be `SUPPORTED`, so
  no malformed or unreviewed step is ever stored. The whole draft must still fit in 32,768 bytes, be `design_only`
  with an unassigned runner, and the field never makes a draft executable or publishable.
- **Hash:** `native_steps` is excluded from `base_spec_sha256` (the same way `contract_v2` is). Existing drafts
  contain no such field, so none of their hashes change.
- **Compatibility:** no migration. Existing drafts are unaffected. A draft that uses the field cannot be opened by
  an older checkout (its validator would reject the field).
- **Editor:** the builder loads `native_steps` when a draft is opened and writes it back on save; the unsaved-work
  guard treats it as part of the draft; the Advanced JSON view shows it; fork and clone copy it. No other canonical
  field changes. (Shared editor files change in the editor PR.)
- **Relationship to the narrative:** `behavior.given/when/then` and `preconditions` stay human text and carry steps
  that are manual or not yet automatable (the mockup's "unsupported step" case). `native_steps` is only the automatable
  subset. The UI can label a step Given/When/Then/And from its shape, so no phase is stored.

## Decisions needed (recommendation first)
1. **Step model: fixed pairs, or independent actions and checks?** The mockups have separate "Add Action Step"
   and "Add Check Step" buttons, and the existing importer (#1410) already treats `do` and `expect` as each
   optional in a native step. The library models 10 actions and 8 checks separately but only offers the 10 reviewed
   pairs. *Recommend independent:* a step may be action-only, check-only, or both, with the 10 pairs kept as suggested
   shortcuts. Caveats: that allows 80 action/check combinations of which only 10 were reviewed as pairs (each action
   and check shape is individually reviewed, so the validation is unchanged), and whether the runner accepts
   single-sided steps is not verified here.
2. **Hash:** exclude `native_steps` from `base_spec_sha256`. *Recommend exclude* (simple, consistent with
   `contract_v2`); including it would block a draft's v2 fingerprint check on every step edit until re-pinned.
3. **Provenance:** store a short `note` per step. *Recommend yes* (it is how a reviewer sees where an ID came from).
4. **Unsupported or manual steps:** not stored in `native_steps`; they stay in the narrative. *Recommend confirm.*
5. **Library version stamp:** include `library_version`. *Recommend yes.*
6. **Confirm** drafts stay design-only and that `native_steps` never makes a draft executable; running remains the
   separate publish, preflight and run path.

## Not covered here
Publish, preflight (environment, account lease, roles, oracle coverage), the supervised run, and results binding
(#1412, #1255). The mockups also show checks the reviewed native vocabulary does not contain (a dialog menu option
being visible, a specific dialog event, character and zone setup). Those need Headless support and a reviewed library
extension first; they are library work, not part of this schema change.

## Proposed order of work
1. Validator, hash exclusion and tests (`native_steps` accepted, bounded, strict; old drafts unchanged).
2. Library step model (only if Decision 1 is "independent"): action-only and check-only templates, review and import
   updated, with parity tests.
3. Editor wiring: open, save, guard, fork and clone, Advanced JSON, with real-browser checks.

## Outcome (2026-10-28)
All six recommendations were accepted and built, in this order:

| Step | Delivered by |
|---|---|
| Validator (`validate_native_steps`), hash exclusion, independent action-only / check-only steps | #1452 |
| Editor wiring: open, save, unsaved-work guard, fork, clone, new, Advanced JSON | #1453 |
| Add Action Step / Add Check Step in the builder | #1454 |
| Given / When / Then preview | #1455 |
| Local verification against a real DSP checkout and XiHeadless loaders (evidence only) | #1456 |
| Builder truly read-only while Advanced JSON is open (found by the local verification) | #1460 |
| Export writes `"expect": {}` for action-only steps; observed execution paths per key | #1461 |

Where reality differs from, or adds to, the proposal:
- **Decision 1 (independent steps):** accepted. The local verification found XiHeadless `CheckStructure` rejects an
  action-only step unless `expect` is an object, so the **export** form writes `"expect": {}`; the **saved** draft stays
  one-sided and the validator still refuses a stored empty `expect`. Import reads that export form back as action-only.
- **Decision 3 (provenance `note`):** the validator accepts a stored `note`, but the builder does not write one: catalog
  provenance ("Source: ...") is shown in the session only and is not saved with the draft. A step with a `note` made in
  Advanced JSON is preserved byte for byte and shown as "cannot show", never rewritten.
- **Execution:** nothing here makes a draft executable. At XiHeadless `e5e8035071` the file loader accepted all 18 native
  keys, but the MCP task path accepted only `wait_ms` (#1459 tracks the rest), and whether the runner executes accepted
  steps is untested (the controlled run was NOT_RUN: no authorized operator). Each key now carries `observed_paths` that say so.
- **Not covered, still open:** publish, preflight and the supervised run (#1412, #1255); library work for the mockups'
  checks that the reviewed vocabulary lacks; saving provenance notes.
