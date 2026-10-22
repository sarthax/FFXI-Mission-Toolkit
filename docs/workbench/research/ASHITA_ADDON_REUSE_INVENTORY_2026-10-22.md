# Ashita addon/plugin capability inventory and integration roadmap

**Recorded:** 2026-10-22  
**Status:** Source-informed research inventory; **not runtime, legal, protocol or gameplay acceptance**  
**Structured source:** [ashita_addon_reuse_inventory_2026-10-22.csv](ashita_addon_reuse_inventory_2026-10-22.csv) — **78 records** across Ashita plugins, addons, forks, an external app, grouped guide items and excluded cases. 78 records do **not** represent 78 source-reviewed implementations or 75 integration requests.

## Why this exists and what's different

The user identified [Sippius Chains](https://github.com/Sippius/Ashita-v4-addons/tree/main/chains) as a personally useful example of real-time skillchain timing and selection, and requested a systematic inventory of the [FFXI Guides Ashita recommended addon/plugin directory](https://ffxi-guides.github.io/ashita/recommended-plugins-addons.html). This research maps **real, user-facing addon behavior** to the repository's existing capabilities and to disciplined Headless test work. It complements, **does not replace**, [Toolkit's Ashita v4 SDK capability audit](../ASHITA_V4_CAPABILITY_AUDIT_2026-10-08.md) and [third-party Live Client research](../LIVE_CLIENT_THIRD_PARTY_CONTROL_RESEARCH.md).

The directory is a curated guide, not a canonical installed-addon manifest, code audit, licensing inventory, evidence of current Ashita v4 compatibility, or permission to use any plugin on retail. It explicitly warns against certain retail automation and server bypasses. Unlinked guide entries have **not** been independently identified in GitHub. Several CSV records represent a group, a fork, or an additional external addon (AutoWS).

### Evidence levels (use these exactly)

| Evidence | Meaning | Confidence |
| --- | --- | --- |
| `CodeRead` | Specific source files inspected through GitHub connector (Chains original/fork and AutoWS) | Source-level behavior only; **no local/runtime proof** |
| `ReadmeRead` | Maintainer README inspected (Metrics); no complete source audit | Maintainer-described capabilities only |
| `RepoMetadata` | GitHub repository identity, available description, version/push/license metadata inspected | Existence and description verified; **implementation unreviewed** |
| `GuideOnly` | Listed/described by the FFXI Guides page; source/version/link may be unverified | Discovery only; **do not implement from guesses** |

**P0/P1/P2/P3 in the CSV are research prioritization**, not `ready` issue labels or merge authority. `Exclude` means no implementation plan. Distinguish client observations, server-authoritative evidence and gameplay PASS/FAIL throughout.

## Chains — deep source audit and why it matters

**Original:** [Sippius Ashita v4 Chains](https://github.com/Sippius/Ashita-v4-addons/tree/main/chains), `chains/chains.lua` (inspected, blob `42a275f32d32e2bd5fdb8c31ec13d412cdb6caec`), `chains/skills.lua`; maintainer describes **retail-only tested** behavior. Repository's latest observed push at this audit: 2023-11-24.

**Fork:** [Lumaro/Lumariano Chains](https://github.com/Lumariano/Ashita-v4-addons/tree/main/chains), `chains/chains.lua` (blob `c761de23d3220bd8b6700fbe7d252c43575f66d3`), `chains/skills.lua`, `chains/packet-dedupe.lua`; latest observed push: 2025-05-29. The directory explicitly points to this fork for **Prime/Bonanza WS support and a packet duplication fix**. The source indeed imports a separate duplicate checker. Do not infer that the fork is maintained today merely because it was newer than Sippius's snapshot.

### Independently inspected mechanics

1. **Verified event surface:** `ashita.events.register('packet_in', ...)` receives an incoming `0x028` action and checks relevant action categories. It parses actor, target and per-target action result, including *additional-effect* bits. It can distinguish successful action message families from preliminary/invalid ones; not all action packets are skillchain events. The source primarily uses the first parsed target/result for the skillchain view, so this **does not solve general multi-target event projection**.
2. **Skill and property data:** `chains/skills.lua` has WS (action category 3), certain spells, pet/NPC actions, multiple chain properties, and specialized timing/delay metadata. The game-side catalog derives available weapon skills from Ashita's `HasWeaponSkill` and the currently equipped main/ranged weapon; it selectively considers SCH **Immanence**, BLU **Chain Affinity/Azure Lore**, pet skills and Aeonic aftermath. Headless's `CombatRoutines.BestWeaponSkill` already chooses the strongest level-unlocked WS, but does **not** thereby know which WS chain property is suitable.
3. **Target-local state:** observed action success or added effect updates a state entry keyed by target server ID. A first step stores property array and step count; subsequent qualifying action results may carry a server-visible skillchain added-effect property. This is **the precise missing connection** between the new Headless action observation PR #205 and its independent, theoretical property catalog PR #211.
4. **Display timing (model, NOT ground truth):** the implementation records local integer-second timestamps with `os.time()`, a per-skill post-WS wait (default `delay = 3` with overrides), a step-dependent estimated duration (first step commonly `7 + delay`, subsequent `8 - step + delay`), and renders **Wait**, **Go**, or **Burst** based on that target state. Timers are user guidance, not a demonstrated exact DSP server acceptance window. Some timing assumptions and BLU status durations are hard-coded.
5. **Potential closures:** action property combinations yield one or more possible follow-up outcomes, grouped by skillchain level; already-unlocked/currently equipped WS are ranked/displayed. Advanced level-4/Aeonic effects have conditional rules and limited documented testing, so the Headless reference catalog appropriately excludes naive unconditional advancement.
6. **Packet repetition:** the fork's `packet-dedupe.lua` considers packet/chunk memory comparisons to identify repeats across chunks. This is a **source design clue, not a drop-in dedupe algorithm**; fixed-size packet copies and raw `memcmp` must be capacity-, identity-, and length-validated before any analogous code. Incorrect dedupe would erase legitimate repeated attacks or double-count skillchain effects.

### Evidence-backed recommended HEADLESS state progression

`UNKNOWN → observed WS/chain-start candidate → target-scoped theoretical window proposal → observed additional-effect result → verified chain state → candidate burst element`

**Never invert this:** a suggested closer WS, a sent command, a repeated packet or a local timer is not a confirmed landed skillchain. An observed `0x028` result can support it only after DSP packet layout, actor/target identity, additional-effect mapping and completeness are accepted. A valid spell-element candidate still needs confirmed cast and server-observed magic-burst feedback. This research makes **no changes** to `Game/`, `Routines/`, `Mcp/`, `Navigation/` or server behavior.

### Six practical Chains-inspired acceptance cases

| Case | Required evidence | Failure to distinguish |
| --- | --- | --- |
| WS opener | Actual result from one actor on target X; known WS id/properties and source SHA | Dispatch accepted but WS missed/failed |
| Suggested closing WS | Target X still current; eligible WS learned/equipped, required TP, window and party order | Valid property but wrong job, insufficient TP or unclaimed target |
| Closed chain | Decoded additional-effect/property plus server-visible damage/effect tied to same target | Guessed chain from elapsed timer or combat log text |
| Back-to-back repeated packets | Chunk/packet identity + source sequence and timestamps; preserve genuinely separate repeats | Legitimate repeated WS confused with transport duplicates |
| Cast/burst followup | Accepted target-specific chain event + independently observed spell result with typed burst effect | Matching element cast outside allowed window |
| Interrupted or wrong target | Cancellation / target moved, zoning, stale actor, interrupted cast or packet loss | Old target window carried to a new mob |

**Local DSP verification is deferred** to an independently authorized operator using pooled disposable characters and existing accepted multi-role gates. No retail/private-server behavior is assumed identical from these public addon sources.

## Integration shortlist — ranked by leverage rather than popularity

| Priority | Addon families and actual concept | What already exists | New independent gap / right owner |
| --- | --- | --- | --- |
| **P0** | **Chains original + fork** — target-scoped WS/property graph, source action timing and deduplication | Headless PR #205 incoming action candidates; PR #211 reference property graph; Toolkit captures/0x028 AnimLab parser | **Headless #199 future read-only chain-state validator**, then #51-owned supervised planner; Toolkit source-backed capture fixtures, not a new animation recorder |
| **P0** | **AutoWS** — queue-time and final outgoing-action guards; spell/JA/WS overlap prevention | Headless `ICombat`, `KillRoutine`, `CombatRoutines.BestWeaponSkill`, `Navigation/` | **Headless action arbitration** after packet review. Do not port client memory/FFXI chat macros. Source [AutoWS](https://github.com/VanillaCheesecake/AutoWS/tree/main/autows); audit [#199](https://github.com/sarthax/xiheadless-dsp/issues/199) |
| **P0** | **Metrics** — attributed damage, accuracy, observed skillchain damage and run timer/reporting | Headless PR #209 bounded encounter measurements; Toolkit scenario evidence/provenance | **Toolkit #1211** controls reproducible comparisons; reuse per-actor/target attribution and prevent packet double count. Guide and [Metrics README](https://github.com/RaraProjects/metrics) describe name-based mob filtering: prefer unique server IDs for scenario evidence |
| **P0** | **Partybuffs** — ally effect and party distance display | Headless PR #207 0x076 source-hypothesis readback; Toolkit party/entity observation | Need **DSP server 0x076 independent proof**. Missing/stale ally status stays UNKNOWN, never “no buffs” |
| **P1** | **tTimers / statustimers** — buff lifetime, status removals, spell/JA recasts | Status snapshots in PRs #205/#207; `IMagic` and `ICombat` readiness | Clarify authoritative server effect vs client-predicted timer, normalize expiry/interrupt and cancellation; Toolkit read-only timeline first |
| **P1** | **tparty, petinfo, rolltracker, BLU addons, colure** — party TP, pets, rolls and job-specific magic | Existing party/jobs, pet and caster routines are partial; live-readback not all proven | Read-only ability/TP/status inventory before policy; fill supported DSP job capabilities only |
| **P1** | **simplelog, Sequencer, PacketFlow** — duplicate action/message handling and receive/upload timing | Toolkit canonical Capture envelopes and drop accounting; Headless packet parser and leases | Replay/arrival correlation and stable dedupe keys with retained raw evidence; **never transplant packet rewriting** |
| **P1** | **LuAshitacast, Packer, FindAll** — gear swaps, inventory presence and equipment readiness | Toolkit Item/Character Editor, wardrobe capacity inspector, Headless `IGear` | Shared read-only gear readiness and resource/provenance check, not a second gear engine |
| **P1** | **mobdb, Electron-FFXI-Atlas** — target/entity data and character map position | Toolkit entity catalog, 3D Viewer, Ashita native/Lua live bridge | Enrich verified provenance/coordinates and zone map context, **do not replace navigation** |

The guide additionally covers AH/inventory, progression and objective timers, multi-window UX, accessibility, macros, pets and language support. These have entries in the structured CSV and can be filtered by domain, project, evidence level and priority. Most are **not** source-reviewed.

## Additional source checks: Metrics, tTimers and older PartyBuffs

These supplements were reviewed **after** the first CSV cut. **Metrics** and **tTimers** now have `CodeRead` confidence in the CSV (**8 CodeRead; 6 RepoMetadata; 64 GuideOnly; no README-only rows**). This does *not* mean every file in either addon or their dependency chain was reviewed. PartyBuffs retains `GuideOnly` for the v4 entry because the **specific source examined was a v3 implementation**, not confirmed as the guide's linked v4 release.

### Metrics: source-projected combat attribution, not only DPS

Public source: [RaraProjects/metrics](https://github.com/RaraProjects/metrics) (reviewed under repository default branch `Release`): [`metrics.lua`](https://github.com/RaraProjects/metrics/blob/Release/metrics.lua), [`packets/_parser.lua`](https://github.com/RaraProjects/metrics/blob/Release/packets/_parser.lua), [`handlers/_handler.lua`](https://github.com/RaraProjects/metrics/blob/Release/handlers/_handler.lua), [`handlers/melee.lua`](https://github.com/RaraProjects/metrics/blob/Release/handlers/melee.lua), [`handlers/tp_action.lua`](https://github.com/RaraProjects/metrics/blob/Release/handlers/tp_action.lua).

Verified design details:
- Incoming `0x028` is decoded into **every target and nested result**, including bitfield count, action category, message and optional additional/spikes effects. This is particularly relevant to Headless #204: do not assume Chains' first-target-only display parser covers full melee/WS metrics.
- Offense/defense classification checks party/alliance affiliates, pets and owners, and whether a mob is hitting party/pets; missed/mitigated attacks are not naively counted as damage, and additional effects remain separate from the base melee strike.
- WS parsing separates damage, drains, debuff-only messages and per-skillchain opener/closer metric counters. **Damage credited to a skillchain may be tracked separately**, so aggregators must avoid adding both the base action's total and additional chain damage twice.
- Incoming packet route has **duplicate packet checking** and zoning refresh, while some output views group targets by *name* rather than unique instance. For reproducible Toolkit encounter oracles, retain **server ID + zone + capture source/sequence** and preserve original evidence. Local name-based grouping may be useful for UI, not authoritative mob identity.
- The parse “active timer” described in the README auto-pauses after inactive periods. It is a user-facing DPS perspective, not necessarily the wall-clock combat interval. Headless [#208](https://github.com/sarthax/xiheadless-dsp/issues/208) should keep explicit encounter boundary and coverage semantics. Future accepted dashboard can display both **active-time DPS** and **wall-clock DPS** only when labeled, with no inferred nonzero duration.

**Recommendation:** Import design *categories and oracle-test cases*, not the Lua or a parallel packet recorder. First validate full 0x028 result attribution and same packet deduplication with sanitized fixtures. Code/source reviewed, **not** actual Metrics runtime or DSP compatibility.

### tTimers: estimated timings with clear provenance

Public source: [ThornyFFXI/tTimers](https://github.com/ThornyFFXI/tTimers) (GitHub metadata **MIT**); reviewed [`actionpacket.lua`](https://github.com/ThornyFFXI/tTimers/blob/main/actionpacket.lua) and [`callbacks.lua`](https://github.com/ThornyFFXI/tTimers/blob/main/callbacks.lua). The repository also contains separate `trackers/buff`, `trackers/debuff`, and `durations/` modules not yet fully audited.

- It has an independent incoming action-bitfield parser and separate buff/debuff timer trackers; these **demonstrate an event→timer UX pattern**, not authoritative DSP recast/duration values.
- Its callbacks include **custom operator timers** and local-wall-clock calculations. Keep manually scheduled timer state distinct from server-observed buff state; **predicted expiry never proves a status was removed**.
- The standalone tTimers parser extracts action categories/results and optional effects; do not mix its specialized packed-id assumptions with Headless's validated command packet schema without bit/fixture comparison.

**Recommendation:** The Toolkit status timeline should show `observed_on`, `predicted_expiry`, `observed_off` and `unknown/stale` as distinct UI states. Headless role policy must not automatically recast or cleanse based on client-predicted time alone.

### PartyBuffs: corroboration is Ashita v3-only

Public reference: [ProjectTako/ffxi-addons/partybuffs/ashita/partybuffs.lua](https://github.com/ProjectTako/ffxi-addons/blob/master/partybuffs/ashita/partybuffs.lua). The inspected source uses older `ashita.register_event('incoming_packet')` (Ashita **v3** surface), recognizes incoming `0x076`, and combines lower status bytes with high-bit masks in party member records; it also shows client-local party distance.

This reinforces the hypothesis behind pending Headless [#206 / PR #207](https://github.com/sarthax/xiheadless-dsp/pull/207), but **does not establish v4 callback compatibility, DSP sends 0x076, the same offsets on Valhalla, or that absent packets mean no buffs**. It is not license clearance for Lua or bundled icons. Local DSP source and capture approval remain decisive.

## 2026-10-22 follow-up — COR, AutoBot-Ashita and all-job party behaviors

Expanded the CSV from 75 to **78** records after reviewing three new public sources (now **8 CodeRead**, 6 RepoMetadata, 64 GuideOnly). This is an addon-reuse inventory, not proof of runtime correctness. The detailed 22-job matrix belongs to [XIHeadless audit #212 / draft PR #213](https://github.com/sarthax/xiheadless-dsp/pull/213) to avoid parallel ownership of the same gameplay implementation.

- **[Buckfutt AutoBot-Ashita](https://github.com/Buckfutt/AutoBot-Ashita):** public MIT-licensed Ashita v4 automation framework with modules for independent jobs, automatic WS, skillchain resonance and a Trust set/summon manager. Audited [`jobs/COR.lua`](https://github.com/Buckfutt/AutoBot-Ashita/blob/main/addons/autobot/jobs/COR.lua) (mainly a generic ability list), [`modules/skillchains.lua`](https://github.com/Buckfutt/AutoBot-Ashita/blob/main/addons/autobot/modules/skillchains.lua) (some trust weapon skills via ability-style packets), and [`modules/trusts.lua`](https://github.com/Buckfutt/AutoBot-Ashita/blob/main/addons/autobot/modules/trusts.lua) (summon/release/retry/monitor). **Trust summons and maintenance do not implement the server-side NPC's role AI.** The repository ships a movement DLL, which was not inspected or executed.
- **[professorpalmer AshitaRoller4](https://github.com/professorpalmer/ashitaroller4):** Ashita v4 COR main/subjob support (main two rolls vs sub one), optional roll-profile presets, Double-Up, lucky/unlucky and bust policies, Snake Eye, Fold, Crooked Cards and recast checks, status-derived roll maintenance. Audited [`ashitaroller.lua`](https://github.com/professorpalmer/ashitaroller4/blob/main/ashitaroller.lua) and README. **Do not import its hardcoded buff IDs, JA recasts or strategy as DSP authority.** These are version-specific reference hypotheses requiring real packet+server confirmation.
- **[ChrisTitusTech RollTracker](https://github.com/ChrisTitusTech/ashita-ffxi/tree/main/addons/RollTracker):** read-only human-facing roll representation and lucky/unlucky/value data. Used only to cross-check what a Headless roll-observation panel might show. Observing a roll name/number is not proof every party member has a buff, or that an action succeeded.
- **[XIHeadless source audit](https://github.com/sarthax/xiheadless-dsp/pull/213):** all 22 jobs already have individual *leveling* Brains, and `Game/PartyRoles.cs` classifies COR as DPS with Support eligibility. `Routines/JobKits.cs` already invokes PhantomRoll and enables generic COR ranged mode, but doesn't include a confirmed allied COR roll rotation. Aged `CorBrain` prose claims no ranged loop; this contradicts current generic `JobKits` configuration and must be reconciled with live evidence, not inferred away.
- **[Ashita community addon directory](https://git.ashitaxi.com/addons?page=4&sort=moststars):** requested supplemental source, but page 4 couldn't be retrieved through the accessible browser at this review. No invented page-4 entries added; GitHub source repositories above were independently inspected.

**Suggested cross-project sequence:** (1) verify Headless #205/207 observed 0x028/0x076 against DSP; (2) add *read-only* COR roll-type/number/bust and ally buff evidence; (3) produce a pure roll-maintenance/advice policy with UNKNOWN/provenance; (4) integrate opt-in decisions under existing #51/#132 action/lease gates; (5) compare support outcomes using #208/#209 and Toolkit differential testing. Retail Trust AI, Valhalla pet-Lua companions, and leased headless players must be separate evidence categories; Headless trust dependency [#53](https://github.com/sarthax/xiheadless-dsp/issues/53) owns retail-style summon enablement.
## Safety, licensing and version caveats

- **Publicly visible source is not automatic reuse permission.** The Chains repository does not advertise a clear repository-wide SPDX license in the metadata inspected. Its `skills.lua` contains an Ivaar copyright/redistribution header; that does not settle the license of every surrounding file or later fork change. Inspect each artifact before copying anything. **Original C# behavior/data models, source attribution and public protocol facts are preferred.**
- Source repository metadata verified separately: [tTimers](https://github.com/ThornyFFXI/tTimers) declares **MIT**; [LuAshitacast](https://github.com/ThornyFFXI/LuAshitacast) declares **MIT**; [statustimers](https://github.com/HealsCodes/statustimers) and [Multisend](https://github.com/ThornyFFXI/Multisend) declare **GPL-3.0**. Additional dependency/individual file licenses and reuse obligations have **not** been audited.
- Ashita v3 example semantics, Ashita v4 Lua/SDK semantics, live client memory, retail packets, DSP/Valhalla packets and Headless protocol state **are distinct systems**. Do not treat a client's `GetStatus`, `GetDistance`, party buff or recast memory read as stable headless authoritative state.
- The guide warns against several retail-unsafe or server-bypassing addons, including `casper`, `gateway`, `nokb`, `fastswap` and packet-search behavior. **These are excluded**, not an implementation backlog. Retail ban risk and test-server authorization are different topics; never perform unauthorized manipulation.
- Avoid raw user-visible chat, auth/account details, packet injection logs with identifiers, DAT/client asset redistribution and binary plugin ingestion. Restrict published evidence to bounded, sanitized, permissioned contexts.
- Tools like `repeater`, `enternity`, `Multisend` and automation of trading/loot are **not authority** to issue actions; they can help define human workflows, but the repository's lease/cancellation/idempotency/oracle controls remain the source of truth.

## Program and next slices

**Owner separation:** Toolkit is the cross-project addon **inventory and evidence catalog**; Headless owns read-only action/status normalization and existing routine consumers; DSP/Valhalla source and operator own server behavior/protocol truth. Retain Toolkit #1197 / #1198 / #1211 and Headless #199 / #204 / #206 / #208 / #210 with existing ownership. Do not expand another agent's PR in progress.

1. **P0 source-evidence pass (remote-safe):** independently inspect [Lumaro Chains](https://github.com/Lumariano/Ashita-v4-addons/tree/main/chains) `skills.lua` and `packet-dedupe.lua`, and Metrics' source attribution. Produce an accepted `WS_ID + job/equipment + property` **proposed map** with exact row provenance and conflicts, not a runtime dispatch rule. Existing Headless `Actions.Ws` must be the WS authority.
2. **P0 local protocol parity (gated):** local reviewer of Headless PR #205/#207 verifies incoming DSP 0x028 and 0x076 semantics, with source SHA, sender/target, freshness, actions and status evidence; also record one repeat-packet fixture and one genuine repeated WS. Mark UNKNOWN when not observed.
3. **P1 pure target-window state machine (separate owner):** after protocol acceptance, simulate **opened/candidate/valid/closed/expired/unknown** with monotonic timestamps, source confidence, per-target identity and zone; test input packet loss/duplicates, interruption, slot reuse and combo steps. Reference Chains timing for **hypotheses only**.
4. **P1 action arbiter and party coordination:** existing Headless `ICombat`, `IMagic`, `KillRoutine`, `PartyCombat` and #51 own dispatch. Add opt-in proposal/hold-TP only after action authority/lease gates; no parallel combat/navigation/movement loops.
5. **P2 encounter-quality measurement:** combine validated observed outcomes with PR #209's offline metrics and Toolkit #1211 comparisons, preserving test identity, gear/party composition, DSP SHA, duplicate accounting and independent oracles. Never infer boss balance from a faster clear alone.

### Inventory maintenance contract

New addon candidates should get a CSV row with **one concrete source URL** (upstream, or the directory URL if only guide-discovered), version/generation, evidence level, runtime/server caveats, benefit, existing owner and proposed read-only acceptance. Promote `GuideOnly → RepoMetadata → ReadmeRead → CodeRead → local runtime evidence` only when actually performed. Add separate source-level reports for important addons rather than inflating a single research document, and avoid opening implementation issues automatically for every promising addon.

**Not performed:** No client launches, no Ashita live capture, no private server access, no gameplay automation, no executed WS/burst sequence, no file/license redistribution and no code modification. Original Toolkit and Headless PRs under independent review are unchanged.
