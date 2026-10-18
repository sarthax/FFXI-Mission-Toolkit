# RUN / GEO domain — operator guide

The **Rune Fencer & Geomancer** domain records a bounded comparison of the user's DSP-Valhalla source against an LSB reference snapshot. The user has confirmed RUN and GEO were added to the server; **a toolkit gap is not proof that a job is missing or broken on the running server**.

## Workflow
1. Open Domains → Rune Fencer & Geomancer; use area and status filters to locate a finding.
2. Inspect its evidence tag and source paths before changing its review status.
3. Set a finding's **status** (missing, partial, done, hold) and **note** with the supporting source or test. The tracker persists these fields to `data/run_geo/gaps.json`.
4. Check both the active DSP checkout and a current LSB reference before proposing implementation. Verify job stat grades, unlock quests, ability effects, gear eligibility, weapons and scroll obtainability independently.
5. Record the live server build, client resources, test character and observed behavior when declaring runtime acceptance.

## Status boundaries
- `done` is a **reviewer-maintained status**, not an automatic server validation.
- The tracker is not a live job loader or GM enablement switch.
- IDs, script names and mechanics can drift between DSP and LSB; do not transplant reference data without explicit comparison.
- The included gap list is a development inventory. Fresh audits can add or supersede findings.

Related: `docs/workbench/ROADMAP_CURRENT.md` and `docs/workbench/ROADMAP_HELP_SYNC_AUDIT_2026-10-17.md`.
