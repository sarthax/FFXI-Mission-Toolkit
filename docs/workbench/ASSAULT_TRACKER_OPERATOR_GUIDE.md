# Assault Development Tracker — operator guide

The tracker imports the **Topaz release Assault issue inventory** and associated fix-log source and compares those records to development/validation status for DSP. Preserve original comments and source lineage when reviewing each item.

## Workflow
1. Open Domains → Assault Development Tracker. Use the zone/instance mission grid or search/filter to select the Assault by number and name.
2. Inspect the imported original issue text and fix-log cross-reference before deciding whether an issue is resolved historically.
3. Record separate determinations for Topaz fix status, DSP port/implementation status, and **actual DSP test evidence**. Do not collapse them into one checkbox.
4. Use the shared/global section for dependencies such as appraisals or world systems that affect more than one Assault.
5. For acceptance, record server revision, instance entry/exit, objective triggers, entities, scripts, reward/appraisal outcomes and the exact observed result. A source fix with no test stays unvalidated.

## Source and caution
- `data/assault/Assault_Issue_Tracker_topaz_release.md`
- `data/assault/Assault_Fix_Log_topaz_release.md`
- `src/workbench/domains/assault_tracker.py`, `assault_fix_crossref.py`, `assault_readiness.py`

**Imported, fixed in Topaz, ported to DSP and validated in DSP are four distinct claims.** A matching fix-log entry alone does not certify successful porting or completion. Keep conflicting historical and runtime evidence rather than overwriting it.

Related: `docs/workbench/ROADMAP_CURRENT.md` and `docs/workbench/ROADMAP_HELP_SYNC_AUDIT_2026-10-17.md`.

## Live-test readiness safeguard (2026-10-18)

The **Ready for live test** mission filter requires explicitly validated mission implementation and DSP port reviews, a pending/not-yet-complete mission test, no known blocker, **and** explicit DSP port review (`fixed` or `not_applicable`) for every linked issue and shared dependency. An unreviewed historical Topaz issue or shared subsystem cannot silently qualify a mission for DSP testing merely because its mission-level port review is positive. This is a triage gate, not proof that an Assault works in-game. Continue using per-issue port and DSP-validation reviews to record outcomes.

## Mission next-action queue (2026-10-18)

The Mission Readiness table now derives a suggested **Next action** for each mission from recorded reviews: resolve blockers, review DSP implementation, verify the DSP port, resolve linked issue/shared-dependency port evidence, then run DSP live validation. This is triage, not proof of port completion or the result of an executed server test. Unreviewed is unknown, not broken. Topaz historical fixes never automatically advance a DSP stage. Use the existing readiness zone/status filters and open the mission detail to update the appropriate evidence-backed review.
