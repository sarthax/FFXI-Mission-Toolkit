# Chocobo Raising domain: DSP audit handoff

Route: `/domains/chocobo_raising` (Domain index), tracker: [issue #1129](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1129).

## Evidence model

The tracker distinguishes **upstream** code coverage from **DSP** compatibility; all ten DSP statuses initially remain `unknown`. The Domain framework's glob-based "present" signals file existence only, not gameplay readiness.

Use `scripts/import_chocobo_audit.py` to import **reviewed** findings, not synthetic probe results. It accepts one JSON report, bound to the actual DSP checkout commit, with findings matching existing subsystem names. Status values: `unknown`, `present`, `partial`, `missing`, `validated`. Validation requires a reference prefixed `test:`, `runtime:`, or `capture:`, but **a prefix is not itself proof**: a reviewer must inspect the artifact and ensure it corresponds to the pinned DSP commit and client build.

### Example report (illustrative, not a DSP audit result)

```json
{
  "target_commit": "0123456789abcdef",
  "findings": [{
    "name": "Eggs and inventory exdata",
    "dsp": "unknown",
    "evidence": ["source:src/map/items/exdata/chocobo_egg.h:12"],
    "note": "Example only; not verified against live DSP."
  }]
}
```

```sh
python scripts/import_chocobo_audit.py audit.json --check
python scripts/import_chocobo_audit.py audit.json --apply
pytest test_fixtures/test_chocobo_domain_import.py
```

The importer modifies only the tracker JSON on the local development branch. Do not import onto `main` without review. Preserve pre-existing local changes.

## Local agent instructions

Use the actual DSP/Valhalla server checkout, not `xiheadless-dsp` (which is a headless client) and not an older fork. Log `git remote -v`, `git rev-parse HEAD`, `git status --short`, and client build identifier. Audit schema/migrations, `getChocoboRaisingInfo` equivalents, item exdata, NPC event start/update/finish, trade, personal mount flag and appearance, and racing packet capability; record exact path/line for each claim. Attach packet captures and runnable test command/output separately. Compare against the pinned LSB reference. Label unsupported behavior `unknown` or `partial`, never `validated` based on file presence.

The importer does **not** run server tests or automatically discover DSP source. Use the existing headless client only for controlled tests after the source audit. Maintain no-write guarantees to live DSP and database.

## Read-only local source inventory (first step)

The inventory collector only reads the DSP source and writes a candidate report **outside** its checkout. It records the Git commit, dirty state, optional origin, and matching path names; all ten subsystem DSP statuses remain `unknown`. It cannot demonstrate that a missing glob means missing functionality or that existing source is compatible with the retail client.

```powershell
python scripts/inventory_chocobo_dsp.py "D:\\path\\to\\actual-DSP-checkout" --output "D:\\temp\\chocobo-dsp-inventory.json"
python scripts/import_chocobo_audit.py "D:\\temp\\chocobo-dsp-inventory.json" --check
```

The second command is a **preview**, not approval. Review the inventory with a human or local agent and add exact references to relevant code paths, packet traces and runtime results before promotion. Once verified, run `--apply` on a feature branch and inspect its diff. Do not run `--apply` on mere source inventories to claim validation.

## Live test status (2026-10-25)

Live headless scenarios run from `tests/live/chocobo_raising/run_live.py` and are logged in `docs/workbench/chocobo_audit/TEST_SCENARIOS.json` (P1-DAY-PROGRESSION, P1-FEEDING, P1-CARE-PLAN, P1-TRAINER-MENU, P2-RETIREMENT, P2-CHOCOCARD) and in the staged `data/testing/domain_drafts/chocobo_raising.json` (CHO-D1..P1).

- Usage: set `TRAINER` (pulonono, hantileon, zopago) and `ACCOUNT` (xitest03..08), then run the scenario name (day_report [days], retirement, chococard, feed, menu, careplan).
- All scenarios pass on all three trainers; day_report 6/65/130 only on Pulonono.
- The canonical `data/testing/test_specifications.json` is untouched: the staged draft is blocked on schema-owner review (#1259).
