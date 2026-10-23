# #1333 — Scenario validation field feedback and operator token boundary

**Mode:** GitHub-only, non-executing canonical error UX. Applies to the Guided Scenario Developer `POST /scenario-developer/validate`. Canonical v1/v2 validation is unchanged; this slice **does not** relax length, required list, step, source or permission constraints. No auto-fix or data normalization.

On a rejected draft, the server retains HTTP 422 and the existing canonical error text as `canonical_error`, adding a bounded list of `{field,control_id,message,required}` **advisory** diagnostics. It checks purpose/rationale if included, Given/When/Then required statements and authoring structure/state/review. Multiple independent problems are listed even when the canonical validator rejects the first one. For unrelated errors, the summary points operators to Advanced JSON, never claims to replace canonical validation. Unknown fields, unauthorized runner and Contract v2 errors still fail.

The editor displays a text-only accessible error summary, `aria-invalid` on known fields and required markers for Guided inputs; **values are not rewritten, drafts are not discarded and validations do not save or execute**. Authoring metadata must be repaired explicitly in Advanced JSON when not exposed in Guided controls; no hidden fix. Save's preflight uses the same diagnostics, preserving its revision/conflict and dirty guards. Agent B's Advanced JSON and new/fork lifecycle PRs remain separate and require conflict-aware reconciliation.

## Operator token, separate from validation

`/scenario-developer/validate` is local same-origin, non-executing and does **not** require the draft-save token. Saving to `/feature-testing/builder/drafts` uses the existing `X-Test-Operator-Token` against `MISSION_TOOLKIT_TEST_OPERATOR_TOKEN` configured in the **local Toolkit process environment**. An accepted configured secret must be at least **32 characters** and match exactly; the local operator should check their private environment/configuration and ensure they are using the same Toolkit instance and sandbox. Do **not** paste it in issues, screenshots, browser logs or CI fixtures; use synthetic values for offline tests.

**Security policy:** Missing configuration, too-short configured token and incorrect presented token all receive the same generic denied response from the existing authentication handler. This deliberately prevents probing whether a secret is configured or correct. No auth endpoint, verbose credential error, token echo, bypass, user enumeration or new privileged connection is introduced. Agent D retains supervisor config/sandbox isolation and security ownership under #1333; this documentation does not authorize shared `%LOCALAPPDATA%` settings in a test sandbox. R7 observation endpoints use a separate `MISSION_TOOLKIT_SUPERVISOR_TOKEN` and are not changed here.

## Future local acceptance (not executed)

Verify errors for simultaneous empty purpose, empty Given and malformed authoring; required and field markers; Guided/Advanced input preservation, no Save or validation side effects, safe text rendering with HTML-like strings, save revision-conflict unchanged, no B20 capture viewer regression, narrow viewport and keyboard screen reader. Test missing/malformed/wrong operator token locally without logging credential bytes. Validate the isolated sandbox does not inherit production readiness; that defect is Agent D's separate fix and must not be treated as resolved by this PR.

Synthetic CI exercises canonical rejection, independent error enumeration, 422 error shape, no mutation or SQL, and fake-DOM focus-independent marker cleanup. Green CI is not browser-local or live DSP acceptance.
