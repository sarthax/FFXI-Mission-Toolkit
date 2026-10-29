# Voidwalker domain — operator guide

Voidwalker (the earlier abyssite/NM system) is **not Voidwatch**. The domain's source-backed views cover zone/position groups, colored abyssite tiers, NM names and spawn IDs, progression paths and an Abyssea branch.

## Workflow
1. Open Domains → Voidwalker. Pick a zone and use the NM/tier filters to narrow the list.
2. Select a node in the progression/path graph to inspect the associated NM and abyssite relationship.
3. Check spawn positions, corresponding mob scripts, special skills, drops, and upgrade logic against the **selected DSP source checkout**.
4. Use available GM diagnostic commands only on an authorized test server. Confirm expected zone/instance and permissions first.
5. Record per-area validation (pop, hint, fight, model/name/skills, drops, upgrade) as observed, with exact client/server versions and evidence.

## Validation coverage and test queue

The Voidwalker page now shows aggregate **untested** and **recorded issue** counts across the six per-NM checks (pop, hint, fight, model, drops, upgrade) and a bounded list of NMs that still need evidence. This is derived from existing `data/voidwalker/validation.json` results; nothing is auto-marked successful, and a missing record remains untested. Prioritize recorded issues, then the most untested checks, and enter observations in the existing per-NM validation controls. The queue describes **currently parsed DSP source NMs** only: it does not establish full overworld/Abyssea implementation coverage when source files or the source root are unavailable.

## Important status boundaries
- Domain metadata dated October 16 describes the Voidwalker implementation on a **separate DSP feature branch**, not a verified merge into the DSP server's mainline. Toolkit UI completion does not establish server deployment.
- The source parser currently has a Windows-specific fallback root (`<local DSP checkout>`); missing local sources may cause incomplete views. Confirm which root the running workbench uses.
- Colored abyssite IDs, NM skills and paths must be checked against the actual DSP checkout and client build. Source/SQL existence is not runtime proof.
- An overworld live test does not validate every zone, NM or the Abyssea branch. Distinguish untested from confirmed failures.

Related: `src/workbench/domains/definitions.d/voidwalker.json`, `data/voidwalker/validation.json`, `docs/workbench/ROADMAP_CURRENT.md`.
