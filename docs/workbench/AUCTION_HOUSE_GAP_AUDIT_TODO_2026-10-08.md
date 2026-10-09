# Auction House feature-gap audit and prioritized TODO — 2026-10-08

Scope: `src/workbench/server_admin/auction_house/`, relevant feature documentation, and `ROADMAP_CURRENT.md`. Baseline: `main` at `32a4e6452a192ec465b69642a7b9611497857d10`. No application-code changes in this audit.

## Maintenance reconciliation — 2026-10-09

This file is the preserved October 8 gap-audit baseline. **Do not treat unchecked historical entries below as the live backlog.** The current authoritative status is [AUCTION_HOUSE_CAPABILITY_STATUS.md](AUCTION_HOUSE_CAPABILITY_STATUS.md) and the AH section of [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md). Core DSP management and the planned final QOL package are implemented and merged (#786, #787, #792, #795, #797, #802, #808, #812, #814, #815, #816).

AH-03/04 diagnostics now include persistent MyISAM interruption cases and recipient-level Inbox attempt journaling; AH-07 account selection is implemented. AH-08 analytics deltas exist, but real multi-day evidence still needs collection. One-time scheduled Test rewards and reusable augment configuration presets are implemented. Augmented Mog sending remains **disabled by default, DSP Test-only and not in-game pickup-verified**. Individual new Test executor acceptance, Topaz runtime parity and runnable LSB writes remain outstanding; AH is otherwise in maintenance mode.

## Completion reconciliation — current main (2026-10-08)

The initial AH-01–AH-16 checklist below is retained as an **audit baseline**, not a live unchecked task board. Use these updated statuses:

| ID | Current status | What remains |
| --- | --- | --- |
| AH-01 | Partial — overall DSP validated by operator | Optional concise per-operation DSP smoke evidence; do not downgrade successful DSP use |
| AH-02 | Updated in current roadmap/status | Refresh operator documentation when new runtime evidence appears |
| AH-03 | Partial — PR #743 merged | Read-only recovery guidance exists; crash-persistent journal/reconciliation not implemented, MyISAM cannot be crash-atomic |
| AH-04 | Substantially addressed — PRs #740/#747 merged | Guarded failed-recipient retry and outcome integrity exist; interrupted in-flight delivery evidence is not fully durable |
| AH-05 | Open | Independent Topaz Test execution evidence |
| AH-06 | Deferred | Runnable LSB Test server and lineage-specific guarded execution contracts |
| AH-07 | Complete for Inbox — PR #749 merged | Other account-wide admin filters only if needed |
| AH-08 | Partial — PRs #754/#756 merged | Validate multi-day real-world supply/sell-through comparison; no need to recreate existing deltas |
| AH-09 | Ongoing | Expand targeted edge-case coverage with real runtime evidence |
| AH-10–AH-16 | Optional/conditional | Forecasting, custom item extras, cohorts/scheduling, production authorization, vendor-loop fixes, Synth inputs, coordinated bridge retirement |

**Newly completed analytics:** PR #758 rejects future activity in anomaly windows; #760 adds evidence sample quality; #762 caches per-item median and evidence count calculations. These are merged, not outstanding TODOs. There is no evidence in this audit of a missing core DSP AH management tab. Distinguish backend/CI implementation from feature-level runtime verification.

## Evidence and status convention

- **Implemented:** inspectable implementation or documented UI/API capability; not a claim that every branch is runtime-tested.
- **User-validated DSP:** project owner confirms Auction House live testing on DSP worked. **Exact tested feature matrix is not specified**; do not transfer that confirmation to every operation.
- **Explicit limitation:** source or operator documentation says unavailable or intentionally gated.
- **Verification needed:** useful feature exists but independent environment/edge-case evidence is not established here.
- **Enhancement:** newly proposed optional work, **not** an unfinished promise from the original requirements.
- **Historical TODO** entries in older roadmaps are not sufficient proof that a feature remains absent.

## Original requirements vs implementation

| Requirement | Evidence | Current assessment |
| --- | --- | --- |
| Browse AH categories; search items; show item icons | `categories.py`, `analytics.py`, `gui.py` `/items/{item_id}/icon.png`, Items hub | Implemented |
| Browse listing, buyer/seller names and sales dates | `listing_management.py`, `service.py`, `buyer_stats.py`, Items/Sellers/Buyers hub | Implemented |
| Search history and assess trends/prices | `analytics.py`, `economy_intelligence.py`, `snapshots.py`, `anomalies.py`, Economy hub | Implemented; quality improves with accumulated history |
| Add/list individual items | `legacy_test_executor.py`, `player_listing.py`, `dsp_myisam_listing.py`, `actions.py`, `seeder_ui.py` | Implemented behind lineage/environment gates; user reports DSP tested |
| Buy individual listings | `admin_buy.py`, `player_purchase.py`, `dsp_myisam_purchase.py`, Items/Sellers | Implemented as admin-buy and player-buy paths; distinguish semantics |
| Mass add items/categories and mass buy by criteria | `batch_actions.py`, `rule_cleanup.py`, `synthetic_seed.py`, `restock_presets.py`, Restock/Cleanup | Implemented; batch rules and maximums intentionally guarded |
| Mog Inbox multi-recipient items, saved templates | `reward_delivery.py`, `reward_templates.py`, `reward_campaigns.py`, `reward_history_api.py`, Inbox/Rewards | Implemented for ordinary items and gil; augmented custom `extra` unsupported |
| Economy/admin analytics inspired by Vanalytics | `economy_intelligence.py`, `anomalies.py`, `arbitrage.py`, `admin_impact.py`, `snapshots.py` | Implemented breadth; forecasts needing historical snapshots remain intentionally deferred |
| DSP / Topaz / LSB support | `schema.py`, `config_policy.py`, `lsb_policy.py`, `lsb_validation.py`, execution modules | DSP/Topaz guarded executors; LSB read/preview + narrow TEST price edit only. No broad LSB writes |

## Important corrections to prior status

1. **DSP is not awaiting its first live test.** User confirms actual DSP live testing and that it works; the precise feature-by-feature outcome has not been collected. Treat the previous blanket "live tests undone" line as stale, not as an instruction to rerun successful user testing.
2. The source includes real legacy Test-write executors (not just previews), MyISAM-specific compensated flows, synthetic seeding, batch cleanup, Inbox rewards, Buy-as-player, Buyers, and a substantial BI surface.
3. Test-only vs Live restrictions are deliberate authorization boundaries, **not by themselves defects**. Do not propose enabling production writes by flipping flags.
4. `AUCTION_HOUSE_DSP_MYISAM_TEST.md` documents a successful DSP Hi-Potion listing test and a distinct MyISAM purchase fallback. Compensating operations are **not crash-atomic**; successful live-path testing does not remove this limitation.
5. The original roadmap's "anomaly detection and forecasting" checkbox is misleading: anomaly detection is already implemented; **forecasting** is a separate optional, data-dependent capability.
6. The original roadmap's KPI delta TODO is likewise ambiguous: prior-period sales/activity deltas exist, while **snapshot-based supply/sell-through comparison** requires sufficient dated observations.

## Actual remaining work — prioritized

### P0 — reconcile truth before writing more AH features

- [ ] **AH-01** Record a *minimal* operator-validated DSP capability matrix (environment/profile and DB table engines, individual restock, player listing, Admin Buy, Buy-as-player/MyISAM, return, batch cleanup, Inbox item/gil delivery, templates/campaigns, rule cleanup, seeding, analytics); mark only observed workflows as tested. Accept the owner's overall DSP success now; do not downgrade it because individual details were not provided.
- [ ] **AH-02** Align operator status/help text, `ROADMAP_CURRENT.md`, and the historic TODO wording with that evidence. State `implemented`, `tested on DSP`, `untested on Topaz`, `LSB limited`, and `intentionally restricted` separately.
- [ ] **AH-03** Audit failure/recovery reporting for compensated DSP MyISAM listing/purchase: failed post-state assertions, interruption/crash window, manual reconciliation instructions, and whether Activity ledger exposes recovery-required cases. Avoid claiming crash atomicity.
- [ ] **AH-04** Review reward fan-out partial-result and retry UX: recipients delivered vs failed vs unknown after interruption, replay-ID consumption, explicit preview of retry subset, and duplicate-prevention confirmation. Current implementation intentionally commits per recipient.

### P1 — targeted support and usability gaps

- [ ] **AH-05** Verify Topaz with its *own* runnable Test configuration and storage engines. DSP success is not proof of Topaz execution parity.
- [ ] **AH-06** Once a runnable LSB Test server is available, design/prove supported write contracts for normal listing, purchase, cleanup and rewards. Preserve existing LSB read-only policy/preview coverage and fail-closed defaults until validated.
- [ ] **AH-07** Implement an **all characters on selected account** recipient/filter mode for Inbox/administration, using verified `chars` account identity. This is an actual unchecked GUI roadmap item; ensure permissions, offline state and preview counts.
- [ ] **AH-08** Validate snapshot-based supply/sell-through delta semantics over multiple days, and clarify "not enough history" messages. Do not duplicate the already implemented prior-period trend metrics.
- [ ] **AH-09** Assess marketplace rules against empty, stale, duplicate, offline/online and large fan-out cases; add isolated regression fixtures for uncovered edge cases before behavioral changes.

### P2 — explicitly optional extension work

- [ ] **AH-10** Forecasting only after sufficient genuine daily history exists; present uncertainty/sample sizes and avoid conflating forecasting with completed anomaly detection.
- [ ] **AH-11** Augmented/custom item delivery only after lineage-specific `extra` payload serialization, DB column behavior, and cross-editor agreement are source-verified. Do not silently deliver unaugmented substitutions.
- [ ] **AH-12** Optional broader Inbox recipient cohorts, scheduling and announcements with audit and idempotency contracts.
- [ ] **AH-13** Optional production authorization architecture: separate permissions and backups/server-native semantics; **do not** broaden current Test-only executor to Live as a shortcut.
- [ ] **AH-14** Revisit vendor-loop economy exploit (vendor prices below BaseSell); audit is documented but fix is not established. Distinguish toolkit alerting from upstream gameplay/server changes.
- [ ] **AH-15** Add gathering/fishing/quest acquisition inputs to Synth audits in the Synth module, *not* the AH implementation; coordinate only when that module is scheduled.
- [ ] **AH-16** Retire temporary `integration.py` legacy GUI bridge only when shared router migration owners can coordinate safely; do not overlap ongoing Wiki/Live Client integration.

## Suggested isolated development batches

1. **Documentation + tests first:** AH-01 through AH-04; modify only Auction House-owned docs/tests/service code. Keep `gui_shell.py`, global host/router files, Wiki and Live Client untouched.
2. **Focused usability:** AH-07 and AH-08 within dedicated AH files/tests, with navigation/central integration deferred.
3. **Environment expansion:** AH-05, then AH-06 only after a test server is ready.
4. **Optional backlog:** AH-10 through AH-16 require explicit prioritization, proof or coordination.

## Constraints / release criteria

- Work on an isolated branch and rebase before merge; other agents own Wiki and Live Client.
- No game-DB mutation as part of this documentation audit.
- No claim of full DSP per-operation coverage, Topaz pass or LSB pass without the actual test evidence.
- Preserve named Test-environment and exact-profile confirmations, stale-preview rechecks, bounded bulk limits and audit/replay protection.
- Retain the distinction between guarded **Admin Buy**, actual **player purchase**, synthetic **restock**, and player-backed **listing**.
