# R7 release baseline and acceptance-gap ledger — 2026-10-21

**Parent:** [Toolkit #1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197)  
**Verified integrated Git baseline:** `main@972ff6fa4337cb5d29a3c8c3eb68c73245f24bb9` (merge of #1291; all nine R6 staged domains integrated).  
**Mode:** remote/GitHub-only read-only assessment. **This is not a gameplay acceptance report.**

## R6 merged deliverables (source-level / offline)

- Canonical optional Contract v2 foundation (#1285) retains outer schema v1 compatibility and UNKNOWN/unapproved oracles; no automatic dispatch grants.
- Unified Scenario Developer (#1283), Coverage Matrix, Evidence Reviewer and Evidence Readiness (#1287) support manual source-backed authoring, evidence review and diagnostics; source-row EXACT is not independently authenticated client/DSP identity.
- One authoritative offline readiness **matrix** (#1292): `SCENARIO_DOMAIN_READINESS_MATRIX_2026-10-21.json`; one distinct observation **capability backlog** (#1293); original staged domain validator (#1294).
- **Nine merged design-only domain drafts**: Gardening 9 (#1277), Voidwalker 7 (#1279), Assault/Nyzul 6 (#1280), Missions/Quests 5 (#1281), Moghancement 14 (#1282), Voidwatch 8 (#1286), Salvage 7 (#1289), RUN/GEO 8 (#1290), Chocobo Raising 9 (#1291).
- **73 unique staged case IDs:** **5 observe-now, 2 needs-readback, 57 needs-mutation, 9 needs-deploy**. Conditional observe-now: `MOG-09`, `RG-01`, `RG-06`, `VOID-01`, `VOID-02`. Every staged case remains `execution_status=design_only`, `runner=unassigned`, `verdict=NOT_RUN`; staged cases were not promoted to `data/testing/test_specifications.json`. The historical narrow runnable `MOG-09` and `INV-OBS-01` remain separate canonical v1 definitions, not newly authorized staged tests.

## CI correction and reproducible offline verification

The pre-merge validator fetched `refs/heads/spec/*`; those branches were automatically deleted after merge, so it cannot be the main release gate. [Draft PR #1305](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1305) adds explicit, mutually exclusive modes to `.github/workflows/r6-domain-specification-validation.yml`:

1. **`integrated-main` (default for pull requests and scoped pushes to main; also workflow_dispatch)**: check out full Git history, read nine checked-in `data/testing/domain_drafts/*.json` and the single matrix **from the same checked-out tree**, verify exact integrated JSON bytes match the matrix's original merged PR commit blobs and that each PR head is an ancestor of checked-out HEAD; run all old 73-case structural/source/UNKNOWN/non-promotion gates and negative fixtures. No remote `spec/*` lookup or silent branch fallback.
2. **`staged-pr` (explicit workflow_dispatch only)**: fetch only the manifest's `refs/pull/<number>/head` JSON, record observed head SHAs, and fail closed if they differ from the reviewed matrix pins or cases. This is for a **future reviewed staging snapshot**; it does not silently substitute merged-main data.

The exact workflow validation command after #1305 lands is:

```shell
python -m pytest -q test_fixtures/test_domain_draft_validator.py
python tools/validate_domain_drafts.py \
  --mode integrated-main \
  --snapshot-root data/testing/domain_drafts \
  --manifest test_fixtures/r6_domain_validation_manifest.synthetic.json \
  --catalog data/testing/test_specifications.json \
  --matrix docs/workbench/SCENARIO_DOMAIN_READINESS_MATRIX_2026-10-21.json \
  --repo-root .
```

**Important:** source file:line links, repository commit SHA and historical blob integrity verify *claimed source snapshot continuity*, not DSP source-byte authenticity, installed deployment, runtime config or gameplay truth. No GitHub CI verdict here establishes a client/server-observed game PASS.

## R7 active development ownership and boundaries

| Owner | Approved domain boundary | Tracking | Coordination |
|---|---|---|---|
| Agent A | CI, roadmap, baseline, read-only integration trace; no executor changes | #1197, draft #1305 | Validate first; no merge without owner/independent review |
| Agent B | Guided/Advanced Scenario Developer UI, per-step provenance and readiness presentation, editor models | #1302, #1261 | **Consumes** canonical optional Contract v2; does not modify its validator/schema |
| Agent C | Canonical Contract v2 validator, source-to-step attribution and compatibility/adapters | #1259, #1302 | Schema authority; communicate agreed field model to B and D before changing shapes |
| Agent D | Offline Evidence Reviewer, readiness-to-authoring projection, immutable source/review provenance | #1262, #1198, #1202 | Does not rewrite B's editor, C's canonical schema, or packet decoder |
| Agent E | Bounded read-only observation contracts and future allowlisted adapters; staged domain requirements | #1295–#1300 | No free-form SQL, privilege escalation, unsupported gameplay readbacks or local XIHeadless assignments |

**Change coupling:** C establishes a reviewed field-level contract; D publishes its read-only projection; B consumes both through the editor. E independently implements bounded readback contracts and keeps capability UNKNOWN until independently observed. Cross-owned files require issue/PR coordination and owner acknowledgment before shared edits. Avoid overlapping modifications in `scenario_contract_v2*.py`, `scenario_developer.js`, `scenario_guided_model.js`, `scenario_review_offline.py`, `scenario_readiness_summary.py` and supervisor DB readback modules.

## Acceptance gaps deliberately OPEN (not resolved by R6 merges)

- [ ] Current installed DSP revision/config/schema and source-content digest independently attested, including deployment/rollback readiness for Chocobo.
- [ ] Original capture file bytes, parser/decoder version and source digests independently compared with indexed projections; source-record IDs cross-checked against actual client/DSP identities.
- [ ] Independent client and authoritative server observations for each expected outcome; fixed-query readbacks and record completeness, especially inventory/furnishings #1295 and quest/job/currency #1296.
- [ ] Active instance/claim/pyxis/status/effect readbacks (#1297–#1300); unknown or unavailable data must not be mislabeled FAIL/PASS.
- [ ] Source-backed candidates reviewed into normative oracles and explicit permissions, without automatic schema/policy promotion (#1198/#1259).
- [ ] End-to-end supervised run/import/idempotency/cancellation and verified cleanup evidence with operator authorization (#1197/#1202); do not treat offline GitHub CI as local gameplay execution.
- [ ] Operator browser, authenticated GUI and source-to-step review acceptance; no local tests performed by this GitHub-only coordinator.

## Release / workflow controls

- All work on separate PRs; do not force push, reuse deleted staging branch refs, merge without **explicit repo-owner authorization**, or treat self-authored COMMENTED reviews as independent APPROVED.
- Mark a narrow issue complete only when its *full listed acceptance* is evidenced, not merely because a design-only PR was merged. Keep #1197, #1198, #1202, #1259, #1261, #1262 and #1295–#1300 open until their own runtime/coverage/implementation gates are satisfied.
- The old R6 branch-source fix #1304 is closed; retain its history, but supersede the branch-fetch assumption with integrated-main CI after this draft is independently reviewed and merged. Branch deletion is a separate authorized hygiene operation, not part of this PR.
- No local XIHeadless-DSP agent work is assigned from this coordination plan.

## Historical release-foundation validation checkpoint (2026-10-21)

The original R6 integration baseline was `972ff6fa4337cb5d29a3c8c3eb68c73245f24bb9`, while the later R7 foundation checkpoint `db8b06abab7cd5f7b0908109184453b30ae3b112` included merged #1305/#1306/#1309/#1308. Integrated-main CI [run #39684273477](https://github.com/sarthax/FFXI-Mission-Toolkit/actions/runs/39684273477) passed on main push at merge commit `986f781ed1fe61000b2ca62552018061441b7522`, running 41 synthetic checks across 73 design-only cases. These immutable historical hashes are **not** current main or independently attested deployed source; no gameplay acceptance is claimed. See current roadmap for the newer R7/R8 release status.
