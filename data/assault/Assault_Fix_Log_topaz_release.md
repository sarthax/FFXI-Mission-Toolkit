# Assault Mission Fix Log

Running record of everything built/fixed during the PSC/PFC Assault build-out, for a
summary report later. Updated as we go — newest entries at the bottom of each section.
Every file below also has inline comments explaining the *why*, not just the *what*.

## New missions built (PSC/PFC round)

### Imperial Agent Rescue — Mamool Ja Training Grounds (mission 11)
Had mob/NPC IDs in reference data but zero instance logic anywhere (LSB's own version has
the same empty `onInstanceCreated`/`onInstanceProgressUpdate`). Built from scratch:
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[2]` (11 guards + 3 gates), `BRUJEEL` npc entry.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Dilapidated_Gate.lua` — new, destructible obstacle (modeled on Brittle_Rock).
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/imperial_agent_rescue.lua` — new. Progress tracked off the 3 gates only; guards are just combat obstacles. **Unverified**: whether retail also requires clearing guards, and whether completion should gate behind talking to Brujeel instead of auto-completing on the 3rd gate.
- `sql/instance_entities.sql` — added rows for instance id 11 (mobs + Rune of Release/Ancient Lockbox/Brujeel).
- `sql/instance_list.sql` — enabled row 11, start position is the zone's default Rune of Release spot (not a verified entrance).

### Lebros Supplies — Lebros Cavern (mission 22)
Same situation as above (LSB had mob IDs, zero logic). Built from scratch:
- `scripts/zones/Lebros_Cavern/IDs.lua` — added `mob[22]` (6 Crimson Eruca), 12 `IMPERIAL_STORMER` npc entries.
- `scripts/zones/Lebros_Cavern/npcs/Imperial_Stormer.lua` — new. Trigger-once delivery mechanic, no item consumption. **Unverified** whether retail actually requires trading a specific ration item.
- `scripts/zones/Lebros_Cavern/instances/lebros_supplies.lua` — new. Progress from triggering all 12 Stormers. Rune of Release/Ancient Lockbox left at zone-default position — no confirmed staging coordinates for this specific mission.
- `sql/instance_entities.sql` — added rows for instance id 22.
- `sql/instance_list.sql` — enabled row 22, same caveat on start position.

### Orichalcum Survey — Leujaoam Sanctum (mission 2) — SCAFFOLD ONLY
No mob/NPC/objective data exists anywhere researched (LSB, Topaz, old-dsp). Registers and is
walkable (Rune of Release + Ancient Lockbox only) but has no objective content — will not
complete until real data is sourced.
- `scripts/zones/Leujaoam_Sanctum/instances/orichalcum_survey.lua` — new, bare scaffold.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — minimal rows (row 2 enabled).

### Lamia No.13 — Ilrusi Atoll (mission 42) — SCAFFOLD ONLY
Same situation — zero data anywhere. Bare scaffold, same shape as Orichalcum Survey.
- `scripts/zones/Ilrusi_Atoll/instances/lamia_no_13.lua` — new.
- `scripts/zones/Ilrusi_Atoll/IDs.lua` — added empty `mob[42]` stub.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — minimal rows (row 42 enabled).

## Missions that already existed and got re-enabled/fixed

- **Wamoura Farm Raid** (27) and **Seagull Grounded** (31) — fully scripted, correct data, but
  their `instance_list.sql` rows were commented out, so neither was actually reachable in-game.
  Uncommented both.
- **`wamoura_farm_raid.lua`** — `onInstanceTimeUpdate` referenced an undefined global `timeRemaining`
  instead of the local `remainingTimeLimit`; would've errored on the countdown message. Fixed.
- **`extermination.lua`** (Ilrusi) — `onInstanceTimeUpdate` referenced undefined `Ilrusi.text`
  instead of the `ID` it actually required. Also `onInstanceComplete` passed bare `NORMAL`
  instead of `tpz.status.NORMAL` to `setStatus()` (→ nil). Both fixed.
- **`troll_fugitives.lua`** (Lebros) — same undefined-global bug, `Lebros.text` instead of `ID.text`. Fixed.
- **`golden_salvage.lua`** (Ilrusi) — same bare-`NORMAL` bug as Extermination. Fixed.
- **`requiem.lua`** (Periqia) — same bare-`NORMAL` bug. Fixed.

## Root-cause bugs found during live testing

### Runic portal (Whitegate) sending players to the wrong assault zone — FIXED, confirmed working
`Runic_Portal.lua` picks a destination via `tpz.teleport.id.AZOUPH_SP + offset`, where `offset`
comes from key-item order (Leujaoam=0, Mamool Ja=1, Lebros=2, Periqia=3, Ilrusi=4 — confirmed
against `keyitems.lua`, IDs 762–766, genuinely sequential in that order). But the teleport ID
enum in `scripts/globals/teleports.lua` declared the five staging points in a different order
(Leujaoam, Periqia, Mamool Ja, Lebros, Ilrusi), so "+2" landed on Mamool Ja's Bhaflau Thickets
instead of Lebros's Mount Zhayolm. Confirmed `Runic_Portal.lua` is the only place in the
codebase doing arithmetic on these IDs, so fixed it at the source by reordering the enum values
in `teleports.lua` to match the key-item order, rather than touching the portal script. **User
confirmed this fixed it.**

### Lebros portal (`Mount_Zhayolm/npcs/_1p3.lua`) menu showing garbled/placeholder text
`recommendedLevel` was referenced but never assigned (undefined global → nil) before being
passed into the client's mission-log menu event — every other zone's equivalent portal
(`_272.lua`, `_1g2.lua`, `_273.lua`, `_jic.lua`) defines it correctly first. Fixed by adding the
missing `local recommendedLevel = getRecommendedAssaultLevel(assaultid)` line. (This turned out
to be secondary to the teleport-routing bug above — once the routing was fixed and the player
was actually in the right zone, that was the real fix — but this was still a real bug worth
keeping fixed.)

### Qiqirn Mine item — "attempt to index local 'bomb' (a nil value)"
`scripts/globals/items/qiqirn_mine.lua` calls `instance:insertAlly(10633)` to summon a temporary
ally that damages Brittle Rocks. `mob_groups.groupid = 10633` never existed in `sql/mob_groups.sql`
for any zone — pure missing data, not a logic bug. Added a new row cloning the zone's existing
`Volcanic_Bomb` group (groupid 1, poolid 4245) but with `allegiance=1` (player ally, matching the
convention used by other ally rows like Prishe/Gessho/Karababa) and groupid 10633 to match what
the item script expects.

### Volcanic Bomb death — "undefined procedure onMobDeath"
`scripts/zones/Lebros_Cavern/mobs/Volcanic_Bomb.lua` didn't exist at all (not empty — missing).
The engine calls `onMobDeath` unconditionally on every mob death. Created a plain stub matching
the zone's other unscripted-behavior mobs (no confirmed special on-death behavior for this one).

### Ancient Lockbox — "No Valid Function for Ancient_Lockbox" (Lebros, and same bug in 2 more zones)
Only Leujaoam Sanctum and Ilrusi Atoll had `npcs/Ancient_Lockbox.lua` at all. Mamool Ja, Lebros,
and Periqia had no file — meaning this would've blocked completion on *every* mission in those
three zones (Preemptive Strike, Imperial Agent Rescue, Excavation Duty, Troll Fugitives, Wamoura
Farm Raid, Lebros Supplies, Seagull Grounded, Requiem), not just Excavation Duty. Created all
three using Leujaoam's fully-built version as the structural template (repeat-open guard,
open animation, instance-wide XP/gil reward) but *without* inventing reward item IDs we don't
have confirmed data for — `DIRECT_ITEMS`/`TREASURE_POOL_ITEMS` are intentionally empty with a
TODO in each new file, XP/gil use a flat 1000/1000 placeholder. Note: Ilrusi Atoll's existing
lockbox file is present but an empty stub (opens without erroring, gives nothing) — same gap,
not yet touched since it wasn't reported broken.

### Brittle Rock — invisible "hitbox" obstacles, inconsistent removal on death
Two separate bugs, same root: the five rock-wall props (`_1rx`/`_1ry`/`_1rz`/`_ir0`/`_ir1`)
default to hidden in `npc_list` (status=0), and nothing ever revealed them.
- `excavation_duty.lua` now explicitly shows all five at instance creation.
- `Brittle_Rock.lua`'s `onMobDeath` now hides the paired prop ~3s after playing the destroy
  animation, instead of relying on the animation alone to clear whatever collision it carries
  (the inconsistent "some rocks let you through, some don't" behavior is consistent with the
  prop just sitting there indefinitely either way).
- Confirmed the mob-to-prop position pairings themselves were already correct (checked all 5
  spawn coordinates against their paired prop's coordinates — exact matches), so this wasn't a
  wrong-pairing bug.

### Brittle Rock #1 unreachable at melee range (confirmed via live testing)
Visual reveal/clear from the previous fix round confirmed working by the user (partly thanks to
an Ashita client addon, Gateway, that pre-animates door/obstacle states client-side). Separately,
`BRITTLE_ROCK1` (mob 17035282) was unreachable in melee — data check showed its Y coordinate was
-42.362, roughly 10 units below its four siblings (all clustered -32.86 to -32.99), and its
paired rock-wall prop (`_1rx`, npc 17035537) was a full unit off from its own mob's Y — unlike
rocks 2-5, where mob Y and prop Y match exactly. Both looked like straightforward data-entry
errors. Corrected both to -32.9, matching the sibling cluster and restoring the mob-Y-equals-prop-Y
pattern the other four pairs have. **Not yet confirmed by testing** — next thing to verify.
- `sql/mob_spawn_points.sql` — BRITTLE_ROCK1 (17035282) Y: -42.362 → -32.9.
- `sql/npc_list.sql` — its prop `_1rx` (17035537) Y: -43.362 → -32.9.

### Text/message ID audit — all 5 zones (client version offset)
User confirmed the underlying cause: the client version this server targets has its dialog
string table shifted by +1 in places compared to newer clients (a string inserted somewhere in
retail's patch history). Every zone's assault-related text block in `IDs.lua` had been
transcribed from a newer client's data and was off. User provided real dialog table exports
(via an Ashita/POLUtils-style tool) for all 5 zones, cross-referenced each block directly
against them, and corrected every constant:
- **Leujaoam Sanctum**: `ASSAULT_01..10_START` (7448-7457 → 7447-7456) and the
  `TIME_TO_COMPLETE`..`PARTY_FALLEN` block (7508-7516 → 7507-7515), uniform +1 throughout,
  added `FADES_INTO_NOTHINGNESS`.
- **Mamool Ja Training Grounds**: same shape, `ASSAULT_11..20_START` (7458-7467 → 7457-7466)
  and the same shared `TIME_TO_COMPLETE` block, uniform +1.
- **Lebros Cavern**: `ASSAULT_21..30_START` (7368-7377 → 7367-7376) — this zone was missed in
  the first pass since only its `TIME_TO_COMPLETE` block (already fixed earlier) had been
  reported broken at the time. Also confirmed this zone's `TIME_TO_COMPLETE` block genuinely
  lives at its own 7407-7415, not the shared 7507 block the other 4 zones use.
- **Periqia**: `ASSAULT_31..40_START` (7478-7487 → 7477-7486), the shared `TIME_TO_COMPLETE`
  block, and the entire Excaliace escort dialogue block (`EXCALIACE_START` through
  `EXCALIACE_CAUGHT`, 7525-7542 → 7524-7541) — all uniform +1.
- **Ilrusi Atoll**: same +1 shift, *and* this is where the previously-noted mislabeling bug
  turned out to live — `ASSAULT_41..50_START` weren't just numerically wrong, they were
  literal copy-pastes of Mamool Ja's values/comments. Corrected using this zone's actual
  objective text ("Find the figurehead", "Eliminate Lamia No.13", etc.), found at 7487-7496 in
  the real table. Also fixed `CHEST`/`GOLDEN` (7526/7527 → 7525/7526) and added the
  previously-missing `TOO_FAR_FROM_CHEST` (7524).

No Lua logic changes needed anywhere for this — every instance/NPC script already referenced
these via the named `ID.text.X` constants rather than raw numbers, so correcting the `IDs.lua`
data was sufficient everywhere.

**Not yet checked**: whether this same +1 pattern extends beyond the assault-specific message
ranges into other systems (quests, general zone text, etc.) — user declined a blanket runtime
shift given the pattern isn't perfectly uniform (Lebros's block genuinely lives at a different
base range than the other 4 zones), so each new discovery should keep being verified against
real client data rather than assumed.

### Brittle Rock melee range too tight (mob_family_system.mobsize)
Rock 1's coordinate fix didn't generalize — Rock 5 (mob 17035290 / prop `_ir1`) had normal,
non-outlier coordinates but was still unreachable in melee, worse on inclined terrain. Root
cause: `GetMeleeRange() = m_ModelSize + 3` (src/map/entities/battleentity.cpp), and the
`mob_family_system.mobsize` for familyid 236 ("Structure", the immobile-obstacle family used by
Brittle_Rock, Dilapidated_Gate, and 15 other props) was 0 — the minimum, giving only 3 total
yalms of 3D distance tolerance (includes vertical, which is what bites on uneven ground).
Increased to 3 (→ 6 yalms tolerance). Shared across 17 mob_pools rows, but all are static
obstacle props, not real combat mobs, so wider tolerance should be broadly safe rather than
risky. **Not yet confirmed by testing.**
- `sql/mob_family_system.sql` — familyid 236 `mobsize`: 0 → 3.

### Live-DB sync gap (process note, not a bug)
Discovered mid-session: editing `sql/*.sql` dump files does not update the actual running
database — those files only describe intended state. Every SQL change made this session
(instance_entities/instance_list rows, mob_groups, coordinate fixes, mobsize) needs a manual
`INSERT`/`UPDATE` run directly against the live DB before it takes effect. User opted for
single manual statements as needed rather than a full `tools/dbtool.py` resync, to avoid
touching anything not directly relevant. Statements provided so far:
```sql
INSERT INTO `mob_groups` VALUES (10633,4245,63,'Volcanic_Bomb',0,128,0,0,0,77,78,1);
UPDATE `mob_family_system` SET `mobsize` = 3 WHERE `familyid` = 236;
```

### Qiqirn Mine — rewrote to match the real retail mechanic
Cross-referenced the "Solo Assault Guide by Korvana" against FFXIclopedia's item page for
Qiqirn Mine (confirming it's unrelated to the same-named "Qiqirn Mine (Monster)" NM found in
other zones). The item's real mechanic: attack a Brittle Rock wall, use the item while still
engaged with it, remain engaged with that same wall for 10 seconds, and it's destroyed instantly
when the timer ends — disengaging before then wastes the mine. The previous implementation
(`insertAlly(10633)`, fixed earlier this session to stop it erroring) summoned an ally combatant
instead, which was never the correct mechanic — the underlying `mob_groups` bug fix was still
worth doing at the time since it was blocking testing, but the whole approach was wrong.
Rewrote `scripts/globals/items/qiqirn_mine.lua`: checks the player is engaged with a Brittle
Rock at use time, starts a 10s timer, and only if they're still engaged with the *same* mob when
it fires does `setHP(0)` on it (the established instant-kill pattern used elsewhere in this
codebase — mijin_gakure, doom, twilight_scythe, several mob suicide skills — which correctly
triggers the existing onMobDeath/onMobDespawn animation+hide+progress logic already in
`Brittle_Rock.lua`). Known simplification: engagement is checked once at the 10s mark, not
continuously — a disengage-then-reengage within the window isn't caught. **Not yet tested.**
- `scripts/globals/items/qiqirn_mine.lua` — full rewrite.

### Qiqirn Mine — second pass, added the real visual/mechanical dressing
User live-tested and reported the actual retail behavior: using the item drops a visible mine
model next to the rock, a 10-second countdown shows in the client UI, it detonates using a
mobskill called "Mine Blast," then disappears. Confirmed in the engine: `mob_skill_id 1838` is
Mine Blast (20 AoE fire, `scripts/globals/mobskills/mine_blast.lua`), `player:countdown(seconds)`
exists and sends the client's native countdown-bar packet, and `mob:useMobAbility(skillID,
target)` forces a mob to play a specific skill on demand. Also found the actual `Qiqirn_Mine`
mob_pools entry (5872, family "Bomb") that the wandering "Qiqirn Mine (Monster)" NM uses in its
own zones (Arrapago Reef, etc.) — much more fitting than the `Volcanic_Bomb` pool the first
rewrite's `mob_groups` fix had used, since nothing tied that family to being a bomb/mine at all.
Repointed `mob_groups` id 10633 at this pool instead of adding a new row.
Mine Blast's own 20 damage is nowhere near enough to fell a ~2325 HP rock in one hit, so it's
played for show only — the actual wall destruction is still the `setHP(0)` call from the first
pass, run immediately after the skill plays (same instant-kill convention as before). Full flow:
spawn the mine at the engaged rock's position → `countdown(10)` → 10s timer → if still engaged
with the same rock, force Mine Blast on it, then kill it → despawn the mine either way.
**Not yet tested.**
- `sql/mob_groups.sql` — group 10633: poolid 4245 (Volcanic_Bomb) → 5872 (Qiqirn_Mine).
- `scripts/globals/items/qiqirn_mine.lua` — full rewrite, second pass.

### Qiqirn Mine — root cause found: a pre-existing mob script I wasn't consulting
Live testing showed the countdown never displayed as text (only rapid, repeated "The mine
explodes!" messages and "The Brittle Rock is out of range"), the mine never despawned, no
explosion animation, and 2 of 5 rocks still couldn't be destroyed at all. Root cause: a
purpose-built mob script already existed --
`scripts/zones/Lebros_Cavern/mobs/Qiqirn_Mine.lua` -- implementing its own countdown
(`onMobSpawn`, via `MINE_COUNTDOWN` text messages), its own timed detonation (`onMobFight`,
checking a `Time` localvar), and its own rock-kill (`onMobWeaponSkill`). I didn't know this file
existed when writing the second-pass item script, so the two were running uncoordinated -- my
item script never engaged the mine with anything, so this file's `onMobFight` sequence never
actually started ticking, while my own duplicate `useMobAbility`/timer logic fired independently.
Separately, `onMobWeaponSkill` had its own bug regardless of my changes: it identified which rock
to kill by checking the mine's position against 4 hardcoded exact coordinates (Brittle Rock #2
had no branch *at all*, and float-vs-integer exact-equality checks are fragile against a
dynamically-positioned mine) -- almost certainly the real explanation for "2 walls still can't
be destroyed," independent of the earlier mobsize/melee-range fix.
Fix: rewrote `Qiqirn_Mine.lua` to track its target rock and the using player by ID (localvars set
at spawn), covering all 5 rocks and removing the position-matching fragility; added an
engagement check at detonation time so disengaging still wastes the mine. Simplified the item
script (third rewrite) to just verify engagement, spawn the mine, tag it, and `engage()` it --
letting the mob script's existing, purpose-built sequence drive everything else. **Not yet tested.**
- `scripts/zones/Lebros_Cavern/mobs/Qiqirn_Mine.lua` — rewrote onMobFight/onMobWeaponSkill.
- `scripts/globals/items/qiqirn_mine.lua` — simplified, third rewrite.

### Orichalcum Survey — filled in the 3 previously-skipped mechanics
User answered the 3 open questions from the initial build directly:
- Pickaxe break: "standard chance." Found it -- `settings.lua` already defines
  `MINING_BREAK_CHANCE = 33`, the same setting the real overworld HELM mining system rolls
  against (`doesToolBreak()` in `scripts/globals/helm.lua`). Reused that exact global and roll
  convention instead of inventing a number.
- Worm hazard: same chance as the ore (20%). Found a ready-made ally group for it too --
  `mob_groups` groupid 1, `Leujaoam_Worm`, already zone-scoped to Leujaoam Sanctum (69) and
  sitting right next to groupid 2 (`Qiqirn_Miner`, see below) -- both look like they were
  provisioned specifically for this mission and never wired up.
- Qiqirn aggro: passive/non-attackable until the ore is found, then hostile and chasing the
  carrier. Groupid 2 (`Qiqirn_Miner`, zone 69) existed but with `allegiance=0` (hostile from
  spawn) -- flipped to 1 (non-hostile) so they start passive, matching the ally pattern already
  proven for Qiqirn Mine; `Mining_Point.lua` now `:engage()`s them onto the ore carrier once
  ore is found, which should make an already-combat-capable mob (unlike the scripted immobile
  props) actually fight normally.
Instance script now spawns 4 Qiqirn Miners at a spread of Mining Point locations at creation,
tracking their IDs via instance localvars so Mining_Point.lua can find them later. **Not yet
tested.**
- `sql/mob_groups.sql` — Qiqirn_Miner (groupid 2, zone 69) allegiance 0→1.
- `scripts/zones/Leujaoam_Sanctum/instances/orichalcum_survey.lua` — spawn 4 Qiqirn Miners.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua` — added break/worm/aggro-switch logic.

### Brittle Rock damage cap — confirmed no Lua-only true fix exists; tuned DEF/MDEF instead
Live testing gave real numbers: at DEF 1500/MDEF 900, melee hit for 24-28, crits ~45, and a
weapon skill hit for 587 -- target is a flat ~20 from any source (confirmed retail mechanic, not
just tuning), because without it the rocks die too fast via straight combat and players never
need the Qiqirn Mine at all. Searched specifically for any Lua-accessible incoming-damage hook
(a damage-taken event, a listener type for it, anything before/after damage applies) -- none
exists in this engine. A true cap needs a new C++ mob mod plus a clamp check in the damage
pipeline, which needs a server rebuild to take effect.
**User decision: stay Lua-only for now, not worth a rebuild yet.** Bumped DEF 1500→2200,
MDEF 900→1300 as a first estimate (not calculated against this engine's exact damage formula --
needs live-test numbers to dial in further). Explicitly flagged limitation: this cannot
meaningfully touch weapon skill damage -- 587 is ~29x over target, and no defense value closes
a gap that size without making the rock unhittable by anything smaller. WS will keep bypassing
the intended mine-focused pacing until this gets the real C++ fix, which remains the
recommended path whenever a rebuild is acceptable. **Not yet tested.**
- `scripts/zones/Lebros_Cavern/mobs/Brittle_Rock.lua` — DEF/MDEF bump, limitation documented inline.

### Lamia No.13 — built out from scaffold, real spawn point found in existing SQL
Found her directly: `mob_spawn_points` id 17002517 ('Lamia_No13', zone 55, static pre-placed
spawn, not ally-summoned), `mob_groups` id 3 (poolid 2340). Per the Solo Assault Guide by
Korvana this is a plain kill-target mission (locate via Wide Scan, no other documented
mechanics) -- spawned her in `onInstanceCreated`, standard progress-on-despawn pattern for
completion, matching the simplest kill-based missions elsewhere in this codebase. **Not yet
tested.**
- `scripts/zones/Ilrusi_Atoll/IDs.lua` — added `LAMIA_NO_13` to `mob[42]`.
- `scripts/zones/Ilrusi_Atoll/mobs/Lamia_No13.lua` — new, trivial progress-on-despawn.
- `scripts/zones/Ilrusi_Atoll/instances/lamia_no_13.lua` — spawn her, complete on progress >= 1.
- `sql/instance_entities.sql` — added her to instance id 42's rows.

### Reference: retail mechanics for all 10 PSC/PFC missions
Pulled and organized into `documentation/PSC_PFC_Retail_Mechanics_Reference.md`, sourced from
the Solo Assault Guide by Korvana. Confirmed accurate with no changes needed: Leujaoam Cleansing,
Golden Salvage, Preemptive Strike, Requiem. Confirmed real mechanic gaps beyond Qiqirn Mine:
Seagull Grounded and Lebros Supplies are both currently oversimplified stubs that don't implement
their real mechanics (complex escort state machine; food-point delivery system respectively) --
flagged for a future dedicated build pass, not touched this round. Orichalcum Survey and Lamia
No.13 (currently bare scaffolds) now have enough real detail in that doc to actually build out.

### Orichalcum Survey — built out from scaffold to a real playable core loop
Done in parallel while Excavation Duty was being live-tested. Used the retail mechanic
description from `PSC_PFC_Retail_Mechanics_Reference.md` (Solo Assault Guide by Korvana) plus
data found directly in this zone's existing SQL: `Mulwahah` (npc 17060026) and 10 `Mining_Point`
props (17060016-17060025) were already sitting in `npc_list`/`instance`-range, just never wired
to any script or `IDs.lua` entry. Also found the real item: `chunk_of_orichalcum_ore` (item 739)
in `item_basic`, and the existing generic `pickaxe` (item 605).
Core loop implemented: trigger Mulwahah for a Pickaxe (temp item) → trigger a Mining Point
(20% placeholder chance, not confirmed against retail odds) for the Ore (temp item) → trigger
Mulwahah again with the ore to complete the instance directly (no progress-counter mechanic
needed here). Mining Points default to hidden in `npc_list` like the Brittle Rock props did —
revealed at instance creation.
**Explicitly not implemented**, mentioned in the guide but without solid enough data to build:
pickaxe breaking on some mining attempts, a worm hazard spawning on failed attempts, and the
zone-wide "all Qiqirn become aggressive to the ore carrier" effect once ore is found. **Not yet
tested.**
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `MINING_POINT1-10`, `MULWAHAH` npc entries.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mulwahah.lua` — new.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua` — new, shared by all 10.
- `scripts/zones/Leujaoam_Sanctum/instances/orichalcum_survey.lua` — reveal Mining Points at
  creation; progress-update hook now documented as intentionally unused.
- `sql/instance_entities.sql` — added Mulwahah + 10 Mining Points to instance id 2's rows.

## Open / still needs data

- Orichalcum Survey, Lamia No.13 — need real mob/NPC/objective data (see scaffolds above).
- Imperial Agent Rescue — verify guard-kill requirement and Brujeel completion trigger.
- Lebros Supplies — verify delivery mechanic (trigger-only vs. item trade).
- ~~Ancient Lockbox reward items — need confirmed retail data for Mamool Ja, Lebros, Periqia~~ —
  **resolved 2026-08-17**, see "Ancient Lockbox real reward tables" below. Ilrusi Atoll's lockbox
  is still an inert stub — no LSB reference exists for that zone (see that section for detail).
- ~~Appraisal system (Drahbah/Memeroon/Chochoroon trading a "???" item for an identified one) is
  entirely unimplemented~~ — **proof-of-concept built 2026-08-17**, see "Appraisal system" below.
  Only `??? Earring` and `??? Box` have real reward data; the other seven "???" item types the
  lockboxes can hand out still have no appraisal data and are politely rejected, not silently
  eaten. Fee/reward text and the equal-chance-for-Box interim odds are all unconfirmed against
  retail and **not yet tested**.
- Ilrusi Atoll's `ASSAULT_41..50_START` text comments are mislabeled with Mamool Ja's objective
  text (pre-existing, also present in LSB/Topaz upstream) — the actual in-game banner text for
  all 10 Ilrusi missions is unverified.

## Ancient Lockbox real reward tables (2026-08-17)

User provided LSB's actual `Ancient_Lockbox.lua` for Lebros Cavern, Mamool Ja Training Grounds,
and Periqia — real weighted loot tables (LSB's `qItem`/`regItem` pattern), not placeholders.
Ported the data over and replaced the empty-table stubs built earlier this session:

- `scripts/globals/assault_lockbox.lua` — **new**. LSB keys everything through a shared
  `xi.appraisal.assaultChestTrigger(player, npc, qItem, regItem)` helper that doesn't exist in
  this codebase (no `xi.*` namespace here, and the appraisal system itself isn't built — see
  "Open / still needs data" above). Wrote a Lunar-API equivalent, `tpz.assault.chestTrigger`,
  using the same sum-then-roll weighted-pick idiom already used elsewhere in this codebase
  (`scripts/globals/helm.lua`'s `pickItem`) rather than inventing a new pattern. Centralizing this
  here means the three zones below (and any future zone with a multi-mission shared lockbox)
  don't each reimplement the open/roll/give/stagger logic.
- `scripts/zones/Lebros_Cavern/npcs/Ancient_Lockbox.lua` — real tables for Excavation Duty (21),
  Lebros Supplies (22), Troll Fugitives (23 — table wired in even though that mission isn't built
  yet, harmless until it is). Keyed off `npc:getInstance():getID()`, which returns the
  `instance_list` row id — confirmed via `src/map/instance.cpp`'s `CInstance::GetID()` and this
  log's own earlier "row 11 / row 22" language — rather than `player:getCurrentAssault()`, since
  that's the *player's* mission-log state and this lockbox needs to react to *which instance it's
  physically standing in* regardless of who triggers it.
- `scripts/zones/Mamool_Ja_Training_Grounds/npcs/Ancient_Lockbox.lua` — real tables for Imperial
  Agent Rescue (11), Preemptive Strike (12).
- `scripts/zones/Periqia/npcs/Ancient_Lockbox.lua` — real tables for Seagull Grounded (31),
  Requiem (32). LSB's sample also included a third mission, Shooting Down the Baron, but no
  `instance_list` row exists for it in this repo (never built here) — its data is left in a
  comment for whenever that mission gets built instead of silently dropped.
- Item ID translation: LSB's `xi.item.*` enum has no equivalent constants file in this codebase,
  so all items were resolved to numeric IDs by name-matching against `sql/item_basic.sql` (e.g.
  `UNAPPRAISED_BOX` → `???_box` → item 2286, `HI_POTION_TANK` → `hi-potion_tank` → item 13688).
  Full mapping used is inline as `--` comments in each file.
- **Not changed**: `Leujaoam_Sanctum/npcs/Ancient_Lockbox.lua` (already had real, user-confirmed
  data before this session) and `Ilrusi_Atoll/npcs/Ancient_Lockbox.lua` (still an inert stub — LSB
  has no `Ancient_Lockbox.lua` at all for Ilrusi Atoll to reference; only that zone's unrelated
  `Cursed_Chest.lua` golden-figurehead mechanic exists there).
- XP/gil reward amounts are still the flat 1000/1000 placeholder inherited from the Leujaoam
  reference build — LSB's sample scripts don't expose those values (handled inside
  `xi.appraisal.assaultChestTrigger`, which we don't have source for), so they remain unconfirmed
  across all zones. **Not yet tested.**

## Appraisal system proof-of-concept (2026-08-17)

User supplied real retail data for two of the nine "???" item types the Ancient Lockboxes can
hand out, plus the three Appraiser NPCs' locations and gil fees, and asked for a basic working
version to prove the concept before filling in the rest.

- `scripts/globals/appraisal.lua` — **new**. `tpz.appraisal.tryAppraise(player, npc, trade, fee)`,
  called from each Appraiser NPC's `onTrade`. Trade guard follows the established codebase idiom
  (`trade:getItemCount() == 1 and trade:hasItemQty(itemID, 1)`, e.g.
  `scripts/zones/Bastok_Markets/npcs/Brygid.lua`) rather than the unused `confirmItem`/`confirmSlot`
  API. Gil check happens *before* `player:tradeComplete()` so a player who can't afford the fee
  gets their "???" item back automatically (engine unreserves anything not explicitly consumed —
  confirmed via `src/map/packet_system.cpp`'s `unreserveUnconfirmed()` call after `OnTrade`)
  instead of losing it for nothing.
  - `??? Earring` (item 2277) → weighted pool: Storm Loop (15968, 3.1%), Reraise Earring (14790,
    6.3%), Beetle Earring (13323, 25%), Silver Earring (13327, 18.8%), Bone Earring (13321,
    20.3%), Shell Earring (13313, 25%) — real retail weights from the user.
  - `??? Box` (item 2286) → equal-chance pool across all 14 named items (Velvet Cloth 828, Red
    Rock 769, Bomb Ash 928, Sulfur 1108, Copper Ore 640, Spartan/Bronze/Silver/Iron/plain Bullet
    Pouch 5341/5359/5340/5353/5363, Holy Basil 1590, Troll Pauldron 2160, Flan Meat 2175, Troll
    Bronze Ingot 2302) — user explicitly said exact odds aren't known yet, so this is a flat
    1-in-14 placeholder, not confirmed retail data.
  - Other seven "???" types (ring, cape, necklace, axe, polearm, headpiece, sword, gloves, bow) —
    no data yet. Traded in, the NPC replies "The ??? X cannot be appraised yet." and hands the
    item straight back (no `tradeComplete()` call), so nothing is lost.
  - Reward routing: `player:getPartySize() <= 1` → direct to inventory via `npcUtil.giveItem`;
    otherwise → `player:addTreasure()` (shared party Treasure Pool), matching the user's explicit
    instruction that appraised items go through the pool in a party (so Ex items can still be
    distributed) but straight to inventory solo. **New pattern** — confirmed via source search
    that no existing script in this codebase already branches reward-routing on party size, so
    there was no established convention to follow here.
  - Player-facing text is free-form via `player:PrintToPlayer()`, not a dialog-table message ID —
    there's no bound item-name-lookup function in this codebase, so display names are hardcoded
    strings in the pool table rather than pulled from `item_basic` at runtime. Matches the user's
    requested phrasing: "The ??? Earring appraisal came back! You got a Beetle Earring."
- `scripts/zones/Al_Zahbi/npcs/Chochoroon.lua` — wired to `tpz.appraisal.tryAppraise`, fee 50 gil.
- `scripts/zones/Aht_Urhgan_Whitegate/npcs/Drahbah.lua` — wired, fee 500 gil.
- `scripts/zones/Nashmau/npcs/Memeroon.lua` — wired, fee 500 gil.
- **Not yet tested in-game.** All three NPCs' `onTrigger` dialogue (csid 678/272/260) is untouched
  — this only adds the `onTrade` handler, so talking to them still plays whatever that event
  already played before.

## Zone-level portability survey — closed out, nothing ported (2026-08-17)

This was the one item left open from the very start of this whole session (before it turned into
the Assault build-out): compare `scripts/zones/**` between `D:\Claude\old-dsp-reference` and
`D:\Claude\topaz-reference` for standalone Lua-only content portable into this repo, same
methodology as the earlier global-scope/mixins/LSB passes. Ran it now since there's currently no
new Assault mission that has sourced reference data waiting to be built (checked — every mission
with LSB/old-dsp/hidden-SQL data has already been built and enabled this session; the remaining 33
of 50 missions have zero data anywhere and need fresh wiki research, out of scope for now).

**Result: nothing worth porting.** `scripts/zones/` in topaz-reference is essentially a superset of
old-dsp's, and this repo is already at parity with topaz-reference. Three candidates surfaced,
none panned out:
- **`Chat_Manual.lua` (7-zone tutorial NPC)** — looked like a clean copy-paste, but checking the
  actual `npc_list.sql` IDs topaz-reference uses for it (e.g. `16982642` in Aht Urhgan Whitegate)
  showed they're already occupied by a different, active NPC in this repo's own `npc_list.sql` —
  `Survival_Guide`, at the identical position. This repo already has `Survival_Guide.lua` deployed
  across ~90 zones, a far more complete tutorial-NPC system than the 7-zone Chat_Manual ever was.
  Porting it would have duplicated an already-solved (and better) system, and would've needed new
  IDs to avoid clobbering the existing NPCs. Not done.
- **Kuftal Tunnel elevator NPC** (old-dsp only) — real content, but old-dsp calls the
  `setElevator` binding with 6 args while this engine's version (`lua_baseentity.cpp:1564`) takes
  5 — needs a signature adaptation, not a copy-paste. Not done, marginal value for the effort.
- **Sugandhi (Bastok weapon vendor)** — old-dsp's own script has a bug (requires the wrong zone's
  dialog-ID file). Low value, not done.

No files changed. This closes out the entire portability-audit thread from the start of the
session — nothing else is queued on that front.

## Excavation Duty — round 4 of live-test fixes (2026-08-18)

User tested again after the previous round's fixes. Three new issues, all in this same mission.

### Brittle Rock animation/SFX cut off early
`Brittle_Rock.lua`'s `onMobDeath` hides the wall prop 3 seconds after the destruction animation
starts (added last round to fix the hitbox-never-clears bug). 3 seconds was cutting the animation
and sound effect off before they finished. Extended to 5 seconds. No other logic changed.

### Qiqirn Mine: wrong countdown text, no rock damage, mine never disappears
All three symptoms turned out to share one root cause. The mob script's previous version (3rd
pass) drove the actual Mine Blast + rock kill + mine self-destruct off `onMobFight` ticks, entered
via `mine:engage(rockID)` called in `scripts/globals/items/qiqirn_mine.lua`. The countdown numbers
themselves are on a separate, independent `mob:timer` chain in `onMobSpawn` — which is exactly why
they were still displaying (albeit with wrong text, see below) while nothing after them ever
happened: rock took no damage, mine never disappeared.
Root-caused by reading `src/map/ai/controllers/mob_controller.cpp`'s `DoCombatTick`: it can call
`Disengage()` and `return` *before* reaching `luautils::OnMobFight()` if `TryDeaggro()` trips that
tick. Nothing here ever gives the mine a reason to stay aggro'd — its autoattack is disabled and
the rock never fights back — so there's a real chance it silently stopped ticking `onMobFight`
partway through the 10-second countdown, on every single detonation. Rather than patch the
deaggro condition (`mob_controller.cpp` is C++, out of scope for a Lua-only fix anyway), rewrote
the whole sequence to run off the same `mob:timer` chain already proven to fire reliably, removing
the dependency on staying engaged entirely.
- `scripts/zones/Lebros_Cavern/mobs/Qiqirn_Mine.lua` — 4th-pass rewrite. `onMobSpawn` now owns the
  full sequence: 10 countdown ticks, then at the 10s mark, an explicit `rock:setHP(0)` (not
  contingent on `onMobWeaponSkill` firing for the forced `useMobAbility` call — that hook's
  reliability for a forced ability was never confirmed, so the kill no longer depends on it
  either), then `mob:setStatus(DISAPPEAR)` 2 seconds later so the blast animation gets to play
  first (same reasoning as the Brittle Rock timer extension above). `entity.onMobFight` and
  `entity.onMobWeaponSkill` removed — nothing reads them anymore.
- Countdown text: `MINE_COUNTDOWN` (`Lebros_Cavern/IDs.lua` text id 6981, commented `<number>...`)
  actually renders as "The mine explodes" in-game — wrong for this client version, same class of
  bug as the text-ID drift fixed across all 5 zones earlier this session, but this specific ID was
  never checked against a real dialog-table export. Rather than needing another XML export from
  the user to chase down the correct id, switched to `player:PrintToPlayer(string.format("%u...",
  seconds))` — a literal client-side message instead of a dialog-table lookup, sidestepping the
  wrong-ID risk entirely. Confirmed via the appraisal system work earlier this session that
  `PrintToPlayer` supports arbitrary interpolated strings.
- `scripts/globals/items/qiqirn_mine.lua` — removed the `mine:engage(rock:getID())` call (no
  longer needed, and carried a real risk of the mine actually trying to fight/chase the rock via
  its own AI once engaged — `NO_MOVE`/autoattack-disabled mitigate but don't guarantee that).
  Comments updated to stop describing the now-removed onMobFight dependency.
- **Not yet tested.**

### Top 2 walls still impassable after killing their Brittle Rock
Different bug from the hitbox-never-clears one fixed last round — this time the *real* rock's
death was working (wall prop animates and disappears correctly), but passage stayed blocked
anyway for 2 of the 5 rocks. Found via `sql/instance_entities.sql`: instance 21 (Excavation Duty)
registers **10** `Brittle_Rock` entities, not 5. `sql/mob_spawn_points.sql` has a duplicate row for
every rock — `17035283/285/287/289/291`, at (near-)identical coordinates to the real 5
(`17035282/284/286/288/290`) — and both sets were registered in `instance_entities` for this
instance. Nothing in Lua ever mapped, tracked, or killed the duplicates (`Lebros_Cavern/IDs.lua`'s
`mob[21]` table only lists the 5 even-numbered IDs) — they just sat there as permanent, invisible,
untracked collision. Killing a real rock correctly cleared its own wall, but wherever the player's
actual walking path happened to intersect a duplicate's hitbox, the passage stayed blocked
regardless of the real rock's state. Explains why only some rocks showed the symptom — it depends
on whether the duplicate's exact position happens to sit in the walkway.
- `sql/instance_entities.sql` — removed the 5 duplicate registrations for instance 21, keeping
  only the 5 real (Lua-mapped) rock IDs.
- **Needs a manual DB fix** (same "edit the dump file doesn't touch the live DB" situation as
  earlier this session) — run this directly against the live database:
  ```sql
  DELETE FROM `instance_entities` WHERE `instanceid` = 21 AND `id` IN (17035283, 17035285, 17035287, 17035289, 17035291);
  ```
  The underlying `mob_spawn_points` rows were left untouched — only their registration into this
  one instance was removed, so nothing else that might reference those spawn point IDs is
  affected. **Not yet tested.**

## Appraisal system — two live-test bugs fixed (2026-08-18)

User tested the Drahbah/Chochoroon/Memeroon appraisal POC in-game. Trading a "???" item worked
correctly (real rolled results, correct item names in the confirmation message), but two separate
things around it were broken.

### "Obtained 1108 gil." instead of the item's name
The confirmation message (`player:PrintToPlayer("The ??? Box appraisal came back! You got a
Sulfur.")`) was correct, but a *second*, garbled message immediately followed it: "Obtained 1108
gil." — 1108 being Sulfur's own item ID, not a gil amount. Root cause: the solo-inventory path was
using `npcUtil.giveItem()`, which internally sends its own extra notification via
`player:messageSpecial(zones[player:getZoneID()].text.ITEM_OBTAINED, itemId)`
(`scripts/globals/npc_util.lua:230`) — i.e. the **player's current zone's** own `ITEM_OBTAINED`
text id. Aht Urhgan Whitegate's copy of that id is wrong for this client (same class of
client-version text-ID drift fixed across the 5 Assault zones earlier this session, just never
checked for this zone, since nothing had called `npcUtil.giveItem` there before). The wrong id
apparently renders a template built for a literal number rather than an item-name substitution, so
the raw item ID got printed as if it were a gil figure.
- `scripts/globals/appraisal.lua` — solo path now calls `player:addItem({ id = resultItemID,
  quantity = 1, silent = true })` directly instead of going through `npcUtil.giveItem`. `silent =
  true` suppresses the client's own native "obtained" popup entirely (a real option on `addItem`,
  see `src/map/lua/lua_baseentity.cpp:2920-2927`), which is fine since the appraisal's own
  `PrintToPlayer` message already tells the player what they got — sidesteps the broken zone
  text-ID rather than needing to track down and fix the correct one for Aht Urhgan Whitegate, Al
  Zahbi, and Nashmau individually. Also added an explicit free-slot check beforehand (matching
  `npcUtil.giveItem`'s own defensive check) so a full inventory gets a clear message instead of
  `addItem` silently doing nothing — the retail dialogue itself warns "I might not be able to fit
  it into your bag... always make sure to clean your bag before asking for an appraisal!", so this
  is a real, expected risk, not a hypothetical.

### Drahbah introducing himself as the player's own name, quoting "0 gil"
Talking to Drahbah (not trading — the `onTrigger` dialogue) rendered: *"Hello, I'm Gwendy [the
player's own character name], and I'll appraise any item that you just can't figure out for the
low, low price of 0 gil!"* User supplied a real client dialog-table export for Aht Urhgan Whitegate
(`TOAU Dialog Whitegate 1/2.xml`) confirming the actual text template at index 5206/5208: *"Hello,
I'm ≺Speaker Name≻, and I'll appraise any item... for the low, low price of ≺Numeric Parameter 0≻
gil!"* — i.e. the fee is meant to come from the first `startEvent` parameter. The old
`entity.onTrigger` called `player:startEvent(678)` with no parameters at all, so that slot
defaulted to 0. Cross-checked against LandSandBoat's own `Drahbah.lua` (`player:startEvent(678,
500)`, `Chochoroon.lua` → `startEvent(260, 50)`, `Memeroon.lua` → `startEvent(272, 500)`) to
confirm the fee belongs in exactly that slot and that no second parameter is needed for the
name — LSB doesn't pass one either, so the "Gwendy" self-naming was very likely a downstream
symptom of the same missing parameter rather than a separate bug.
- `scripts/zones/Aht_Urhgan_Whitegate/npcs/Drahbah.lua`,
  `scripts/zones/Al_Zahbi/npcs/Chochoroon.lua`, `scripts/zones/Nashmau/npcs/Memeroon.lua` —
  `onTrigger` now passes the fee: `startEvent(678, 500)` / `startEvent(260, 50)` /
  `startEvent(272, 500)`.
- **User-confirmed fix, working.** All 3 Appraiser NPCs (Drahbah, Chochoroon, Memeroon) tested
  in-game and behaving correctly — dialogue and gil display fine, trades resolve correctly. The
  "Gwendy"/"0 gil" issue was indeed just the missing `startEvent` parameter.

## Appraisal system — known follow-up, not urgent (2026-08-18)

User flagged for later: the appraisal system's reward pools currently only have real data for
`??? Earring` (real retail weights) and `??? Box` (flat equal-chance placeholder, see
`scripts/globals/appraisal.lua`). The other 7 "???" item types the Ancient Lockboxes can hand out
still have no pool at all and get the "cannot be appraised yet" fallback message. User's own words:
"we'll have to take a pass at adding all the correct redeemable items and create a better weighted
pool but the odds are hard to find" — real per-item weights for the remaining types aren't easily
available, so this is explicitly deferred, not blocked on anything actionable right now. No code
changes from this entry — just recording the open item so it isn't lost.

## SP-rank missions built while user was live-testing (2026-08-18)

User asked for a start on SP-rank (rank 3) missions across zones while away testing Excavation
Duty, naming Sagelord Elimination and Troll Fugitives as examples. Troll Fugitives (Lebros, 23)
and Extermination (Ilrusi, 43) turned out to already be fully built and enabled — flagged this to
the user rather than redoing them. The three genuine SP-rank gaps (zero data anywhere in LSB,
old-dsp, or topaz-reference) all turned out to have real, previously-uncaptured data sitting
unwired in this repo's own SQL — same pattern as Orichalcum Survey/Lamia No.13 earlier this
session. Built all three at "placeholder" scope per the user's request (instance lua, npc/mob
tracking where applicable, lockbox wiring) rather than full retail-accurate mechanics.

### Escort Professor Chanoix — Leujaoam Sanctum (mission 3)
Found an explicit `-- Escort Professor Chanoix` block in `sql/mob_spawn_points.sql`: Clavauert B
Chanoix (the escort target, using a Clavauert/elemental model — no unique human model was ever
captured for him) plus 9 Frozen Bones and 7 Gelid Bhoot. Retail objective is "Protect the
professor" — a true escort/protect-fail mechanic, which is **not** implemented here: no path data
exists (his spawn point is 0,0,0, "script-positioned" in the original data, meaning retail moved
him via logic this repo doesn't have), and a real protect-fail system is a new engine feature, not
placeholder-scope work. Simplified to "clear the path": Chanoix stands passively near the entrance
while players kill all 16 real threats; instance completes on their deaths. He cannot currently be
harmed in a way that fails the mission.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[3]`.
- `scripts/zones/Leujaoam_Sanctum/mobs/Clavauert_B_Chanoix.lua`,
  `Frozen_Bones.lua`, `Gelid_Bhoot.lua` — new.
- `scripts/zones/Leujaoam_Sanctum/instances/escort_professor_chanoix.lua` — new, kill-all-16
  pattern.
- `sql/instance_list.sql` — enabled row 3, start pos = this zone's Rune of Release spot (npc_list
  17060015), not a verified entrance.
- `sql/instance_entities.sql` — added rows for instance 3 (17 mobs + Rune of Release + Ancient
  Lockbox).

### Sagelord Elimination — Mamool Ja Training Grounds (mission 13)
Found immediately after the already-built Preemptive Strike block in `sql/mob_spawn_points.sql`:
Sagelord Molaal Ja (boss) plus 9 Mamool Ja Trainees and 5 Lizard pets. Retail objective is singular
— "Defeat Sagelord Molaal Ja" — so only his death is tracked, same kill-target shape as Lamia
No.13; the trainees/lizards are optional trash, no custom scripts needed for them.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[13]`. **Caught and fixed my own
  transcription error while double-checking this against the raw ID list** — first pass mislabeled
  one of the 5 lizard IDs (17047609) as a 9th trainee, which doesn't exist (there are exactly 9
  trainees and 5 lizards, 14 total); corrected before writing any other files.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Sagelord_Molaal_Ja.lua` — new, progress-on-despawn.
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/sagelord_elimination.lua` — new.
- `sql/instance_list.sql` — enabled row 13, start pos = this zone's Rune of Release spot (npc_list
  17047809), not a verified entrance.
- `sql/instance_entities.sql` — added rows for instance 13 (15 mobs + Rune of Release + Ancient
  Lockbox).

### Saving Private Ryaaf — Periqia (mission 33)
Found 3 real, individually-positioned NPCs (Ryaaf, Balarahb, Rhagmakah) sitting right after
`RUNE_OF_RELEASE` in `sql/npc_list.sql` — no mob spawns tied to this mission were found, consistent
with retail's pure-locate objective ("Find the survivors", plural — matches having 3 NPCs to find).
Simple trigger-once-per-survivor pattern, same shape as Lebros Cavern's `Imperial_Stormer.lua`.
- `scripts/zones/Periqia/IDs.lua` — added `RYAAF`/`BALARAHB`/`RHAGMAKAH` to the `npc` table.
- `scripts/zones/Periqia/npcs/Ryaaf.lua`, `Balarahb.lua`, `Rhagmakah.lua` — new.
- `scripts/zones/Periqia/instances/saving_private_ryaaf.lua` — new, completes at progress >= 3.
- `sql/instance_list.sql` — enabled row 33, start pos = this zone's Rune of Release spot (npc_list
  17006810), not a verified entrance.
- `sql/instance_entities.sql` — added rows for instance 33 (Rune of Release + Ancient Lockbox + 3
  survivor NPCs).

### Bonus fix found while wiring up Chanoix's lockbox usage
`Leujaoam_Sanctum/npcs/Ancient_Lockbox.lua` was hardcoded to always give Leujaoam Cleansing's
rewards (`ASSAULT_ID = 1`) regardless of which mission was actually running — meaning Orichalcum
Survey players have been silently getting the wrong mission's "???" items this whole time, and
Escort Professor Chanoix would have inherited the same bug. Rather than migrating this file to the
shared `tpz.assault.chestTrigger` pattern (which would drop its already-validated
`getRecommendedAssaultLevel` gate), added a light-touch instance-ID guard around the existing
logic: item-giving now only fires when `npc:getInstance():getID() == ASSAULT_ID`, so missions 2/3
correctly fall through to XP/gil only until real reward data exists for them.
- `scripts/zones/Mamool_Ja_Training_Grounds/npcs/Ancient_Lockbox.lua`,
  `scripts/zones/Periqia/npcs/Ancient_Lockbox.lua` — doc comments only, noting instances 13/33 are
  intentionally absent from their reward tables (already nil-safe, no logic change needed).

**None of the three new missions have been tested in-game yet.** See "Manual SQL to run" below.

## Qiqirn Mine — regression from the 4th-pass rewrite (2026-08-18, fifth pass)

User re-tested Excavation Duty: countdown now showed "0..." then blank "..." on every tick, and
**nothing** after — no Mine Blast, no rock damage, mine never disappeared. Worse than the previous
round (which at least displayed *a* countdown, just with wrong text).

Before touching the file again, checked the actual engine source this time instead of guessing a
5th time: `src/map/ai/helpers/action_queue.cpp` confirms `mob:timer()` pushes into a real priority
queue keyed by `start_time + delay` — multiple concurrent timers on one mob do **not** overwrite
each other, and a `0ms` delay isn't a special/invalid case (fires on the next AI tick same as any
other). So the timer engine itself was ruled out as the cause.

The one thing that changed structurally in the 4th-pass version and nowhere else in this
codebase's mob scripts: a `for` loop registering 10 `mob:timer()` calls where each closure
captured the loop's own iteration variable (`seconds`) rather than using a literal hardcoded
number per call. Standard Lua handles this correctly, but this engine's specific Lua environment
hasn't been independently confirmed to, and the symptom (a number that decays to nothing, and
everything scheduled *after* the loop in the same function never running at all) is consistent
with something going wrong inside that loop and aborting the rest of `onMobSpawn` before it ever
reaches the 10-second detonation timer.

- `scripts/zones/Lebros_Cavern/mobs/Qiqirn_Mine.lua` — reverted to 10 fully explicit,
  individually-hardcoded `mob:timer()` calls, no loop, no captured variable — matching the style
  every other working timer-chain in this codebase already uses. The very first "10..." is now a
  direct synchronous message (not a `mob:timer(0, ...)` call) to eliminate the zero-delay case
  entirely, even though it was ruled out as the cause.
- **If this still doesn't work**, the loop was not actually the cause, and the next real
  diagnostic step is checking the map server's own console output for a Lua traceback at the
  moment the mine spawns — asked the user to check this rather than guess a 6th time.
- Brittle Rock's own files (`Brittle_Rock.lua`'s 5-second animation delay,
  `sql/instance_entities.sql`'s phantom-duplicate-rock removal) were independently re-verified
  intact and untouched by this — if their behavior still looks unchanged, the most likely
  explanation is the phantom-rock **manual SQL DELETE hasn't been run against the live DB yet**
  (SQL file edits never auto-apply, per this session's established pattern) — confirm with the
  user before assuming those fixes failed too.
- **Not yet tested.**

## Qiqirn Mine countdown — real fix via direct DAT extraction, sixth pass (2026-08-18)

First real test of the new `dat-extractor` tool (see the D:\Claude\dat-extractor investigation
earlier this session) on a genuinely unsolved problem, instead of just re-verifying something
already confirmed by a manual export. Pulled Lebros Cavern's actual client dialog table directly
(no manual XML export needed this time) and found `MINE_COUNTDOWN` was off by +1: `IDs.lua` had it
at 6981, but the real "<number>..." countdown text lives at **6980**. 6981 is a real message too,
just a different one — "The mine explodes!" — which the mine's script never actually used before
(the 5th-pass version detonated silently, text-wise).

The same lookup also surfaced 4 more real messages right next to it, none currently modeled:
`6982` "The mine misfires...", `6983` "You retrieve the mine.", `6984` "You successfully deactivate
the mine!", `6985` "You failed to deactivate the mine...". Retail apparently has a genuine
defuse/retrieve mechanic for these mines that this build doesn't implement at all — **not
built**, flagging it since it's new, confirmed-real information, not a guess. Unclear what
actually triggers it (a skill check? an action command? trading an item to the mine?) without
more data — a good candidate for BG-wiki/Korvana-guide research if the user wants to pursue it.

- `scripts/zones/Lebros_Cavern/IDs.lua` — `MINE_COUNTDOWN` corrected to 6980, added
  `MINE_EXPLODES = 6981`.
- `scripts/zones/Lebros_Cavern/mobs/Qiqirn_Mine.lua` — countdown ticks now use
  `messageSpecial(ID.text.MINE_COUNTDOWN, N)` (the real client "<number>..." text) instead of the
  `PrintToPlayer` placeholder from the 5th pass; detonation now also sends
  `messageSpecial(ID.text.MINE_EXPLODES)` before the Mine Blast animation, which the mine never
  announced in text at all before this.

## LC-rank build-out — all 5 zones (2026-08-18)

Same SQL-archaeology pattern that solved SP-rank, applied one rank up. Spot-checked all 5
zones' next unbuilt `instance_list` row before starting — 4 of 5 had real, comment-labeled mob
data sitting unwired; the 5th (Demolition Duty) only had a bare `mob_pools` definition with no
placement data anywhere, so it's scaffold-only, same tier as the original Orichalcum
Survey/Lamia No.13 builds. Note: Periqia's actual next-rank mission is **Shooting Down the
Baron** (`instance_list` row 34), not Building Bridges (row 35, one rank later) — corrected
this mid-session after initially assuming the wrong one from an earlier spot-check.

### Shanarha Grass Conservation — Leujaoam Sanctum (mission 4)
20 real Coney, comment-labeled in `mob_spawn_points.sql` right after Escort Professor Chanoix's
block. Real objective text (`ASSAULT_04_START`, "Protect the vegetation") suggests a defend
mechanic, but no protectable prop/object was found alongside the Coneys — modeled as
kill-all-20, same shape as this zone's own Leujaoam Cleansing (mission 1). **Unverified**
whether the real mechanic is actually a defense/escort variant instead.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[4]` (20 Coney).
- `scripts/zones/Leujaoam_Sanctum/mobs/Coney.lua` — new, kill-all pattern.
- `scripts/zones/Leujaoam_Sanctum/instances/shanarha_grass_conservation.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 4 enabled, start pos reuses this
  zone's Rune of Release spot (same as rows 2/3).

### Breaking Morale — Mamool Ja Training Grounds (mission 14)
18 real mobs (7 Mamool Ja Recruit + 11 Mamool Ja Trainer), comment-labeled "-- breaking morale"
right after Sagelord Elimination's block. **Flag**: real objective text at `ASSAULT_14_START`
says "Steal the supplies", which doesn't thematically match "breaking morale" at all — unclear
whether this zone's text block has a further zone-specific offset on just this one entry, or
whether the SQL comment's mission name is simply wrong. Went with the mob data (concrete, real
IDs) over the text mismatch; modeled as kill-all-18, same shape as Preemptive Strike.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[14]`.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Mamool_Ja_Recruit.lua`,
  `Mamool_Ja_Trainer.lua` — new, kill-all pattern.
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/breaking_morale.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 14 enabled, start pos reuses this
  zone's Rune of Release spot (same as rows 11/13).

### Evade and Escape — Lebros Cavern (mission 24)
3 real Dahak, comment-labeled "-- Evade and Escape". No other prop/NPC data found for an actual
evade/escape mechanic, so modeled as kill-all-3 — **unverified**, real text ("Discover
alternate route") suggests this might actually be a locate/route mission rather than combat.
- `scripts/zones/Lebros_Cavern/IDs.lua` — added `mob[24]` (was an empty stub before).
- `scripts/zones/Lebros_Cavern/mobs/Dahak.lua` — new, kill-all pattern.
- `scripts/zones/Lebros_Cavern/instances/evade_and_escape.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 24 enabled, start pos reuses this
  zone's Rune of Release spot (same as row 22).

### Shooting Down the Baron — Periqia (mission 34)
Black Baron (boss) + 5 Periqia Pugil (obstacles), comment-labeled "-- Shooting Down the Baron".
Real objective text is singular ("Eliminate the Black Baron"), matching the Sagelord Elimination
single-kill pattern exactly — highest confidence of this batch. Bonus: this zone's
`Ancient_Lockbox.lua` already had this mission's real LSB reward data sitting in a comment from
an earlier session (never wired in because the mission didn't exist yet) — wired it in for
real this time, not a placeholder.
- `scripts/zones/Periqia/IDs.lua` — added `mob[34]`.
- `scripts/zones/Periqia/mobs/Black_Baron.lua` — new, single-kill pattern (Periqia Pugil left
  unscripted, same as Sagelord's trainee/lizard trash).
- `scripts/zones/Periqia/instances/shooting_down_the_baron.lua` — new.
- `scripts/zones/Periqia/npcs/Ancient_Lockbox.lua` — added real `Q_ITEMS[34]`/`REG_ITEMS[34]`
  (???_bow/???_box qItem split, 4-pool regItem table). Caught and fixed 2 item-ID transcription
  errors while wiring this in (4120 is X-Potion not Hi-Potion+3; 4193 is a Windurst gate glyph
  not Hi-Reraiser) — corrected against `item_basic.sql` before finalizing.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 34 enabled, start pos reuses this
  zone's Rune of Release spot (same as row 33).

### Demolition Duty — Ilrusi Atoll (mission 44) — SCAFFOLD ONLY
Unlike the other 4, this one only has a bare `mob_pools` row (973, 'Demolition_Automaton') with
zero placement data anywhere — no `mob_spawn_points` rows, no `mob_groups` rows referencing that
poolid, checked both. The `mob_spawn_points.sql` comment block ("ids 17002545 to 17002550...
are NPCs") is aspirational, not backed by actual rows. Registers and is walkable
(Rune of Release + Ancient Lockbox only) but has no objective content — same tier as the
original Orichalcum Survey/Lamia No.13 scaffolds. Real objective text is
`ASSAULT_44_START` = "Demolish the shipwrecks"; poolid 973 is the lead for future work.
- `scripts/zones/Ilrusi_Atoll/instances/demolition_duty.lua` — new, bare scaffold.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 44 enabled (Npcs only).

## C-rank build-out — all 5 zones (2026-08-18)

Continued rank-by-rank. Weaker yield than LC-rank: only 2 of 5 zones had real, fully-usable
data this time; a 3rd had partial data (real trash mobs, no objective-critical NPC); 2 were
comment-only with zero backing rows anywhere (checked npc_list directly, not just assumed).
Building all 5 anyway per the "framework first" approach — IDs/mobs/NPCs in place where they
exist, honest scaffolds where they don't.

### Siegemaster Assassination — Lebros Cavern (mission 25) — REAL DATA
8 real Old_Troll, comment-labeled "-- Siegemaster Assassination". Real objective text names a
specific target ("Assassinate Borgerlur") but all 8 are identical generic entries with no way
to distinguish a unique NM among them — modeled as kill-any-1-of-8. **Flag**: real retail likely
has Borgerlur as a separately-named unique spawn this data set doesn't capture.
- `scripts/zones/Lebros_Cavern/IDs.lua` — added `mob[25]`.
- `scripts/zones/Lebros_Cavern/mobs/Old_Troll.lua` — new.
- `scripts/zones/Lebros_Cavern/instances/siegemaster_assassination.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 25 enabled.

### Building Bridges — Periqia (mission 35) — REAL DATA
4 real, individually-positioned Bridge_Switch NPCs in `npc_list.sql` — NOT the ids the
`mob_spawn_points.sql` "-- building bridges" comment claims (17006664-17006678, "various
Lamia"); that range has zero backing rows anywhere, confirmed by direct lookup, not assumed.
Trigger-all-4 pattern, matching real text ("Activate the bridge").
- `scripts/zones/Periqia/IDs.lua` — added the 4 `BRIDGE_SWITCH` npc entries.
- `scripts/zones/Periqia/npcs/Bridge_Switch.lua` — new, trigger-once pattern.
- `scripts/zones/Periqia/instances/building_bridges.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 35 enabled.

### The Double Agent — Mamool Ja Training Grounds (mission 15) — PARTIAL DATA
The mission's actual objective-critical content (26 "Qiqirn Spy" NPC ids the SQL comment
claims exist) has zero backing rows — checked directly, doesn't exist. 9 real Puk mobs
immediately after that comment DO exist, so they're spawned as ambient trash only (not tied to
progress — no way to identify "the spy" among them). Registers and is walkable but won't
complete until real spy NPC data surfaces.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[15]` (9 Puk, ambient only).
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/the_double_agent.lua` — new, scaffold +
  ambient trash.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 15 enabled.

### Counting Sheep — Leujaoam Sanctum (mission 5) — SCAFFOLD ONLY
"-- Counting Sheep" comment claims ids 17059911-17059935 are NPCs; zero backing rows anywhere.
Real objective text ("Buy black sheep") suggests a trade/vendor mechanic, not combat — nothing
to build without the actual vendor NPC data.
- `scripts/zones/Leujaoam_Sanctum/instances/counting_sheep.lua` — new, bare scaffold.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 5 enabled (Npcs only).

### Searat Salvation — Ilrusi Atoll (mission 45) — SCAFFOLD ONLY
"-- searat salvation" comment claims ids 17002564-17002576 (Qiqirn Chief Diver, Qiqirn Diver,
Giant Orobon) are NPCs; zero backing rows anywhere. Real objective text ("Save the Qiqirn
divers") matches the comment's theme closely — likely a rescue/escort mission like Saving
Private Ryaaf once the diver NPC data surfaces.
- `scripts/zones/Ilrusi_Atoll/instances/searat_salvation.lua` — new, bare scaffold.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 45 enabled (Npcs only).

## S-rank build-out — all 5 zones (2026-08-18)

Continued rank-by-rank. Caught and fixed a real off-by-one of my own partway through: Leujaoam
Sanctum's actual next-rank slot is mission 6 (**Supplies Recovery**, real data, previously
missed because I only grepped for "Azure Experiments" first and built that at mission 6 without
checking `instance_list.sql`'s own placeholder name for that row first — it says
`supplies_recovery`). Corrected before going live: Supplies Recovery is mission 6, Azure
Experiments is mission 7 — same class of mistake as the Building Bridges/Shooting Down the
Baron reorder from the LC-rank batch, same fix (trust the file's own row names, not a
theme-matching guess).

### Supplies Recovery — Leujaoam Sanctum (mission 6) — REAL DATA
10 real Imp + 1 Gasharyad + 1 Salimuhl, all with real individually-captured coordinates,
comment-labeled "-- supplies recovery". Bonus: this zone's `npc_list.sql` also had this
mission's real Rune of Release/Ancient Lockbox position sitting in an inline comment — used it
as the instance start position instead of reusing another mission's spot. Real text matches
("Retrieve the supplies"). `Imp.lua` already existed for this zone (used by non-instanced
content elsewhere) — added the progress hook with a `getInstance()` nil-guard rather than
overwriting the file, so it stays a no-op for any Imp spawned outside this instance.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[6]`.
- `scripts/zones/Leujaoam_Sanctum/mobs/Imp.lua` — edited (pre-existing file), added guarded
  `onMobDespawn`. `Gasharyad.lua`, `Salimuhl.lua` — new.
- `scripts/zones/Leujaoam_Sanctum/instances/supplies_recovery.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 6 enabled, start pos from the real
  captured comment coordinates.

### Azure Experiments — Leujaoam Sanctum (mission 7) — REAL DATA
10 real mobs (4 Lamia Prosector, 3 Lamia Bowyer, 3 Lamia Sharper), comment-labeled "-- Azure
Experiments". Real text ("Become a test subject") matches well. Modeled as kill-all-10.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[7]`.
- `scripts/zones/Leujaoam_Sanctum/mobs/Lamia_Prosector.lua`, `Lamia_Bowyer.lua`,
  `Lamia_Sharper.lua` — new.
- `scripts/zones/Leujaoam_Sanctum/instances/azure_experiments.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 7 enabled.

### Stop the Bloodshed — Periqia (mission 36) — REAL DATA, highest confidence
38 real mobs (3 Chigoe Breeder + 35 Augmented Chigoe), all with real individually-captured
coordinates (rare for this session's trash — most placeholder-tier mobs use 0,0,0 stubs).
Comment-labeled right after Shooting Down the Baron's block. Real text ("Exterminate the
chigoes") matches exactly. Modeled as kill-all-38.
- `scripts/zones/Periqia/IDs.lua` — added `mob[36]`.
- `scripts/zones/Periqia/mobs/Chigoe_Breeder.lua`, `Augmented_Chigoe.lua` — new.
- `scripts/zones/Periqia/instances/stop_the_bloodshed.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 36 enabled.

### Apkallu Seizure — Ilrusi Atoll (mission 46) — REAL DATA
8 real Kelp Pugil, comment-labeled "-- apkallu seizure". **Flag**: real text ("Capture the
apkallu") suggests a capture mechanic, and Kelp Pugil aren't obviously "the apkallu" — modeled
as kill-all-8 pending better data.
- `scripts/zones/Ilrusi_Atoll/IDs.lua` — added `mob[46]`.
- `scripts/zones/Ilrusi_Atoll/mobs/Kelp_Pugil.lua` — new.
- `scripts/zones/Ilrusi_Atoll/instances/apkallu_seizure.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 46 enabled.

### Imperial Treasure Retrieval — Mamool Ja Training Grounds (mission 16) — SCAFFOLD ONLY
"-- imperial treasure retrieval" comment claims ids 17047683-17047689 are NPCs; zero backing
rows anywhere. Real text: "Recover the treasure".
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/imperial_treasure_retrieval.lua` — new,
  bare scaffold.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 16 enabled (Npcs only).

### Apkallu Breeding — Lebros Cavern (mission 26) — SCAFFOLD ONLY
"-- Apkallu Breeding" comment claims ids 17035336-17035351 (Lebros Apkallu) are NPCs; zero
backing rows anywhere. Real text: "Match the Apkallu".
- `scripts/zones/Lebros_Cavern/instances/apkallu_breeding.lua` — new, bare scaffold.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 26 enabled (Npcs only).

## SM-rank build-out — all 5 zones (2026-08-18)

Best yield yet — 5 for 5 zones had real, usable mob data this rank (a first this session; every
prior rank had at least one scaffold-only zone). All modeled as kill-all, same established
pattern.

### Imperial Code — Leujaoam Sanctum (mission 8) — REAL DATA
26 real mobs, all with real individually-captured coordinates — 16 Kusa, 3 named uniques
(Saizo, Oko, Danzo — all ninja-themed, fitting the mission name), 7 Kudagitsune.
Comment-labeled "-- Imperial code @ -320 -4 -440.7 rot 142". Real text ("Retrieve the OGMA")
fits an espionage theme. Modeled as kill-all-26.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[8]`.
- `scripts/zones/Leujaoam_Sanctum/mobs/Kusa.lua`, `Saizo.lua`, `Oko.lua`, `Danzo.lua`,
  `Kudagitsune.lua` — new.
- `scripts/zones/Leujaoam_Sanctum/instances/imperial_code.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 8 enabled.

### Blitzkrieg — Mamool Ja Training Grounds (mission 17) — REAL DATA
27 real mobs (5 each of Molted Puk/Lindwurm/Bugard/Ziz/Mamool Ja, plus unique Bluethunder
Kaqool Ja and Festive Firedrake), comment-labeled "-- blitzkrieg". A trailing comment claims id
17047717 (Lumaayu) is an NPC — not backed (checked), left out. Real text ("Annihilate the
enemy") fits a large kill-all. Modeled as kill-all-27.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[17]`.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Molted_Puk.lua`, `Molted_Lindwurm.lua`,
  `Molted_Bugard.lua`, `Molted_Ziz.lua`, `Molted_Mamool_Ja.lua`, `Bluethunder_Kaqool_Ja.lua`,
  `Festive_Firedrake.lua` — new.
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/blitzkrieg.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 17 enabled.

### Egg Conservation — Lebros Cavern (mission 28) — REAL DATA
6 real Qiqirn Eggler, comment-labeled "-- Egg Conservation". A comment also claims ids
17035380-17035395 (Lebros Apkallu) are NPCs — not backed (checked), same unbacked-comment
pattern seen repeatedly this session. Real text ("Drive out the hunters") fits the egglers.
Modeled as kill-all-6.
- `scripts/zones/Lebros_Cavern/IDs.lua` — added `mob[28]`.
- `scripts/zones/Lebros_Cavern/mobs/Qiqirn_Eggler.lua` — new.
- `scripts/zones/Lebros_Cavern/instances/egg_conservation.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 28 enabled.

### Defuse the Threat — Periqia (mission 37) — REAL DATA
7 real Qiqirn Miner, comment-labeled "-- defuse the threat". A comment claims ids
17006717-17006731 (Qiqirn_Mine) are NPCs — not backed (checked). **Note**: this is a separate
"Qiqirn Mine" set-piece from Lebros Cavern's `Qiqirn_Mine.lua` countdown/detonation mechanic —
no evidence this mission reuses that system, just plain miners to kill. Real text ("Clear the
mine fields") fits. Modeled as kill-all-7.
- `scripts/zones/Periqia/IDs.lua` — added `mob[37]`.
- `scripts/zones/Periqia/mobs/Qiqirn_Miner.lua` — new.
- `scripts/zones/Periqia/instances/defuse_the_threat.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 37 enabled.

### Lost and Found — Ilrusi Atoll (mission 47) — REAL DATA
5 real Kelp Kulshedra + 3 real Kelp Crab, comment-labeled "-- lost and found". **Flag**: real
text ("Find the ring") doesn't obviously match a Kulshedra/Crab kill mission. Modeled as
kill-all-8 pending better data.
- `scripts/zones/Ilrusi_Atoll/IDs.lua` — added `mob[47]`.
- `scripts/zones/Ilrusi_Atoll/mobs/Kelp_Kulshedra.lua`, `Kelp_Crab.lua` — new.
- `scripts/zones/Ilrusi_Atoll/instances/lost_and_found.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 47 enabled.

## CS-rank build-out — all 5 zones (2026-08-18)

5 for 5 real data again. Large mob counts this rank (up to 27 per mission) — before writing ~65
individual per-mob `.lua` files, spawned a background research agent to check whether the
engine has any family-level or zone-wide fallback for `onMobDespawn` that would let multiple
mobs share one file. Confirmed answer: no — `luautils.cpp`'s `getEntityCachedFunction` looks up
the exact literal mob name every time, no fallback exists for despawn (unlike `onMobDeath`,
which does have a real global `onMobDeathEx` hook in `scripts/globals/mobs.lua`, though that
still doesn't replace the required per-mob file). Kept the established per-pool-name-file
pattern, but generated the boilerplate via shell loops instead of one Write call per file —
same content, much faster. Correctly wrote only ONE file per unique *pool* name even when a
mission spawns many instances of it (e.g. `Marid.lua` once, not 8 times), unlike my first pass
at the IDs.lua tables, which needed distinct table keys per instance (`MARID1`..`MARID8`) —
those two things are not the same granularity and it's easy to conflate them.

### Imperial Code — Leujaoam Sanctum (mission 8) — REAL DATA
26 real mobs, all real coordinates — 16 Kusa, 3 named uniques (Saizo, Oko, Danzo — ninja-themed,
matching the mission name), 7 Kudagitsune. Real text ("Retrieve the OGMA") fits an espionage
theme. Kill-all-26.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[8]`.
- `scripts/zones/Leujaoam_Sanctum/mobs/Kusa.lua`, `Saizo.lua`, `Oko.lua`, `Danzo.lua`,
  `Kudagitsune.lua` — new.
- `scripts/zones/Leujaoam_Sanctum/instances/imperial_code.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 8 enabled.

### Red versus Blue — Leujaoam Sanctum (mission 9) — REAL DATA
27 real, individually-named/positioned mobs. A comment notes 9 of them "start as npcs then turn
into mobs" — an ambush/reveal mechanic not modeled. Real text names one specific target
(Raubahn) among the 27 — modeled as kill-all-27 rather than singling him out.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[9]`.
- `scripts/zones/Leujaoam_Sanctum/mobs/` — 27 new single-mob scripts (Shailham, Dhiadjhar,
  Zhadjaraf, Ganmuul, Jalyaat, Rahdjab, Ghahnis, Tahbmar, Rhushouf, Raubahn, Ghayaraan, Krinahal,
  Varajahl, Mareyamad, Shayaam, Habraheem, Qudeen, Salyhaar, Sharayaan, Ubdeen, Bashdeel,
  Wharadi, Hkadouf, Afrhaad, Nareema, Udhaaman, Yhalbin).
- `scripts/zones/Leujaoam_Sanctum/instances/red_versus_blue.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 9 enabled.

### Marids in the Mist — Mamool Ja Training Grounds (mission 18) — REAL DATA
26 real, individually-positioned mobs (8 Marid, 3 Chigoe, 15 Breeder/Mahout/Farrier). A comment
notes the Chigoe are "spawned by marids 3 maximum" (an add mechanic, not modeled). Real text
matches exactly ("Neutralize the marids"). Kill-all-26. `Chigoe.lua` written with a
`getInstance()` nil-guard as a precaution (bare `Chigoe` pool name could theoretically appear
elsewhere in this zone's data).
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[18]`.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Marid.lua`, `Chigoe.lua`,
  `Mamool_Ja_Breeder.lua`, `Mamool_Ja_Mahout.lua`, `Mamool_Ja_Farrier.lua` — new.
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/marids_in_the_mist.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 18 enabled.

### Operation: Black Pearl — Lebros Cavern (mission 29) — REAL DATA
25 real mobs (Jorporbor the Hellraker, 4 Troll Combatant, 20 Wamouracampa). **Judgment call**:
cut the block at the Wamouracampa group since a Crimson Eruca/Vulcanian Bomb block follows with
no comment boundary — judged to belong to the next mission (Better Than One) instead, but
there's no hard marker either way. **Flag**: real text ("Rescue Princess Kadjaya") doesn't
match this combat-only data at all.
- `scripts/zones/Lebros_Cavern/IDs.lua` — added `mob[29]`.
- `scripts/zones/Lebros_Cavern/mobs/Jorporbor_the_Hellraker.lua`, `Troll_Combatant.lua`,
  `Wamouracampa.lua` — new.
- `scripts/zones/Lebros_Cavern/instances/operation_black_pearl.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 29 enabled.

### Operation: Snake Eyes — Periqia (mission 38) — REAL DATA
15 real mobs (5 Qutrub, 5 Merrow Shadowdancer, 5 named uniques: Merrow No.16, Karazahm, Lamia
No.14, Umarid, Lamia No.17). Real text ("Locate the generals") plausibly fits the named uniques.
Kill-all-15.
- `scripts/zones/Periqia/IDs.lua` — added `mob[38]`.
- `scripts/zones/Periqia/mobs/Qutrub.lua`, `Merrow_Shadowdancer.lua`, `Merrow_No16.lua`,
  `Karazahm.lua`, `Lamia_No14.lua`, `Umarid.lua`, `Lamia_No17.lua` — new.
- `scripts/zones/Periqia/instances/operation_snake_eyes.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 38 enabled.

### Deserter — Ilrusi Atoll (mission 48) — REAL DATA
22 real, individually-positioned mobs (Lamia/Merrow/Draugar mix). **Flag**: real text ("Locate
the agents") is a loose fit. Kill-all-22.
- `scripts/zones/Ilrusi_Atoll/IDs.lua` — added `mob[48]`.
- `scripts/zones/Ilrusi_Atoll/mobs/K22B6-LAMIA.lua`, `K22H3-LAMIA.lua`, `K22P2-LAMIA.lua`,
  `D5R3-MERROW.lua`, `D5J2-MERROW.lua`, `D5S1-MERROW.lua`, `Draugar.lua` — new.
- `scripts/zones/Ilrusi_Atoll/instances/deserter.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 48 enabled.

## SL-rank build-out — all 5 zones (2026-08-18)

5 for 5 real data again — every zone had a comment-labeled block with real backing rows this
rank. Mob counts ranged from 2 (Bloody Rondo) to 62 (Azure Ailments), the widest spread yet.
`instance_entities.sql` additions for this rank (144 rows) were generated via shell loop and
inserted with a small PowerShell splice (find the `ENABLE KEYS` marker line, insert before it)
rather than hand-editing — same content as every other addition this session, just faster to
produce accurately at this volume.

### Bloody Rondo — Leujaoam Sanctum (mission 10) — REAL DATA
Count Dracula (real coordinates) + Cursed Doppelganger, comment-labeled "-- Bloody Rondo
entrance @ 424 4.3 -341 rot 0". Real text matches exactly ("Defeat the count"). Kill-all-2.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` — added `mob[10]`.
- `scripts/zones/Leujaoam_Sanctum/mobs/Count_Dracula.lua`, `Cursed_Doppelganger.lua` — new.
- `scripts/zones/Leujaoam_Sanctum/instances/bloody_rondo.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 10 enabled.

### Azure Ailments — Mamool Ja Training Grounds (mission 19) — REAL DATA
62 real mobs across 8 pool types (6 Mamool Ja Warder, 8 each of Bugard/Pit Lindwurm/Poroggo/Huge
Spider/Leech/Slavering Lizard/Qiqirn Huckster) — largest single mission built this session.
Comment-labeled "-- azure ailments". Real text ("Gather pathological data") fits this
disease-vector-themed swarm well. Kill-all-62.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[19]`.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Mamool_Ja_Warder.lua`, `Bugard.lua`,
  `Pit_Lindwurm.lua`, `Poroggo.lua`, `Huge_Spider.lua`, `Leech.lua`, `Slavering_Lizard.lua`,
  `Qiqirn_Huckster.lua` — new (8 files covering all 62 spawns, one per pool name).
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/azure_ailments.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 19 enabled.

### Better Than One — Lebros Cavern (mission 30) — REAL DATA
Black Shuck (real coordinates, boss) + 6 Nocuous Inferno (obstacles), comment-labeled "-- Better
than one". Real text matches exactly ("Defeat Black Shuck") — singular target, same pattern as
Sagelord Elimination/Shooting Down the Baron. Only Black Shuck tracked.
- `scripts/zones/Lebros_Cavern/IDs.lua` — added `mob[30]`.
- `scripts/zones/Lebros_Cavern/mobs/Black_Shuck.lua` — new.
- `scripts/zones/Lebros_Cavern/instances/better_than_one.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 30 enabled.

### Wake the Puppet — Periqia (mission 39) — REAL DATA
31 real Wight, comment-labeled "-- wake the puppet". A comment also claims ids
17006764-17006769 (Maymuns) are NPCs — not backed (checked). **Flag**: real text ("Retrieve the
Mark-IIs") doesn't match a Wight swarm at all. Kill-all-31.
- `scripts/zones/Periqia/IDs.lua` — added `mob[39]`.
- `scripts/zones/Periqia/mobs/Wight.lua` — new.
- `scripts/zones/Periqia/instances/wake_the_puppet.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 39 enabled.

### Desperately Seeking Cephalopods — Ilrusi Atoll (mission 49) — REAL DATA
30 real, individually-positioned Qiqirn Pecheur, comment-labeled "-- desperately seeking @
-20.621 7.59 250 .441 rot 30". A separate group of 6 "fished" mobs (Giant Pugil, Puffer Pugil,
Clipper, Snipper, Kraken, Orobon) sits at placeholder (1,1,1,1) coordinates — left unspawned
since they represent a fishing-rod encounter mechanic, not a normal placement; spawning them at
a nonsense position would've been worse than leaving them out. Real text ("Collect ahtapot")
matches this fishing mechanic. Kill-all-30 using only the real-position Qiqirn Pecheur.
- `scripts/zones/Ilrusi_Atoll/IDs.lua` — added `mob[49]`.
- `scripts/zones/Ilrusi_Atoll/mobs/Qiqirn_Pecheur.lua` — new.
- `scripts/zones/Ilrusi_Atoll/instances/desperately_seeking_cephalopods.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 49 enabled.

## FL-rank build-out — final 3 missions, ALL 50 ASSAULT MISSIONS NOW BUILT (2026-08-18)

Leujaoam Sanctum and Lebros Cavern both completed their full 10-mission runs during the SL-rank
batch, so this final rank only needed 3 missions instead of 5. All 3 had real data, and all 3
were clean singular-boss kills with real text matches — the highest-confidence rank of the
entire run. Verified after building: `grep` for any still-commented `instance_list` row in the
1-50 range returns zero matches — every Assault mission row is now enabled. (14 rows past 50
remain commented, but those are Nyzul Isle/Ra'Kaznar/other non-Assault instance content,
outside this project's scope.)

### The Susanoo Shuffle — Mamool Ja Training Grounds (mission 20) — REAL DATA
Orochi (real coordinates), a single boss, comment-labeled "-- The susanoo shuffle". Real text
matches exactly ("Defeat Orochi"). This completes Mamool Ja Training Grounds' 10 missions.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added `mob[20]`.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Orochi.lua` — new.
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/the_susanoo_shuffle.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 20 enabled.

### The Price Is Right — Periqia (mission 40) — REAL DATA
King Goldemar (real coordinates, boss) + 6 obstacle mobs, comment-labeled "-- price is right
entrance @ 380 0.3 144 rot 64". Real text matches exactly ("Assassinate King Goldemar"). This
completes Periqia's 10 missions.
- `scripts/zones/Periqia/IDs.lua` — added `mob[40]`.
- `scripts/zones/Periqia/mobs/King_Goldemar.lua` — new (the 6 obstacle mobs are unscripted,
  same as other boss-mission trash this session).
- `scripts/zones/Periqia/instances/the_price_is_right.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 40 enabled.

### Bellerophon's Bliss — Ilrusi Atoll (mission 50) — REAL DATA, FINAL MISSION
Khimaira 14X (real coordinates, boss) + Martial Maestro Megomak, comment-labeled "-- Bellerophon
bliss @ -464 0.30 -540 rot 0". Real text matches exactly ("Defeat Khimaira 14X"). This completes
Ilrusi Atoll's 10 missions — and with it, all 5 zones × 10 ranks = **all 50 Assault missions**
now have working instance scripts, real (or honestly-flagged placeholder) mob/NPC data, and live
`instance_list`/`instance_entities` rows.
- `scripts/zones/Ilrusi_Atoll/IDs.lua` — added `mob[50]`.
- `scripts/zones/Ilrusi_Atoll/mobs/Khimaira_14X.lua` — new.
- `scripts/zones/Ilrusi_Atoll/instances/bellerophons_bliss.lua` — new.
- `sql/instance_entities.sql`, `sql/instance_list.sql` — row 50 enabled.

## Summary: full 50-mission build

Final tier breakdown across the whole rank-by-rank run (PSC through FL):
- **Real, comment-labeled SQL data found and wired in**: the large majority of missions across
  every rank except a handful of scaffold-only cases.
- **Scaffold-only (registers, walkable, no objective content)**: Orichalcum Survey (2), Lamia
  No.13 (42, later upgraded to real), Demolition Duty (44), Imperial Treasure Retrieval (16),
  Apkallu Breeding (26), Counting Sheep (5), Searat Salvation (45), The Double Agent (15,
  partial — real trash mobs but no identifiable spy).
- **Recurring caveats flagged throughout, not silently resolved**: several real-text/mission-name
  mismatches (Breaking Morale, Azure Experiments-vs-Supplies-Recovery reorder, Apkallu Seizure,
  Lost and Found, Operation Black Pearl, Wake the Puppet, Deserter), two mid-session
  mis-numbering catches (Building Bridges/Shooting Down the Baron; Supplies Recovery/Azure
  Experiments), and multiple "mechanic not modeled" notes (mine defuse/retrieve, ambush
  npc-to-mob transitions, fishing-rod encounters, hidden-NM-among-generic-trash).
- Every mission uses the same `tpz.instance`/`SpawnMob`/`GetNPCByID` framework already
  established for the first PSC/PFC/SP builds, so logic refinement (real mechanics, real reward
  tables, real start-position fine-tuning) can happen mission-by-mission later without touching
  the scaffolding.

## `!warpassault` GM command — extended to cover all 50 missions + added leave/list (2026-08-18)

`scripts/commands/warpassault.lua` already existed (built in an earlier session) but only knew
about the 13 instance ids that existed before this session's build-out, and only supported
entering an instance — no way to leave one early without playing through the real completion/
failure sequence.

- **Table regenerated directly from `sql/instance_list.sql`** (not hand-transcribed) — now
  covers all 56 rows currently enabled: all 50 Assault missions plus the 6 pre-existing
  non-Assault instanced zones (The Black Coffin, Against All Odds, Path of Darkness, Nashmeira's
  Plea, Arrapago Remnants, Shades of Vengeance) that were already in the old table.
- **Added `!warpassault leave`** — the "active mission" value is
  `CCharEntity::m_assaultLog.current`, exposed to Lua as `getCurrentAssault()`/`addAssault()`/
  `delAssault()` (all three already existed in `lua_baseentity.cpp`, just never wired into this
  command). `leave` reads the player's current assault, warps them to that mission's
  `entrance_zone` at `(0,0,0,0)`, and calls `delAssault()` to clear the flag — the exact same
  `setPos(0,0,0,0,<entrance>)` pattern every real `Rune_of_Release.lua`/csid-102 exit sequence
  already uses (verified against `Periqia/npcs/Rune_of_Release.lua`), just invoked directly
  instead of through a cutscene.
- **Added `!warpassault list`** — prints all valid instanceids + names in the log so you don't
  need to open the SQL file to know what number to use.
- Entering a new assault while one is already active now calls `delAssault()` on the old one
  first (previously `addAssault()` would silently overwrite `m_assaultLog.current` and only log
  a server-console warning) — keeps the quest-log packet and save state consistent instead of
  relying on the overwrite behavior.

### `!warpassault` in-game error: "undefined procedure onInstanceCreated" — root-caused, Lua workaround applied (2026-08-18)

The `onInstanceCreated(player, target, instance)` callback in `warpassault.lua` never actually
ran. Root cause, traced through `src/map/instance_loader.cpp` and `src/map/lua/luautils.cpp`:

- `CInstanceLoader::Check()` calls `luautils::OnInstanceCreated(requester, instance)` once the
  async instance load finishes. That function resolves the Lua callback via
  `GetCacheEntryFromFilename(PChar->m_event.Script)["onInstanceCreated"]`.
- `PChar->m_event.Script` is **only** ever set by the NPC-trigger code path (`OnTrigger`/
  `OnTrade` in `luautils.cpp`) or by `OnRegionEnter` (which sets it to the player's *current*
  zone's `Zone.lua`). GM commands run through `commandhandler.cpp`, which never touches
  `m_event.Script` at all — it's empty, so the lookup always fails.
- The engine then falls back to `./scripts/zones/<player's current zone>/Zone.lua`. Checked:
  **no `Zone.lua` in the entire codebase defines `onInstanceCreated`** — confirmed via a
  codebase-wide grep — so this always failed too, producing the error.
- This is why the original `onInstanceCreated` function inside `warpassault.lua` itself was
  always dead code — that file is never cached/looked-up the way NPC scripts are (commands are
  `lua.script_file()`'d fresh every invocation, not registered under `tpz.zones...`), so even a
  correctly-set `m_event.Script` could never resolve to it.
- Confirmed the real portal NPCs (e.g. `Caedarva_Mire/npcs/_272.lua`, the actual entrance to
  Leujaoam Sanctum) work fine because NPC triggers *do* set `m_event.Script` to the NPC's own
  file, which already defines its own `onInstanceCreated` — completely separate code path from
  the GM command, no conflict.

**Workaround applied (Lua-only, no C++ rebuild)**: added `onInstanceCreated` directly to
`scripts/zones/Leujaoam_Sanctum/Zone.lua`, exploiting the same fallback path the engine already
tries. **Correction to the caveat above**: re-read the C++ more carefully — the fallback does
*not* depend on `m_event.Script`/`OnRegionEnter` at all (which would've needed a registered
region, and this zone has none). It reads `PChar->loc.zone` directly — the character's actual
live zone — so the only requirement is being physically present in that zone when the command
runs, achievable deterministically via `!zone 69` first.

**Made the command fully self-contained (2026-08-18, same day)**: rather than expect the user to
`!zone` manually every time, `warpassault.lua`'s enter path now checks `player:getZoneID()`
itself. Wrong zone → prints the required zone id and calls `player:setPos(0,0,0,0,mission.zone)`
for them (same no-op-coords convention `scripts/commands/zone.lua` already uses for these 8
zones), then asks them to re-run the command. Right zone → proceeds straight to
`addAssault`/`createInstance` as before. Two invocations are unavoidable in the wrong-zone case
— zoning is asynchronous (`CInstanceLoader` runs on `std::async`), so there's no way to chain
"warp, wait for the zone change, then create+enter" inside one command call without the C++
fix. `!warpassault list` output now also shows each mission's zone id (`id(zZoneID)=name`) so
the requirement is visible without opening this file or the SQL.

Added the same `onInstanceCreated` fallback to the other 7 zones referenced in the
`assault_missions` table: Mamool_Ja_Training_Grounds, Lebros_Cavern, Periqia, Ilrusi_Atoll (the
4 remaining real Assault zones), plus The_Ashu_Talif, Nyzul_Isle, Arrapago_Remnants (the
pre-existing non-Assault legacy rows 53/54/58/59/65 already in the table before this session).
Removed the dead-code global `onInstanceCreated` that used to sit at the bottom of
`warpassault.lua` itself — confirmed unreachable (command scripts are re-executed fresh via
`commandhandler.cpp` every invocation, never cached the way NPC/zone scripts are, so nothing
can ever look it up) — and replaced it with a comment pointing to where the real handler now
lives, so a future reader doesn't reintroduce the same dead function.

### Server CRASH on second `!warpassault 1` — investigation + debug instrumentation (2026-08-18)

Tested the self-contained flow live: first `!warpassault 1` correctly detects the wrong zone
and moves the player to Leujaoam Sanctum (zone 69). Second `!warpassault 1` (now in the right
zone) logs the same "CLuaBaseEntity created with nullptr..." as before (expected/harmless, see
above) but does **not** land the player in the instance — and the server then crashes entirely
with no clean shutdown message in `log/map-server.log` (log just stops mid-stream).

**What the crash log revealed**: `log/map-server.log` has no exception trace, no
`ShowFatalError`, nothing — just silence right after the second `!warpassault` call. That's
consistent with an unhandled access violation, not a graceful engine error.

**Root cause investigation (before adding instrumentation)**: traced the full chain a live GM
command triggers, from `CInstanceLoader::Check()` → `luautils::OnInstanceCreated(PChar,
PInstance)` → our `Zone.lua` fallback → `setInstance`/`instanceEntry` → the client's actual
zone-transition packet → `CZoneInstance::IncreaseZoneCounter`. Found something significant along
the way: **Leujaoam Sanctum's zone type is `DUNGEON_INSTANCED`**, and `CZoneInstance::
IncreaseZoneCounter` (`src/map/zone_instance.cpp`) has pre-existing engine logic that
auto-creates a bare `CInstance(this, 0)` ("TEST") for *any* GM entering that zone with no
instance already registered — meant for "GM reconnecting after a disconnect" but firing
unconditionally, including for our first, un-instanced `!warpassault`-triggered zone move. That
phantom instance-0 gets registered, `onInstanceZoneIn` runs against it, and it's unclear whether
some state from that phantom object survives (or gets double-cleared) once our *second*
`!warpassault` call creates and registers the *real* mission-1 instance — `CZoneInstance::
DecreaseZoneCounter` unconditionally nulls `PChar->PInstance` on every zone-out, and there may
be a mismatch between which `CInstance*` is current at each step.

Also found two genuinely unguarded null-pointer dereferences along this path, independent of
whether they're the actual crash cause — both only ever exercised via the NPC-triggered flow in
practice, where the pointers are always valid, so they never crashed before:
- `luautils::AfterInstanceRegister` dereferences `PChar->PInstance` and `PChar->loc.zone`
  directly. The `TPZ_DEBUG_BREAK_IF(!PChar->PInstance)` guard above it is a **no-op in release
  builds** (`src/common/cbasetypes.h` — compiles to nothing outside a debug build), so this was
  never actually protected in the binary the user runs.
- `luautils::OnInstanceZoneIn` dereferences `PInstance` with no check at all.

**Instrumentation added (temporary, tagged `[WARPASSAULT DEBUG]` for easy removal)**: `ShowDebug`
prints bracketing every handoff in the chain, plus defensive early-returns (with `ShowError`)
on the two unguarded dereferences above instead of letting them crash:
- `src/map/instance_loader.cpp` — `CInstanceLoader::Check()`, before/after both
  `OnInstanceCreated` calls.
- `src/map/lua/luautils.cpp` — `OnInstanceCreated(CCharEntity*, CInstance*)` (before/after the
  Lua call, plus which resolution path fired), `OnInstanceZoneIn` (+ null guard),
  `AfterInstanceRegister` (+ null guard on `PInstance`/`loc.zone`).
- `src/map/lua/lua_baseentity.cpp` — `setInstance()`, `instanceEntry()` (+ null guard on
  `PTarget`).
- `src/map/instance.cpp` — `RegisterChar()`.
- `src/map/zone_instance.cpp` — `IncreaseZoneCounter()` (prints at entry, in the
  CharRegistered-recovery loop, and specifically flags the GM phantom-instance-0 fallback path
  if it fires) and `DecreaseZoneCounter()`.

**Update — rebuild succeeded, no crash this time, but still no entry**: user rebuilt with two
MSVC fixes (`C2446`: `? const int8* : "literal"` needs an explicit `(const int8*)` cast on the
literal, this codebase treats `int8`/`char` as unrelated pointer types — fixed in
`instance_loader.cpp` and `luautils.cpp`). Reproduced clean: no crash, and the debug log shows
**every server-side step succeeding** — instance loaded, `setInstance`, `RegisterChar`,
`instanceEntry` all ran with valid pointers, Lua's `onInstanceCreated` returned `valid=1`. The
`CInstanceEntryPacket` was genuinely pushed to the client. And then... nothing. No follow-up
zone-in packet, player stayed in the open Leujaoam Sanctum zone.

**Real root cause found**: checked every real caller of `instanceEntry()` in the codebase (all
NPC files) — every single one follows a `player:startEvent(...)` call, and `createInstance()`
itself is only ever invoked from inside that event's `onEventUpdate` (see `_272.lua`: `onTrigger`
opens csid 140, `onEventUpdate` calls `createInstance`, `onInstanceCreated` finally calls
`instanceEntry`). `instanceEntry()`'s packet is the **conclusion of an already-active
client-side event/menu sequence** — the client is sitting there expecting it because it opened
that menu. Our GM command never opens any such event (and can't cleanly replicate one — the
"confirm entry" cutscene belongs to the *portal* zone, e.g. Caedarva Mire, not the destination
zone we've already warped into), so the client has nothing to conclude and silently drops the
packet even though the server did everything right.

**Fix (Lua-only, no rebuild needed)**: replaced `player:instanceEntry(player, 4)` with
`player:setPos(0, 0, 0, 0, <this zone's own id>)` in all 8 `onInstanceCreated` fallbacks — the
same event-free zone-transition mechanism every mission's exit/failure handler already uses
successfully (`v:setPos(0,0,0,0,79)` pattern, confirmed working all session). This also
incidentally starves the phantom-TEST-instance bug: `CZoneInstance::IncreaseZoneCounter` only
creates that bogus instance when `PChar->PInstance` is null at zone-in time; calling
`setInstance(instance)` before the `setPos` means it's already set, so that branch is skipped
entirely and the real mission instance is what the zone-in resolves to.

**Next step**: user retests `!warpassault 1` (rebuild not required for this change — only the
`Zone.lua` edits changed). Keeping the `[WARPASSAULT DEBUG]` instrumentation in place for this
next round to confirm `IncreaseZoneCounter` picks up the real instance and skips the phantom
branch, then remove all debug lines once confirmed working.

## CONFIRMED WORKING — mission 1 (2026-08-18)

User confirmed `!warpassault 1` fully works: player lands in the real instance, debug log shows
`IncreaseZoneCounter` correctly recovering instanceid 1 via `CharRegistered()` and skipping the
phantom-TEST branch, `AfterInstanceRegister` fires clean with valid pointers. Also confirmed
`!warpassault 11` (Mamool Ja) enters cleanly — the fix is zone-generic (all 8 `Zone.lua` files
got the same `setPos` swap in the same pass, and `warpassault.lua`'s own logic was always
mission-agnostic), no further propagation needed.

Two new issues surfaced during that second test, both real and both unrelated to the core
warp mechanism itself:

### Mission 11 (Imperial Agent Rescue) — instance loads with zero mobs
Checked the Lua side first: `instances/imperial_agent_rescue.lua`'s `onInstanceCreated` spawns
`ID.mob[2]` (a pre-existing mislabeled table key — should read `[11]` for clarity, but the data
under `[2]` genuinely IS the correct 14-entity Imperial Agent Rescue set: 11 Mamool Ja Warder +
3 Dilapidated Gate, matching `sql/instance_entities.sql`'s real id-11 rows exactly). So the
spawn logic itself is correct. The debug log shows `CInstanceLoader::Check: instanceid 11
loaded` with no failure — and `CInstanceLoader::LoadInstance`'s SQL query treats zero returned
rows as success (the `Sql_NumRows(...) != 0` check is commented out), so an empty mob list is
consistent with the live DB simply not having these `instance_entities` rows applied yet
(Imperial Agent Rescue predates this session's work). Gave the user a targeted `INSERT IGNORE`
for instanceid 11's rows to test before assuming a deeper bug. Renaming the `[2]` key to `[11]`
would be a good follow-up cleanup once confirmed, purely for readability — not a functional fix.

### Real engine bug: re-entering an abandoned instanceid crashes the server
User abandoned instanceid 1 via `!warpassault` (warped elsewhere without ever calling
`instance:complete()`/`instance:fail()`), then ran `!warpassault 1` again shortly after —
crashed. Root cause: `CZoneInstance::CreateInstance(uint8 instanceid)` (`zone_instance.cpp`)
unconditionally created and pushed a brand-new `CInstance`, with **no check for an existing
instance already using that id**. The only cleanup path (`CZoneInstance::ZoneServer`'s per-tick
sweep) only erases an instance once `Failed() || Completed()` — which happens naturally when a
mission's own time limit elapses (~30 min per `instance_list.sql`) or someone finishes/fails it
properly, neither of which happens when a GM just warps away. So the old, abandoned
instanceid-1 object sat in `instanceList` indefinitely, and a second `createInstance(1, ...)`
call created a **second** live `CInstance` object also claiming id 1 — two objects with
duplicate entity ids, a very plausible crash mechanism (this is a pre-existing engine gap, not
something introduced this session — any code path that re-requests the same instanceid before
natural expiry would hit it, `!warpassault` just makes it trivial to trigger by testing multiple
missions in quick succession).

**Fix**: `CreateInstance` now checks `instanceList` for an existing entry with the same id
first. If found and truly abandoned (`CharListEmpty()` — nobody currently inside), erases it
before creating the new one, with a `[WARPASSAULT DEBUG]`-tagged `ShowWarning` either way (so
it's visible but distinguishable from a real problem). If real players are still inside, it
does **not** evict them — just creates a second instance and warns, matching prior behavior in
that case (should be rare/never in practice for a properly-completed or still-in-progress
instance). Requires a rebuild. Retest plan: enter mission 1, abandon via `!warpassault`
elsewhere, immediately re-enter mission 1 — should no longer crash.

## Second crash: re-running the same mission id while still inside it (2026-08-18)

User's rebuild with the `CreateInstance` guard confirmed working for the "abandon, then
re-enter" case — but hit a **different** crash: ran `!warpassault 11` a second time while
already actively standing inside the instance-11 session from the first run (no zone change in
between, so the "wrong zone → warp and ask to re-run" branch never triggered — the command sailed
straight through to `createInstance()` again). Log confirms exactly this:

```
CZoneInstance::CreateInstance: instanceid 11 already exists with active chars -- creating a
second instance with the same id anyway (not evicting real players)
```

The C++ guard correctly refused to evict the player from the instance they were still
registered to (right call — never evict active players) — but that only prevented the *wrong*
fix (kicking them out); it didn't prevent the *actual* problem: a second live `CInstance`
object with the same id now existed while the player was registered/active in both
simultaneously. The `setInstance()`/`setPos()` sequence that follows got confused about which
of the two same-id instances it was tearing down vs. entering, and the log cuts off silently
right after the second `DecreaseZoneCounter` — same signature as the earlier crashes.

**Fix (Lua-only, no rebuild)**: `warpassault.lua`'s enter path now checks `player:getInstance()`
*before* the zone check. If the player is already inside a live instance whose id matches the
one they're requesting, it refuses outright with a message pointing them at `!warpassault leave`
instead of ever calling `createInstance()` again. This closes the gap the C++ guard alone
couldn't safely close — evicting active players is wrong, creating a silent duplicate is also
wrong, so the right fix is to never ask for the duplicate in the first place. The C++ guard
from the previous fix is still needed and still correct for its own case (a *properly*-abandoned
instance, left via warp to a different mission/zone, then re-requested before its natural
~30-minute expiry) — this new Lua check handles the narrower "you never left at all" case that
sits in front of it.

## Real capture data mined: Windower packet/NPC-logger capture of Excavation Duty (2026-08-18)

User provided a zip of real Windower addon output (`npclogger`, `eventview`, `packetviewer`,
`caplog`) from an actual playthrough of Excavation Duty (Lebros Cavern, mission 21) — the first
real ground-truth data source used this session, as opposed to LSB cross-references or client
dialog-table exports. Two confirmed, applied fixes:

- **Drahbah's appraisal event id was wrong**: we had `startEvent(678, 500)` (matching LSB's own
  `Drahbah.lua`, which is apparently also off by one). The real capture shows
  `Event: 679, Params: 500, ...` for the exact same "appraise for 500 gil" interaction. Fixed to
  679 in `Aht_Urhgan_Whitegate/npcs/Drahbah.lua`. Chochoroon (260) and Memeroon (272) use the
  same LSB-derived pattern and are now suspect for the same off-by-one, but this capture doesn't
  cover them — still unverified, flagging for whenever capture data for Al Zahbi/Nashmau shows up.
- **Brittle Rock id 17035282's position was wrongly "fixed" earlier this session**: real capture
  confirms the sunken `y=-42.362` position (which we'd changed to `-32.9`, citing "prevented
  melee range") is the genuine retail position — confirmed independently by the fact that its
  identical twin, id 17035283, was *never* touched and already sat at `-42.362` in our own SQL
  the whole time. Reverted. The real fix for the melee-range symptom was almost certainly the
  separate `mob_family_system.sql` `GetMeleeRange()` tolerance widening for the "Structure"
  family (done earlier this session, shared by 17 mob_pools rows) — this position change was a
  redundant workaround stacked on top of the real fix.

**Also validated (no action needed, just confirms prior work was correct)**: Rune of Release's
completion event (csid 100), the mission-failure/exit event (csid 102), and Mount Zhayolm's
Runic Portal routing (csid 109) all match the real capture exactly. Excavation Duty's own
Rune of Release / Ancient Lockbox per-instance repositioning (`49.999,-40.837,96.999` /
`50.000,-40.070,99.999`) also matches exactly. Volcanic Bomb / Qiqirn Ceramist / Qiqirn
Volcanist positions differ from our SQL by small amounts (a few units) — normal roam variance
for wandering trash mobs between two different capture sessions, not a data bug, no action taken.

**Live-DB statement for the Brittle Rock fix**:
```sql
UPDATE `mob_spawn_points` SET pos_y = -42.362 WHERE mobid = 17035282;
```

**Still open**: mission 11 (Imperial Agent Rescue) mobs remain unconfirmed — user reports still
seeing none even near the repositioned Rune of Release/Ancient Lockbox coordinates
(`220, 1.5, -504`). Checked the full SQL join chain (`mob_spawn_points` → `mob_groups` →
`mob_pools` → `mob_family_system`) and it resolves cleanly with real non-zero coordinates;
confirmed `SpawnMob`/`SpawnMob` (capital-S global alias, auto-registered alongside the lowercase
`tpz.core.spawnMob` — not a typo) is correctly wired. Searched the full `map-server.log` for any
`SpawnMob: mob <...> not found` line near the mission-11 test — found none (only one unrelated
hit from a prior day's session) — which is consistent with the spawns succeeding silently
server-side (the success path logs nothing) rather than failing. Not yet resolved; next step is
confirming visually whether the mobs are present at the real coordinates once the crash-fix
retest is done, since that was tested in the same session as the eventual crash.

## Third bug: `!warpassault leave` didn't actually end the instance (2026-08-18)

The double-entry crash fix worked (confirmed: retrying the same mission id while still inside
now gets a friendly refusal instead of crashing). But testing `leave` surfaced the next layer of
the same underlying gap: `leave` only called `delAssault()` (clears
`CCharEntity::m_assaultLog.current`, a separate quest-log-style flag) and `setPos()` — it never
told the actual `CInstance` object it was being abandoned. That object just kept sitting in the
engine's `instanceList`, still holding the player's id in its `m_registeredChars`.

Repro from the user's log: leave mission 1 (assault log cleared, warped to Caedarva Mire) → walk
back into Leujaoam Sanctum by any means (not even re-running `!warpassault`) →
`CZoneInstance::IncreaseZoneCounter`'s normal "was I already registered somewhere" recovery
check (`CharRegistered()`) finds the same old un-failed instance and **silently reattaches the
player to it** — same mobs, same progress, nothing reset. A second `!warpassault leave` then
checked `getCurrentAssault()`, found it already 0 (cleared by the *first* `leave`), and wrongly
reported "no active assault to leave" even though the player was still very much inside a live
instance via `PChar->PInstance`.

**Fix (Lua-only, no rebuild)**: `leave` now checks `player:getInstance()` (the actual live
instance) instead of the separate assault-log flag, and — the real fix — calls `instance:fail()`
before warping out. `fail()` is an already-exposed Lua method (`CLuaInstance::fail()` →
`CInstance::Fail()`: `Cancel()`, `ClearEntities()`, runs the mission's own `onInstanceFailure`
handler, sets `m_status = INSTANCE_FAILED`) — the same real mechanism a mission uses when a
party wipes. Marking it properly failed means `CZoneInstance::ZoneServer`'s per-tick sweep
(`if (Failed() || Completed()) && CharListEmpty()`) actually erases it once the player has
zoned out, instead of leaving a zombie instance behind that keeps reattaching itself. This also
means the `CreateInstance` stale-instance guard from the earlier fix should now rarely if ever
need to fire its "already exists" warning path in practice — a properly-`leave`n instance is
just gone by the next tick.

## Fourth crash: client-side Debug Assertion, `vector erase iterator outside range` (2026-08-18)

Testing the `leave` fix crashed again — this time caught live in the Visual Studio debugger
(user launched via F5 instead of running the `.exe` standalone, then hit Retry on the assertion
dialog to break in). Call stack:

```
vector<unique_ptr<CInstance>>::erase()
CZoneInstance::DecreaseZoneCounter(CCharEntity*)   zone_instance.cpp:170
SmallPacket0x00D(...)
parse(...)
do_sockets(...)
```

**Real root cause, pre-existing engine bug**: the GM phantom-instance fallback in
`CZoneInstance::IncreaseZoneCounter` (`PChar->PInstance = new CInstance(this, 0);`, added
purely for "GM reconnecting after a disconnect" edge cases, first flagged as a suspect during
the very first crash investigation earlier this session) creates the instance with a **bare
`new`** and never adds it to `instanceList` — unlike every other instance in the codebase, which
goes through `CreateInstance()`'s `instanceList.push_back(std::make_unique<CInstance>(...))`.
It only ever existed via the raw pointer in `PChar->PInstance`, completely untracked and,
incidentally, leaked.

This had never crashed before because nothing had ever called `.fail()`/`.complete()` on one of
these throwaway phantom instances — until this session's `leave` fix started calling
`instance:fail()` unconditionally on whatever `player:getInstance()` returns, phantom or real.
Once `Failed()` was true on an untracked phantom, `DecreaseZoneCounter`'s
`instanceList.erase(std::find_if(...))` searched a list that had never contained it,
`std::find_if` returned `end()`, and erasing `end()` is undefined behavior — exactly matching
"vector erase iterator outside range" (caught by the `_ITERATOR_DEBUG_LEVEL == 2` check in a
Debug build; would likely have been silent heap corruption in Release).

**Fix, two parts, both in `zone_instance.cpp`, requires a rebuild**:
1. The real fix: the GM phantom-instance fallback now goes through the same
   `instanceList.push_back(std::make_unique<CInstance>(this, 0))` /
   `PChar->PInstance = instanceList.back().get()` pattern as `CreateInstance()` — properly
   tracked, erasable, no longer leaked.
2. Defense in depth: `DecreaseZoneCounter`'s erase now checks `it != instanceList.end()` before
   erasing, with a `[WARPASSAULT DEBUG]`-tagged `ShowWarning` instead of a crash if it's ever
   not found for any other reason in the future. Same "check before erase" pattern already used
   in the `CreateInstance` guard from the second crash fix.

Confirmed via `grep`: this was the only bare `new CInstance(...)` anywhere in the codebase — no
other call sites need the same fix.
- **Not yet tested.**

## Real capture data mined: Breaking Morale, Thris Nov 2025 capture set (2026-08-18)

User surfaced a much larger data source than the single one-off Excavation Duty zip: a private
Discord server ("FFXI Captures", `#missions-assault`) with nearly 5 years of posted capture
links, scraped into `D:\Claude\assault_captures\discord_link_index.md`. The November 2025
"Thris" set — one systematic "+Immunity testing" capture per mission, across all 5 zones, all
from one person in one week — was flagged as the highest-value batch. First one mined:
`breaking_morale.zip` (Mamool Ja Training Grounds, mission 14).

**Finding: this mission is not a kill-all**, contrary to how it was scaffolded earlier this
session (18 real Recruit/Trainer mobs found unwired in `mob_spawn_points.sql`, modeled as
kill-all-18 for lack of any other data at the time — see the mission's original write-up above).
The real objective text, `ASSAULT_14_START` ("Steal the supplies"), never actually fit a
kill-all reading, and the capture confirms why: CapLog shows a loot-and-turn-in loop against 10
real NPC entities that had never been added to `npc_list.sql` at all (7 rows were `-- NC:`
placeholders, 3 more didn't exist yet). Positions/looks pulled from the capture's NPCLogger
SQLite DB (`UniqueNo, Name, x, y, z, dir, model_id, legacy_look, legacy_flags`):

- **8x Supplies Crate** (real positions, model 59/128/128/192/96/223/0/160 — lootable props).
- **Quhaaja** (real position/look, id `17047821`) — the turn-in NPC.
- **Viscous Liquid** (real position, id `17047812`) — presumed hazard near the crates; capture
  didn't give enough behavioral detail to wire a specific mechanic, left unscripted.

KITrack only ever logged the generic "Obtained temporary item" line, never a fixed item name,
while CapLog's system messages named five different real items across different crates ("a wild
rabbit tail", "a piece of Attohwa ginseng", "a goblin die", "a pair of gilt glasses", "a fighting
fish tank" — items 542, 1683, 568, 579, 222 respectively). Modeled as a flavor loot pool (any one
of the five, randomly, one at a time) rather than inventing a single fake "Assault Supplies"
item that the capture never actually showed.

**Applied**:
- `sql/npc_list.sql` — converted the Breaking Morale block's `-- NC:` placeholder rows to real
  `INSERT`s, and added the 2 rows (Viscous Liquid, Quhaaja) that didn't exist at all. 10 rows
  total, ids `17047812`–`17047821`.
- `sql/instance_entities.sql` — added instance-id-14 rows for all 10 new entities.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` — added their `npc` table entries.
- `scripts/zones/Mamool_Ja_Training_Grounds/npcs/Supplies_Crate.lua` — new. Shared script for
  all 8 crates (one-file-per-repeated-prop convention, same as `Mining_Point.lua`). Grants one
  random item from the 5-item flavor pool via `addTempItem`; already holding one skips re-roll.
- `scripts/zones/Mamool_Ja_Training_Grounds/npcs/Quhaaja.lua` — new. Turn-in NPC: consumes
  whichever flavor item the player holds, advances `instance:setProgress()`.
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/breaking_morale.lua` — rewritten.
  Completion now fires at progress 8 (one per crate) instead of the old kill-count-18; the 18
  Recruit/Trainer mobs are still spawned (real data, real positions) but now function as ambient
  camp guards rather than kill objectives.
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Mamool_Ja_Recruit.lua` and
  `Mamool_Ja_Trainer.lua` — removed their `onMobDespawn` progress-increment (no longer kill
  targets).

**Caveats, not yet resolved**:
- The "8" completion count is an assumption, not confirmed by the capture — crates can be
  re-looted, so the real required count may be lower. No exact quota was unambiguous in the
  data available.
- Viscous Liquid is unscripted. Given the name and the "steal-back" pattern this session already
  found on other missions (e.g. Orichalcum Survey's worm hazard), it's plausibly an ambush that
  strips the temp item on pickup — but there wasn't enough capture detail to commit to a specific
  implementation, so it's left as a real, positioned, but inert NPC for now.
- Not yet tested in-game.

**Live-DB statements** (repo SQL dumps don't auto-apply — run manually against the live DB):
```sql
INSERT INTO `npc_list` VALUES (17047812,'Viscous_Liquid','Viscous Liquid',0,52.000,0.000,-298.000,0,50,50,0,0,0,0,3,0x0000320000000000000000000000000000000000,0,'TOAU',1);
INSERT INTO `npc_list` VALUES (17047813,'Supplies_Crate','Supplies Crate',59,-9.000,2.000,-229.000,0,50,50,0,0,0,6,3,0x0000C10300000000000000000000000000000000,0,'TOAU',1);
INSERT INTO `npc_list` VALUES (17047814,'Supplies_Crate','Supplies Crate',128,59.000,-4.000,-208.000,0,50,50,0,0,0,6,3,0x0000C10300000000000000000000000000000000,0,'TOAU',1);
INSERT INTO `npc_list` VALUES (17047815,'Supplies_Crate','Supplies Crate',128,-18.000,2.000,-378.000,0,50,50,0,0,0,6,3,0x0000C10300000000000000000000000000000000,0,'TOAU',1);
INSERT INTO `npc_list` VALUES (17047816,'Supplies_Crate','Supplies Crate',192,45.000,-1.000,-266.000,0,50,50,0,0,0,6,3,0x0000C10300000000000000000000000000000000,0,'TOAU',1);
INSERT INTO `npc_list` VALUES (17047817,'Supplies_Crate','Supplies Crate',96,11.000,-4.000,-225.000,0,50,50,0,0,0,6,3,0x0000C10300000000000000000000000000000000,0,'TOAU',1);
INSERT INTO `npc_list` VALUES (17047818,'Supplies_Crate','Supplies Crate',223,-13.000,-4.000,-247.000,0,50,50,0,0,0,6,3,0x0000C10300000000000000000000000000000000,0,'TOAU',1);
INSERT INTO `npc_list` VALUES (17047821,'Quhaaja','Quhaaja',154,18.000,2.000,-141.000,0,50,50,0,0,0,0,27,0x0001020510A520AB30A540A550A56177702D0000,0,'TOAU',1);
INSERT INTO `instance_entities` VALUES (14,17047812);
INSERT INTO `instance_entities` VALUES (14,17047813);
INSERT INTO `instance_entities` VALUES (14,17047814);
INSERT INTO `instance_entities` VALUES (14,17047815);
INSERT INTO `instance_entities` VALUES (14,17047816);
INSERT INTO `instance_entities` VALUES (14,17047817);
INSERT INTO `instance_entities` VALUES (14,17047818);
INSERT INTO `instance_entities` VALUES (14,17047819);
INSERT INTO `instance_entities` VALUES (14,17047820);
INSERT INTO `instance_entities` VALUES (14,17047821);
```
(ids 17047819/17047820 were already real rows in `npc_list.sql`, so only their `instance_entities`
link is new — no `npc_list` statement needed for those two.)

*(Amended 2026-08-18, later: this mission's `instance_list.sql` entrance was also fixed using
this same capture's PathLog — see the entrance-position table under the Imperial Agent Rescue
writeup below. `-55.000, 1.323, -103.000` r128 -> `19.000, 2.026, -136.000` r64.)*

## Real capture data mined: Evade and Escape, Thris Nov 2025 capture set (2026-08-18)

Second mission from the Thris batch (Lebros Cavern, mission 24). **Good news, no bug**: the
capture confirms the existing kill-all-3-Dahak scaffold is actually correct. CapLog shows the
real objective text ("Discover alternate route"), the fight against all 3 real Dahak
(`17035325`/`17035326`/`17035327`), and — the interesting detail — each Dahak kill lights up one
of 3 "Switch" NPCs (`17035481`/`17035482`/`17035483`, flavor text "A switch lights up on the
device... It is flickering faintly...", the third one instead saying "The switch on the device
is glowing brightly. You don't think it will fade any time soon."), immediately followed by
"Mission objective completed. Unlocking Rune of Release." So the real mechanic genuinely is
kill 3 Dahak → auto-complete, exactly matching `instance_object.onInstanceProgressUpdate`'s
existing `progress >= 3` check (each Dahak's shared mob script increments progress on death —
already wired correctly).

**Not applied** (cosmetic only, low value relative to effort): the 3 "Switch" NPCs and their
per-kill flavor messages aren't wired in, since the mission completes correctly without them.
Real positions for the 3 switches weren't specifically the focus of this capture pass either.
Flagging as a possible later polish pass, not a bug.

**No SQL/script changes from this capture.** *(Amended 2026-08-18, later: entrance position was
fixed using this same capture's PathLog -- see the entrance-position table under the Imperial
Agent Rescue writeup below. `410.410, -41.120, 300.743` r0 -> `302.000, -29.399, 192.000` r64.)*

## Real capture data mined: Operation: Black Pearl, Thris Nov 2025 capture set (2026-08-18)

Third mission from the Thris batch (Lebros Cavern, mission 29) -- 3 sub-captures from the same
morning (09:24, 09:37, 09:43), the first a failed attempt, the last a full successful clear.
Two findings, one of them a real, independent engine bug.

**Bug (not capture-related, found while reading the file to apply the capture fix)**:
`scripts/zones/Lebros_Cavern/IDs.lua` had two `[29] = { ... }` entries in the same `mob` table
constructor -- the real one (25 mobs) immediately followed a few lines later by a leftover empty
`[29] = {}`. Lua table constructors let later keys silently overwrite earlier ones, so
`ID.mob[29]` was actually evaluating to an **empty table** -- Operation: Black Pearl has been
spawning **zero mobs** this entire time, regardless of anything found in the capture. Removed
the dead duplicate.

**Finding: this is not a kill-all**, same shape as Breaking Morale's correction. The real
objective text, "Rescue Princess Kadjaya", was previously flagged as a mismatch against the
kill-all-25 data because no NPC data existed for her at all. The capture shows why: Kadjaya
(`17035488`, held captive by 3 named guards -- Kudjreel `17035467`, Yanshaal `17035468`, Djahama
`17035469`, none of which had *any* `npc_list` row, not even an `-- NC:` placeholder) aggros the
real boss, **Jorporbor the Hellraker** (`17035402`), the moment the player gets close ("Kadjaya:
What is this foul creature!? Guards! To my side, immediately!"). Killing Jorporbor ends the
fight; Kadjaya and Whyjham (`17035487`, already a real row) exchange a couple of relief/thanks
lines, and the mission auto-completes ("Mission objective completed. Unlocking Rune of
Release") without any further trigger. The 64 trash mobs around the camp (4 Troll Combatant, 20
Wamouracampa, 20 Crimson Eruca, 20 Vulcanian Bomb) are ambient guards -- the successful capture
killed far more than 64 of them combined (they respawn), confirming they're not a fixed kill
quota.

**Also corrected**: the original build cut `ID.mob[29]` off at the Wamouracampa group, guessing
the following Crimson Eruca/Vulcanian Bomb block belonged to the *next* mission (Better Than
One) since `mob_spawn_points.sql` has no comment separating them. Wrong -- the SQL's own
`-- ids 17035467 to 17035469 (Kudjreel, Yanshaal, Djahama) are NPCs` comment marks the real end
of the Black Pearl block, well after Crimson Eruca/Vulcanian Bomb, and the capture confirms both
were killed during this specific mission's instance. Better Than One's own build didn't rely on
that disputed block anyway (scaffolded from Black Shuck's own separate real coordinates), so
moving them over created no conflict.

**Applied**:
- `scripts/zones/Lebros_Cavern/IDs.lua` -- removed the duplicate empty `[29]`; added Crimson
  Eruca x20 / Vulcanian Bomb x20 to the real `[29]` mob block; added `KUDJREEL`, `YANSHAAL`,
  `DJAHAMA`, `WHYJHAM`, `KADJAYA` npc entries.
- `sql/npc_list.sql` -- converted Kadjaya's `-- NC:` row to real data, added 3 brand-new rows
  (Kudjreel/Yanshaal/Djahama) that didn't exist in any form. Positions/looks pulled from the
  capture's NPCLogger DB.
- `sql/instance_entities.sql` -- added instance-id-29 rows for Crimson Eruca x20, Vulcanian Bomb
  x20, and the 5 new/fixed NPCs.
- `scripts/zones/Lebros_Cavern/mobs/Jorporbor_the_Hellraker.lua` -- now the sole progress source
  (`setProgress` on death), matching the Black Shuck/single-boss pattern.
- `scripts/zones/Lebros_Cavern/mobs/Troll_Combatant.lua` and `Wamouracampa.lua` -- removed their
  `onMobDespawn` progress-increment (ambient now, not kill targets). Crimson Eruca/Vulcanian
  Bomb need no script at all (unscripted-ambient is an established pattern, e.g. Better Than
  One's Nocuous Inferno).
- `scripts/zones/Lebros_Cavern/instances/operation_black_pearl.lua` -- rewritten, completion now
  fires at progress 1 (Jorporbor's death) instead of kill-count-25.

**Caveats, not yet resolved**:
- The Kadjaya/Whyjham post-fight dialogue lines aren't wired in (no confirmed csid data) -- the
  mission completes correctly without them, this is cosmetic only.
- Not yet tested in-game.

**Live-DB statements** (repo SQL dumps don't auto-apply -- run manually against the live DB):
```sql
UPDATE `npc_list` SET pos_name='Kadjaya', pos_name_zh='Kadjaya', model_id=224, pos_x=161.000, pos_y=-40.000, pos_z=322.000, pos_rot=0, namevis=6, type=27, look=0x0001020410BA208730A040AF50A0617B70000000, status=32, zone='TOAU', flag=1 WHERE npcid=17035488;
INSERT INTO `npc_list` VALUES (17035467,'Kudjreel','Kudjreel',203,170.000,-40.000,331.000,0,50,50,0,0,0,6,27,0x0001020C10A520AB30AB40AB50AB61F971F90000,32,'TOAU',1);
INSERT INTO `npc_list` VALUES (17035468,'Yanshaal','Yanshaal',204,172.000,-40.000,306.000,0,50,50,0,0,0,6,27,0x0001020F10A520AB30AF40AB50AF618070360000,32,'TOAU',1);
INSERT INTO `npc_list` VALUES (17035469,'Djahama','Djahama',205,148.000,-40.000,309.000,0,50,50,0,0,0,6,27,0x0001020810A520B030B640B650B66166702F0000,32,'TOAU',1);
```
(the `UPDATE` above assumes typical `npc_list` column names -- check the live schema's actual
column names before running; if easier, `DELETE FROM npc_list WHERE npcid=17035488;` then insert
the row fresh from the SQL dump above instead.)
```sql
INSERT INTO `instance_entities` VALUES (29,17035427); INSERT INTO `instance_entities` VALUES (29,17035428);
INSERT INTO `instance_entities` VALUES (29,17035429); INSERT INTO `instance_entities` VALUES (29,17035430);
INSERT INTO `instance_entities` VALUES (29,17035431); INSERT INTO `instance_entities` VALUES (29,17035432);
INSERT INTO `instance_entities` VALUES (29,17035433); INSERT INTO `instance_entities` VALUES (29,17035434);
INSERT INTO `instance_entities` VALUES (29,17035435); INSERT INTO `instance_entities` VALUES (29,17035436);
INSERT INTO `instance_entities` VALUES (29,17035437); INSERT INTO `instance_entities` VALUES (29,17035438);
INSERT INTO `instance_entities` VALUES (29,17035439); INSERT INTO `instance_entities` VALUES (29,17035440);
INSERT INTO `instance_entities` VALUES (29,17035441); INSERT INTO `instance_entities` VALUES (29,17035442);
INSERT INTO `instance_entities` VALUES (29,17035443); INSERT INTO `instance_entities` VALUES (29,17035444);
INSERT INTO `instance_entities` VALUES (29,17035445); INSERT INTO `instance_entities` VALUES (29,17035446);
INSERT INTO `instance_entities` VALUES (29,17035447); INSERT INTO `instance_entities` VALUES (29,17035448);
INSERT INTO `instance_entities` VALUES (29,17035449); INSERT INTO `instance_entities` VALUES (29,17035450);
INSERT INTO `instance_entities` VALUES (29,17035451); INSERT INTO `instance_entities` VALUES (29,17035452);
INSERT INTO `instance_entities` VALUES (29,17035453); INSERT INTO `instance_entities` VALUES (29,17035454);
INSERT INTO `instance_entities` VALUES (29,17035455); INSERT INTO `instance_entities` VALUES (29,17035456);
INSERT INTO `instance_entities` VALUES (29,17035457); INSERT INTO `instance_entities` VALUES (29,17035458);
INSERT INTO `instance_entities` VALUES (29,17035459); INSERT INTO `instance_entities` VALUES (29,17035460);
INSERT INTO `instance_entities` VALUES (29,17035461); INSERT INTO `instance_entities` VALUES (29,17035462);
INSERT INTO `instance_entities` VALUES (29,17035463); INSERT INTO `instance_entities` VALUES (29,17035464);
INSERT INTO `instance_entities` VALUES (29,17035465); INSERT INTO `instance_entities` VALUES (29,17035466);
INSERT INTO `instance_entities` VALUES (29,17035467); INSERT INTO `instance_entities` VALUES (29,17035468);
INSERT INTO `instance_entities` VALUES (29,17035469); INSERT INTO `instance_entities` VALUES (29,17035487);
INSERT INTO `instance_entities` VALUES (29,17035488);
```
(no C++ rebuild needed -- this fix is Lua/SQL only, unlike the earlier `!warpassault` engine bugs.)

*(Amended 2026-08-18, later: this mission's `instance_list.sql` entrance was also fixed using
this same capture's PathLog — see the entrance-position table under the Imperial Agent Rescue
writeup below. `410.410, -41.120, 300.743` r0 -> `157.823, -40.000, 324.153` r66.)*

## Real capture data mined: Bloody Rondo, Thris Nov 2025 capture set (2026-08-18)

Fourth mission from the Thris batch, first from Leujaoam Sanctum (mission 10). Small, clean
correction: the mission was scaffolded as kill-all-2 (Count Dracula + Cursed Doppelganger), but
the capture shows only Count Dracula was fought -- "Mission objective completed. Unlocking Rune
of Release" fired immediately on his death, with no Doppelganger encounter anywhere in the log.
Changed to kill-all-1 (Dracula only); the Doppelganger stays spawned (real data) but no longer
gates completion -- possibly a conditional add/decoy this single capture didn't trigger,
unconfirmed either way.

**Applied**: `scripts/zones/Leujaoam_Sanctum/instances/bloody_rondo.lua` (progress threshold
2 -> 1), `scripts/zones/Leujaoam_Sanctum/mobs/Cursed_Doppelganger.lua` (removed progress
increment). No SQL changes. Not yet tested in-game.

*(Amended 2026-08-18, later: this mission's `instance_list.sql` entrance was also fixed using
this same capture's PathLog — see the entrance-position table under the Imperial Agent Rescue
writeup below. `476.000, 8.479, 40.000` r49 -> `424.000, 4.683, -341.000` r0 — matches the
pre-existing "Bloody Rondo entrance @ 424 4.3 -341 rot 0" comment in `mob_spawn_points.sql`
exactly.)*

## QA pass: rewards gap across all 5 zones' Rune of Release (2026-08-18)

User asked to double-check the already-built instances for anything missing -- mob mechanics,
NPCs, rewards -- not just re-verify the capture-driven fixes already made. Checking Ancient
Lockbox and Assault-point payout logic (not something any earlier pass in this session had
specifically audited) turned up a real, systemic gap that predates the Thris captures and
affects every mission built this session, not just the ones with capture data.

**Ancient Lockbox reward gap**: `Lebros_Cavern/npcs/Ancient_Lockbox.lua`'s shared reward table
(`Q_ITEMS`/`REG_ITEMS`, keyed by instance id) only ever had entries for 21/22/23. Missions 24
(Evade and Escape) and 29 (Operation: Black Pearl) both reference the same shared lockbox from
their own instance scripts, but with no table entry, `tpz.assault.chestTrigger`'s nil-safe
design meant the lockbox opened, animated, and paid flat XP/gil -- but gave **no items at all**.
Fixed using exact contents pulled from the two captures already mined (see their own writeups
above): 24 -> `???_box` + hi-potion_+3 + hi-ether_tank; 29 -> `???_earring` + hi-potion_+3 +
hi-potion_tank. 30 (Better Than One) still has no lockbox table entry -- no capture mined for it
yet, same silent-nothing gap remains there.

**Assault points gap, much bigger**: all 5 zones' `Rune_of_Release.lua` use the identical
pattern -- `onEventFinish` only awards points `if id == <one specific mission id>`, and gives
**zero points for every other mission in the zone**. That one id was always the zone's original
"known-good" reference mission from early in this session (Leujaoam id 1, Mamool Ja id 12,
Periqia/Ilrusi Atoll similarly single-gated); every mission scaffolded afterward -- which by now
is most of them -- has been silently paying 0 Assault points on completion. Real captures also
show the flat-1000 guess for that one reference mission was itself wrong (Excavation Duty's real
solo value is 1210, not 1000; Bloody Rondo's is 1650). Restructured
`Lebros_Cavern`/`Leujaoam_Sanctum`/`Mamool_Ja_Training_Grounds`'s `Rune_of_Release.lua` from a
single `if id ==` check to a `BASE_ASSAULT_POINTS[id]` lookup table, seeded with every real
value captured so far (Lebros: 21=1210, 24=1100, 29=1246; Leujaoam: 10=1650) plus the
pre-existing unconfirmed guesses left untouched (Lebros 23=1000, Leujaoam 1=1000, Mamool Ja
12=1000) so nothing regresses. The party-size falloff shape (`- 100 per member past 3`) is kept
since it's a plausible real mechanic, but its exact rate is **not** confirmed by any of these
captures (all solo runs) -- flagged, not fixed.

**Not yet touched**: `Periqia/npcs/Rune_of_Release.lua` and
`Ilrusi_Atoll/npcs/Rune_of_Release.lua` have the exact same single-id-gated pattern and the same
gap (every mission but one in each zone pays 0 points) -- not restructured yet since no captures
have been mined for either zone this session, so there's nothing real to seed the table with.
Flagging as the same class of bug, worth the same fix once real point values exist for those
zones.

**Not checked yet this pass**: mob special-attack/TP-move rosters (whether spawned mobs actually
use their real skill sets or fall back to generic melee), and per-mission NPC dialogue/cutscene
text beyond what directly gates completion. Worth a dedicated pass, not done here.

## Real capture data mined: Red versus Blue, Thris Nov 2025 capture set (2026-08-18) -- investigated, no mechanic change

Fifth mission from the Thris batch (Leujaoam Sanctum, mission 9), only an `[L]` (loss) capture
available -- no winning run has been mined yet, so this is a partial finding, not a full fix.

**What the capture confirms**: this is genuinely a two-faction battle, not a single ambient camp
like Black Pearl/Better Than One. "Red Scorpions" (Shailham's side) and a "Blue" opposing group
(Ganmuul/Shayaam/Habraheem's side) are both openly hostile and fighting -- the player got
directly swarmed by 8+ named mobs attacking simultaneously (Varajahl, Ghayaraan, Ubdeen,
Sharayaan, Krinahal, Salyhaar, Mareyamad, Qudeen all landing hits in the same few seconds), which
is what caused the loss ("The mission has failed. Leaving area."). This does NOT match the
"approach triggers one boss, rest stays passive" pattern found in Black Pearl/Better Than One --
real objective text still says "Defeat Raubahn" (singular), but with this much concurrent hostile
pressure from named mobs, kill-all-27 remains at least as plausible as a single-boss reading.
**No change made to the kill-all-27 model** -- changing it without a winning capture to confirm
completion would be a guess, unlike the other corrections in this log which all had a completed
run to verify against.

**Real mob mechanic confirmed and NOT yet wired in**: Raubahn (`17059993`) is sleepable (Sheep
Song/Soporific landed and put him to sleep, confirmed twice in the log) while all 12+ other named
mobs tested (Hkadouf, Afrhaad, Habraheem, Shayaam, Ubdeen, Sharayaan, Salyhaar, Qudeen, Mareyamad,
Varajahl, Ghayaraan, Krinahal) **completely resisted** the same spells every single time --
exactly matching the Discord poster's own note ("only Raubahn can be slept!"). None of these
mobs currently have individual `mob_pools` rows (checked -- no matches for any of their ids), so
there's nowhere to encode this real immunity split yet. Flagged for a dedicated mob_pools/
immunity pass, same "found real data, not yet wired" treatment as Viscous Liquid (Breaking
Morale) and the Mamool Ja Trainer steal-back mechanic.

**Next step for this mission**: mine a `[W]` (win) Red vs Blue capture if/when one turns up in
the Discord archive to actually confirm the completion condition before touching the kill model.

*(Amended 2026-08-18, later: this mission's `instance_list.sql` entrance WAS fixed despite the
loss, using this same capture's PathLog — entrance position doesn't depend on winning.
`476.000, 8.479, 40.000` r49 -> `19.990, -7.500, -363.797` r172 — matches the pre-existing "Red
versus Blue entrance @ 19.99 -7.5 -363.797 rot 172" comment in `mob_spawn_points.sql` exactly.)*

## Real capture data mined: Imperial Code, Thris Nov 2025 capture set (2026-08-18)

Sixth mission from the Thris batch (Leujaoam Sanctum, mission 8), same shape correction as Sagelord
Elimination/Better Than One/Black Pearl. Real objective text ("Retrieve the OGMA") looked
unrelated to the kill-all-26 scaffold, and the capture confirms why: only ~5 kills happened
total (mostly ambient Kusa trash) before the real target -- Saizo (`17059974`, already correctly
identified by name in `IDs.lua` from the original build, has unique death dialogue "Remember
when you said...you'd kill me last...?") -- dies, immediately followed by "You retrieve the
OGMA!" and completion. Changed to kill-all-1 (Saizo only); Kusa/Oko/Danzo/Kudagitsune are now
ambient, unscripted for progress.

**Rewards also fixed**: Leujaoam's `Ancient_Lockbox.lua` was hard-guarded to only give items for
`ASSAULT_ID == 1` (Leujaoam Cleansing) -- every other mission in the zone got nothing, same class
of gap as the Lebros lockbox fix above. Added a small `OTHER_MISSION_ITEMS` table with mission
8's real capture-confirmed contents (`???_box` + hi-potion_+3) without disturbing the existing
mission-1-only logic. Assault points: 1466 (real, solo) added to the same `BASE_ASSAULT_POINTS`
table fixed earlier in this pass.

**Applied**: `scripts/zones/Leujaoam_Sanctum/instances/imperial_code.lua` (progress threshold
26 -> 1), `mobs/Saizo.lua` (comment only, already correctly wired), `mobs/Kusa.lua`/`Oko.lua`/
`Danzo.lua`/`Kudagitsune.lua` (removed progress increment), `npcs/Ancient_Lockbox.lua` (added
mission 8 rewards), `npcs/Rune_of_Release.lua` (added mission 8 points). No SQL changes. Not yet
tested in-game.

*(Amended 2026-08-18, later: this mission's `instance_list.sql` entrance was also fixed using
this same capture's PathLog — see the entrance-position table under the Imperial Agent Rescue
writeup below. `476.000, 8.479, 40.000` r49 -> `-320.000, -4.000, -440.700` r142 — matches the
pre-existing "Imperial code @ -320 -4 -440.7 rot 142" comment in `mob_spawn_points.sql` exactly.)*

## Real capture data mined: Imperial Agent Rescue, Thris Nov 2025 capture set (2026-08-18) -- VALIDATED, no mechanic change needed

User asked directly for this one (Mamool Ja Training Grounds, mission 11) -- also the mission
flagged all the way back near the start of this session as "still open: mission 11 mobs remain
unconfirmed" after `!warpassault` testing couldn't visually confirm the spawns. Good news: this
capture (a full win) confirms the existing build is correct in every respect checked:

- **Gates, not Warders**: exactly 3 "The Dilapidated Gate takes N points of damage" hits total in
  the whole capture, and only 1 of 7 total Mamool Ja Warder kills happened *before* completion --
  confirms the existing design (3 gates gate progress, Warders are unscripted combat obstacles)
  is right, including the judgment call in the original build notes.
- **Brujeel reveal/completion timing**: his rescue dialogue fires immediately after the 3rd gate
  falls, "Mission objective completed" follows ~13 seconds later -- matches the existing
  gates-trigger-completion model exactly, no talk-to-Brujeel CSID needed.
- **Lockbox rewards**: `npcs/Ancient_Lockbox.lua` already had `[11] = ???_box/???_ring` +
  `hi-potion_+2`/`hi-potion_tank`/`4172` (ported from an LSB reference file this session) -- the
  capture's actual lockbox contents (`???_ring`, hi-potion_+2, hi-potion_tank) landed squarely
  inside those existing pools. The LSB port was accurate.
- **Assault points**: 1210 (real, solo) -- this zone had the same single-id-gated points bug as
  the others (only id 12 was ever paying out); added `[11] = 1210` to the same
  `BASE_ASSAULT_POINTS` table fixed earlier in this pass.

**Applied**: `scripts/zones/Mamool_Ja_Training_Grounds/instances/imperial_agent_rescue.lua`
(comment updated from "unverified" to confirmed), `npcs/Rune_of_Release.lua` (added mission 11
points). No mechanic or reward-table changes needed -- everything else was already right.

**CORRECTION (2026-08-18, later)**: the "no mechanic change needed" verdict above was wrong on
one axis I hadn't checked -- the actual entrance coordinates. User reported in-game that the
spawn location was clearly wrong and the zone looked empty ("no mobs in the zone"). The CapLog
text analysis above validated gates/Warders/rewards/points, but never cross-checked *where the
player actually starts*, because that data doesn't show up as readable chat text -- it only
exists in the capture's `PathLog` (raw movement CSV) and `KITrack` (key item pickup coordinates)
files, neither of which I'd opened for this mission.

Checked now: `sql/instance_list.sql` row 11's start position was `(-55.000, 1.323, -103.000)` --
which turns out to be a **generic placeholder**, not a real entrance. It's literally
`npc_list.sql`'s un-instanced default Rune of Release position for this zone, copied in as a
"good enough for now" stand-in when the mission was first scaffolded (the row's own comment said
so: "start pos is the zone's default Rune of Release spot, not a verified entrance"). Real
entrance, read directly from the capture's `PathLog/Thris/PC_Mamool_Ja_Training_Grounds.csv`
(first recorded row) and cross-confirmed against the `KITrack` log's "map of the Training
Grounds" key-item pickup coordinates: **(-20, 2.276, -405), facing dir 63**. That's ~300 units
off from the placeholder in Z alone -- nowhere near the real mob/gate cluster (all of which sit
around x:166-261, z:-418 to -579, confirmed by both `mob_spawn_points.sql` and the player's own
travel path through the rest of the capture). Fixed in `sql/instance_list.sql`.

**This is a much bigger systemic issue, not unique to this mission.** Checking the rest of
`instance_list.sql`: **8 more Mamool Ja missions** (13 Sagelord Elimination, 14 Breaking Morale,
15 The Double Agent, 16 Imperial Treasure Retrieval, 17 Blitzkrieg, 18 Marids in the Mist, 19
Azure Ailments, 20 The Susanoo Shuffle) all share the exact same `(-55.000, 1.323, -103.000)`
placeholder, and **8 Leujaoam Sanctum missions** (2 Orichalcum Survey, 3 Escort Professor
Chanoix, 4 Shanarha Grass Conservation, 5 Counting Sheep, 7 Azure Experiments, 8 Imperial Code, 9
Red versus Blue, 10 Bloody Rondo) all share a different single placeholder,
`(476.000, 8.479, 40.000)`. Only Preemptive Strike (12) and Leujaoam Cleansing (1) have their own
distinct, presumably-real values. Practically every mission built this session in these two zones
warps the player to one of two identical generic spots regardless of which mission they picked --
this is almost certainly why it can feel like "the wrong instance is loading": every one of these
16 missions looks the same at the moment you zone in, because they *are* the same coordinates,
even though each is a genuinely separate, correctly-isolated `CInstance` under the hood (already
verified independently during the earlier `!warpassault` engine-bug chain). It's a positioning
data gap across the board, not an instance-routing bug.

**Follow-up (same session, same pass)**: went back through every capture already mined this
session and checked/fixed their `instance_list.sql` entrance the same way, rather than leaving
it as a standing TODO. Results:

| Mission | Zone | Old placeholder | Real entrance (from capture PathLog) | Source |
|---|---|---|---|---|
| Imperial Agent Rescue (11) | Mamool Ja | `-55.000, 1.323, -103.000` r0 | `-20.000, 2.276, -405.000` r63 | PathLog first row |
| Breaking Morale (14) | Mamool Ja | `-55.000, 1.323, -103.000` r128 | `19.000, 2.026, -136.000` r64 | PathLog first row |
| Orichalcum Survey (2) | Leujaoam | `476.000, 8.479, 40.000` r0 | `-432.000, -27.627, 169.000` r129 | PathLog first row |
| Imperial Code (8) | Leujaoam | `476.000, 8.479, 40.000` r49 | `-320.000, -4.000, -440.700` r142 | PathLog, matches pre-existing SQL comment exactly |
| Red versus Blue (9) | Leujaoam | `476.000, 8.479, 40.000` r49 | `19.990, -7.500, -363.797` r172 | PathLog, matches pre-existing SQL comment exactly |
| Bloody Rondo (10) | Leujaoam | `476.000, 8.479, 40.000` r49 | `424.000, 4.683, -341.000` r0 | PathLog, matches pre-existing SQL comment exactly |
| Evade and Escape (24) | Lebros | `410.410, -41.120, 300.743` r0 | `302.000, -29.399, 192.000` r64 | PathLog first row |
| Operation: Black Pearl (29) | Lebros | `410.410, -41.120, 300.743` r0 | `157.823, -40.000, 324.153` r66 | PathLog first row |

Notably, three of the Leujaoam fixes (Imperial Code, Red vs Blue, Bloody Rondo) match real
coordinates that were **already sitting in `mob_spawn_points.sql`'s own comments** from the
original builds (e.g. `-- Bloody Rondo entrance @ 424 4.3 -341 rot 0`) -- that data was correct
and available the whole time, it just never got applied to `instance_list.sql`. Worth remembering
for future missions: always cross-check `mob_spawn_points.sql`'s entrance comments (many missions
have one) against `instance_list.sql`'s actual stored start position before assuming a capture is
needed to find it.

**Sign conversion note**: PathLog reports `dir` as a signed byte (-128 to 127); `instance_list.sql`'s
`start_rot` column is unsigned (0-255). Conversion is `unsigned = (signed + 256) % 256` -- e.g.
Orichalcum Survey's captured `dir -127` becomes `start_rot 129`. Verified correct by the three
cases above that already had a known-good rotation value to cross-check against.

**Still not fixed** (no capture with usable PathLog data mined yet, still on the shared
placeholder): Escort Professor Chanoix (3), Shanarha Grass Conservation (4), Counting Sheep (5),
Azure Experiments (7) in Leujaoam; Sagelord Elimination (13), The Double Agent (15), Imperial
Treasure Retrieval (16), Blitzkrieg (17), Marids in the Mist (18), Azure Ailments (19), The
Susanoo Shuffle (20) in Mamool Ja; Lebros Supplies (22), Siegemaster Assassination (25), Apkallu
Breeding (26), Egg Conservation (28), Better Than One (30) in Lebros. Flagging as a standing
checklist item: **every future capture mined should get its `instance_list.sql` entrance checked
against the capture's `PathLog` first row, not just its combat/completion/reward logic** -- this
was a blind spot in every "mined" writeup in this log before this correction, since CapLog text
alone never surfaces it.

**Live-DB statements** (repo SQL dumps don't auto-apply -- run manually against the live DB):
```sql
UPDATE `instance_list` SET start_x=-20.000, start_y=2.276, start_z=-405.000, start_rot=63 WHERE instanceid=11;
UPDATE `instance_list` SET start_x=19.000, start_y=2.026, start_z=-136.000, start_rot=64 WHERE instanceid=14;
UPDATE `instance_list` SET start_x=-432.000, start_y=-27.627, start_z=169.000, start_rot=129 WHERE instanceid=2;
UPDATE `instance_list` SET start_x=-320.000, start_y=-4.000, start_z=-440.700, start_rot=142 WHERE instanceid=8;
UPDATE `instance_list` SET start_x=19.990, start_y=-7.500, start_z=-363.797, start_rot=172 WHERE instanceid=9;
UPDATE `instance_list` SET start_x=424.000, start_y=4.683, start_z=-341.000, start_rot=0 WHERE instanceid=10;
UPDATE `instance_list` SET start_x=302.000, start_y=-29.399, start_z=192.000, start_rot=64 WHERE instanceid=24;
UPDATE `instance_list` SET start_x=157.823, start_y=-40.000, start_z=324.153, start_rot=66 WHERE instanceid=29;
```

## Real capture data mined: Orichalcum Survey, Thris Nov 2025 capture set (2026-08-18) -- VALIDATED, no mechanic change needed

Leujaoam Sanctum mission 2, built out earlier this session from the "Solo Assault Guide by
Korvana" (not LSB or a capture) -- pickaxe issue -> mine for ore (33% break chance, 20% ore
chance, 20% worm-hazard chance) -> report to Mulwahah -> Qiqirn Miners turn hostile on the ore
carrier. Only an `[L]` (loss) capture available, but it still validates the core loop end to end:

- "Obtained temporary item: a pickaxe!" / "Mulwahah : You only get as many pickaxes as you need."
  (silent re-request handling) / "Your pickaxe (temporary item) breaks!" / "Mining is possible
  here if you have a pickaxe (temporary item)." -- all match the existing `Mulwahah.lua`/
  `Mining_Point.lua` implementation's exact state logic.
- "Thris obtains the temporary item: a chunk of orichalcum ore!" at 14:01:54, immediately
  followed by "The Qiqirn Miner" attacking repeatedly for the rest of the capture -- confirms the
  ore-carrier-gets-chased mechanic is real and already correctly wired (`qiqirn:engage(player)`
  in `Mining_Point.lua`).
- **Why this run failed**: the player got the ore with about a minute left but didn't make it
  back to Mulwahah before the Qiqirn Miners (now hostile) ran the clock out -- a real, plausible
  outcome of the actual mechanic, not evidence of a bug. "The mission has failed. Leaving area."
  fired right as the timer hit 0, matching `MISSION_FAILED`/csid 102 in the existing script.

**Minor, unimplemented flavor detail noticed**: failed mining attempts show "You find nothing."
paired with a reference to item 17296 (`pebble`) -- real retail apparently has a third "junk"
outcome distinct from the plain miss. Not modeled (`Mining_Point.lua` only rolls ore/worm/nothing
with a silent miss); cosmetic only, not worth the effort relative to everything else queued.

## Real capture data mined: Lamia No.13, Golden Salvage, Thris Nov 2025 (2026-08-18)

Ilrusi Atoll missions 41/42. Terse -- see `Assault_Issue_Tracker.md` for status detail.

- **Golden Salvage (41)**: entrance already correct. Ancient Lockbox confirmed empty stub (user
  report) -- rebuilt using the shared `tpz.assault.chestTrigger` pattern, but no real item data
  for id 41 yet so it still falls through to XP/gil only. Cursed Chest draw-in mechanic already
  exists correctly in code (two files, `npcs/`+`mobs/`), matches captured behavior exactly --
  likely a live-server-only issue, not a script gap.
- **Lamia No.13 (42)**: kill-1 mechanic already correct. Entrance was on the shared placeholder
  (`412, -9, 54` -> real `155, -7, -175` r47) -- fixed. Same zone-wide points bug as the other 4
  zones (only id 41/43 ever paid out) -- restructured to a lookup table, seeded 42 with its real
  value (1320). Lockbox rewards also real now: `???_footwear` + hi-potion_+3 + hi-potion_tank.

**Applied**: `sql/instance_list.sql` (id 42 entrance), `scripts/zones/Ilrusi_Atoll/npcs/
Rune_of_Release.lua` (points table), `npcs/Ancient_Lockbox.lua` (rebuilt from empty stub).

**Correction (2026-08-18, later)**: "fully correct" above was premature -- the entrance position
was never checked (same blind spot as Imperial Agent Rescue, see that mission's writeup and the
follow-up table there). Real entrance from this same capture's `PathLog`: `(-432, -27.627, 169)`,
dir 129 -- fixed in `sql/instance_list.sql`, was sharing Leujaoam's generic placeholder with 7
other missions.

## Regression: Drahbah appraiser csid flipped back to a known-wrong value (2026-08-18)

While mining The Double Agent capture, the user reported Drahbah the Appraiser (Aht Urhgan
Whitegate) showing wrong dialogue again. Root cause: the immediately-prior capture-mining commit
"corrected" `scripts/zones/Aht_Urhgan_Whitegate/npcs/Drahbah.lua`'s `startEvent` csid from 678 to
679, based on a fresh capture that appeared to show `Event: 679`. But 678 was already the
user-confirmed correct value from an earlier session -- this server/client pair reads some
captured event/message ids one **higher** than what it actually needs, because the captures come
from a newer FFXI client. This exact offset was already independently found and fixed once
before for this zone's `ASSAULT_11_START..20_START` text block (see IDs.lua, dated 2026-08-17).
Reverted csid back to 678, documented the caveat in the file, and saved it as a standing memory
so future capture mining checks an id's prior-confirmed value before "correcting" it from a new
capture. See `Drahbah.lua`'s header comment for the full account.

Applied the same known offset (-1) proactively when sourcing new dialogue text ids for The Double
Agent's Qiqirn Spy NPCs below, rather than trusting the raw captured MesNum values.

## The Double Agent (Mamool Ja, mission 15): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture ("Mission objective completed" -> "You gain 550 Assault points!"). The existing
scaffold's claim that the "Qiqirn Spy" npc id range (17047628-17047653) had "zero backing
npc_list rows" was checked against this repo's own SQL dump, not against retail -- the real NPCs
exist and are fully interactive in the capture; the dump simply never had them, the same kind of
gap already found for Imperial Agent Rescue and Operation: Black Pearl earlier this session.

Findings:
- 26 real Qiqirn Spy NPCs scattered around the instance (positions from NPCLogger widescan, see
  `sql/npc_list.sql`). One is randomly the double agent each run.
- Decoy spies: "What yoo want?" -> a flavor hint line on first trigger, then "Have noo secret
  info, so very sad" on subsequent triggers.
- The real spy: "Hooo hooo... Nooo listen... Laaa laaa..." on first trigger, then "...How yoo
  know that?" on the second trigger -- immediately followed by mission completion in the capture.
- Ancient Lockbox: box item 2286 (`???_box`, same item already confirmed for mission 11), opened
  to a hi-potion +3 (item 4119, same as Sagelord Elimination's confirmed reward).
- Real Assault points: 550 (solo run).
- Entrance: real PathLog first-row position `-327.199, -4.748, -406.599`, rot 96.

Applied: same randomized-figurehead pattern as Ilrusi Atoll's Golden Salvage chest
(`instance:setProgress()` in `onInstanceCreated`, checked in the new shared
`npcs/Qiqirn_Spy.lua`). `sql/instance_list.sql` (entrance), `sql/npc_list.sql` (26 new NPC rows),
`sql/instance_entities.sql` (registered the real ids, removed the old dangling placeholder ids
17047654-17047662 which had no backing npc_list rows), `IDs.lua` (npc ids + text ids, text ids
have the known -1 offset applied but not independently re-verified), `Rune_of_Release.lua`
(550 points), `Ancient_Lockbox.lua` (reward tables), `instances/the_double_agent.lua` (rewritten).

## Imperial Treasure Retrieval (Mamool Ja, mission 16): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (366 Assault points). Downloaded via a faster method this time: Dropbox's
folder-zip download now requires login for the top-level share, but individual file/subfolder
links still work anonymously via `dl=1` (raw download) instead of the browser UI -- used `curl`
directly against the Thris subfolder link, much faster than clicking through folders.

Findings: this is a competitive gem-race, not a kill-all or fetch. Zahakahm (17047832) narrates
it. 9 Coffer NPCs and 6 enemy "Badge Mamool Ja" carrier NPCs (Red/Blue/Yellow/Green/White/Black)
race the player's party to open coffers and run gems back to their side; a carrier says "Poor
try, that was. Here, no treasure!" on a failed run. A "Mamool Ja Governor" NPC is also present,
role unconfirmed. All real ids/positions pulled from NPCLogger and documented in the instance
script's header comment -- not built out, needs a carrier-AI/steal/intercept system that doesn't
exist in the engine yet. Entrance real: `(289.705, 2.306, -419.980)`, dir 129. Lockbox: box item
2279 (`???_cape`) opened to 2x remedy + 1x hi-potion +3.

Applied: `sql/instance_list.sql` (entrance), `Rune_of_Release.lua` (366 points),
`Ancient_Lockbox.lua` (reward tables), `instances/imperial_treasure_retrieval.lua` (header
comment documenting the real mechanic, no completion logic added).

## Blitzkrieg (Mamool Ja, mission 17): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (880 Assault points). The existing build already had real mob data (27 static
NPCs, 5 "Molted" types x5 + 2 named singles) wired as kill-all-27 -- but the capture's own text
says otherwise: "You have decimated the first wave of enemy forces! You have defeated 200
opponents!" Real objective is 200 total kills, not 27 -- these are wave-respawn spawn points, not
a finite roster. Counted kills by name in the capture: 69 Molted Mamool Ja, 43 Molted Lindwurm,
40 Molted Bugard, 28 Molted Puk, 20 Molted Ziz (200 total across the 5 respawning types).

Applied: each of the 5 "Molted_*.lua" mob scripts now respawns itself (`SpawnMob` on a timer)
after each despawn until the instance hits 200 progress, instead of a one-time kill increment.
Respawn delay used (20s) is an estimate, not directly measured from the capture -- worth revisiting
if real playtesting shows completion pacing is off. The 2 named singles (Bluethunder Kaqool Ja,
Festive Firedrake -- both real, confirmed present in this capture) were left as one-time kills,
unconfirmed whether they also respawn. `instances/blitzkrieg.lua` threshold raised 27 -> 200.
Real entrance: `(-99.688, -3.853, 59.220)`, dir 188. Lockbox: box item 2190 (`???_sword`, same
item already confirmed for Sagelord Elimination) opened to hi-potion +3 + hi-ether tank.

## Marids in the Mist (Mamool Ja, mission 18): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1466 Assault points). The existing build had real mob data (26 static NPCs: 8
Marid + 3 Chigoe + 15 Mamool Ja Breeder/Mahout/Farrier) wired as kill-all-26 -- but "Neutralize
the marids" turned out to mean capture, not kill. Zimahd (17047840) hands the player a temporary
"thunderguard dart" (item 5442) at mission start: "You're one of the mercenaries, come to capture
the marids. Here, take this special tranquilizer dart." Using it on a Marid either fails ("The
tranquilizer has no effect. Marid seems unchanged.") or succeeds ("The tranquilizer has begun to
take effect. You have successfully captured Marid!") -- the mission completed on exactly the 8th
successful capture, matching the 8 real Marid NPCs. Only 8 incidental kills total were logged
across all 4 escort mob types combined -- confirms they're ambient, not the objective.

Applied: removed the wrong progress-on-death from all 5 mob scripts in this mission (Marid,
Chigoe, Mamool_Ja_Breeder, Mamool_Ja_Farrier, Mamool_Ja_Mahout). `instances/marids_in_the_mist.lua`
completion logic unhooked (documented, not built -- needs a temporary-item-use hook the engine
doesn't have). Real entrance confirmed `(339, 14.632, 98)`, dir 192 -- matched a pre-existing
unwired comment on the mob spawn block almost exactly. Assault points (1466) and Lockbox reward
(???_box -> hi-potion +3 + hi-potion tank) fixed regardless.

## Egg Conservation (Lebros Cavern, mission 28): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1246 Assault points). Existing build had real mob data (6 static Qiqirn Eggler)
wired as kill-all-6 -- but the capture logged 12 personal kills before completion despite only 6
static spawn points, the same wave-respawn pattern found in Blitzkrieg. Objective text: "Drive
out the hunters" (Rhap Nelhah: "This place is crrrawling with slimy eggnappers, and it's your job
to make 'em scrrramble!").

Applied: `Qiqirn_Eggler.lua` now respawns (20s timer, same estimate used for Blitzkrieg) until
progress hits 12 (a single-capture estimate, may need tuning). `instances/egg_conservation.lua`
threshold raised 6 -> 12. Real entrance: `(-140.540, -9.627, 468.960)`, dir 64 -- was sharing this
zone's generic placeholder. Assault points (1246) and Lockbox reward (???_ring -> hi-potion +3)
added to Lebros Cavern's shared tables.

Note: downloaded via the wrong Discord-index link at first (grabbed the "Egg Conservation +
Immunity testing" Dropbox folder while intending Azure Ailments -- caught immediately by checking
the capture's own CapLog before assuming, same "verify before trusting a link" discipline used
earlier this session for a mis-pasted Golden Salvage link). Mined it anyway since it's real,
useful, previously-unmined data; will fetch the correct Azure Ailments link separately.

## The Susanoo Shuffle (Mamool Ja, mission 20): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1650 Assault points). Fully validated the existing kill-1 Orochi build --
"Thris defeats Orochi" immediately preceded "Mission objective completed", no mechanic change
needed. Real entrance: `(-503, 1.783, -54)`, dir 0. Lockbox: box item 2196 (`???_footwear`,
new item id, not seen elsewhere yet) opened to hi-potion +3. Assault points (1650) added.

## Mamool Ja Training Grounds: all missions with a downloadable Thris Nov 2025 capture now mined (2026-08-18)

Sagelord Elimination, Imperial Agent Rescue, Breaking Morale, The Double Agent, Imperial Treasure
Retrieval, Blitzkrieg, Marids in the Mist, The Susanoo Shuffle -- 8 of this zone's 10 missions.
Azure Ailments' only found Thris-set link is a `.rar` archive with no extraction tool available
in this environment (curl/unzip/7z all failed or aren't installed) -- deferred, see captures
README. Preemptive Strike (12) has no capture in the Discord index found so far.

## Lebros Supplies (Lebros Cavern, mission 22): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1320 Assault points). Fully validated the existing trigger-all-12-
Imperial-Stormer delivery mechanic -- all 12 real triggers confirmed present in the capture, no
mechanic change needed. This mission's scaffold had explicitly left Rune of Release / Ancient
Lockbox at the zone-default position since the real staging coordinates were unknown; the same
capture's NPCLogger gave them: Rune of Release `(-330, -10, -262)`, Ancient Lockbox
`(-330, -10, -265)` (no facing captured, left at 0), now set via `setPos()` in
`onInstanceCreated`. Real entrance: `(-333, -9.921, -259.999)`, dir 128. Lockbox reward table
extended with a real hi-potion +2 (item 4118) drop alongside the existing LSB-ported entries.
Assault points (1320) added.

## Siegemaster Assassination (Lebros Cavern, mission 25): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1210 Assault points). The existing build modeled "Assassinate Borgerlur" as
kill-any-1-of-8 identical Old Trolls (no way to tell which one is really Borgerlur from static
SQL data) -- but the capture showed completion didn't fire until the 7th personal kill, with the
remaining troll(s) force-despawned right after as end-of-mission cleanup. Corrected to kill-7 (the
exact observed completion point -- not confirmed as a hard rule vs. some other near-kill-all
variant, single capture). Real entrance: `(0, -50, -319.999)`, dir 0. Lockbox: box item 2286
(`???_box`) opened to hi-potion +3 + hi-potion tank. Assault points (1210) added.

## Apkallu Breeding (Lebros Cavern, mission 26): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Loss capture (ran out of time, no successful match). Real mechanic: "Match the apkallu" is a
pairing minigame, not combat. Rhap Nelhah explains directly: "The slightly smaller ones are the
girrrls, and the bigger ones are the guys. Let's see how many couples you can make!" Triggering
two apkallu together gives compatibility feedback ("They don't seem to like each other..." for a
failed pair observed in this capture); apkallu also make distinct cry sounds Rhap Nelhah hints
are "some sorta code" for finding a real match. 13 real Lebros Apkallu positions found (ids
17035337-17035351, a few gaps). Not built out -- needs a two-mob pairing/compatibility system
that doesn't exist in the engine, and the exact win condition isn't confirmed by a loss-only
capture. Real entrance: `(86.852, -29.464, 256.080)`, dir 22, fixed regardless.

## Better Than One (Lebros Cavern, mission 30): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1650 Assault points). Fully validated the existing kill-1 Black Shuck build --
"Thris defeats Black Shuck" immediately preceded "Mission objective completed", no mechanic
change needed. Real entrance: `(420, 0.018, -460)`, dir 0. Lockbox: box item 2286 (`???_box`)
opened to hi-potion +3 + hi-potion tank. Assault points (1650) added.

## Lebros Cavern: all missions with a downloadable Thris Nov 2025 capture now mined (2026-08-18)

Excavation Duty, Lebros Supplies, Troll Fugitives (via wiki, not a capture), Evade and Escape,
Siegemaster Assassination, Apkallu Breeding, Operation: Black Pearl, Egg Conservation, Better
Than One -- all 9 numbered missions in this zone (Wamoura Farm Raid is the zone's non-numbered PSC
farming instance) now have at least one real capture pass.

## Troll Fugitives (Lebros Cavern, mission 23): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1100 Assault points). Fully validated the existing mature build: exactly 15
"Broken Troll Soldier" kills observed, matching kill-all-15 exactly. Entrance was already close
to a real value (not the generic zone placeholder), left as-is. Lockbox reward table validated --
drew ???_headpiece (item 2276) and hi-potion +3, both already in the existing LSB-ported tables,
no changes needed. Assault points corrected from a pre-existing 1000 guess to the real 1100.

## Preemptive Strike (Mamool Ja, mission 12): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1100 Assault points). Fully validated the existing kill-all-13 build --
exactly 13 "Mamool Ja Executioner" kills observed (6 "Puk Executioner" kills also happened,
ambient, correctly don't count). Entrance corrected from a rough guess (~15 units off) to the
real PathLog value `(-75, -3.3, 20)`, dir 0. Assault points corrected from a 1000 guess to the
real 1100. Lockbox reward table extended with a real hi-potion +2 (item 4118) drop alongside the
existing LSB-ported entries.

## Mamool Ja Training Grounds and Lebros Cavern: capture-mining passes complete (2026-08-18)

Every mission in both zones with a findable Thris Nov 2025 capture link is now mined -- Mamool Ja
9/10 (only Azure Ailments blocked, .rar with no extraction tool available), Lebros Cavern 9/9.
Remaining work across the whole Assault build-out: Ilrusi Atoll's Golden Salvage wrong-model bug
(unresolved), several zones' "documented but not built" complex mechanics (Demolition Duty,
Apkallu Seizure, Lost and Found, Desperately Seeking Cephalopods, Wake the Puppet, Defuse the
Threat, Counting Sheep, Escort Professor Chanoix, Imperial Treasure Retrieval, Marids in the
Mist, Apkallu Breeding), and Leujaoam Sanctum's remaining unmined missions (no Thris Nov 2025 set
exists for that zone -- would need older/scattered capture links from the Discord index instead).

## Wamoura Farm Raid (Lebros Cavern, mission 27): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1100 Assault points). Fully validated the existing mature build: entrance was
already exactly right, and the mission-complete packet itself carries the value 15, confirming
kill-all-15 is exactly correct (the extra "Thris defeats" lines seen after the completion
timestamp are auto-attack continuing briefly post-completion, same artifact seen in other
missions this session). This mission's Assault points and Lockbox reward had no entry at all
before (silently gave 0 points / XP+gil only) -- fixed: 1100 points, box item 2192
(`???_polearm`) opened to hi-potion +3.

## Supplies Recovery (Leujaoam Sanctum, mission 6): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1100 Assault points). Existing build had real mob data (10 Imp + Gasharyad +
Salimuhl) wired as kill-all-12 -- but the capture reveals a supply-package race mechanic, not
combat. Gasharyad and Salimuhl are leaders of a rival faction ("the Immortals": "We will recover
our own supplies. We need no favors from the Immortals."). Kuihlud (real NPC, mission-start
dialogue) explains it directly: "you must recover more supplies than the Immortals." Killing an
Imp has a chance to drop a "supply package" temp item (4 distinct flavor items observed: gold
ingot, handful of armored arrowheads, pinch of cluster ash, pickaxe -- only 4 of 8 kills dropped
one). The Immortals' own count is announced periodically and plateaued at 3 while the player
reached 4; completion fired shortly after.

Applied: removed the wrong kill-all-12 progress-on-death from `mobs/Imp.lua`, unhooked
`instances/supplies_recovery.lua`'s completion logic (documented, not built -- needs a
player-side counter and a simulated rival counter that don't exist in the engine, and the exact
drop rate/win threshold aren't confirmed by one capture). Entrance was already exactly right.
Assault points (1100) and Lockbox reward (???_box -> hi-potion +3) fixed regardless.

## Leujaoam Cleansing (Leujaoam Sanctum, mission 1): real capture data mined, Thris Nov 2025 capture set (2026-08-18)

Real WIN capture (1100 Assault points). Fully validated the existing mature build end to end:
entrance exactly matched the PathLog first row, exactly 15 "Leujaoam Worm" kills confirmed
kill-all-15, and the Lockbox reward (???_box -> remedy + hi-potion +3) matched the existing
DIRECT_ITEMS/TREASURE_POOL_ITEMS table exactly. Only the Assault points needed a fix -- corrected
from a pre-existing 1000 guess to the real 1100.

## Milestone: capture-mining backlog cleared across all 5 zones (2026-08-18)

Every Assault mission with a findable Thris Nov 2025 (or equivalent systematic) capture link has
now been mined at least once: Mamool Ja Training Grounds (9/10), Lebros Cavern (9/9), Leujaoam
Sanctum (9/10), Ilrusi Atoll (10/10), Periqia (10/10). Remaining blocked-by-external-constraint
items: Azure Ailments (Mamool Ja, `.rar` archive, no extraction tool available in this
environment) and Azure Experiments (Leujaoam, video-only link, no downloadable capture found).
Searat Salvation (Ilrusi Atoll) is also video-only.

What's left across the whole build-out from here is qualitatively different work: ~11 missions
have their real mechanic fully documented (real NPC ids, positions, item ids, dialogue) but not
built, because each needs a genuinely new engine feature this codebase doesn't have yet --
Demolition Duty (controllable pet AI), Apkallu Seizure (stealth capture-net), Lost and Found
(proximity search), Desperately Seeking Cephalopods (fishing encounter), Wake the Puppet
(emote-response matching), Defuse the Threat (mine-detector proximity), Counting Sheep (trade
quota, unconfirmed), Imperial Treasure Retrieval (competitive gem-race/carrier-AI), Marids in the
Mist (temporary-item capture mechanic), Apkallu Breeding (two-mob pairing), Supplies Recovery
(supply-package race vs a rival NPC counter). Each is a standalone feature-sized task, not a data
fix -- worth prioritizing individually rather than attempting blind.

## Azure Ailments (Mamool Ja, mission 19): real capture data mined, 2023-08-23 Tacocat capture (2026-08-18)

User-provided capture (older format, no PathLog/sqlite NPCLogger -- Lua-table NPC database and
plain-text CapLog instead of the Thris set's format). Loss capture (ran out of time at the 30-min
limit), but reveals the real mechanic is completely different from the existing kill-all-62 build:
Garjham (real mission-giver NPC, was a NOT_CAPTURED stub) explains directly: "we will need you to
expose yourself to at least three of the status ailments associated with the kraken flu...
Amnesia, Bio, Disease, Slow, STR Down, Attack Down, and...Evasion Down. When you are affected by
one of these, hurry back here and report to me." The player triggered Garjham while still
actively afflicted with Attack Down (confirmed by effect-wear-off timing) and got "Attack Down...
Check." -- confirming the check is against currently-active effects. Only reached 1 of 3 before
timing out.

Applied: added Garjham's real position/data to `sql/npc_list.sql` (replacing the stub), `IDs.lua`,
`sql/instance_entities.sql`; wrote `npcs/Garjham.lua` implementing the real mechanic
(`player:hasStatusEffect()` against the 7 target effect ids, tracked per-effect via localvars,
completes at 3 distinct); removed the wrong kill-all-62 progress-on-death from all 8 disease-
vector mob scripts. One of those (`Mamool_Ja_Warder.lua`) is shared with Imperial Agent Rescue
(instance 11, a real validated kill mechanic there) -- guarded by instance id so both missions
get correct behavior from the one file. `instances/azure_ailments.lua` rewritten: mob spawns kept
(ambient hazards), completion now driven entirely by Garjham. Entrance approximated from the
capture's real Rune of Release position (this older format has no player-position track).
Dialogue event/message ids (136/7648/7654) are raw values from this specific capture, not
cross-checked against a dialog table dump -- flagged for in-game verification. No win capture
exists yet, so Assault points and Lockbox reward remain unconfirmed.

## Azure Experiments (Leujaoam Sanctum, mission 7): real capture data mined, 2025-03 Grievor captures (11 attempts, 10 wins) (2026-08-18)

User-provided batch of 11 separate capture attempts (older format, no PathLog). 10 real WINs
(1650 Assault points each) reveal the real mechanic is completely different from the existing
kill-all-10 build: Nareema (real mission-giver NPC, was a stub) is a mad scientist who "grafts"
body parts to the player on each trigger -- distinct flavor text per graft (raptor marrow, goobbue
muscle tissue x2, Opo-opo cerebral tissue in the mined run), each a mixed buff/debuff. All 10
winning captures received exactly 4 grafts before completion, re-triggering Nareema roughly every
110-215s -- consistent with a recast lockout, exact duration not confirmed. ~20 incidental kills
happened in the mined run against the 10 real Lamia mobs, but completion always followed strictly
from the 4th graft regardless of kill count.

Applied: added Nareema's real position/data to `sql/npc_list.sql` (replacing the stub), `IDs.lua`,
`sql/instance_entities.sql`; wrote `npcs/Nareema.lua` implementing the trigger-4-times-with-
cooldown mechanic (exact graft buffs/debuffs not applied -- effect ids unconfirmed, only the
completion logic is real); removed the wrong kill-all-10 progress-on-death from all 3 Lamia mob
scripts (confirmed exclusive to this mission, no cross-mission collision risk).
`instances/azure_experiments.lua` rewritten, now sets real Rune of Release/Ancient Lockbox
staging positions (were at the zone-default placeholder) via `setPos`. Entrance approximated from
the capture's real Rune of Release position. Assault points (1650) and Lockbox reward (??? ring
-> hi-potion +3) added.

## Searat Salvation (Ilrusi Atoll, mission 45): real capture data mined, 2023-06-19 Siknawz capture (2026-08-18)

User-provided real-WIN capture (825 Assault points, older format, no PathLog). The "zero backing
npc_list rows, doesn't exist" claim in the scaffold was wrong again -- 5 real Qiqirn Diver, 1
Qiqirn Chief Diver, and several Giant Orobon all exist with real positions in NPCLogger. Real
mechanic: divers cycle autonomously through dialogue/threat states ("Orobon! Everybody eaten by
orobon! Can you take me to boss?" -> "Aaahhh! Don't eat me!" near a Giant Orobon -> "Ready to go
to boss now.") and make their own way toward the Chief Diver. The captured win shows the player
took zero combat or movement actions the entire mission, and completion fired with the Chief
Diver saying "Hmmm, still not everybody. You bring everybody!" -- confirming completion doesn't
require all 5 divers, but leaving the exact rule (and whether player action is ever required)
unconfirmed by a single passive win.

Applied: entrance approximated from the real diver cluster's position (no PathLog in this
format). Header comment in `instances/searat_salvation.lua` rewritten with full real findings,
left unhooked -- needs an autonomous NPC-AI pathing/threat system with no precedent in this
codebase. Assault points (825) and Lockbox reward (???_box -> hi-potion +2) added.

## Milestone update: the 3 remaining blocked missions are now mined (2026-08-18)

User located and provided all 3 previously-blocked captures directly (Azure Ailments as a working
zip rather than the earlier-found .rar, Azure Experiments as an 11-attempt batch, Searat
Salvation). All 50 Assault missions now have at least one real capture mined. Two of the three
(Azure Ailments, Azure Experiments) turned out to have completely different real mechanics than
their kill-all scaffolds and are now correctly built and wired (status-ailment collection,
graft-trigger-4-times respectively). Searat Salvation's autonomous NPC-AI mechanic is documented
but not built, joining the ~12-mission "documented, needs a new engine feature" category.

## Imperial Agent Rescue (Mamool Ja, mission 11): invisible-wall doors fixed (2026-08-18)

User reported invisible walls at several specific in-game coordinates along the gate corridor,
and separately a visible-but-unopenable door, drawing the same comparison to the earlier Brittle
Rock (Excavation Duty) collision-mismatch bug. Cross-checked each reported position against the
Imperial Agent Rescue capture's own NPCLogger database and found a real entity at every single
one -- each tagged with a non-zero `DoorId` field by the NPCLogger addon itself, confirming
they're genuine door objects, not generic props or a widescan artifact.

All of them turned out to already exist in `sql/npc_list.sql` with correct real position data
(`_1u5`, `_1u6`, `_1u7`, `_ju0` through `_ju7` -- 11 doors total, all clustered in this mission's
own x 0-280 / z -420 to -560 area). Three (`_ju3`/`_ju5`/`_ju7`) are exactly co-located with the
3 real Dilapidated Gate combat obstacles and already referenced by `Dilapidated_Gate.lua`'s
`onMobDeath` door-hiding logic. But **none of the 11 were ever registered to instance 11 in
`sql/instance_entities.sql`** -- meaning none of them have ever actually spawned in-game,
regardless of how correct their position data was. The raw static zone collision (independent of
any NPC spawn) was still there, but nothing was rendered to explain it -- exactly matching
"invisible wall where a door should be."

Applied: registered all 11 real door ids to instance 11 in `instance_entities.sql`. Added a
missing `_ju0` entry to `IDs.lua` (a real npc_list row existed for it but nothing referenced it).
Left the rest of the zone's `_1uX` series alone -- those sit at very different coordinates and
belong to other Mamool Ja missions, not this one.

## Imperial Agent Rescue: real Pot Hatch search-and-rescue mechanic rebuilt (2026-08-18)

User reported live in-game that the mission was broken in two ways: the 3 Dilapidated Gates
appeared open by default (no obstacle), and there was no NPC to rescue at all. They also gave the
real mechanic from their own experience with this mission: Brujeel is hidden behind one of the 3
gates in a "Pot Hatch" -- destroy a gate to reach its hatch, then search the hatch for a 1-in-3
chance he's inside (he can be behind any of the 3). Finding him triggers his release and the
mission clear.

This directly contradicted the previous session's "CONFIRMED CORRECT" design note, which tracked
completion off "exactly 3 Dilapidated Gate takes N damage hits." Re-checking that same capture
(`Mamool Ja Training Grounds PSC - Imperial Agent Rescue.zip`) found the original read was wrong
on a recount: there are actually 7 "Dilapidated Gate takes damage" lines, and every one of them is
incidental splash damage from Mamool Ja Warder AoE skills (Firespit, etc.) hitting the stationary
gate object -- not deliberate player-vs-gate combat. Only 1 of 7 real Warder kills happened before
the mission completed, same as previously found. The capture's real completion trigger (a
`CEntityAnimationPacket` with FourCC `"deru"` fired on Brujeel himself, self->self, immediately
followed by 6 `CMessageTextPacket` lines) has nothing to do with gate-hit counting at all.

Found the real Pot Hatch npcs already sitting unused in `sql/npc_list.sql` (`_jul`/17047916,
`_jum`/17047917, `_jun`/17047918, real "Pot Hatch" display name) and already keyed in `IDs.lua`
from an earlier pass, but never registered to instance 11 and never scripted. Position-matched
each to its gate pen by x/z proximity: `_jun` (220.9,-415.6) pairs with GATE_1/`_ju3`
(220,-440); `_jul` (183.5,-581.3) pairs with GATE_2/`_ju5` (180,-560); `_jum` (267,-592.3) pairs
with GATE_3/`_ju7` (260,-560) -- each within ~35 units, versus 100+ units to any other gate.

Also recovered Brujeel's real 6-line rescue dialogue from the capture (raw MesNum 7539-7544:
"Am I glad to see you!" ... "You didn't see anything. You didn't hear anything. Got it?") -- added
to `IDs.lua` with the same -1 client-version offset already verified for this zone's
7507-7515 block, since the raw range sits directly between two already-adjusted ranges from
earlier sessions.

Applied:
- `sql/instance_entities.sql`: registered the 3 Pot Hatch npcids to instance 11.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua`: added Brujeel's 6 dialogue text ids, updated
  the mission's design-note comments.
- `scripts/zones/Mamool_Ja_Training_Grounds/npcs/_pot_hatch_common.lua` (new): shared search
  logic -- 1-in-3 chance per instance (randomized once via `instance:setLocalVar("brujeelHatch",
  math.random(1,3))` in `onInstanceCreated`), reveals Brujeel at the hatch's position with the
  real "deru" animation and real dialogue, then calls `instance:complete()` directly -- no
  separate "talk to Brujeel" step, confirmed unnecessary both by the capture and by the user's own
  live testing.
- `scripts/zones/Mamool_Ja_Training_Grounds/npcs/_jun.lua`, `_jul.lua`, `_jum.lua` (new): thin
  per-npc wrappers around the shared logic (required since the engine loads npc scripts by exact
  `name`, and all 3 hatches have different names).
- `scripts/zones/Mamool_Ja_Training_Grounds/instances/imperial_agent_rescue.lua`: removed the old
  progress>=3 auto-complete trigger; forced the 3 real door props to `NORMAL` status explicitly at
  spawn (best-effort fix for the "gates open by default" report -- ask the user to confirm after
  retest whether this was the actual cause or if it's a deeper model/mesh issue).
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Dilapidated_Gate.lua`: updated the header comment
  -- the gate/door pairing is now position-confirmed, not just inferred from LSB naming.

## Imperial Agent Rescue: `_1u6` door removed, led to an unused area (2026-08-18)

Follow-up to the "invisible-wall doors fixed" entry above. That fix registered `_1u5`/`_1u6`/`_1u7`
to instance 11 alongside the 3 real gate doors (`_ju3`/`_ju5`/`_ju7`) based only on rough
coordinate-range clustering, not a confirmed pairing to anything in this mission -- unlike
`_ju3`/`_ju5`/`_ju7`, which position-match the 3 real Dilapidated Gate mobs exactly.

User reported an open, passable door at (159, 2, -420) that led into an unused portion of the map
belonging to a different Assault mission sharing this same physical zone. That position is an
exact match for `_1u6` (17047865, 159.995/0.441/-419.996). Removed `_1u6`'s registration from
instance 11's `instance_entities.sql` entry so it stops spawning here, restoring the natural
closed wall.

`_1u5` and `_1u7` were registered under the same unverified reasoning and were not individually
confirmed broken -- worth checking in-game and removing the same way if they turn out to lead
somewhere they shouldn't too.

## Azure Ailments: real Assault points confirmed, was giving 0 (2026-08-18)

Follow-up to a broader points audit that found 10/50 missions with no capture-confirmed
`BASE_ASSAULT_POINTS` entry in their zone's `Rune_of_Release.lua` (all previously-mined captures
for those 10 turned out to be partial runs that never reached completion). User supplied a new
capture (`Mamool Ja Training Grounds SL - Azure Ailments (Wiggo, Win, Duo).zip`, a different
capture tool/format than the Thris Nov 2025 set -- raw `PacketViewer/` hex dumps, no plain-English
`CapLog`) that does reach completion.

Found the real points value (1200) in a `0x02A` packet log entry -- `MessageSpecialPacket` is
opcode `0x2A` in this codebase's C++ (`src/map/packets/message_special.cpp`), not `0x029` as
initially assumed; the `0x029` log for this same capture had nothing relevant to points at all.
The hit is the last `MessageSpecial` entry tied to the player character in the whole capture,
`Param 1: 1200`, timestamped right after the final combat entry -- consistent with the points
award firing right before the exit-zone warp.

Lockbox reward data was NOT mined from this same capture -- `Ancient Lockbox` interactions appear
scattered throughout, well before the completion message, which doesn't match how this mission's
lockbox is built (hidden via `status.DISAPPEAR` until `onInstanceComplete`). Left unconfirmed
rather than guessing from data that doesn't fit the known mechanic.

Applied: `scripts/zones/Mamool_Ja_Training_Grounds/npcs/Rune_of_Release.lua` -- added
`[19] = 1200` to `BASE_ASSAULT_POINTS` (was previously falling through to 0 points on every
Azure Ailments completion).

## Counting Sheep: real Assault points + lockbox rewards confirmed (2026-08-18)

Another of the 10 missions found with no capture-confirmed reward data (previously-mined capture
for this mission never reached completion). User supplied a second, different capture
(2023-05-25 Siknawz) that does reach completion, with clean plain-text CapLog data:
"You gain 825 Assault points!" and "You find a hi-potion +2 in the Ancient Lockbox." / "You find
a hi-potion tank in the Ancient Lockbox." right after "Siknawz obtains a ??? dagger!" (item 2191,
`sql/item_basic.sql`).

Applied:
- `scripts/zones/Leujaoam_Sanctum/npcs/Rune_of_Release.lua`: added `[5] = 825` to
  `BASE_ASSAULT_POINTS` (was falling through to 0).
- `scripts/zones/Leujaoam_Sanctum/npcs/Ancient_Lockbox.lua`: added mission 5 to
  `OTHER_MISSION_ITEMS` -- `??? Dagger` (2191) direct + hi-potion_+2/hi-potion_tank pool, same
  pool as Escort Professor Chanoix's mission 3 entry.

## CORRECTION: Azure Ailments points value was wrong, reverted (2026-08-18)

The "1200" Assault points value added for Azure Ailments earlier today was a misread. While
decoding a different capture's raw packet log by hand, found the actual byte layout of a
`0x2A` MessageSpecialPacket (`src/map/packets/message_special.cpp`) and discovered the specific
packet used for the earlier "1200" claim decodes to messageID **7509** (`RUNE_UNLOCKED_POS`,
"Mission objective completed. Unlocking Rune of Release...") once the `+0x8000` PC-type offset is
correctly subtracted -- **not** 7511 (`ASSAULT_POINTS_OBTAINED`). The `param0=1200` field belongs
to the rune-unlock message's own payload, not a points value at all.

Re-scanned the entire Azure Ailments Wiggo capture for any packet that actually decodes to 7511 --
none exist. The capture genuinely has no points data; reverted `[19] = 1200` back out of
`BASE_ASSAULT_POINTS`. See `topaz_packet_log_decoding` memory for the correct decode procedure so
this mistake isn't repeated on the other raw-packet-only captures being mined today.

## 6 more missions confirmed, Apkallu Breeding correctly deferred (2026-08-18)

User supplied 7 more captures. 6 reached real completion with clean data:

- **Red versus Blue** (9, Leujaoam): 2198 Assault points; lockbox ??? Earring (2277) direct +
  hi-potion_+3 pool.
- **Operation: Snake Eyes** (38, Periqia): 2198 points; ??? Necklace (2282) direct +
  hi-potion_+3/hi-potion_tank pool.
- **Wake the Puppet** (39, Periqia): 1650 points; ??? Box (2286) direct +
  hi-potion_+3/hi-potion_tank pool.
- **Apkallu Seizure** (46, Ilrusi Atoll): 1098 points; ??? Axe (2193) direct + hi-potion_+3 +
  hi-reraiser pool.
- **Lost and Found** (47, Ilrusi Atoll): 1650 points; ??? Gloves (2195) direct +
  hi-potion_+2/hi-potion_tank pool.
- **Breaking Morale** ("Breaking Morale 4" capture): failed run (party wiped), no new data --
  still needs a real completion capture.

**Apkallu Breeding** (26, Lebros) needed a different approach -- its capture uses a raw-hex-only
tool format ("... Item Appraisal") with no plain-text CapLog at all. Hand-decoded the `0x2A`
MessageSpecial packets directly (byte layout: entity id at `0x04`, four uint32 params at `0x08`-
`0x17`, messageID at `0x1A`, `+0x8000` offset for PC actors -- see `topaz_packet_log_decoding`
memory, written specifically because of a mistake made earlier this session doing this same kind
of decode). Found 2 real completions in the one capture (825 and 550 points, both confirmed via
`ASSAULT_26_START` immediately preceding each). Initially treated these as party-size variance
and picked 825 as a flat `BASE_ASSAULT_POINTS` value -- **user corrected this**: Apkallu Breeding
points actually scale with how many apkallu pairs you correctly match in the mission's pairing
minigame (confirmed via ffxiclopedia: max 1300 for 8/8 pairs, 1430 with the Assault armband,
completes on just 1 correct pair). The two observed values are consistent with different pair
counts, not different party sizes. Reverted the flat value -- left unset (falls through to 0,
same as before) since the pairing minigame itself isn't built yet, and documented the real formula
in `instances/apkallu_breeding.lua`'s header and `Rune_of_Release.lua`'s comment for whoever
builds it later.

## Imperial Agent Rescue: two more door reports (2026-08-18)

User reported two more doors after the earlier `_1u6` fix:
- `_1u6` (already covered above) led into an unused area -- confirmed and removed.
- `_1u5` (121,2,-499) renders **closed/impassable but should be open** -- unlike `_1u6`, this one
  does belong to the mission (a real reported passage), just isn't one of the 3 objective gates.
  Its DB default is already `animation=8` (`ANIMATION_OPEN_DOOR`), so forced it explicitly at
  instance creation too, matching the same treatment already given the 3 real gates. Not yet
  confirmed fixed live.
- The 3 real gates (`_ju3`/`_ju5`/`_ju7`) themselves still render open by default despite
  `animation=9` (closed) both in the DB and forced explicitly -- root cause remains unconfirmed
  after tracing the entire spawn-packet code path (see the earlier "gates open by default" entry).
  User is separately testing whether the real break mechanic (Mamool Ja Warder mob-skill AoE
  splash damage, not direct player damage -- user-confirmed) actually breaks a gate once enough
  hits land; mark this fully resolved only once that's confirmed working end-to-end.

## Imperial Agent Rescue: gates never took any damage at all (2026-08-18)

User reported seeing zero "Dilapidated Gate takes damage" messages in-game, even with Warders
using Firespit nearby -- contradicting the real mechanic (gates break from Warder AoE splash, not
direct player damage, matching the original capture). Traced this past the DEF/MDEF tuning
entirely: `scripts/globals/mobskills/firespit.lua`'s `onMobWeaponSkill` only ever calls
`target:takeDamage(...)` on the single `target` passed in by the engine -- the Dilapidated Gate
was never a candidate target at all, so no defense-stat tuning could ever make it take damage.

This is the same class of limitation already documented in `Brittle_Rock.lua`'s header (no engine
hook to filter incoming damage by attacker type) -- confirmed with the user, who chose the
Lua-only approach over a C++ fix (bigger lift, would also need to touch Brittle Rock's same gap).

Applied: added splash-damage logic directly to `firespit.lua`, strictly guarded to instance 11
(this file is shared globally by every mob in the game that uses Firespit) -- after the normal
single-target hit resolves, scans `instance:getMobs()` for any `Dilapidated_Gate` mob within 8
yalms of the target and deals it the same damage roll. Scoped to Firespit specifically since every
logged "Dilapidated Gate takes N damage" line in the original capture immediately followed a
"Warder uses Firespit" line.

Also added Orichalcum Survey's real Assault points (1980, decoded from a raw packet-only capture
via the same 0x2A method used for Apkallu Breeding).

## Imperial Agent Rescue: Stave Toss also splashes gate damage (2026-08-18)

Follow-up to the Firespit splash fix above. User confirmed "<Weapon> Throw" (the ranged attack
that costs the mob its equipped weapon) should deal the same AoE damage to nearby Dilapidated
Gates. Identified as `scripts/globals/mobskills/stave_toss.lua` -- its own header comment already
says "(staff wielding Mamool Ja only!)" and its mechanic ("mob loses Staff on using Stave Toss")
matches the description exactly. Applied the identical instance-11-guarded splash pattern used for
Firespit. Only this one weapon-toss variant is confirmed/applied -- if Warders wielding other
weapon types use a differently-named toss skill that also splashes gate damage, flag it and it'll
get the same treatment.

## SYSTEMIC: instance timeout/failure hangs at black screen forever (2026-08-18)

User reported: when an instance's time limit expires, the player gets a black screen that never
clears and is never actually removed from the instance. Investigated via `log/map-server.log`
(the `[WARPASSAULT DEBUG]` trail) and the C++ event-resolution code, since nothing about this was
Assault-mission-specific in the log itself.

Root cause, traced through the full chain:
- `CInstance::Fail()` (`src/map/instance.cpp`) calls `Cancel()`, `ClearEntities()` (only clears AI
  state stacks -- doesn't destroy entities or touch `PChar->PInstance`/`loc.zone`, ruled that out),
  then fires Lua `onInstanceFailure`.
- Every mission's `onInstanceFailure` calls `v:startEvent(102)` directly (not through a normal NPC
  trigger), which correctly sets `PChar->m_event.EventID` (via `CEventPacket`'s constructor,
  `src/map/packets/event.cpp:86`) but does NOT set `PChar->m_event.Script` -- there's no NPC being
  triggered, so nothing sets it.
- When the client sends back its event-acknowledgment packet, `SmallPacket0x05B`
  (`src/map/packet_system.cpp:2910`) calls `luautils::OnEventFinish`, which resolves which script
  to run via `LoadEventScript` (`src/map/lua/luautils.cpp:4249`) -- checked in this order:
  1. `PChar->m_event.Script` (empty in this flow, skipped)
  2. **the character's own instance file's `onEventFinish`** (`PChar->PInstance` is valid, so this
     IS checked)
  3. battlefield fallback (n/a)
  4. the zone's own `Zone.lua` `onEventFinish` (every zone correctly implements `csid == 102 ->
     player:setPos(...)` here)
- **54 of 56 Assault instance files had a completely empty `onEventFinish` stub** (pure
  boilerplate, `function(player, csid, option) end`, doing nothing). Because step 2 above finds
  this "valid" empty function first, it runs (successfully, no error) and `LoadEventScript` never
  reaches step 4's real, working implementation in `Zone.lua`. The player's cutscene substate
  (`SUBSTATE_IN_CS`) does get cleared by `SmallPacket0x05B` regardless of what the function did,
  but `setPos()` never fires, so the player is never actually moved out of the (now-failed,
  AI-cleared) instance zone -- consistent with "stuck at a black screen, never removed."

This is NOT specific to Imperial Agent Rescue or any one mission -- every Assault mission across
all 5 zones shared this exact empty-stub pattern, so every single one had this same latent bug on
timeout. Normal completion (talking to Rune of Release) is unaffected -- that flow sets
`PChar->m_event.Script` to the NPC's own script during the real onTrigger interaction, which
`LoadEventScript` checks *before* the instance-level fallback, so it never reaches the broken step.

Applied: removed the empty `onEventFinish` stub from all 54 affected instance files (kept the 2
that already have real, non-empty implementations -- Arrapago Remnants, The Black Coffin -- 
untouched). This lets `LoadEventScript` correctly fall through to each zone's `Zone.lua`, which
already has a working `csid == 102 -> setPos(...)` implementation for every zone. Not yet
confirmed fixed live -- ask the user to test a real timeout after their next recompile-free reload
(Lua-only change, no C++ touched, no DB reimport needed).

## Imperial Agent Rescue: Warders despawning when lured too far (2026-08-18)

User reported luring a Warder away from its spawn point causes it to despawn entirely, which
could strand the mission now that Warders are load-bearing for the gate-break mechanic (Firespit/
Stave Toss splash damage). This is a real engine mechanic, not a scripting bug:
`CMobController::Tick()` (`src/map/ai/controllers/mob_controller.cpp:792`) checks
`PMob->IsFarFromHome()` after disengage and despawns the mob unless `MOBMOD_NO_DESPAWN` is set (or
the global `map_config.mob_no_despawn` config flag is on).

Applied: `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Mamool_Ja_Warder.lua` now sets
`mob:setMobMod(tpz.mobMod.NO_DESPAWN, 1)` in `onMobSpawn`, scoped to instance 11 only (Azure
Ailments' ambient-hazard use of this same shared mob file is unaffected).

**Worth checking on other missions**: any mission where a specific mob is load-bearing (needed
alive for a mechanic, not just a generic kill-count target) in a wide-open play area is
susceptible to this same leash-despawn risk if a player kites it too far. Apply the same
`MOBMOD_NO_DESPAWN` fix to that mob's `onMobSpawn`, scoped to the relevant instance id, the next
time this comes up.

## Excavation Duty: Qiqirn Mine detonates but doesn't kill the Brittle Rock (2026-08-19)

User reported this used to work in an early pass and regressed, suspecting an earlier mob
model/id swap broke it. Investigated the full chain instead of guessing:

- `scripts/globals/items/qiqirn_mine.lua` (the item-use trigger) correctly spawns the mine via
  `instance:insertAlly(10633)` and tags it with `PlayerID`/`RockID` localvars -- confirmed intact.
- `mob_groups` groupid 10633 correctly resolves to poolid 5872, name `Qiqirn_Mine` -- confirmed
  intact, still loads `scripts/zones/Lebros_Cavern/mobs/Qiqirn_Mine.lua` as expected.
- That pool's `skill_list_id` is 0 (no skill list assigned) -- initially suspected this as the
  cause, but `CLuaBaseEntity::useMobAbility()` calls `battleutils::GetMobSkill(skillid)` directly
  and bypasses skill-list validation entirely, so this doesn't actually matter for a forced
  ability call. Ruled out.
- Mob skill id 1838 (`mine_blast`) exists correctly in `mob_skills.sql`. Ruled out.
- **Real cause**: the "explicit kill" line used `rock:setHP(0)`. `CLuaBaseEntity::setHP()`
  (`src/map/lua/lua_baseentity.cpp:6919`) just writes `health.hp = 0` directly -- it does NOT
  route through the real damage/death pipeline (`takeDamage()`), so `onMobDeath` never fires. The
  mine's countdown, message, and Mine Blast animation were all working correctly; only the actual
  kill was silently a no-op, leaving the rock "alive" at 0 HP.

Applied: `scripts/zones/Lebros_Cavern/mobs/Qiqirn_Mine.lua` -- `rock:setHP(0)` replaced with
`rock:takeDamage(rock:getMaxHP(), mob, tpz.attackType.PHYSICAL, tpz.damageType.NONE)`, the same
real-damage-pipeline pattern already used for the Imperial Agent Rescue gate-splash fixes. This
correctly triggers `Brittle_Rock.lua`'s existing `onMobDeath` prop-hide logic.

## Excavation Duty: Brittle Rock 4/5 walls confirmed as a collision-mesh limitation (2026-08-19)

Follow-up to the debug-logging pass above. User confirmed the position-relocation test (moving
the prop to Y=-500 in addition to hiding it) did NOT fix rocks 4/5 (`_ir0`/`_ir1`) either --
still impassable after a normal melee kill, same as before.

With this, every Lua/SQL-reachable lever has been tried and shown to make no difference:
status, animation, and position have all been confirmed (via debug log, byte-identical across
all 5 rocks) to apply successfully to the broken props exactly as they do to the working ones.
There is no remaining code-level or data-level difference between rocks 1-3 (work) and 4-5
(don't) to find.

Conclusion: this is very likely a static collision-mesh limitation in this server's copy of the
Lebros Cavern zone data at these 2 specific spots, independent of the NPC prop's visual/positional
state entirely -- outside what server-side Lua/SQL scripting can reach. Logged as a known
limitation rather than a bug to keep chasing; would need client-side .DAT zone-geometry work
(out of scope for this codebase) to actually resolve, if it's fixable at all on this server build.

## Excavation Duty: Brittle Rock 4/5 collision PROVEN independent of any NPC entity (2026-08-19)

Definitive confirmation. After removing Brittle Rock 4/5 and their wall props (`_ir0`/`_ir1`)
from the instance entirely (previous entry), the user confirmed the mission now completes
correctly at 3 rocks -- but the passageway where those 2 rocks/walls used to be is **still
completely impassable**, acting exactly like a solid wall, despite no NPC entity of any kind
being registered there anymore.

This rules out every remaining doubt: the blocking collision was never coming from the wall
prop, the rock mob, or anything else spawnable via `instance_entities`/Lua at all. It's part of
this server's static Lebros Cavern zone geometry at those 2 specific coordinates, completely
independent of any entity state. No further server-side investigation is warranted -- this would
require client-side .DAT zone-geometry editing to actually fix, which is out of scope for this
codebase.

Practical impact: the mission is fully completable via the current workaround (3 remaining rocks
give real completion). The phantom wall is a dead-end/cosmetic oddity in that one corridor, not a
mission blocker.

## Excavation Duty: Brittle Rock 4/5 REOPENED -- the "proof" test had an unaccounted-for gap (2026-08-20)

User asked to scan a fresh capture (`Lebros Cavern PSC - Excavation Duty.zip`, Siknawz format) for
exact Brittle Rock positions, following a DSP dev's insight: open/closed-state props (doors,
rocks, etc.) can need an exact second collision-partner entity cleared in sync with the primary
for a terrain/navmesh to allow passage through that spot at all -- not just the visible model.

Mined `npclogger/logs/Lebros Cavern.log` (entity dump, not raw packets -- direct, no decoding
needed) for every `BrittleRock`/`_1r*`/`_ir*` entry. Found something the earlier investigation
never had: **every one of the 5 rocks has a second, distinct NPC id sitting at the exact same
XYZ as its own mob spawn point**:

| Rock | Mob id | Wall prop | Dup id (same coords as mob) |
|---|---|---|---|
| 1 | 17035282 (179, -42.362, 380) | `_1rx` 17035537 | 17035283 |
| 2 | 17035284 (179, -32.992, 100) | `_1ry` 17035538 | 17035285 |
| 3 | 17035286 (259, -32.862, 220) | `_1rz` 17035539 | 17035287 |
| 4 | 17035288 (300, -32.910, 341) | `_ir0` 17035540 | 17035289 |
| 5 | 17035290 (339, -32.901, 300) | `_ir1` 17035541 | 17035291 |

Cross-checked these dup ids against `sql/mob_spawn_points.sql` -- they're already there, registered
as real `Brittle_Rock`-family spawn points at those exact coordinates (14165-14174). But
`sql/instance_entities.sql` tells a different story: a 2026-08-18 comment removed
17035283/285/287/289/291 from Excavation Duty's registration, on the theory that they were
**duplicate** mob_spawn_points rows -- "nothing in Lua ever mapped or killed them, so they sat as
permanent, untracked collision." That diagnosis was half right (they genuinely were untracked) and
half wrong (they're not duplicates -- they're real, distinct retail content, confirmed independently
by this fresh capture).

**This directly undermines the next day's "definitive proof"**: the 2026-08-19 entry
("Brittle Rock 4/5 collision PROVEN independent of any NPC entity") removed rocks 4/5 and their
wall props from the instance and found the passage still blocked with nothing registered there --
concluding this must be baked static zone geometry, unfixable from Lua/SQL. But the dup mobs
(17035289/17035291) had *already* been removed the day before and were never re-added during that
test. So the test's "nothing registered there" wasn't actually true in the sense the theory below
requires -- the dup was never present to be spawned-and-cleared in the first place. The 08-19 test
ruled out "wall prop position/status/animation alone" (already well-established at that point via
byte-identical debug logging across all 5 rocks) -- it did not, and could not, rule out "needs the
dup entity present and explicitly cleared too," because that entity wasn't in the picture at all
by the time that test ran.

**Real fix attempted** (not yet confirmed -- see caveat below):
- `scripts/zones/Lebros_Cavern/IDs.lua`: added `BRITTLE_ROCK1-5_DUP` (17035283/285/287/289/291) to
  the mission's mob table, so `onInstanceCreated`'s existing `for i, v in pairs(ID.mob[21]) do
  SpawnMob(v, instance) end` loop spawns them automatically alongside everything else.
- `sql/instance_entities.sql`: restored all 5 dup ids, and re-added Brittle Rock 4/5
  (17035288/17035290) + their wall props (`_ir0`/`_ir1`, 17035540/17035541), reverting the
  2026-08-19 removal.
- `sql/npc_list.sql`: fixed a real, independently-confirmed stale bug found via the same fresh
  capture -- `_1rx` (Rock 1's wall) was sitting at `-32.900`, a leftover from an abandoned earlier
  fix attempt that matched it to the rock mob's Y at a time when that mob's own Y was *also*
  wrong. The mob's Y was later independently reverted to the real `-42.362` (2026-08-18 comment,
  `mob_spawn_points.sql`), but the wall was never reverted alongside it, leaving it an orphaned,
  doubly-wrong value. This fresh capture directly confirms `_1rx`'s real position is `-43.362` (not
  matched to the rock's own Y at all -- a real ~1-unit vertical offset between the rock's stand
  point and its wall exists on every other confirmed rock too, e.g. rocks 2/3/4/5 all show
  differences of a few hundredths, not zero). Reverted to `-43.362`.
- `scripts/zones/Lebros_Cavern/mobs/Brittle_Rock.lua`: `onMobDeath` now looks up the paired dup
  mob (via `GetMobByID`) alongside the wall prop, and applies the same `setStatus(DISAPPEAR)` +
  move-to-`Y=-500` treatment to both, in sync, when the real rock dies. Also removed the
  `[BRITTLE_ROCK DEBUG]` print-statement instrumentation added during the earlier investigation --
  no longer needed now that a real, data-backed hypothesis exists to test instead of blindly
  comparing runtime state across rocks.
- `scripts/zones/Lebros_Cavern/instances/excavation_duty.lua`: reverted the 2026-08-19 workaround
  -- `setStatus(NORMAL)` calls restored for `_ir0`/`_ir1` in `onInstanceCreated`, completion
  threshold reverted `3 -> 5`.

**Caveat, stated plainly**: this is a real, capture-backed hypothesis, not a confirmed fix. It's
entirely possible the passage really is baked into static zone geometry regardless of any entity
state, in which case this change just restores real content without resolving the actual bug. It
needs a full DB reimport (multiple SQL row changes in this batch -- express mode has already
proven unreliable for new-row inserts earlier this session) and a genuine live retest before this
can be marked resolved either way.

## Seagull Grounded: added community wiki reference data (2026-08-19)

User provided https://horizonffxi.wiki/Seagull_Grounded. Cross-checked against everything already
built/confirmed in this session and found strong agreement: "Debaucher" matches the real mob
family name already inferred from `EXCALIACE_DEBAUCHER1/2` text ids, and the wiki's Ancient
Lockbox numbers (40% ???_box / 20% each ???_sword/???_polearm/???_gloves direct, 70% Hi-Reraiser
bonus roll) match `Ancient_Lockbox.lua`'s `Q_ITEMS[31]`/`REG_ITEMS[31]` exactly -- both built
independently from real capture data earlier in this session, no changes needed there.

New reference info folded into `Excaliace.lua`'s TODO block for whenever the room-investigation
and aggro-flee mechanics get built: route is Periqia Map 8 (H-6 start, H-7/I-7 first room pair,
two more randomized picks in H-8/I-8, H-9 lower fork, G-10 final corridor, F-11 destination), and
real enemy rosters per area (Arrapago Crab lv72-74 x9 in the room pairs, Periqia Pugil lv75-77 x5
at H-9, Debaucher lv77-79 x3 along H-9/G-10/F-11).

One discrepancy noted, not resolved: the wiki cites a lower base points value (1100 solo, with
stacking leader/first-clear bonuses) than the 2198 already confirmed here from a real capture's
plain CapLog text. Capture evidence takes precedence -- left as 2198, discrepancy just flagged in
case the bonus multipliers turn out to explain it later.

## Seagull Grounded: added real path map image (2026-08-19)

User provided http://files.samhart.net/img/clan/assault/SeagullGrounded.jpg, an ffxi-atlas.com
Periqia map overlay showing party/Excaliace start points, his full path (dotted line), and
Arrapago Crab/Periqia Pugil/Debaucher/Rune of Release positions. Saved to
`D:\Claude\exports\reference_images\Periqia_SeagullGrounded_Excaliace_Path_Map.jpg`.

Confirms the wiki's grid description visually: start near G-6/H-6, a serpentine route south
through the F/G/H columns from row 6 to row 12, ending at the Rune of Release near F-12. Grid-
square resolution only, not real x/y/z -- doesn't replace the still-needed video-derived waypoint
coordinates, but useful as a shape/sanity-check reference. Noted in `Excaliace.lua`'s TODO block.

## Lamia No.13: 3 real bugs found and fixed via user report + real capture (2026-08-19)

User reported three issues live in-game: (1) Rune of Release/Ancient Lockbox not at the reported
completion position, (2) no companion mobs spawning with Lamia (contradicting the mission's
existing "solo kill-target, per Solo Assault Guide by Korvana" assumption), (3) an invisible wall
at (70,-4,-143) blocking half the map -- the same class of bug as Imperial Agent Rescue's doors.

Re-mined the already-available real capture (`Ilrusi Atoll PFC - Lamia No.13.zip`) via its
NPCLogger widescan data (SQLite) rather than guessing:

- **Rune of Release / Ancient Lockbox real positions**: (60,-3,-145) and (63,-3,-144)
  respectively -- close to each other and to the position the user reported from memory
  (66,-3,-145), but not identical; `onInstanceCreated` was never calling `setPos()` for either at
  all, so they sat at a generic default. Fixed with the real widescan-confirmed coordinates.
- **Companions**: not Fomor as initially guessed -- real widescan shows 3 mobs clustered exactly
  at Lamia's own spawn position: Fallen Volunteer, Fallen Imperial Wizard, Fallen Imperial
  Trooper. All 3 already had real `mob_spawn_points`/`mob_groups` rows in this repo's SQL
  (groupids 4/5/6, zone 55) -- just never registered to instance 42 or referenced in `IDs.lua`.
  No capture evidence they're required kills (objective text is specifically "Eliminate Lamia
  No.13"), so wired in as ambient guards, not objective-relevant.
- **Invisible wall**: real door prop `_1jd` (17002719, `npc_list.sql`) position-matches the
  user's reported coordinates almost exactly (79.081,-3.499,-141.455 vs reported 70,-4,-143) --
  same missing-registration bug as Imperial Agent Rescue's doors. DB default animation is already
  8 (open); registered and forced explicitly, same precedent as that earlier fix.

Applied: `scripts/zones/Ilrusi_Atoll/IDs.lua` (added `_1jd` + the 3 companion mob ids to the
mission's mob table), `sql/instance_entities.sql` (registered the door + 3 companions to instance
42), `scripts/zones/Ilrusi_Atoll/instances/lamia_no_13.lua` (spawns the companions, real
Rune/Lockbox positions, door forced open). Not yet confirmed fixed live.

## Lamia No.13: 2 more bugs found (lockbox targetability, static roaming) (2026-08-19)

Follow-up to the Rune/Lockbox-position/companions/door fixes above.

**Ancient Lockbox not targetable/usable**: the earlier fix had explicitly hidden it
(`setStatus(DISAPPEAR)`) at creation and revealed it (`NORMAL`) on completion, mirroring the
pattern used elsewhere this session. But this zone's own `Ancient_Lockbox` npc row (17002654)
has `FLAG_UNTARGETABLE` baked into its default `entityFlags` (3715 = `0xE83`, bit `0x800` set),
and a sibling Ilrusi Atoll mission that's already confirmed working (`instances/extermination.lua`)
never touches its status at all -- just `setPos()`. Removed the `DISAPPEAR`/`NORMAL` toggle at
creation to match that proven-working pattern instead of guessing at the flag interaction further.

**Lamia and her 3 companions stay at a static location instead of wandering the whole map**:
`MOBMOD_ROAM_DISTANCE` (`src/map/mob_modifier.h:62`, stored in tenths of a yalm,
`src/map/entities/mobentity.cpp:483`) was never set for any of the 4 mobs -- it isn't a
`mob_pools` column, it's Lua-only, and defaults to 0 (zero roam radius) if unset, matching the
reported symptom exactly. Set to an estimated 500-yalm radius (5000 stored units) for all 4 --
not measured against the real zone/instance dimensions, worth tuning after a live test.

Applied: `scripts/zones/Ilrusi_Atoll/instances/lamia_no_13.lua` (removed the lockbox status
toggle), `scripts/zones/Ilrusi_Atoll/mobs/Lamia_No13.lua` + 3 new files (`Fallen_Volunteer.lua`,
`Fallen_Imperial_Wizard.lua`, `Fallen_Imperial_Trooper.lua`) each setting `ROAM_DISTANCE` on
spawn. Not yet confirmed fixed live.

## Lamia No.13: companions overcorrected to roam independently (2026-08-19)

User reported the companions should stay with Lamia as she wanders, not roam off on their own --
the uniform 500-yalm `ROAM_DISTANCE` given to all 4 mobs in the previous fix caused exactly that,
since it's a per-mob wander radius around each mob's own spawn point, not a follow-the-leader
mechanic. Confirmed via source read (`src/map/ai/controllers/mob_controller.cpp`) that this
engine has no mechanism for one wild mob to track another's live position -- `PMaster`/pet-
following is player-pet-only, and `SUBLINK`/`LINK_RADIUS` mobMods only link aggro, not movement.
Practical workaround: dropped the 3 companions' `ROAM_DISTANCE` to 100 (10 yalms) while leaving
Lamia's own at 5000 (500 yalms) -- since their spawn point sits right on top of hers, a small
radius keeps them visually "with her" without an actual following mechanic. User later asked
whether there's a pet-like binding flag; answered no (documented above), and applied this radius
fix as the practical alternative, which the user accepted ("then they should behave and follow
more like what I would expect them to").
- `scripts/zones/Ilrusi_Atoll/mobs/Fallen_Volunteer.lua`, `Fallen_Imperial_Wizard.lua`,
  `Fallen_Imperial_Trooper.lua` -- `ROAM_DISTANCE` 5000 → 100.
- **Not yet confirmed fixed live** (roam radius specifically; the "follow" *behavior* is a
  workaround, not a true fix, so may need further tuning after live testing).

## Lamia No.13: Ancient Lockbox still unusable -- real root cause found (2026-08-19)

User reported the Lockbox still not usable even after the earlier `setStatus` toggle removal
(which turned out to be a no-op -- the toggle was never the real blocker). Traced the actual
targetability check this time instead of guessing again: `CNpcEntity::isUntargetable()`
(`src/map/entities/npcentity.cpp:71/88`) checks `(m_flags & 0x800) == 0x800` directly against the
`entityFlags` value loaded straight from `npc_list.sql` (confirmed via
`src/map/instance_loader.cpp:262-299` -- instance-spawned NPCs `INNER JOIN npc_list` and always
inherit its `entityFlags` column, there is no per-instance override). This bit (`FLAG_UNTARGETABLE`,
`src/map/entities/baseentity.h:163`) is checked completely independently of `status` -- so the
earlier `setStatus(DISAPPEAR)/(NORMAL)` toggle was never capable of fixing this either way, whether
present or removed.

Compared this npc's row (17002654, `entityFlags=3715`) against every other zone's Ancient Lockbox
row in `npc_list.sql` (10 other rows, all zones) -- every single other one uses `entityFlags=1667`.
3715 - 1667 = 2048 = exactly `0x800` (`FLAG_UNTARGETABLE`) -- this was the sole outlier, a stray
extra bit on top of the same base value every other lockbox in the game uses. Real data-entry bug,
not an engine quirk or a Lua-fixable issue: also confirmed there's no Lua binding to clear this at
runtime even if desired -- `setEntityFlags`/`getEntityFlags` (`lua_baseentity.cpp:11536-11584`)
only exist for `CMobEntity`, not `CNpcEntity`. Since this npcid is shared across all 10 Ilrusi
Atoll Assault missions (41-50) via `instance_entities.sql`, this almost certainly explains "Ancient
Lockbox not usable" for every one of them, not just Lamia No.13 -- fixing the shared row fixes all
of them at once.
- `sql/npc_list.sql` -- npcid 17002654 `entityFlags`: 3715 → 1667.
- **Needs a manual DB reimport** (`py -3 dbtool.py`, from `C:\topaz\tools`) before this takes
  effect live.

## Whitegate Assault mission-giver rank cap (2026-08-19)

User asked how to restrict which Assault missions are offered by rank -- specifically, to allow
only PSC and PFC (ranks 1-2) for now, ahead of releasing the higher-rank missions later.

Traced how rank-gating actually works: each of the 5 Whitegate mission-giver NPCs (Yahsra ->
Leujaoam, Isdebaaq -> Mamool Ja, Famad -> Lebros, Lageegee -> Periqia, Bhoy_Yhupplo -> Ilrusi) calls
`tpz.besieged.getMercenaryRank(player)` (counts owned mercenary badge key items,
`scripts/globals/besieged.lua`) and passes that number straight into the client's mission-selection
event (`player:startEvent(27X, rank, ...)`). Confirmed there's no independent server-side check
anywhere else -- `addAssault()` (`src/map/lua/lua_baseentity.cpp:6096`) just accepts whatever
mission ID the client sends back from that menu, no rank validation of its own. This means the
client's compiled event menu decides which missions are selectable purely from the `rank` number
it's given -- capping that number is both necessary and sufficient to restrict what's offered,
without needing to touch real badge possession or the C++ client at all.

Added a new `tpz.besieged.getAssaultRank(player)` helper (right next to `getMercenaryRank`) that
returns `math.min(getMercenaryRank(player), ASSAULT_MAX_RANK)` -- a new global setting in
`scripts/globals/settings.lua`, currently `2` (PSC+PFC). Deliberately a *separate* function from
`getMercenaryRank` rather than modifying it in place, since that function is also used for
Besieged sanction duration and other non-Assault purposes that must keep seeing the player's real
rank. All 5 mission-giver NPCs now call `getAssaultRank()` instead of `getMercenaryRank()` for the
value passed to the client.

**To unlock more ranks later**: change the single `ASSAULT_MAX_RANK` value in
`scripts/globals/settings.lua` (1=PSC only ... 10=all ranks, real badge-based). No other file needs
touching -- all 5 NPCs read from the same setting.
- `scripts/globals/settings.lua` -- added `ASSAULT_MAX_RANK = 2`.
- `scripts/globals/besieged.lua` -- added `tpz.besieged.getAssaultRank()`, requires `settings.lua`.
- `scripts/zones/Aht_Urhgan_Whitegate/npcs/{Yahsra,Isdebaaq,Famad,Lageegee,Bhoy_Yhupplo}.lua` --
  switched from `getMercenaryRank` to `getAssaultRank`.
- **Not touched**: `Sorrowful_Sage.lua` (event 278) -- a 6th Whitegate NPC using the same rank
  pattern but not one of the 5 real per-zone mission givers; unclear purpose, left alone pending
  confirmation it's actually Assault-related.
- **Not yet tested live.**

## Lamia No.13: Belly Dance charm implemented for the Fallen companions (2026-08-19)

User asked to add Lamia's charm mechanic to the Fallen companions, then corrected the specific
skill: "the skill is belly dance," not the generic single-target `charm.lua` mob skill (710)
initially investigated. Found `scripts/globals/mobskills/belly_dance.lua` (mob skill id 1762,
animation 1193) already existed as a fully commented-out template, with a header comment
confirming the real retail description: "Charms all targets in an area of effect, that are facing
the Lamia... Used only by Lamia NM's, particularly in Besieged" -- an exact match for this
mission's family.

Implemented for real, reusing the confirmed-working charm pattern from `charm.lua`
(`MobStatusEffectMove()` + `mob:charm()`) rather than the broken `addStatusEffect()` pattern the
old template sketched:
- `scripts/globals/mobskills/belly_dance.lua` -- full rewrite. 15-yalm range check
  (`mob:checkDistance(player) <= RANGE`), `player:isFacing(mob)` to match "facing the Lamia,"
  charms the first qualifying player found (this engine's `mob:charm()` can only track one victim
  at a time regardless, so true simultaneous multi-charm isn't possible here either way).
- `sql/mob_skills.sql` -- uncommented row 1762 (was previously disabled, never fired). Confirmed
  as the correct row by its position directly adjacent to `tail_slap`(1758)/`hypnotic_sway`(1759),
  both already active in the same `Lamiae` skill list (171).
- `sql/mob_skill_lists.sql` -- added `('Lamiae',171,1762)` to skill list 171 (was not present at
  all, not even commented out, despite the skill row existing in `mob_skills.sql`) -- this is the
  step that actually makes the skill selectable in Lamia's combat rotation; without it the row in
  `mob_skills.sql` alone would never fire.
- **Needs a manual DB reimport** (`py -3 dbtool.py`, from `C:\topaz\tools`) before either SQL
  change takes effect live -- editing the dump files alone doesn't touch the running database,
  same as every other SQL change this session.

## CORRECTION: the "Fallen companions also show Charm" claim above was never actually tested (2026-08-20)

Re-auditing this entry after a direct question about whether the mobskill implementation was
verified: the line above claiming "User confirmed via live testing that the Fallen companions
themselves also show Charm" was **wrong** -- user has since confirmed this specific behavior has
never been tested at all. That claim shouldn't have been written as confirmed.

More importantly, checking the actual code against it: **the implementation as written cannot
produce that behavior regardless of testing.** `belly_dance.lua`'s target loop is:
```lua
for _, player in pairs(instance:getChars()) do
    if player:isPC() and mob:checkDistance(player) <= RANGE and player:isFacing(mob) then
```
`instance:getChars()` (`CLuaInstance::getChars()`, `src/map/lua/lua_instance.cpp:67`) returns only
`m_charList` -- registered player characters. There's a separate `getMobs()`/`m_mobList` binding
for mob entities, and this script never calls it. The `player:isPC()` filter makes this doubly
explicit even if a mob somehow ended up in that table. **The Fallen companion mobs (Fallen
Volunteer/Imperial Wizard/Imperial Trooper) can never be selected as charm targets by this code as
it stands**, no matter what actually happens in a live test.

This matters because the *original ask* (see the top of this entry) was specifically "add Lamia's
charm mechanic to the Fallen companions" -- charming her own allied mobs was the actual feature
requested, not (only) charming players. The skill itself is real, correctly wired into
`mob_skills.sql`/`mob_skill_lists.sql`, and will genuinely charm any player in range and facing
Lamia when tested -- that part is sound. But the specific feature originally asked for is **not
implemented**. Extending the target loop to also consider Lamia's own nearby mob allies (via
`instance:getMobs()` or similar, filtering to her companion group specifically rather than any mob
in the instance) would be needed to actually deliver what was requested -- not done yet, flagged in
`Assault_Issue_Tracker.md` instead of silently left as a false "confirmed" claim.

**Everything else in the entry above stands**: the skill wiring, the SQL fixes, the `mob:charm()`
pattern reused correctly from `charm.lua`, and the DB reimport requirement are all still accurate
and unaffected by this correction. Also worth noting, found during this same audit: `mob_skills.sql`
row 1762 sets `mob_skill_distance = 7.0`, but the skill's real range (per its own header comment)
is 15'. `mob_skill_distance` gates the AI's decision to even attempt this skill against her
*current* engaged target (`mob_controller.cpp:312`), not the actual effect radius applied once
cast -- so this doesn't break the skill, but it does mean Lamia will only consider using it when
already within 7 yards of her primary target, noticeably tighter than the real 15' range might
suggest. Not fixed -- no real capture data exists to confirm the correct trigger distance, and the
effect itself is unaffected either way. Separately, the DB's `mob_skill_aoe = 0` flag looks like a
mismatch against the skill's AoE description, but `CMobSkill::getAoe()` has zero callers anywhere
in the C++ engine -- confirmed dead/unused data, doesn't affect behavior.

## Lamia No.13: real "charm the Fallen, dispel to turn them on her" tactic -- investigated, deferred (2026-08-20)

User described the actual retail tactic this mission is built around: Lamia's Belly Dance charms
both players and her own Fallen companion mobs; dispelling the charm off a Fallen makes it attack
Lamia; if a freed Fallen then attacks a player, Lamia can charm *that* player too. This is a real,
coherent combat loop -- confirms the "Fallen companions also show Charm" claim corrected above
wasn't wrong about the *intended* mechanic, just wrong that it had been built or tested.

**Investigated what implementing this for real would take.** Two pieces:

1. **`belly_dance.lua` targeting** -- straightforward, Lua-only. Currently only loops
   `instance:getChars()` filtered to `isPC()`. Would need to also consider Lamia's own companion
   mobs (via `instance:getMobs()`, filtered to just the 3 Fallen companion IDs, not every mob in
   the instance) as charm-eligible targets alongside players.

2. **Dispel actually freeing a charmed mob and turning it hostile -- this is a real engine gap, not
   a Lua-fixable one.** `battleutils::applyCharm()` (`src/map/utils/battleutils.cpp:4571`) fully
   supports a `TYPE_MOB` victim -- it correctly turns the mob into the charmer's pet (swaps its AI
   to `CPetController`, clears its enmity, links `PMaster`/`PPet`). But `battleutils::unCharm()`
   (same file, line 4630), called by `effects/charm.lua`'s `onEffectLose` whenever CHARM_I/II is
   removed (Dispel or natural expiry), **only has a branch for `TYPE_PC`** -- for a mob target it's
   a complete no-op: no AI restoration, no cleared cross-references, no hostility toward the former
   charmer. Checked whether the existing player Beastmaster Charm mechanic (the one other place
   mob-charm exists in this engine) already solves this -- it doesn't: a BST pet's charm timing out
   just **despawns it outright** (`CPetController::Tick()`, `petutils::DespawnPet`), it doesn't
   release it back into the world as a live, hostile mob. There is no existing precedent anywhere
   in this codebase for "a charmed mob gets freed and turns on its charmer." Also checked all 8
   other mob skills that call `:charm()` (`charm.lua`, `danse_macabre.lua`, `entice.lua`,
   `fanatic_dance.lua`, `gala_macabre.lua`, `luminous_drape.lua`, `soothing_aroma.lua`,
   `wisecrack.lua`) -- every one of them restricts targeting to `isPC()` only. Mob-on-mob charm is
   genuinely new territory for this engine.

Restoring a charmed mob's native AI requires `PAI->SetController(std::make_unique<CMobController>(...))`,
which isn't exposed to Lua at all -- `resetAI()` (`Lua: mob:resetAI()`) only calls `Reset()` on
whatever controller is *currently* active, it doesn't swap controller types, so it can't undo the
`CPetController` swap `applyCharm()` performs. There's no Lua-only path around this.

**Deferred, not implemented, per user direction.** The real fix would be a genuine C++ engine
change (a new `TYPE_MOB` branch in `unCharm()`: restore native `CMobController`, clear
`isCharmed`/`PMaster`/`PPet`, and add hate on the former charmer) plus the `belly_dance.lua`
targeting extension above, then a full recompile + restart before it's even testable -- the most
invasive change scoped this session, and one open design question needs an answer before writing
it: should a freed Fallen hate *only* Lamia (ignoring players unless they attack it first), or
become generally hostile the way any other released mob would? Left as a documented future-work
item (see `documentation/TODO.md`) rather than implemented now.

## Lamia No.13: companions actually follow her now, real fix (2026-08-20)

User re-reported the 2026-08-19 companion-roaming fix regressed -- Fallen companions observed at
least 50 yalms from Lamia, should be "right with her, under 10." Confirmed the earlier fix
(dropping their `ROAM_DISTANCE` to 100/10 yalms) never actually addressed the real cause: it only
anchors a mob to *its own* spawn point, not to another entity's current position. Lamia's own roam
radius is much larger (5000 = 500 yalms, set separately to fix her own "stays static instead of
wandering the whole map like a real NM" bug) -- so as she legitimately roams away from the shared
spawn point, the companions (tethered to that same fixed point, max 10 yalms) get left behind. The
gap can grow as large as her own roam radius allows, which matches the reported 50+ yalms exactly.

User confirmed the real intent: the Fallen should actively follow her wherever she goes, not just
stay near a fixed point. Re-investigated available movement primitives -- `mob:pathTo(x, y, z)`
(`CLuaBaseEntity::pathTo`, `src/map/lua/lua_baseentity.cpp:1367`) makes a non-PC entity walk toward
an arbitrary point via the AI's own pathfinder "without changing action" -- already proven in this
engine for Selh'Teus's final CoP fight, so a safe, precedented primitive to build on.

**Implemented a real follow loop** in all 3 companion scripts
(`Fallen_Volunteer.lua`/`_Imperial_Wizard.lua`/`_Imperial_Trooper.lua`, all identical): a
self-rescheduling timer (`mob:timer(3000, followLamia)`, the function re-queues itself each firing)
checks distance to Lamia's *live* position (via `GetMobByID(ID.mob[42].LAMIA_NO_13, instance)`,
not her spawn point) every 3 seconds, and calls `mob:pathTo()` toward her current position whenever
more than 10 yalms away. Guards: `mob:isAlive()` stops the recursion once the companion dies
(cleanly ends the loop instead of erroring on a dead entity), and `mob:isEngaged()` skips the
follow check entirely while the companion is fighting, so it doesn't get yanked out of combat
positioning mid-fight. `ROAM_DISTANCE` (100) is left in place as a fallback/safety net rather than
removed.

**Needs a script reload/restart to pick up** (Lua-only, no SQL/C++ touched, no DB reimport needed).
Not yet live-tested.

## Lamia No.13 false-complete-on-despawn (2026-08-19)

User reported: aggroed Lamia, ran away, came back, and found her already despawned with the
mission marked complete -- without ever killing her.

Root cause: `Lamia_No13.lua` used the same "progress-on-despawn" pattern as most other simple
kill-target Assault mobs in this codebase (`entity.onMobDespawn` unconditionally increments
instance progress). `luautils::OnMobDespawn` (`src/map/lua/luautils.h:241`) fires on **any**
despawn, per its own doc comment ("death not assured") -- including a mob leashing home and
fading out after losing aggro (`CMobEntity::OnDespawn`, `src/map/entities/mobentity.cpp:1186`),
not just a real death. This pattern happened to be safe everywhere it existed before only because
those mobs all defaulted to `MOBMOD_ROAM_DISTANCE = 0` (can't wander, so can't leash) -- Lamia's
new 500-yalm roam radius (added earlier this session for the "wander the whole map" fix) is what
made the leash-despawn path reachable for the first time.

Fix: moved progress tracking from `onMobDespawn` to `onMobDeath`, gated on a real killer being
present (`CMobEntity::Die()` always passes the actual killer to `luautils::OnMobDeath`,
`src/map/entities/mobentity.cpp:796`) -- guarantees only a genuine player kill can complete the
mission.
- `scripts/zones/Ilrusi_Atoll/mobs/Lamia_No13.lua` -- progress moved to `onMobDeath`, gated on
  `player ~= nil`; `onMobDespawn` now a no-op.

**User flagged this as a systemic risk, not a one-off**: "it can break a lot of missions if mobs
are despawning when they should not be... we should be ensuring this does not affect other mobs."
A grep found the same `onMobDespawn`-increments-progress pattern in **~250+ mob files** across the
whole codebase -- the large majority pre-existing content unrelated to Assault (Arrapago Remnants
BCNM, other Ilrusi Atoll NM/BCNM content, various zone-level battlefield mobs), not something to
blind-fix in one pass. Scoped the fix to the two other single-kill-target Assault mobs already
built this session that share the exact same shape, since the fix is a strict improvement with no
behavior change for a real kill:
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Sagelord_Molaal_Ja.lua` (Sagelord Elimination,
  mission 13) -- same fix applied preemptively (currently has no roam distance set, so not
  presently exploitable via this exact path, but the same class of risk).
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Mamool_Ja_Executioner.lua` (Preemptive Strike,
  mission 12, previously user-confirmed "tested and passed") -- same fix applied preemptively.
- **Saved as a persistent memory** (`topaz_progress_on_despawn_false_complete`) so this pattern is
  checked against before adding roam distance (or anything else that could cause leashing) to any
  other kill-target mob, and flagged as a candidate for a dedicated future audit pass across the
  rest of the codebase's ~250 hits.
- **Not yet confirmed fixed live** (Lamia). Sagelord/Executioner fixes are precautionary and don't
  need separate live confirmation beyond their missions continuing to complete normally on kill.

### Correction: the real fix is preventing the despawn, not reworking the progress hook

User pushed back on the framing above: "We do not want to change the whole code base. The despawn
mechanic is part of the game, but normal mobs have a spawn point and will respawn. Assault mobs on
death trigger win conditions so we want to ensure they do not despawn in the first place." Correct
call -- despawn/respawn is normal, intended behavior for ordinary mobs; only Assault objective mobs
(where death is the win condition) are the exception, and the actual fix for those is to stop them
from despawning at all, not to keep tolerating the despawn and just gate what happens afterward.

Applied `mob:setMobMod(tpz.mobMod.NO_DESPAWN, 1)` in `onMobSpawn` -- the exact same mechanism
already used for Imperial Agent Rescue's Warders (`Mamool_Ja_Warder.lua`, applied earlier this
session for a different symptom -- losing a load-bearing Warder mid-mechanic -- but the same
underlying fix) -- to the three Assault mobs whose death is a win condition:
- `scripts/zones/Ilrusi_Atoll/mobs/Lamia_No13.lua`
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Sagelord_Molaal_Ja.lua`
- `scripts/zones/Mamool_Ja_Training_Grounds/mobs/Mamool_Ja_Executioner.lua`

The `onMobDeath`-gated-on-`player` progress hook from the entry above is kept as a harmless
defense-in-depth safety net alongside `NO_DESPAWN`, not removed -- but `NO_DESPAWN` is the real
fix. Explicitly **not** doing a codebase-wide conversion of the ~250-file
`onMobDespawn`-increments-progress pattern found earlier -- scoped strictly to these 3 Assault
objective mobs. Companions (Fallen Volunteer/Wizard/Trooper) were deliberately left without
`NO_DESPAWN` since their death isn't a win condition for this mission.

## Golden Salvage: real positions + points from a user-provided win capture (2026-08-19)

User supplied a real win capture ("Ilrusi Atoll PSC - Golden Salvage (Win, Cap60, BST Solo).zip",
saved to `D:\Claude\assault_captures\`) and reported the Ancient Lockbox is still unusable --
"same issue we had with Lamia No.13."

Mined via the standard Windower capture toolkit (npclogger widescan, PacketViewer raw packet
logs, idview):

- **Ancient Lockbox untargetable**: confirmed same root cause as Lamia No.13 -- this npc
  (17002654) is the single shared Ancient Lockbox used by all 10 Ilrusi Atoll missions, and its
  `entityFlags` bug (`3715` instead of every other zone's `1667`, the stray extra
  `FLAG_UNTARGETABLE` bit) was already fixed in `sql/npc_list.sql` on 2026-08-19 (see the
  standalone "Fix Ilrusi Atoll Ancient Lockbox untargetable bug" entry above) -- that fix is
  zone-shared, so it should already cover Golden Salvage too, pending the DB reimport
  (`py -3 dbtool.py`) the user hadn't run yet at capture time.
- **Real positions, independently wrong on top of the targetability bug**: widescan shows Rune of
  Release at (380.000, -7.894, 64.999, 0) and Ancient Lockbox at (380.000, -7.756, 61.999, 0) --
  the script's previous values (420,-15,72,148 / 415,-15,75,148) were a generic, never-confirmed
  guess, ~35-40 units off with the wrong rotation entirely. Even with the entityFlags fix live,
  the lockbox would have been in the wrong place. Fixed.
- **Real Assault points**: decoded the 0x2A MessageSpecial packet at the mission-complete moment
  -- messageID `0x9D57 - 0x8000 = 0x1D57 = 7511` (`ASSAULT_POINTS_OBTAINED`), first param = 1210.
  Previous value (1100) was an unconfirmed guess. A second nonzero param (1757) appeared in the
  same packet's later slot, but the identical number also shows up as a param in the very next CS
  Event packet (the Rune of Release menu event) -- read as stale/reused packet-buffer data, not a
  second real number, consistent with this session's established decoding caution (see memory
  note `topaz_packet_log_decoding`, and the earlier Azure Ailments misread this same caution
  exists because of).
- **Lockbox reward items: still no data.** This capture never shows a successful lockbox trade --
  consistent with the user's report that it couldn't be used at all. `Q_ITEMS[41]`/`REG_ITEMS[41]`
  in `scripts/zones/Ilrusi_Atoll/npcs/Ancient_Lockbox.lua` remain unset (falls through to XP/gil
  only); still needs a capture where the lockbox is actually successfully opened.
- `scripts/zones/Ilrusi_Atoll/instances/golden_salvage.lua` -- real Rune/Lockbox positions.
- `scripts/zones/Ilrusi_Atoll/npcs/Rune_of_Release.lua` -- `BASE_ASSAULT_POINTS[41]`: 1100 -> 1210.
- **Not yet confirmed fixed live** -- in particular, worth re-testing the lockbox specifically
  after the DB reimport, since the entityFlags fix (the more likely actual blocker) predates this
  capture and may already resolve it on its own even without today's position/points changes.

## Golden Salvage: 2 real bugs found on live retest, chest mechanic still broken (2026-08-19)

User retested after the earlier "draw-in fixed" / "respawn-on-return fixed" pass and reported no
change at all: no draw-in, mimic doesn't immediately engage, still respawns after leaving sight
range and returning, plus a new visual report (lid appears normal-sized but the chest's base looks
larger after Death Trap plays).

Root-caused two of these properly this time instead of re-guessing:

### Draw-in never worked at all -- Lua scoping bug
`scripts/zones/Ilrusi_Atoll/mobs/Cursed_Chest.lua` declared `CheckForDrawnIn` as a `local function`
*below* `onMobFight`, which calls it. In Lua, `local function X` only creates the local binding at
the point of declaration -- since `onMobFight`'s closure was created earlier in the chunk, its
reference to `CheckForDrawnIn` resolved to an undefined **global**, not the local declared later.
Every `onMobFight` tick was silently erroring ("attempt to call a nil value") instead of running
the draw-in distance check at all -- this was never a live-vs-capture mismatch, the function
straight up never ran, on this file's very first version. Fixed by moving the function above
`onMobFight`.
- `scripts/zones/Ilrusi_Atoll/mobs/Cursed_Chest.lua`.

### Mimic never engages -- wrong ID type passed to engage()
The earlier fix added `mimic:engage(player:getID())`, but `CLuaBaseEntity::engage()` calls
`CAIContainer::Engage(uint16 targid)` (`src/map/ai/ai_container.cpp:71`) -- it wants a **targid**
(the entity's short in-zone index), not the full entity id `getID()` returns. Passing the wrong
value meant `Engage()` was looking up the wrong (or no) target, so the mimic never actually sprang
to life. `player:getShortID()` is the correct accessor -- confirmed against an existing working
example elsewhere in the codebase (`allyassist.lua`'s `ally:engage(target:getShortID())`).
- `scripts/zones/Ilrusi_Atoll/npcs/Cursed_Chest.lua`.
- **Proactively also fixed the identical mistake** in `scripts/zones/Leujaoam_Sanctum/npcs/
  Mining_Point.lua` (Orichalcum Survey, mission 2), built this same session with the same
  copy-pasted pattern (`qiqirn:engage(player:getID())` x1, `worm:engage(player:getID())` x1) --
  not yet reported broken, but certain to have the same bug. Grepped the rest of the codebase for
  the same `:engage(...:getID())` pattern -- no other live occurrences found.

### Still respawns after leaving/returning -- code already has the fix, not yet confirmed live
The `triggered` localvar guard added in an earlier pass (`Cursed_Chest.lua`'s `onTrigger`) is
still present and looks correct on inspection -- nothing in the current code path resets it, and
instance-scoped localvars persist for the instance's lifetime regardless of the player's sight
range. Given the *other two* reported-still-broken behaviors above turned out to be real bugs the
user's live server genuinely still had (not stale reports), and given the guard code itself
doesn't show an obvious flaw, the most likely explanation is the live server hasn't picked up
these fixes yet (needs a script reload or restart) -- flagged to the user to confirm rather than
guessed at further without server-side logs to look at.

### Wrong model / lid-vs-base size mismatch after Death Trap
Matches the already-tracked "wrong model" limitation (`mob_pools` row 864 uses one shared modelid
for all 12 chests; real capture data shows 12 distinct `ActIndex` values that were never decoded
to real per-chest model overrides). The new specific symptom (lid renders normal-sized, base
renders oversized once Death Trap plays) is consistent with that same generic-model substitution,
not a new, separately-fixable bug -- still blocked on decoding the real ActIndex-to-model mapping.
- **Not fixed**, same known limitation as before -- see Assault_Issue_Tracker.md.

## Orichalcum Survey: real text-ID bug, animation gap, and Worm targetability root-caused (2026-08-19)

User retested and reported: Mulwahah's pickaxe grant shows "Obtained 605 gil" instead of the real
text, Mining Points show the same for the ore ("Obtained 739 gil"), mining has no animation and can
be spammed instantly, and the Leujaoam Worm hazard spawns but isn't targetable by the player at all.

### "Obtained <item id> gil" -- wrong message class, not a numeric drift
Same *symptom* as earlier text-ID-drift bugs this session, but a different root cause this time:
`Mulwahah.lua` and `Mining_Point.lua` both call `player:addTempItem(...)` (a **temporary** item
grant) but then message it with `ID.text.ITEM_OBTAINED` -- the template for a **permanent** item
grant. This client has a dedicated, separate template for temporary items
(`PLAYER_OBTAINS_TEMP_ITEM`, "Obtained temporary item: <item>!") -- every other zone in the entire
game already has this constant defined; Leujaoam Sanctum's `IDs.lua` simply never had it added.
Confirmed the real value via an existing plain-text CapLog capture ("Leujaoam Sanctum PFC -
Orichalcum Survey [L].zip"): `MessageNumber: 7325 ... num: {605, ...}` immediately followed by the
decoded line "Obtained temporary item: a pickaxe!", and the same pattern later in the same capture
for the ore ("obtains the temporary item: a chunk of orichalcum ore!").
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` -- added `PLAYER_OBTAINS_TEMP_ITEM = 7325`.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mulwahah.lua`,
  `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua` -- both switched from `ITEM_OBTAINED` to
  `PLAYER_OBTAINS_TEMP_ITEM`.
- **Same bug, not yet fixed**: `scripts/zones/Mamool_Ja_Training_Grounds/npcs/Supplies_Crate.lua`
  (Breaking Morale, mission 14) has the identical `addTempItem()` + `ITEM_OBTAINED` mistake, and
  Mamool Ja Training Grounds' `IDs.lua` also has no `PLAYER_OBTAINS_TEMP_ITEM` constant. Not fixed
  here -- unlike Leujaoam, there's no capture in hand yet showing this specific message for Mamool
  Ja, so the real per-zone number isn't known; guessing one would repeat the exact mistake this
  session has been careful to avoid elsewhere. Needs a capture that reaches a crate-loot moment.

### No mining animation, feels instantly spammable
Mining Points never called any animation -- confirmed this whole mechanic is directly modeled on
the real overworld HELM excavation system (item 605 is literally HELM's own EXCAVATION tool,
`tpz.helm.type.EXCAVATION` in `scripts/globals/helm.lua`, which uses
`player:sendEmote(npc, tpz.emote.EXCAVATION, tpz.emoteMode.MOTION)`). Added the same call here so
mining at least visually paces like the real system. **Not a full port to `tpz.helm` itself** --
that system holds zone-wide singleton state and isn't designed for per-instance points; converting
this mission to actually run through it would need its own dedicated investigation (does HELM even
function correctly inside an Assault instance at all?) rather than a quick swap. Flagged as a
larger follow-up, not attempted here.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua` -- added the animation call.

### Leujaoam Worm hazard spawns but is not targetable -- real architecture mismatch found
Root-caused, not just guessed at: `instance:insertAlly()` (`CLuaInstance::insertAlly`,
`src/map/lua/lua_instance.cpp:225`) calls `mobutils::InstantiateAlly()`
(`src/map/utils/mobutils.cpp:1217`), which inserts the resulting entity into the zone via
**`InsertPET`**, not the normal mob-list insertion path real hostile mobs go through. Checked the
SQL data first to rule out the two already-known classes of targetability bug from earlier this
session (`FLAG_UNTARGETABLE` in `entityFlags`, and `namevis`) -- neither is set for this pool
(`mob_pools` poolid 2401, `entityFlags=131`, no `0x800` bit; `mob_groups` row has real
`allegiance=0`, i.e. genuinely hostile, not forced into an ally/player-allegiance state either).
The problem is structural: `insertAlly()`/`InstantiateAlly()` is built for CoP-BCNM-style
*player-ally* summons (Prishe, Gessho, etc.) -- inserting a **hostile combat hazard** through it
means the engine treats it as a PET-type entity from the moment it's created, which likely excludes
it from the player's normal enemy-targeting cycle regardless of its `allegiance` field being
correctly set to hostile.
- **Not fixed yet** -- the real fix is switching the Worm to the same spawn pattern already proven
  working for this mission's Qiqirn Miners (pre-registered via `instance_entities.sql` +
  `mob_spawn_points.sql`, brought to life with `SpawnMob()` in `onInstanceCreated`, matching normal
  hostile-mob registration instead of the ally-summon path) rather than `insertAlly()`. Needs new
  SQL rows (spawn point position(s), `IDs.lua` entry) and a `Mining_Point.lua` rewrite of the worm
  branch -- scoped as a real follow-up, not attempted in this pass to avoid guessing at spawn
  coordinates without real capture data for where the worm should appear relative to each of the
  10 Mining Points.

## Orichalcum Survey: corrected text-ID guess with dat-extractor, real Mulwahah dialogue, real positions (2026-08-19)

User pointed out the `dat-extractor` tool (built earlier this session, reads FFXI client `.DAT`
files directly for ground-truth dialog text) could resolve the temp-item message ID more reliably
than the CapLog-based guess used in the previous fix. It did -- and caught a real mistake.

### PLAYER_OBTAINS_TEMP_ITEM was wrong -- 7325 corrected to 7310
The previous fix used `7325`, read from a CapLog transcript's inline `MessageNumber` field shown
directly above the decoded text "Obtained temporary item: a pickaxe!". Checked against
`dat-extractor-cache/leujaoam_sanctum_6489.json`: index 7325 in this zone/client is actually
"VIT Down removed." -- totally unrelated. The CapLog label was misleading. Re-derived the real ID
by decoding the actual pickaxe-grant `0x2A` packet byte-for-byte from the same win capture
(`messageID 0x9C8E - 0x8000 = 7310`) and confirming dat-extractor's text at index 7310 matches
exactly: "Obtained temporary item: <item>!". Saved a memory
(`topaz_dat_extractor_tool`) about checking dat-extractor before trusting a CapLog label for any
text ID going forward.

### The whole ITEM_OBTAINED/GIL_OBTAINED/KEYITEM block was off by exactly -1
While in the dat-extractor cache confirming 7310, checked the rest of this zone's shared item/gil/
key-item message block against the real table and found it was never actually verified -- unlike
the ASSAULT_XX_START block (individually confirmed against a real client dialog dump earlier this
session), this block was copy-pasted identically across all 5 zones and never checked. Confirmed
zero other Leujaoam Sanctum scripts reference it (only Mulwahah.lua/Mining_Point.lua do, both
touched this session), so correcting it in place is fully scoped. All 8 constants shifted by -1:
`ITEM_CANNOT_BE_OBTAINED` 6383->6382, `FULL_INVENTORY_AFTER_TRADE` 6387->6386, `ITEM_OBTAINED`
6389->6388, `GIL_OBTAINED` 6390->6389, `KEYITEM_OBTAINED` 6392->6391, `KEYITEM_LOST` 6393->6392,
`NOT_HAVE_ENOUGH_GIL` 6394->6393, `ITEMS_OBTAINED` 6398->6397.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua`.

### Mulwahah's silent ore turn-in -- real dialogue found and wired in
User reported turning in the ore completes the mission with zero dialogue. A real win capture
shows Mulwahah playing exactly 2 real NPC Chat lines immediately before the completion event
fires. Decoded both message IDs (7532, 7534) from the same capture and pulled their real text
straight from dat-extractor: "You found some? Let's take a look then..." and "The rumors were
true! Excellent work!". Wired in via the established staggered-dialogue-timer pattern
(`npc:timer()`, cumulative delays), with `instance:complete()` delayed until after both lines play
so the player isn't warped out mid-dialogue (`CLuaInstance` has no `timer()` binding, so the delay
runs off the npc's own timer with the instance captured in the closure).
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` -- added `MULWAHAH_ORE_TURNED_IN_1/2`.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mulwahah.lua`.

### Rune of Release / Ancient Lockbox not at the correct position
User reported both were wrong. Root cause: `orichalcum_survey.lua` never called `setPos()` for
either -- they sat at `npc_list.sql`'s generic zone-default position (476, 8.479, ~39-40), ~900
units off in X from the real widescan-confirmed position (-432, -27.6, ~167-169) found in the same
win capture. Fixed.
- `scripts/zones/Leujaoam_Sanctum/instances/orichalcum_survey.lua`.

### "You find nothing" flavor message -- confirmed real, now wired in
User confirmed live: "I notice the 7524 response 'You find nothing', played after the player
interacts with the mining point with a pickaxe." Independently cross-checked 7524 against
dat-extractor -- confirmed real and unrelated to the -1 shift above (it was already correct).
Previously an untracked cosmetic gap (`Mining_Point.lua` played nothing at all on a silent-miss
roll) -- now plays this message on the roll's `else` branch (silent miss, not ore/worm).
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` -- added `MINING_FIND_NOTHING = 7524`.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua`.

### Qiqirn Miners share the Worm's insertAlly-as-PET architecture problem -- confirmed, not yet fixed
The 4 Qiqirn Miners are *also* spawned via `instance:insertAlly()` in `orichalcum_survey.lua`'s
`onInstanceCreated` -- same underlying mechanism (`InsertPET`, built for CoP-BCNM ally summons, not
real hostile-mob registration) already root-caused for the Worm hazard above. **User confirmed the
real mechanic**: once ore is found, the Miners should turn aggressive, immediately chase and attack
the carrier, *and* be targetable/killable by the player -- i.e. this is the same bug, not a
narrower one. Not fixed here -- same follow-up as the Worm: switch both to the pre-registered
`SpawnMob()` pattern (proper hostile-mob registration) instead of `insertAlly()`. Grouping them
together makes sense since it's one root cause across two hazards in the same mission.

## Breaking Morale: same temp-item text bug fixed with real capture data (2026-08-19)

Follow-up to Orichalcum Survey's `PLAYER_OBTAINS_TEMP_ITEM` fix, which flagged this exact same bug
in `Supplies_Crate.lua` as present but unfixed for lack of a capture. Mined an already-downloaded
Breaking Morale capture (`Mamool Ja Training Grounds CS - Breaking Morale (4).zip`) -- CapLog shows
"Obtained temporary item: a pair of gilt glasses!" at 20:35:46; decoded the matching raw `0x2A`
packet (param 579 = gilt_glasses, confirming the right packet) to get messageID `0x9C96 - 0x8000 =
7318`. That index's real text in this zone's dat-extractor table didn't match (unrelated "Ranged
Weapon/Ammo restriction removed."), same mismatch pattern as Leujaoam Sanctum's first attempt --
but this zone's table has an index **7310** with the exact same text as Leujaoam's confirmed value
("Obtained temporary item: <item>!", byte-for-byte identical special-code structure), strongly
indicating this is a shared system-wide message id, not zone-specific data. Used `7310` directly
rather than chase down the second capture's own byte-offset quirk.

While in the dat-extractor cache, checked this zone's own `ITEM_OBTAINED`/`GIL_OBTAINED`/
`KEYITEM_OBTAINED`/`ITEM_CANNOT_BE_OBTAINED` block -- same exact -1 shift as Leujaoam Sanctum's,
never previously verified. Confirmed only `Supplies_Crate.lua` references any of them, so safe to
correct in place.
- `scripts/zones/Mamool_Ja_Training_Grounds/IDs.lua` -- shifted `ITEM_CANNOT_BE_OBTAINED`
  6383->6382, `ITEM_OBTAINED` 6389->6388, `GIL_OBTAINED` 6390->6389, `KEYITEM_OBTAINED`
  6392->6391; added `PLAYER_OBTAINS_TEMP_ITEM = 7310`.
- `scripts/zones/Mamool_Ja_Training_Grounds/npcs/Supplies_Crate.lua` -- switched to
  `PLAYER_OBTAINS_TEMP_ITEM`.
- **Not yet tested live** -- worked autonomously from real capture + dat-extractor data while the
  user was away; flag if the crate message still looks wrong on next test.

## Orichalcum Survey: real spawn-point data found for the Worm/Miner architecture fix, plus a bigger surprise (2026-08-19)

Started the follow-up already scoped for the Worm hazard's `insertAlly()`-as-PET bug (user
confirmed the Qiqirn Miners share it). Checked `sql/mob_spawn_points.sql` for any pre-existing,
unwired real spawn data before inventing anything -- found real, positioned rows already sitting
in this zone's own ID range (17059841+), never referenced anywhere in the Lua:

- 16 `Leujaoam_Worm` spawn points (17059841-17059855) with real coordinates -- but an inline SQL
  comment right above the next block reads "all worms spawn @ mining points in npc_list", which
  matches the *current* Lua design (spawning the worm at whichever Mining Point triggered it, not
  a fixed point) -- so these 16 may be unrelated overworld spawns for the same-named mob type
  elsewhere in the zone, not this mission's hazard specifically. Unconfirmed either way.
- 8 real `Qiqirn_Miner` spawn points (17059856-17059863) in this zone, positioned near the
  Orichalcum Survey area (an adjacent comment confirms: "Orichalcum survey assaut entrance @ -432
  -27.627 169", matching the exact real Rune of Release position fixed earlier today).
- **A third, completely unused mob type**: `Mineral_Eater` (`mob_groups` groupid 3, poolid 2671,
  zone 69, level 77-78) with 9+ of its own real spawn points immediately following the Qiqirn
  Miner block, comment: "each mineral eater can spawn from any mining point" -- structurally
  identical framing to the Worm's own comment. **Nothing in the current build references this mob
  at all.** Given the thematic fit (a "Mineral Eater" is a far more natural mining hazard than a
  generic "Worm"), this raises a real, unresolved question: is `Mineral_Eater` actually the
  correct hazard mob for this mission, with "Worm" having been an earlier guess based on
  `mob_groups`' zone-scoped `Leujaoam_Worm` entry alone (which is real, but may just be a
  coincidentally-present overworld mob, not this mission's own hazard)?

**Deliberately not implemented.** This surfaced a genuine design question (Worm vs. Mineral Eater,
or possibly both) that a real capture showing the hazard actually triggering would resolve cleanly
-- rather than guess and potentially build the wrong hazard on top of the insertAlly architecture
fix, this is left as a properly scoped follow-up with all the real data pointers recorded above.
The insertAlly-vs-SpawnMob mechanism fix itself (for whichever mob turns out correct, and for the
Qiqirn Miners) is still straightforward once the hazard identity question is settled.

## Orichalcum Survey: real mining hazard identified and rebuilt from a retail walkthrough (2026-08-19)

User provided a real FFXIclopedia walkthrough for this mission and confirmed the mining hazard's
real identity: a named NM called **Mineral Eater**, not "Leujaoam_Worm" as originally guessed (the
walkthrough's own "a worm spawns" was a colloquial description of its appearance, not its real
name). This resolved the open question from the previous entry (which found `Mineral_Eater` sitting
completely unwired in the SQL alongside the Worm data and couldn't tell which was real).

### Real 5-outcome mining roll implemented
The walkthrough lists 5 outcomes per mining attempt: ore success, pickaxe breaks, hazard NM
spawns, a true miss ("You are unable to mine anything"), or a Pebble/Zinc Ore straight to the
party's treasure pool. Only 3 of these were modeled before (ore/hazard/miss) -- the Pebble/Zinc Ore
outcome was flagged as a known gap since the mission's original scaffold (item 17296 already
correctly identified as the real Pebble item, just never wired in). Implemented via the established
`player:addTreasure()` pattern. **No real percentage breakdown exists** for miss-vs-loot within the
remaining 60% share after ore/hazard -- split 50/50 as an explicitly-flagged unconfirmed estimate,
not presented as real data.

### Mineral Eater + Qiqirn Miners: switched from insertAlly() to real SpawnMob() registration
Confirmed via source (`mobutils::InstantiateAlly`, `InsertPET`) that `instance:insertAlly()`
creates a PET-type entity -- the mechanism built for CoP-BCNM ally summons, not a real hostile mob
-- and the user confirmed live this made both the hazard and the Qiqirn Miners untargetable and
unkillable. Found real, positioned, completely unwired spawn data already sitting in
`sql/mob_spawn_points.sql` for both (`Mineral_Eater`, `mob_groups` groupid 3/poolid 2671, 9+ real
points; `Qiqirn_Miner`, groupid 2/poolid 3259, 8 real points) -- an inline SQL comment even
confirms the exact real Rune of Release position already fixed earlier today ("Orichalcum survey
assaut entrance @ -432 -27.627 169"), strong corroboration this data belongs to this mission.
Switched both to real pre-registered `SpawnMob()`-based mobs:
- The 4 Qiqirn Miners now spawn immediately at instance creation (roaming/passive, matching the
  walkthrough), at their own real fixed positions -- no more localvar-based id tracking, since the
  ids are static and known ahead of time via `IDs.lua`.
- Mineral Eater (a singular NM) spawns on-demand when the hazard roll hits, moved to whichever
  Mining Point triggered it (same positioning intent as the old design), guarded against
  re-triggering while already alive via `isSpawned()`.
- `scripts/zones/Leujaoam_Sanctum/IDs.lua` -- added `mob[2]` (`MINERAL_EATER`, `QIQIRN_MINER1-4`).
- `sql/instance_entities.sql` -- registered all 5 real ids to instance 2.
- `scripts/zones/Leujaoam_Sanctum/instances/orichalcum_survey.lua`,
  `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua` -- rewritten to match.
- **Not yet tested live** -- built autonomously from real capture/wiki/SQL data while the user was
  away. Worth a full re-test of the mining loop end to end: ore, hazard engage/kill, pebble/zinc
  loot, and the miners actually being targetable this time.

## Orichalcum Survey retest round 2: real onTrade interaction, real animation pacing (2026-08-19)

User retested the Mineral Eater/Qiqirn Miner rebuild. Mulwahah's dialogue, Rune/Lockbox position,
and lockbox usability/rewards all confirmed working. Two new real defects found:

### Cannot "use" the pickaxe on a Mining Point (direct interact works fine)
Confirmed real: every other HELM-family harvesting point in this codebase (e.g.
`Attohwa_Chasm/npcs/Excavation_Point.lua`) exposes both a plain `onTrigger` (walk up and interact)
*and* an `onTrade` (trade/use the tool item directly onto the point) -- this file only ever had the
former; `onTrade` was a permanent empty stub. Refactored the roll logic into a shared local
function (`tryMine`) called from both entry points, with `onTrade` validating the traded item is
the Pickaxe (`trade:getItemCount() == 1 and trade:hasItemQty(PICKAXE_ITEM, 1)`, the established
trade-guard idiom used elsewhere in this codebase).
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua`.

### No mining animation pacing -- the earlier "add sendEmote" fix wasn't enough
User's follow-up after the first animation fix: the animation call was present, but the roll
result still landed in the same instant the animation started, rather than the animation actually
playing out first. Split `tryMine` into an immediate animation-only step and a delayed result step
(`resolveMining`, run via `npc:timer()`, 4 seconds -- an approximation, no exact real timing data
exists for this specific mission, but matches typical HELM harvesting-point animation length).
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua`.

### Qiqirn Miners still not present in the instance after a DB reimport -- SQL verified sound, cause still open
User reported zero Qiqirn Miners anywhere in the instance even after re-running the reimport.
Traced the exact mob-loading query the engine uses for instance-registered mobs
(`CInstanceLoader::LoadInstance`, `src/map/instance_loader.cpp:118-133`) -- a 4-way INNER JOIN
chain: `instance_entities` -> `mob_spawn_points` -> `mob_groups` (matched on `groupid` *and*
`zoneid = (mobid>>12)&0xFFF`) -> `mob_pools` -> `mob_family_system`. Verified every link in that
chain has real, matching data for both the Qiqirn Miners (`mob_groups` groupid 2/zone 69,
`mob_pools` poolid 3259, `mob_family_system` familyid 199 "Qiqirn") and Mineral Eater (`mob_groups`
groupid 3/zone 69, `mob_pools` poolid 2671, `mob_family_system` familyid 258 "Worm" -- confirms
Mineral Eater genuinely reuses the generic Worm model/family, consistent with the walkthrough's own
colloquial "a worm spawns"). Also independently re-verified the zone-id arithmetic in the JOIN
condition by hand -- correct for these ids. **The SQL data itself checks out end-to-end** -- if
they're still not appearing, the most likely remaining explanation is that this exact
`instance_entities.sql` change wasn't included in whichever reimport was run (multiple SQL edits
have accumulated across this session), rather than a data or query bug. Not resolved -- needs
confirmation of reimport timing relative to this specific change before further investigation.

## Orichalcum Survey: real lockbox rewards added, corrected to random pick (2026-08-19)

User provided real lockbox reward data: Remedy + hi-potion_+3 (matching the pool pattern several
other missions already use in this same table) plus `??? Gloves` / `??? Necklace` / `??? Box`.
First implementation gave all 3 "???" items together, matching mission 1's own Ring+Box batch
pattern in this file -- user corrected: these 3 are a random pick (1-in-3 chance each), not a
batch. Added a `randomPick` flag to the `OTHER_MISSION_ITEMS` entry format (`Ancient_Lockbox.lua`)
so mission 2 picks one of `reward.direct` at open time instead of giving the whole list, while
every other mission in the table keeps the existing batch-give behavior unchanged.
- `scripts/zones/Leujaoam_Sanctum/npcs/Ancient_Lockbox.lua` -- added `[2]` entry with
  `randomPick = true`, and the dispatch logic to honor it.
- **Confirmed Qiqirn Miner status**: user's DB backup showed all 5 new `instance_entities` rows
  (Mineral Eater + 4 Qiqirn Miners) are genuinely present for instance 2 after a full `dbtool.py`
  update -- root cause was the earlier "express" update mode not picking up new-row inserts,
  confirmed and saved as a memory (`topaz_sql_reimport_required`). Worth a fresh live retest now
  that the DB is known-good.
- **Not yet tested live** (lockbox rewards).

## Ancient Lockbox: real drop-probability and level-gate mechanics (2026-08-19)

User provided a detailed real mechanics writeup for the Ancient Lockbox system generally (not
specific to one mission), confirming several things this session had gotten wrong or never
implemented at all:
- **"???" items are NOT guaranteed** -- the box rolls against a fixed drop rate, "typically
  ranging from ~20% to ~50% depending on the specific Assault" (a few missions have a guaranteed
  base item instead). Every mission's lockbox implementation in this codebase has given its
  "???" item at a guaranteed 100% this entire session -- a real, previously-unknown bug, not
  something any capture data contradicted (captures only show what *did* drop in one run, not the
  underlying rate).
- **Recommended-level gate applies to every mission**, not just the one(s) that happened to have
  it wired in already.
- The "???" item goes to whoever personally opened the box (already correct everywhere -- these
  scripts already call `npcUtil.giveItem(player, ...)` on the opener specifically, not the party).
- Performance modifiers (party size, clear speed, first-time clear, etc.) do **not** affect the
  lockbox at all, unlike Assault Points (which do scale by party size elsewhere in this codebase,
  e.g. Ilrusi Atoll's `Rune_of_Release.lua`) -- confirms the lockbox scripts were right to never
  apply that kind of scaling, and shouldn't gain it later.

### Applied to Leujaoam Sanctum's `Ancient_Lockbox.lua` (all missions sharing this file)
- Added `QITEM_DROP_CHANCE_PCT = 35` (midpoint of the stated 20-50% range -- **no exact
  per-mission rate is confirmed**, this is an explicitly-flagged default, not real data) and
  gated both the `ASSAULT_ID == 1` branch and the `OTHER_MISSION_ITEMS` branch behind it.
- Added the missing recommended-level gate to the `OTHER_MISSION_ITEMS` branch (missions 2-8) --
  it only ever existed on the `ASSAULT_ID == 1` branch before.
- `scripts/zones/Leujaoam_Sanctum/npcs/Ancient_Lockbox.lua`.

### Deliberately NOT applied elsewhere yet -- scoped as a follow-up, not guessed at broadly
The shared `scripts/globals/assault_lockbox.lua` (`tpz.assault.chestTrigger`, used by Lebros
Cavern/Mamool Ja Training Grounds/Periqia) and Ilrusi Atoll's own `Ancient_Lockbox.lua` have the
exact same gaps -- no drop-chance roll anywhere, no level-gate at all in the shared function. Not
touched in this pass: several missions using these files (Preemptive Strike, Requiem) are already
**user-confirmed tested and passed end-to-end** -- changing their lockbox's effective drop rate
from guaranteed to probabilistic is a real behavior change to already-signed-off content, not
something to apply blindly across every zone without being asked. Flagged here so it's tracked,
not lost, and so the same `QITEM_DROP_CHANCE_PCT`-style fix can be applied deliberately if/when
the user wants it extended.

## Ancient Lockbox: set drop chance back to 100% for testing, real value documented as 50% (2026-08-19)

User asked to keep the "???" drop guaranteed (100%) for now while other Orichalcum Survey
mechanics are still being verified, with the real value (50%, corrected from the earlier
35%-midpoint guess) left as a clear comment to switch back to later.

- `scripts/zones/Leujaoam_Sanctum/npcs/Ancient_Lockbox.lua` -- `QITEM_DROP_CHANCE_PCT`: 35 -> 100,
  comment updated to note the real value is 50.
- `scripts/globals/assault_lockbox.lua` (`tpz.assault.chestTrigger`, shared by Lebros Cavern/
  Mamool Ja Training Grounds/Periqia/Ilrusi Atoll) -- added the same `QITEM_DROP_CHANCE_PCT = 100`
  gate this file never had at all (previously unconditionally guaranteed, no toggle existed).
  Since 100% matches this file's pre-existing behavior exactly, this is a no-op for every mission
  currently routing through it (including the already-confirmed-tested Preemptive Strike/Requiem)
  -- just adds the documented, one-line toggle for whenever real probabilistic drops are wanted.
- **Both files now have the identical pattern**: a single `QITEM_DROP_CHANCE_PCT = 100` constant
  with a comment noting the real value is 50 -- change both to 50 together when ready, or
  individually per-zone if some should switch before others.

## Orichalcum Survey retest round 3: real animation bug and real allegiance bug (2026-08-19)

User confirmed the Qiqirn Miners are now genuinely present (the DB full-reimport fixed that), and
confirmed the 4-second mining delay works. Two new real bugs found and fixed:

### Mining animation never plays -- sendEmote() can't target an NPC, ever
Root cause in the engine itself: `CLuaBaseEntity::sendEmote()` (`src/map/lua/lua_baseentity.cpp:
1861`) does `dynamic_cast<CCharEntity*>(target)` on whatever's passed as the emote's target -- for
an NPC target (the mining point, as this code was calling it) that cast always returns null, so
the `if (PChar && PTarget)` guard silently skips sending the emote packet at all. This is a hard
engine limitation (sendEmote can only ever target another player character), not a Lua mistake --
confirmed by grepping the whole codebase: only `helm.lua`'s own EXCAVATION animation call and this
file used this pattern, and helm.lua's call has the exact same bug. This pattern has apparently
never actually worked anywhere in this codebase, just never been noticed until now. Fixed by
targeting the player themselves (a valid `CCharEntity`) instead of the mining point.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua`.

### Qiqirn Miners never aggro -- same-allegiance targets can't engage each other
Root cause found by tracing the engine's own targeting validation, not guessed at: `mob_groups`'
`allegiance=1` (`ALLEGIANCE_TYPE::PLAYER`) for the Qiqirn Miner group -- set deliberately in an
earlier pass this session so they'd spawn passive/non-hostile -- makes them permanently invalid
`TARGET_ENEMY` candidates against the player. `CBattleEntity::ValidTarget`'s PVE case
(`src/map/entities/battleentity.cpp:1275-1278`) is `return allegiance != PInitiator->allegiance` --
since both the miner and the player are allegiance `PLAYER` (1), this is always `false`, so
`engage()` was silently failing to ever establish a real attack state no matter what targid was
passed -- this was true even after the earlier `getID()`/`getShortID()` fix, since that bug was
real but not the only one blocking this. Fixed by calling `qiqirn:setAllegiance(0)`
(`ALLEGIANCE_TYPE::MOB`) immediately before `engage()` -- `setAllegiance()` is a real per-entity
Lua binding (`lua_baseentity.cpp:4307`) that only affects the live entity, not the `mob_groups` SQL
default, so the Miners still spawn passive and only turn genuinely hostile at the moment ore is
actually found.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua`.
- **Mineral Eater unaffected**: its own `mob_groups` row (groupid 3) already has `allegiance=0`
  (MOB/hostile) from the start, so it doesn't share this bug -- no fix needed there.

## Real lockbox reward data for 6 more missions (user-provided, 2026-08-19)

User continued providing real reward data mission-by-mission following the missing-rewards audit.
All entries follow the established pattern: multi-item "???" qItem pools with no stated odds are
encoded as an equal-weight `randomPick`-equivalent (native to the shared weighted-pool format used
by these 3 zones -- putting multiple items in one pool is inherently a random pick, no extra flag
needed), and regular items are each their own guaranteed (weight 1000) pool. No SQL changes
involved -- these are pure `.lua` table edits, so **no `dbtool.py` reimport is needed** for any of
these six missions.

- **Breaking Morale** (Mamool Ja Training Grounds, mission 14) -- qItems ??? Polearm / ??? Sword /
  ??? Box (334/333/333); regItems Hi-Potion +2, Hi-Potion Tank, Reraiser. Previously fully missing.
  `Mamool_Ja_Training_Grounds/npcs/Ancient_Lockbox.lua`.
- **Azure Ailments** (Mamool Ja Training Grounds, mission 19) -- qItems ??? Box / ??? Earring /
  ??? Sash (334/333/333); regItems Hi-Ether Tank, Hi-Potion +3, Hi-Reraiser, Hi-Potion Tank.
  Previously fully missing. `Mamool_Ja_Training_Grounds/npcs/Ancient_Lockbox.lua`.
- **Apkallu Breeding** (Lebros Cavern, mission 26) -- qItems ??? Earring / ??? Sash / ??? Box
  (334/333/333); regItems Hi-Potion +2, Hi-Potion Tank, Reraiser. Previously fully missing.
  Independent of this mission's still-unset Assault points formula (lockbox rewards apply
  regardless of pairs matched). `Lebros_Cavern/npcs/Ancient_Lockbox.lua`.
- **Golden Salvage** (Ilrusi Atoll, mission 41) -- qItems ??? Earring / ??? Box (500/500);
  regItems Hi-Potion +2, Hi-Potion Tank, Reraiser. Previously fully missing (this was the
  `!warpassault`-adjacent "cannot be used" mission from earlier this session -- reward data was the
  last missing piece once the underlying targetability/position bugs were fixed).
  `Ilrusi_Atoll/npcs/Ancient_Lockbox.lua`.
- **Saving Private Ryaaf** (Periqia, mission 33) -- full data supersedes the earlier single-item
  capture (???_shield only, no regItem). qItems ??? Axe / ??? Polearm / ??? Shield / ??? Box
  (250 each); regItems Hi-Potion +3, Hi-Reraiser, Hi-Potion Tank, Hi-Ether Tank.
  `Periqia/npcs/Ancient_Lockbox.lua`.
- **Building Bridges** (Periqia, mission 35) -- full data supersedes the earlier single-item entry
  (???_axe only, no regItem). qItems ??? Axe / ??? Polearm / ??? Box (334/333/333); regItems
  Hi-Potion +3, Hi-Potion Tank, Hi-Ether Tank, Hi-Reraiser. `Periqia/npcs/Ancient_Lockbox.lua`.

**Still open from the original missing-rewards audit**: Bloody Rondo (mission 10, Leujaoam
Sanctum) -- user provided item names but marked all percentages "???" and the two "???" items'
give-mode (batch vs. random-pick) unconfirmed; clarifying questions were explicitly dismissed
("wait for next instruction"). Do not implement with guessed values.

## Orichalcum Survey retest round 4: allegiance was the wrong mechanism, real despawn bug found (2026-08-19)

Round 3's `setAllegiance(0)` runtime fix made the Qiqirn Miners engage/attack correctly, but the
user's round-4 retest surfaced that this was a partial, side-effect-laden fix, not the real one --
plus a genuinely new despawn bug, and the mining animation still doesn't play even with the
earlier `sendEmote` target fix live.

### Miners aggro/attack correctly now, but keep a green "ally" nametag
Root cause: the `mob_groups.allegiance=1` change from an earlier session pass (made to force the
Miners to "spawn passive") was based on a wrong assumption about what allegiance controls.
`mob_pools.aggro` is the actual field governing whether a mob attacks on sight -- and this group's
pool (poolid 3259, `Qiqirn_Miner`) already has `aggro=0`, confirmed via `sql/mob_pools.sql`. The
allegiance change was therefore never load-bearing for the passivity requirement at all, and it
had a real, previously-unknown side effect: `src/map/packets/entity_update.cpp:93` explicitly
special-cases `allegiance == ALLEGIANCE_TYPE::PLAYER` mobs to report `STATUS_TYPE::NORMAL`
(friendly) to the client instead of their true `STATUS_TYPE::MOB` status -- this is what painted
the ally-green nametag, and it's independent of the round-3 `setAllegiance(0)` runtime call
(which flips the *live* field the targeting logic reads, but nothing forces an immediate
`entity_update` re-broadcast right when that happens, so the client keeps showing whatever color
its last packet said until an unrelated update happens to fire).
- **Fix**: reverted `mob_groups.allegiance` for this group (zoneid 69, groupid 2) back to `0`
  (MOB) in `sql/mob_groups.sql` -- the Miners are now real hostile-allegiance mobs from spawn,
  `aggro=0` alone still keeps them passive until manually engaged, and they'll color/re-color
  normally through combat like every other correctly-behaving mob in the game. **Requires a DB
  reimport** (this is a `mob_groups` row edit, an UPDATE not an INSERT -- per the earlier
  express-vs-full lesson, a full update is the safe choice regardless).
- The round-3 `qiqirn:setAllegiance(0)` call in `Mining_Point.lua` is now a no-op (the mob is
  already allegiance 0 by the time it fires) -- left in place rather than removed, since it's
  harmless and cheap insurance if this group's SQL default ever gets touched again.

### Some Miners despawn permanently if they can't path to the ore carrier
Real, known engine behavior, not a new class of bug: `CMobController` checks `IsFarFromHome()` and
despawns a mob that's wandered/chased too far from its spawn point unless `MOBMOD_NO_DESPAWN` is
set (`mob_controller.cpp:792`) -- the exact same mechanism already found and fixed for Imperial
Agent Rescue's Warders (`Mamool_Ja_Warder.lua`) and Sagelord Elimination's boss
(`Sagelord_Molaal_Ja.lua`). The 4 Qiqirn Miners (`QIQIRN_MINER1`-`4`, spawned at
`onInstanceCreated`) previously had no dedicated mob script at all, so nothing was setting this
mod. If a Miner can't successfully path to whichever player found the ore (spawned too far away,
blocked by terrain), it can wander far enough from home to leash-despawn and never come back --
permanently reducing the mob count for the rest of that instance run.
- **Fix**: new `scripts/zones/Leujaoam_Sanctum/mobs/Qiqirn_Miner.lua`, `onMobSpawn` sets
  `tpz.mobMod.NO_DESPAWN`. Pure Lua, no SQL/reimport needed.

### Only half the real Qiqirn Miners were ever spawned
User-reported live ("There should be more qiqirn than this"). Checked `sql/mob_spawn_points.sql`
directly: there are 8 real Qiqirn Miner spawn points for this zone/group (`17059856`-`17059863`),
not 4. `IDs.lua`'s own header comment from an earlier pass explicitly said "4 Qiqirn Miners picked
from the 8 real spawn points to match the original 'spread of 4' design" -- that was a guess, not
real data, and the guess was wrong.
- **Fix**: added `QIQIRN_MINER5`-`QIQIRN_MINER8` (ids `17059860`-`17059863`) to `IDs.lua`'s
  `mob[2]` table, changed `orichalcum_survey.lua`'s `onInstanceCreated` spawn loop from `1,4` to
  `1,8`, and changed `Mining_Point.lua`'s ore-found engage loop from `1,4` to `1,8`. Pure Lua, no
  SQL/reimport needed (the spawn point rows themselves were already correct and present).

### Mulwahah's pickaxe-grant dialogue was completely silent, and CapLog mislabeled both real lines
User provided a fresh capture ("Assault - Orichalcum Survey.zip", Thris Nov 2025 set) containing
the pickaxe-grant interaction from the start, after the previous two captures on hand turned out
not to include it. The plain-text `CapLog/Thris.log` inside has the real dialogue:
```
[13:34:20]Mulwahah : Take this.
If you come across a chunk of orichalcum ore, bring it directly back to me.
[13:34:23]Obtained temporary item: a pickaxe!
[13:34:26]Mulwahah : You only get as many pickaxes as you need.
```
Gaps between repeats of this sequence line up with pickaxe-break events elsewhere in the same log
(confirmed by the user) -- each "Take this..." is a genuine new-pickaxe grant after the old one
broke, while "You only get as many..." fires when the player re-triggers Mulwahah while still
holding a valid, unbroken pickaxe.

**CapLog's inline `MessageNumber` field was wrong for both lines** -- labeled `7551` for "Take
this..." and `7550` for "You only get as many...". Per the established practice of never trusting
a CapLog label without cross-checking `dat-extractor`, checked both against the real client table
(`dat-extractor-cache/leujaoam_sanctum_6489.json`):
- Index 7551 (real client text): "All right now, who was it? Who said this was the right way?"
- Index 7550 (real client text): "No, this is definitely the right way."

Neither matches. Both are unrelated lines from a different NPC's dialogue tree nearby in the same
table. Scanned adjacent indices and found the real matches 15 lower than the CapLog labels:
- **7536**: "Take this.\nIf you come across [Chunk of Orichalcum Ore], bring it directly back to
  me." -- exact match.
- **7535**: "You only get as many [Pickaxe] as you need.\nNow, get moving!" -- exact match.

This is a different drift (+15 on the CapLog label, i.e. real id = label - 15) from the -1 shift
already found and fixed in this same zone's item/gil/key-item message block earlier this session --
confirms CapLog label drift isn't a single zone-wide constant, it can vary by dialogue block, so
every new id from this tool still needs an independent dat-extractor cross-check. For contrast,
`MULWAHAH_ORE_TURNED_IN_1/_2` (7532/7534) checked out with **no** drift against dat-extractor,
right next to these two mislabeled ones in the same table.
- Added `MULWAHAH_PICKAXE_GRANT = 7536` and `MULWAHAH_ALREADY_HAVE_PICKAXE = 7535` to `IDs.lua`.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mulwahah.lua`: plays `MULWAHAH_PICKAXE_GRANT` before the
  temp-item grant (previously silent), and `MULWAHAH_ALREADY_HAVE_PICKAXE` in the
  already-holding-one branch (previously silent, no confirmed text existed until now).

## Mulwahah's item-name placeholder rendered blank -- new C++ binding required (2026-08-20)

User tested the two new lines above live -- both rendered with a hole where the item name should
be ("If you come across , bring it directly back to me."), matching a screenshot. Initially
assumed this could be worked around in Lua and shipped a `PrintToPlayer()` text-substitution
fallback, but the user correctly pushed back: this exact class of bug (item ID showing instead of
name) had already been fixed properly elsewhere this session (the `PLAYER_OBTAINS_TEMP_ITEM`/
`ITEM_OBTAINED` fix), and a real mechanism for it must exist since every NPC in the game that hands
out items shows the correct name (cited Rytaal, `Aht_Urhgan_Whitegate/npcs/Rytaal.lua`, as a known
example).

Re-investigated properly instead of relying on the C++ source alone. The user's supplied capture
has an `EventView/Thris/Leujaoam_Sanctum.log` -- a decoded-packet log more detailed than CapLog --
which labels the exact packet type for both lines directly:
```
[2025-11-02 13:34:20] << [0x02A] CMessageSpecialPacket (GP_SERV_COMMAND_TALKNUMWORK)
{
  MessageNumber = 7551,
  SpeakerName = "Mulwahah",
  UniqueNo = 17060026,
  num = { 739, 4, 1757, 0 }
}
```
This is `CMessageSpecialPacket` (opcode `0x2A`) -- the same packet type `messageSpecial()` already
uses successfully for `PLAYER_OBTAINS_TEMP_ITEM` -- **not** `CMessageTextPacket` (`0x36`,
`messageText()`) as originally assumed. And it carries both `SpeakerName="Mulwahah"` (an NPC) *and*
`num[0]=739` (the real item id for Chunk of Orichalcum Ore, resolved into the placeholder) in the
same packet. The second line's packet (`MessageNumber = 7550`) carries `num[0]=605` (Pickaxe),
confirming the pattern: `param0` supplies whichever item the text template needs to name.

**Root cause, precisely**: `CMessageSpecialPacket`'s C++ constructor
(`src/map/packets/message_special.cpp`) takes any `CBaseEntity*` as its source -- nothing requires
it to be a player. But the existing Lua binding, `CLuaBaseEntity::messageSpecial()`
(`lua_baseentity.cpp:393`), always uses the *calling* entity (`self`/`m_PBaseEntity`) as **both**
the push-target (whose connection the packet is sent to -- must be a real player) **and** the
embedded source/speaker entity (used for `id`/`targid`/`SpeakerName`). There's no way to push to a
player's connection while embedding a *different* entity (the NPC) as source -- which is exactly
what this line needs. `messageText()` can't help either -- its packet (`message_text.cpp`) carries
no param fields at all, confirmed by inspection, so it can never resolve an item placeholder
regardless of source entity.

This is a real, general gap (documented as a new memory, `topaz_npc_item_name_substitution`, since
it'll recur for any other NPC dialogue with an item placeholder) -- not something fixable from Lua
alone without either faking the text manually (rejected -- loses the real packet shape, purple
speaker name, and doesn't scale to future cases) or extending the C++ binding.

**Real fix, C++ (needs recompile)**:
- `src/map/lua/lua_baseentity.h`/`.cpp`: added `messageSpecialFrom(CLuaBaseEntity* PSource, uint16
  messageID, sol::variadic_args va)` -- identical param handling to `messageSpecial()`, but builds
  the `CMessageSpecialPacket` from `PSource->GetBaseEntity()` instead of `m_PBaseEntity`, while
  still requiring `self` (the pushing entity) to be a real player connection (same
  `TPZ_DEBUG_BREAK_IF` guard). Registered via `SOL_REGISTER("messageSpecialFrom", ...)`. Purely
  additive -- `messageSpecial()` itself is untouched, so every existing call site keeps working
  exactly as before.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mulwahah.lua`: both lines now call
  `player:messageSpecialFrom(npc, ID.text.X, itemID, 0, 0, 0, true)`, matching the real capture's
  params exactly (item id in `param0`, `showName=true`).

**This needs a full server recompile + restart to take effect** -- it's a C++/binary change, not a
Lua reload and not a `dbtool.py` DB reimport. Not yet confirmed live.

## Rock/stalactite prop (_1XO) blocking half the map -- never revealed or forced open (2026-08-20)

User reported a "door" (a rock/stalactite prop) at real position (-460, -27, 125) blocking half
the map, sitting in a closed state. Found the real npc: `_1XO` (npc id `17060143`, already tracked
in `IDs.lua`), real position `(-460.054, -32.172, 120.370)` -- matches the user's reported position
closely.

`sql/npc_list.sql`'s row for this prop: `status=0` (hidden by default, same as the Mining Points
and Brittle Rock wall props), `animation=8` (`ANIMATION_OPEN_DOOR`). So the DB default is
technically already correct/open -- but nothing in `orichalcum_survey.lua` ever revealed it at
all, and this exact class of bug (a real DB default that's already correct but still needs to be
forced explicitly at instance creation to actually render right) was already found once this
session for Imperial Agent Rescue's `_1u5` door.

Applied: `orichalcum_survey.lua`'s `onInstanceCreated` now explicitly calls `setStatus(NORMAL)`
and `setAnimation(8)` on `_1XO`, matching the same forcing pattern already used for `_1u5`. Pure
Lua, no reimport needed. Not yet live-retested.

## _1XO blocking prop: animation flip diagnostic negative, added a navmesh-query tool (2026-08-20)

Follow-up to the `_1XO` rock/stalactite fix. User confirmed via a real video playthrough that this
passage should be open in retail, and pushed back on a user-provided writeup claiming door
open/closed state ties into server-side collision -- asked whether that matched this codebase's
actual behavior. Checked the real source rather than take the writeup at face value:

- **Animation IDs are real**: `ANIMATION_OPEN_DOOR = 8`, `ANIMATION_CLOSE_DOOR = 9`
  (`src/map/entities/baseentity.h:65-66`), and `setAnimation()` (`lua_baseentity.cpp:4245`) just
  writes the field and flags an update-mask -- confirmed accurate.
- **The writeup's flag claims are wrong for this codebase**: real `ENTITYFLAGS` enum
  (`baseentity.h:156-164`) is `FLAG_NONE, FLAG_INFO_ICON, FLAG_HIDE_NAME, FLAG_CALL_FOR_HELP,
  FLAG_HIDE_HP, FLAG_UNTARGETABLE` -- no `FLAG_TARGETABLE`/`FLAG_UNINTERACTABLE`/`FLAG_HIDDEN` as
  claimed. `setUntargetable()` and `zone:lineOfSight()` don't exist anywhere in this source tree
  (grepped the whole tree, no hits).
- **Navmesh claim partially real**: this codebase does use genuine Recast/Detour
  (`src/map/navmesh.h` includes `DetourNavMesh.h`), one compiled `.nav` file per zone
  (`navmeshes/<ZoneName>.nav`, loaded once via `CZone::m_navMesh`). But `CNavMesh` only exposes
  `findPath()`/`raycast()`/`validPosition()` -- no method anywhere ties a door's `animation` field
  to the navmesh dynamically. This matches the established Excavation Duty Brittle Rock precedent
  exactly: collision in this codebase can be baked into static per-zone navmesh data, completely
  independent of any entity's visual/animation state.

**Diagnostic test 1 (user-confirmed live)**: flipped `_1XO`'s forced animation from `8` (open) to
`9` (closed) -- **no visible change at all**, same model either way. This is real evidence `_1XO`
either isn't a functioning 2-state door model, or its rendered state isn't gated by `animation`
the way real doors elsewhere in this codebase are. Reverted, then (per user request) also trying
`0` (`ANIMATION_NONE`) as a third data point -- a plain resting state, in case this prop was never
meant to use the door-animation pair (8/9) at all.

**New diagnostic tool**: no existing binding could directly ask "does the navmesh allow a path
here," so added one -- `zone:checkNavPath(x1,y1,z1,x2,y2,z2)` (`src/map/lua/lua_zone.cpp`/`.h`),
wraps `CNavMesh::findPath()` and returns `(bool pathFound, uint32 waypointCount)`. Wired into
`orichalcum_survey.lua`'s `onInstanceCreated` as a temporary debug `print()` querying straight
across the reported corridor (30 yalms on either side of `_1XO`'s real Z, same X/Y) -- logs to the
map-server console as `[ORICHALCUM NAV DEBUG]`. **Needs a full recompile + restart.** Remove the
debug query once the result is in -- it's investigation-only, not a real fix by itself. If the
navmesh genuinely has no path there, that's conclusive evidence of baked static collision requiring
real navmesh/`.dat` data work to fix (out of scope for Lua/SQL, same conclusion as Brittle Rock);
if a path is found, the block is coming from somewhere else entirely and needs more investigation.

## Mining animation: real root cause found, sendEmote() target restriction was the bug (2026-08-20)

User asked whether a third-party writeup on Topaz/LSB animation systems had any relevance to the
still-unresolved mining animation. Checked every specific claim against real source before acting
on any of it (same discipline as the earlier door-writeup investigation):

- `player:actionAnimation()`, `player:animation()`/`showAnimation()`, `player:animatedEmote()`,
  `player:face()`, `player:freeze()`/`unfreeze()` -- **none of these exist anywhere in this
  codebase** (full source grep, zero matches for any of them).
- `npcUtil.tradeHasExactly()` -- real, exists.
- `player:injectActionPacket(action, anim, spec, react, message)` -- real binding, but its own
  header comment is explicit: "Used for testing and finding animations, not production use...
  ONLY FOR DEBUGGING." Not what the writeup implied.

Rather than write code against a source that kept citing nonexistent functions, pointed the user
at the one real, legitimate thing in the writeup: `!injectaction` (`scripts/commands/
injectaction.lua`), a genuine GM debug command wrapping `injectActionPacket` specifically for
finding animation IDs. Suggested testing `!injectaction 6 41 0 0 0` (animation 41 = the real
`EXCAVATION` constant, just via the Action-packet system rather than Emote) as a first guess.

**User tested it -- result was a ranged/bow weaponskill animation, not mining.** This negative
result was actually informative: it proved animation ID numbers are **not shared across packet
types** -- `41` means `EXCAVATION` in the `Emote` enum (`CCharEmotionPacket`, opcode `0x5A`) but
means something completely unrelated in the Action-packet animation space
(`CActionPacket`-family). This ruled out the Action-packet path for finding the mining swing and
prompted a closer re-read of the Emote path instead of accepting the earlier "hard engine
limitation, HELM is broken too, nothing to be done" conclusion.

**Real root cause, this time actually confirmed by reading the full call chain**:
`CLuaBaseEntity::sendEmote()` (`lua_baseentity.cpp:1893`) does
`dynamic_cast<CCharEntity*>(target->GetBaseEntity())` on its target parameter -- always null for
an NPC. But the function's *own documented example*, right above the code
(`player:sendEmote(npc, tpz.emote.EXCAVATION, tpz.emoteMode.MOTION)`), targets an NPC. And
`CCharEmotionPacket`'s constructor (`char_emotion.cpp`) only ever consumes `PTarget->id`/
`PTarget->targid` -- both plain `CBaseEntity` fields present on every entity type, nothing
CCharEntity-specific. The cast was an unnecessary restriction that silently broke the function's
own intended usage for every real caller in the codebase, including HELM's genuine overworld
mining/logging/harvesting excavation call (`scripts/globals/helm.lua:1415`,
`player:sendEmote(npc, info.animation, tpz.emoteMode.MOTION)`) -- which has apparently never
worked correctly in retail-parity HELM either, this whole time.

**Fix**: `src/map/lua/lua_baseentity.cpp` -- `sendEmote()` now uses `target->GetBaseEntity()`
directly instead of casting it to `CCharEntity*`, so any entity type (NPC included) is a valid
target. `Mining_Point.lua` reverted from the earlier player-targeting workaround back to targeting
the mining point itself -- the original, correct convention, now actually functional.
`helm.lua` needed **no Lua change at all** -- it was already calling `sendEmote()` the right way;
this C++ fix alone should make real overworld HELM animations start working too, a genuine bonus
beyond this one mission.

**Needs a full recompile + restart.** Not yet confirmed live.

## Excavation Duty navmesh re-test: round 1 result was ambiguous, round 2 in progress (2026-08-20)

Re-tested the Brittle Rock 4/5 "proven baked static collision" theory with `zone:checkNavPath()`
(the same tool that just disproved the identical theory for Orichalcum Survey's `_1XO`). Since all
of Excavation Duty's relevant entities are already correctly registered in `instance_entities`
(double-checked directly), this test doesn't have the registration confound that `_1XO`'s did.

**Round 1**: tested with a rough +-20 yalm diagonal offset around each rock's real position
(exact corridor orientation wasn't known). Result: `pathFound=false, waypoints=0` for both Rock 4
and Rock 5, with a real `[Navmesh Error] CNavMesh::findPath Couldn't find path (...) (63)` in the
map-server log (`63` is `m_zoneID`, not an error code -- confirmed by reading `navmesh.cpp`
directly).

**Caught before treating this as conclusive**: read `CNavMesh::findPath()`'s exact source
(`src/map/navmesh.cpp:201-252`). That specific error fires from this branch:
```cpp
if (!m_navMesh->isValidPolyRef(startRef) || !m_navMesh->isValidPolyRef(endRef))
{
    ShowNavError("CNavMesh::findPath Couldn't find path (...) (%u)", ..., m_zoneID);
    return ret;
}
```
This means **at least one of the two query points wasn't within reach of any navmesh polygon at
all** (`findNearestPoly`'s search extent is only +-10 units X/Z, +-20 Y) -- a materially different,
weaker signal than "a route was searched for between two valid points and none was found." The
`_1XO` test that succeeded kept the object's own exact X/Y constant and only varied Z, staying
centered on the known corridor; this round's diagonal guess for Rock 4/5 (both X and Z offset
simultaneously, exact corridor axis unknown) could easily have placed one or both test points
outside the actual walkable strip and into solid rock, producing this exact error regardless of
whether the real corridor is passable.

**Round 2, added to properly isolate the question**: new `zone:checkNavPosition(x,y,z)` binding
(`src/map/lua/lua_zone.cpp`/`.h`, wraps the already-implemented but previously Lua-unexposed
`CNavMesh::validPosition()`) -- checks a single point's validity independent of any path search.
`excavation_duty.lua`'s diagnostic now: (1) validates each rock's own real, already-confirmed
position is itself a valid navmesh point, then (2) tests `checkNavPath()` along each axis
separately (X-only, Z-only, +-15 yalms) instead of guessing a diagonal. **Needs another recompile.**
Not yet confirmed either way -- round 1's `pathFound=false` should not be treated as proof of the
baked-geometry theory until round 2 rules out a bad test coordinate.

## Excavation Duty navmesh re-test round 2: navmesh is fine, real cause is model collision (2026-08-20)

User recompiled and retested. **Round 2 result, user-provided log**:
```
[EXCAVATION NAV DEBUG] _ir0 own position valid=true
[EXCAVATION NAV DEBUG] _ir1 own position valid=true
[EXCAVATION NAV DEBUG] _ir0 X-axis path: pathFound=true, waypoints=4
[EXCAVATION NAV DEBUG] _ir0 Z-axis path: pathFound=true, waypoints=4
[EXCAVATION NAV DEBUG] _ir1 X-axis path: pathFound=true, waypoints=5
[EXCAVATION NAV DEBUG] _ir1 Z-axis path: pathFound=true, waypoints=4
```
Every check passed. This confirms round 1's `pathFound=false` really was caused by a bad diagonal
test coordinate landing off the navmesh, not a real gap -- **the compiled navmesh genuinely
considers the entire area around both rocks walkable, in every direction tested.**

Separately, the user did a live in-game test: rotated the camera at one rock's location and
visually confirmed **two overlapping entity names** at the same spot (the real rock +
`BRITTLE_ROCK*_DUP`, exactly matching the capture data from earlier this session). Killed one;
the second immediately showed a greyed-out name and "cannot attack that target" -- consistent
with `Brittle_Rock.lua`'s existing `onMobDeath` correctly clearing the wall prop and the dup mob
together (both set to `status.DISAPPEAR`) once the real rock dies. **Despite that -- and despite
the navmesh confirming the area is walkable -- the passageway remained impassable.**

**Conclusion**: the navmesh was never the actual blocker. With both the navmesh test and the "kill
everything, still blocked" live test now pointing away from server-side data, the most consistent
explanation is that the rock/wall prop's own client-rendered 3D model provides real collision that
persists independent of the server's `status`/`animation` fields -- the same underlying symptom
already seen on Orichalcum Survey's `_1XO` (navmesh also open there, door still functionally
blocked regardless of animation value). No server-side Lua/SQL/C++ lever found in this codebase
that clears this kind of model-level collision -- `setStatus(DISAPPEAR)` should logically remove a
rendered model from the client, and empirically doesn't relieve the block here.

**Decision**: user is choosing to relocate the Brittle Rock 4/5 objective to wherever the mission's
real layout should place it, rather than continue chasing a server-side fix for the current
coordinates. Since the block travels with the model rather than being tied to this specific
coordinate, relocating should preserve real "must kill it to pass" gating at the new location
instead of becoming a decorative object with no real barrier.

## Excavation Duty: dup-entity theory reverted after live testing (2026-08-20)

Two follow-up live tests, both against the restored dup-entity code from the previous entry, gave
results that changed the conclusion again:

1. **Widescan confirmed the dup pattern is universal**: user reported all 5 Brittle Rock walls
   show a "twin" on widescan, not just 4/5 -- consistent with the capture data.
2. **But live behavior diverged sharply between rocks 1-3 and 4-5, despite identical code and
   identical underlying data** (confirmed via direct DB query: every rock's primary and dup mob
   share the exact same `mob_groups`/`mob_pools` groupid -- no structural difference exists
   between any of the 5 pairs). User reported: rocks 1-3 now load with a visible name and a
   *small, player-sized hitbox* -- walkable past even while alive, contrary to the confirmed-
   correct historical behavior ("solid rock wall, impassable until killed, then plays a death
   animation and becomes passable"). Rocks 4/5: attackable, but impassable both before *and*
   after death, unchanged from before.
3. With identical code and identical data producing different live outcomes on different rocks,
   the most likely explanation is that two fully identical mobs stacked at the exact same
   coordinate produce non-deterministic client-side collision/targeting resolution -- which of the
   pair actually gets hit, and how the client resolves overlapping solid geometry, isn't
   consistent. This isn't something further server-side debugging can reliably fix, since the
   server-side data genuinely is identical across all 5 pairs.

**Reverted** the entire dup-entity restoration back to the confirmed-good pre-2026-08-20 state
(commit `81d05b3a30`'s parent, `3f622fceba`):
- `scripts/zones/Lebros_Cavern/mobs/Brittle_Rock.lua` -- `onMobDeath` back to only clearing the
  wall prop, no dup-mob lookup/clearing.
- `scripts/zones/Lebros_Cavern/instances/excavation_duty.lua` -- back to the 3-rock workaround
  (rocks 4/5 and their wall props not revealed, completion threshold 3), and all
  `[EXCAVATION NAV DEBUG]` diagnostic prints removed.
- `scripts/zones/Lebros_Cavern/IDs.lua` -- `BRITTLE_ROCK1-5_DUP` entries removed.
- `sql/instance_entities.sql` -- dup mobs (17035283/285/287/289/291), rocks 4/5
  (17035288/290), and their wall props (17035540/541) all un-registered from instance 21 again.

**Kept** (real, independently-valid fixes, unrelated to whether the dup theory panned out):
- `_1rx`'s Y-coordinate correction (`-43.362`, `sql/npc_list.sql`) -- confirmed directly by capture
  data, independent of the dup entity question.
- `zone:checkNavPath()`/`checkNavPosition()` (`src/map/lua/lua_zone.cpp`/`.h`) -- generically
  useful diagnostic tools, already proven valuable for the unrelated Orichalcum Survey `_1XO`
  investigation.

Needs a DB reimport to fully take effect (the `instance_entities` revert).

## Mining animation: retested after recompile, still doesn't play -- PAUSED (2026-08-20)

User recompiled and confirmed the new build was live (the Orichalcum Survey nav diagnostic in the
same build worked correctly, ruling out a stale-binary explanation). Retested mining -- **the
animation still does not visibly play**, despite the `sendEmote()` fix above being real and
correct by source inspection (not a guess). Also separately confirmed `PERFORMING ACTION 00` in
the map-server log is unrelated noise -- it's the generic client "trigger" action logged for every
NPC interaction (`packet_system.cpp:658`), not anything specific to mining or the emote packet.

User made the call to pause here rather than keep chasing it: **"good enough" for now, mission is
fully completable without the animation (cosmetic only), revisit later.** Recorded the full
investigation trail in `Assault_Issue_Tracker.md`'s Orichalcum Survey entry so a future session
doesn't have to re-derive any of this. Summary of where it stands:

- The `sendEmote()` C++ fix is real and confirmed correct -- it fixes a genuine bug (an
  unnecessary target-type restriction that broke the function's own documented usage), and should
  independently fix real overworld HELM mining/logging/harvesting animations too, since `helm.lua`
  was already calling `sendEmote()` the right way. Worth checking that side effect sometime.
- It did not resolve the visible symptom for this mission's mining animation specifically.
- **Next diagnostic, not yet performed**: a fresh packet capture of a mining attempt on the
  current (post-fix) build, checked for whether opcode `0x5A` (`CCharEmotionPacket`) is now
  actually present in the outgoing stream.
  - If present: the packet is sending correctly now, and the remaining issue is a client-side
    rendering limitation for this specific animation id (`41`/`EXCAVATION`) + mode (`MOTION`)
    combination -- likely not fixable from server-side Lua/C++ at all.
  - If absent: there's still a real, unfound bug somewhere in the send path (possibly a second
    guard/condition not yet identified), worth continuing the investigation from that point rather
    than starting over.

## REAL ROOT CAUSE FOUND: Miners 5-8 and _1XO missing instance_entities rows (2026-08-20)

After the navmesh diagnostic (previous entry) shipped, user retested and reported both `_1XO` and
Qiqirn Miners 5-8 still "not found" live, even after a clean map-server restart done specifically
*after* confirming the data existed in the DB. This directly contradicted every code-level theory
tried so far (content-tag filtering, zone-id bit math, DB connection mismatch), so the investigation
went further instead of assuming user error:

1. **Ruled out DB/connection mismatch conclusively**: `netstat -ano | findstr :3306` showed only
   one process bound to port 3306; `Get-CimInstance Win32_Service` confirmed it's
   `C:\Program Files\MariaDB 12.3\bin\mysqld.exe` -- the exact same instance the user's own SQL
   client connected to. Queried it directly (via the `mysql.exe` CLI, using the user-provided root
   password) and confirmed both `_1XO`'s `npc_list` row and all 4 Miners' `mob_spawn_points` rows
   are present, correct, and exactly as expected.
2. **Root cause, found by tracing `SpawnMob()`'s actual C++ implementation**
   (`luautils::SpawnMob`, `luautils.cpp:1071`): it does **not** query `mob_spawn_points` at all --
   it calls `PInstance->GetEntity(mobid & 0xFFF, TYPE_MOB)`, searching only the instance's own
   already-loaded entity list. That list is built once, at instance creation, from
   `instance_entities`'s join with `mob_spawn_points`/`mob_groups`/`mob_pools`/`mob_family_system`
   (`CInstanceLoader::LoadInstance`). `GetNPCByID()` works the same way for npcs.
3. Checked `sql/instance_entities.sql` for instance 2 (Orichalcum Survey) directly: it registers
   Qiqirn Miners **1-4** (`17059856-17059859`) but never had 5-8 added, and never had `_1XO`
   (`17060143`) added either -- both were wired into `IDs.lua`/the Lua scripts earlier this
   session (the "spawn all 8 Miners" fix, and the `_1XO` door fix) without adding the matching
   `instance_entities` rows. This is a separate table from `mob_spawn_points`/`npc_list`, purely
   about which entities belong to which running instance -- correct base data in those other
   tables is necessary but not sufficient; the entity also has to be registered here or the
   instance's join simply never picks it up, and `SpawnMob()`/`GetNPCByID()` fail silently
   (logged, but no crash) as a result.

**Fix**: added `INSERT INTO instance_entities VALUES (2,17059860)` through `(2,17059863)` and
`(2,17060143)` to `sql/instance_entities.sql`. Needs a DB reimport.

**Also fixed a related crash**: `orichalcum_survey.lua`'s unguarded
`GetNPCByID(ID.npc._1XO, instance):setStatus(...)` chain threw "attempt to index a nil value" and
aborted the rest of `onInstanceCreated` whenever `_1XO` resolved to nil -- this is also why the
navmesh diagnostic print never appeared in the user's first retest (the script crashed one line
before reaching it). Guarded with a nil-check, and moved the diagnostic query to run
unconditionally before the `_1XO` handling.

**Navmesh diagnostic result, now confirmed real (user-provided log)**: `pathFound=true,
waypoints=2` -- the compiled navmesh genuinely allows a path across this corridor. This rules out
the Brittle-Rock-style "baked static geometry, unfixable from server scripts" theory entirely for
this specific spot. Once the `instance_entities` fix lands and `_1XO` actually loads for the first
time, this may simply resolve on its own -- worth a full fresh retest before assuming anything else
is wrong.

## Qiqirn Miners spawning level 1 -- minLevel/maxLevel were never set (2026-08-20)

User confirmed (after a full DB reimport, cross-checked byte-for-byte against their own live DB
dump for the `QIQIRN_MINER5-8` rows added earlier) that all 8 Miners show as level 1 and are
freely attackable before ore is found. Checked `mob_groups`: this group's row
(`2,3259,69,'Qiqirn_Miner',...`) has `minLevel=0, maxLevel=0` -- never set to a real value at any
point this session, unlike its sibling ambient mobs in the same mission (`Leujaoam_Worm`,
`Mineral_Eater`, both `77-78`). The engine renders a 0/0 level range as level 1.

User provided the real range directly: **76-82**. Applied to `sql/mob_groups.sql` -- consistent
with the other 2 ambient/hazard mobs in this mission sharing the same real level band (77-78),
which corroborates the range rather than being an isolated guess.

Being attackable by the player before ore is found is real, expected behavior for this mob (real
allegiance=0/MOB mob, real `aggro=0` -- passive/no-auto-attack, but not the same as untargetable),
not a separate bug -- see the earlier allegiance/aggro root-cause writeup in this same section of
the tracker. Needs a DB reimport (row UPDATE, not INSERT -- but full reimport is still the safe
default per the earlier express-vs-full lesson).

## Mining Points don't cycle -- ported HELM's real hideNPC()/uses pattern (2026-08-20)

User reported: after a hazard roll (Mineral Eater) spawns and is killed, its Mining Point just
sits there, still visible but effectively unusable-feeling. Pushed back on treating this as a
one-off bug -- correctly identified it as a missing real mechanic: "Mining points are not supposed
to be visible when not able to be interacted with. The behavior is the mining points move around
after a certain number of tries or a failed mining attempt," then pointed directly at
`scripts/globals/helm.lua` as the place this logic should already exist for the overworld
HELM system.

Read `helm.lua`'s real `movePoint()`/`onTrade()` (lines ~1370-1425): confirmed the exact mechanic --
`npc:hideNPC(120)` (a real binding, `lua_baseentity.cpp:1690`, hides an NPC and auto-reveals it
again after N seconds, default 15s) combined with a per-point `uses` localvar that decrements
every successful gather and triggers a relocate (`movePoint`) once it hits 0 every 4 uses.

This mission (`Orichalcum Survey`) has 10 separate, pre-placed Mining Point NPCs rather than one
roaming point like overworld HELM, so a straight port of `movePoint()`'s `setPos()`-based
relocation doesn't apply directly -- adapted the same real primitives (`hideNPC` + a per-point use
counter) to this mission's actual shape: hide the exhausted/hazard-triggered point via
`hideNPC(120)` (reusing HELM's own literal 120-second constant) and immediately reveal a different
currently-hidden point from the pool of 10, achieving the same "points move around" effect the
user described without inventing new numbers where a real established constant already exists.

Applied:
- `scripts/zones/Leujaoam_Sanctum/instances/orichalcum_survey.lua`: `onInstanceCreated` now
  reveals only 3 of the 10 points at a time (randomly chosen), hiding the rest -- was showing all
  10 simultaneously with no cycling at all. `ACTIVE_POINT_COUNT = 3` is an explicitly flagged
  estimate -- no real data exists for how many are concurrently visible in retail, only that "all
  10" is confirmed wrong per the user's report.
- `scripts/zones/Leujaoam_Sanctum/npcs/Mining_Point.lua`: new `cyclePoint(npc, instance)` (hides
  the given point via `hideNPC(CYCLE_HIDE_SECONDS)`, reveals a different currently-hidden point)
  and `cycleIfExhausted(npc, instance)` (per-point `attempts` localvar, cycles once
  `USES_BEFORE_CYCLE` is hit). Both constants (120s hide, 4 uses) are ported directly from
  `helm.lua`'s own real values rather than guessed. Wired in: `cyclePoint()` fires directly on the
  hazard-roll branch (matches the user's specific "failed mining attempt with a Mineral Eater"
  example), and `cycleIfExhausted()` fires on the pickaxe-break and miss/pebble branches (any
  non-ore outcome counts as a use toward the threshold, mirroring HELM's own per-attempt
  countdown).

Pure Lua change, no SQL/reimport needed. Not yet live-retested.

### Mining animation still doesn't play
Not resolved. The round-3 fix (targeting the player instead of the Mining Point NPC in
`player:sendEmote(...)`) should make `CLuaBaseEntity::sendEmote()`'s `dynamic_cast<CCharEntity*>`
succeed now (a real player is a valid cast target, unlike the NPC before) -- meaning the packet
should actually get pushed this time, unlike before where it silently never sent at all. But
there's no confirmed-working reference anywhere in this codebase to compare against: HELM's own
copy of this identical call (`scripts/globals/helm.lua:1415`,
`player:sendEmote(npc, info.animation, tpz.emoteMode.MOTION)`) is *still* unfixed and has never
been confirmed to actually render an animation either. Whether this is now a pure client-side
rendering gap (nothing a server-side fix can address) or there's still a real bug left to find
can't be determined from source alone -- needs a fresh packet capture checking whether opcode
`0x5A` (`CCharEmotionPacket`) is actually going out to the client on this interaction now.
- **Not yet tested live.**

## MAJOR ROOT CAUSE FOUND: !warpassault has been corrupting the client entity cache since 2026-08-18 (2026-08-20)

User pushed back hard, and correctly, on continuing to treat the "door/wall renders in the wrong
state" symptom as four separate mission-specific mysteries: Lamia No.13 (reported last night),
Imperial Agent Rescue's Dilapidated Gates (reported last night, retested and apparently regressed
today), Orichalcum Survey's `_1XO`, and Excavation Duty's Brittle Rock walls (both today). Asked
directly: what changed, and when, that could explain this across completely unrelated missions in
completely unrelated zones? That's the right question -- a whole day of Lua/SQL/navmesh/model
investigation on 2 of these 4 missions had come up completely empty, which in hindsight was itself
a strong signal none of that was ever the real bug.

**Investigation, done properly this time -- via git history across the whole repo, not guessing**:
searched every commit from the last 2 days touching core entity/collision/door-adjacent C++ files
(`lua_baseentity.cpp`, `baseentity.h`, `packet_system.cpp`, `trigger_state.cpp`, `transport.cpp`,
`zone_entities.cpp`, `mobentity.cpp`, `battleentity.cpp`). Found the real cause in commit
`7d0482686e`, **2026-08-18 20:10** -- "last night," exactly matching the user's own timeline, and
well before any of today's mission-specific work started.

That commit (a real, correct fix for an actual `!warpassault` crash -- a dangling `CCharEntity*`
left in a stale instance's `m_charList` after a same-zone instance transition) added a call to
`POldInstance->DecreaseZoneCounter(PChar)` inside `CLuaBaseEntity::setInstance()`
(`lua_baseentity.cpp`), firing whenever a character's new instance differs from their old one but
shares the same physical zone -- which is **every single `!warpassault` use**, since it always
routes through a temporary "TEST" instance (`CInstance(this, 0)`) before the real target instance
loads, visible in literally every map-server log from today's entire session
("`GM fallback creating a bare CInstance(this, 0) ('TEST')`" followed shortly after by the real
instance loading).

**The actual bug**: `CZoneEntities::DecreaseZoneCounter()` (`zone_entities.cpp:335`) is a real,
correct cleanup function -- but it only cleans up the *other side* of the relationship (removes
the character from the zone's own `m_charList`, clears other entities' enmity/ownership/battle-
target references to that character). It never touches the character's *own* per-entity
view-tracking lists: `SpawnNPCList`/`SpawnMOBList`/`SpawnPCList`/`SpawnPETList`/`SpawnTRUSTList`
(`charentity.h:296-300`). Those lists are exactly what `CZoneEntities::SpawnNPCs()`/`SpawnMOBs()`
(`zone_entities.cpp:534`, `:460`) check before deciding whether to push a fresh `ENTITY_SPAWN`
packet to that character:
```cpp
if (NPC == PChar->SpawnNPCList.end() || PChar->SpawnNPCList.key_comp()(PCurrentNpc->id, NPC->first))
{
    PChar->SpawnNPCList.insert(...);
    PChar->pushPacket(new CEntityUpdatePacket(PCurrentNpc, ENTITY_SPAWN, UPDATE_ALL_MOB));
}
```
If an entity's id is **already present** in that list (from a previous visit, however brief -- even
just the momentary "TEST" instance every `!warpassault` passes through counts), the server assumes
the client already has correct, current data for it and sends **nothing**, even though that same
entity id may now represent a completely different instance's own repositioned, hidden, or
re-animated door/wall/prop. The client just keeps rendering whatever it cached the very first time
it ever saw that entity id -- potentially from an entirely unrelated mission, hours earlier.

This is a perfect, complete explanation for everything chased today:
- It's not mission-specific -- any shared prop/door/gate NPC id is vulnerable, in any zone, the
  moment a tester `!warpassault`s into more than one instance sharing that zone in a session.
- It started exactly when the timeline says it started (last night, `7d0482686e`), independent of
  any of today's Brittle Rock/Orichalcum Survey work.
- It fully explains why an entire day of real, careful investigation -- direct navmesh queries
  proving paths exist, direct live-DB queries proving data is correct, dup-entity theories,
  animation-field testing across values 0/8/9, cross-checking a third-party doc's claims against
  source -- kept finding nothing wrong server-side. Nothing *was* wrong server-side, in the sense
  of "wrong data being computed." The data was right; it just was never being *sent* to the
  already-stale client.

**Fix**: `setInstance()`'s same-zone-transition branch (`lua_baseentity.cpp`) now also clears all
5 spawn-tracking lists (`SpawnNPCList.clear()`, etc.) right after calling `DecreaseZoneCounter()`,
forcing a genuinely fresh resend of every entity's current state the next time this character's
view gets rebuilt in the new instance.

**Needs a full recompile + restart, and critically: retest with a genuinely fresh `!warpassault`
session** (not a session that's already accumulated a stale cache from testing done before this
fix). If confirmed, this may mean some or all of today's reverted Brittle Rock 4/5 dup-entity work
and the Orichalcum Survey `_1XO` investigation were chasing a symptom of this bug rather than a
real problem in that mission-specific data -- worth a careful, clean re-test of both before
concluding anything further about those missions specifically.

## CORRECTION: the actual root cause was client-side, not `SpawnNPCList` (2026-08-20)

The `SpawnNPCList` fix above was a real, well-reasoned hypothesis (the code path and the staleness
mechanism it describes are both genuinely real), but **the user's live retesting disproved it as
the cause of this symptom**: after a clean recompile, full DB reimport, and fresh `!warpassault`
session, the door/wall rendering bug was still present. The fix was left in place (it's a real,
valid improvement to a genuine `!warpassault` same-zone-instance-transition staleness case), but it
is **not** what was making rocks/gates/doors render as passable-and-open across missions all day.

**The user found the actual root cause directly**, independent of any further server-side
investigation: **Gateway**, a client-side addon for the Ashita FFXI launcher (used by private-server
players), automatically forces *all* door/wall/animation states to render as open on the tester's
own client -- completely independent of whatever the server actually sends. This explains every
symptom chased today far more completely than the `SpawnNPCList` theory did:
- Why it affected Lamia No.13, Imperial Agent Rescue, Orichalcum Survey, and Excavation Duty
  simultaneously, with no shared server-side code path between several of them.
- Why none of the server-side levers tried across the whole day -- navmesh queries (which came back
  clean), `status`/`animation` field changes, the dup-entity theory, `SpawnNPCList` clearing --
  ever produced a single visible change during live testing: the client was overriding the render
  regardless of what the server sent, so no server-side change *could* have shown up.
- Why disabling the addon immediately and correctly restored rocks 1-3 to their real, correct,
  DB-driven passable/impassable behavior without any further server-side change at all.

**Correcting the record**: treat the "MAJOR ROOT CAUSE FOUND: !warpassault..." entry above as a
real but ultimately incorrect hypothesis for this specific symptom, not the resolution. The
`sendEmote()` fix, the Qiqirn Miners 5-8/`_1XO` `instance_entities` registration fix, and the
`SpawnNPCList` clearing fix are all still real, valid, independent improvements worth keeping --
none of them were the door-bug fix. The actual fix for the door/wall/gate rendering symptom is: **on
the client, disable or configure the Gateway addon to stop forcing all animation states open.**
There is no further server-side action needed for this specific symptom.

Following this correction, Excavation Duty's Brittle Rock 4/5 were restored to the simple
(non-dup) pattern matching rocks 1-3, using the position data already confirmed via the round-2
navmesh diagnostic -- see `sql/instance_entities.sql` and
`scripts/zones/Lebros_Cavern/instances/excavation_duty.lua`, commit `478eb89f65`.

## Excavation Duty: Brittle Rock 4/5 REGRESSION CONFIRMED -- the Gateway restore was wrong for this pair (2026-08-20)

**User retested after the restore above (fresh code, post-rollback): Brittle Rock 4/5 still cannot
be passed through after being destroyed.** Same symptom as before Gateway was ever discovered.

Root problem with the restore: it inferred from "Gateway explains rocks 1-3 and several zones'
doors" that it must also explain rocks 4/5, and reverted straight to the simple pattern without
re-running the 4/5-specific test with Gateway disabled. That inference doesn't hold up against this
mission's own earlier, independent investigation:
- The **navmesh round 2** test (`checkNavPath`/`checkNavPosition`, see the entry above) found the
  compiled navmesh genuinely open in every direction around both rocks -- not a pathing gap.
- A **live kill test** during that same investigation confirmed both the real rock and its dup
  entity were correctly cleared (`status.DISAPPEAR`) after death, and the passage **still stayed
  blocked**.
- A separate, even more direct test (2026-08-19, "PROVEN independent of any NPC entity") removed
  rocks 4/5 and their wall props from the instance **entirely** -- no entity of any kind registered
  at those coordinates -- and the passage was **still** a solid wall.

That last test in particular is hard to square with a Gateway explanation: Gateway forces
animation/door *states* open on the client, but there was no entity and no state to force open in
that test, and it was still blocked. The most consistent read across all of this mission's testing
(now including today's regression) is that these 2 specific coordinates in this server's copy of
the Lebros Cavern zone geometry carry static collision that no server-side status/animation/
position/entity-presence lever reaches -- separate from, and not fixed by, the Gateway finding that
correctly explained the *other* doors/rocks/gates investigated this session.

**Action taken**: reverted back to the known-working 3-rock configuration (mission completes at 3
kills, same as the 2026-08-19 "definitively proven" state) -- `sql/instance_entities.sql` (removed
17035288/17035290 and `_ir0`/`_ir1` from instance 21 again) and
`scripts/zones/Lebros_Cavern/instances/excavation_duty.lua` (threshold back to `progress >= 3`, no
`setStatus` calls for the removed props). **Needs a DB reimport** (`py -3 dbtool.py` from
`C:\topaz\tools`) for the SQL side to take effect.

**Not attempting another server-side fix for rocks 4/5 right now** -- every Lua/SQL-reachable lever
has already been tried and shown to make no difference (see the two 2026-08-19 entries above), and
today's regression is further evidence this is genuinely outside this layer's reach. If this gets
picked up again, the previously-identified path forward is **relocating** the Brittle Rock 4/5
objective (mob spawn position + wall prop position) to different coordinates in the zone, since the
2026-08-19 "removed entirely, still blocked" test proves the block travels with the *coordinate*,
not the entity -- moving the objective elsewhere should preserve real "must kill it to pass" gating
without inheriting this dead spot. That needs real reference data (a capture or wiki source showing
where retail actually places these 2 obstacles) that hasn't been gathered yet.

## Lebros Supplies: full object/dialogue scan of its own capture (2026-08-20)

Re-scanned `Lebros Cavern PFC - Lebros Supplies (Thris).zip` end to end (NPCLogger SQLite db for
positions, CapLog for dialogue) rather than trusting the single 2026-08-18 pass that built the
mission. Several real findings:

**2 more wall props with real position data.** `_1rj` (17035523) and `_1rq` (17035530) were both
`NOT_CAPTURED` placeholders in `npc_list.sql` and were never registered to instance 22 at all --
this capture's NPCLogger gives real coordinates for both (`-279,-13,-59` status 9; `-399,-13,-180`
status 8). Filled in and wired into `onInstanceCreated` the same way Excavation Duty's wall props
are revealed.

**Yazuhma (17035480) was never registered to this instance.** Real `npc_list.sql` row already
existed, but `instance_entities.sql` had no row for it under instance 22 and `IDs.lua` didn't even
have a name for it -- meaning this mission-giver NPC could never spawn. Confirmed present and
talked to repeatedly throughout the capture. Added the ID, the registration, and a reveal call.

**Real dialogue found for both Yazuhma and Imperial Stormer, previously 100% silent.** Read every
`MesNum`/decoded text pair directly off the client's own rendered `0x036` packets (not a manual
CapLog inline label -- the actual text the retail client displayed for that id):
- Yazuhma: `YAZUHMA_GRANT_1`/`_2` (7445/7444, the two-line ration hand-off), plus
  `YAZUHMA_ALREADY_HAVE_RATION` (7443), `_STILL_STARVING` (7446), `_HALFWAY` (7447), `_DENT` (7448),
  `_LEFTOVER` (7449) -- these last 4 look like progress-tier nag lines but the exact thresholds
  aren't disambiguated by one capture, so only the grant pair and the already-holding line are wired
  into `npcs/Yazuhma.lua` for now.
- Imperial Stormer: `IMPERIAL_STORMER_THANKS`/`_MORE`/`_PROVISIONS`/`_FULL_BELLY` (7439-7442) --
  wired `_THANKS` as the single trigger line in `Imperial_Stormer.lua`; which of the 4 plays when
  isn't disambiguated either.

**Real mechanic gap surfaced, not implemented**: the capture shows Yazuhma handing out one of (at
least) 6 distinct real food temp items per trigger -- seafood stewpot, serving of bison steak,
coeurl sub, loaf of white bread, strip of bison jerky, bowl of pea soup -- and re-triggering while
still holding one shows `YAZUHMA_ALREADY_HAVE_RATION` instead of granting a new item. This is a real
random-ration-item hand-off/consume loop (the same shape as Mulwahah's pickaxe/ore loop in
Orichalcum Survey), but `Imperial_Stormer.lua`'s `onTrigger` still has zero item requirement -- the
mission is completable without ever holding a ration. Not implemented this pass (dialogue-mapping
was the scope); flagged in `Assault_Issue_Tracker.md`.

**Confirmed the `messageSpecial(RUNE_UNLOCKED, 22, 10)` bug** (same class already fixed on
Excavation Duty -- `RUNE_UNLOCKED` takes no params, `(22, 10)` is the `ASSAULT_x_START` param
shape) and switched to `RUNE_UNLOCKED_POS` with the real, capture-confirmed grid position, H-8.

**Also confirmed the letter-index encoding for `RUNE_UNLOCKED_POS` is 0-based (A=0)**: the
capture's own decoded text renders `Num1={7,8,...}` as "(H-8)" -- H is the 8th letter, so index 7
only works if A=0. This retroactively **corrects a mistake in Excavation Duty's own F-10 fix**
earlier today, which assumed 1-based (A=1) and used index 6; corrected to 5.

**New, higher-stakes finding, NOT applied**: cross-checking this capture's raw `MesNum` values
against `IDs.lua`'s existing Assault system-message block (`TIME_TO_COMPLETE`=7407,
`RUNE_UNLOCKED_POS`=7409, `ASSAULT_POINTS_OBTAINED`=7411, `TIME_REMAINING_MINUTES`=7412,
`ASSAULT_22_START`=7368) turned up **5 independent, exact +15 mismatches** against what this
capture's client actually rendered (7422, 7424, 7426, 7427, 7383 respectively -- confirmed via
distinct message types: mission start, timer, rune-unlock, points-awarded, and time-remaining, all
landing exactly 15 higher). This directly conflicts with this same block's own header comment,
which claims it was "verified 2026-08-17... against a real client dialog table dump." Given that
prior claim and this file's own caution about CapLog labels needing independent verification (see
`topaz_packet_log_decoding` project note), **this was not applied** -- it affects the shared
system-message block used by all 10 Lebros Cavern missions' start/timer/rune/points/failure text,
too wide a blast radius to flip on internal capture evidence alone, however strong. Needs a
dat-extractor cross-check against the real client DAT before touching it. Flagged prominently in
`Assault_Issue_Tracker.md`.

## Lebros Supplies: real food hand-out/turn-in mechanic built (2026-08-20)

User provided a community wiki writeup of the real mechanic (previously only flagged as a gap, not
implemented -- see the entry above). Replaced the placeholder trigger-once-per-Stormer mechanic with
the real one:

- **Yazuhma** (`npcs/Yazuhma.lua`) hands out one of 6 real temp items when the player isn't already
  holding one: 5 point-valued foods (white bread=1, pea soup=2, bison jerky=3, coeurl sub=4, bison
  steak=5 -- real item ids from `sql/item_basic.sql`) or a Seafood Stewpot (group-wide instant fill).
  Which item is granted is "sticky" per player (a `lebrosSuppliesFood` localvar) until actually
  delivered to a Stormer -- matches the wiki's "drop it and ask again, she gives the same thing" and
  "eat it + Antacid, still the same thing" notes, modeled as persistent assignment rather than
  re-rolling every trigger. Re-triggering while still holding food repeats
  `YAZUHMA_ALREADY_HAVE_RATION` instead of granting a second item. Remaining-hungry-count nag
  dialogue (4 tiers, matched to the wiki's 7-12/4-6/2-3/1 breakpoints) reads `12 -
  instance:getProgress()` directly, since progress now only increments when a Stormer transitions to
  full.
- **Imperial Stormer** (`npcs/Imperial_Stormer.lua`) now requires holding food to be fed at all --
  talking to one auto-delivers whatever food the player holds (no prompt, per the wiki), adds its
  point value to a per-Stormer `points` localvar, and marks the Stormer `full` once it reaches a
  `threshold` of 6 or 7 (randomized per Stormer per instance in `onInstanceCreated`, since the wiki
  says "either 6 or 7" without disambiguating which). A Seafood Stewpot instead instantly fills every
  Stormer in the same group as whichever one it's handed to. Talking to a Stormer without food, or to
  one already full, gets real flavor-only dialogue instead of silently doing nothing.
- **Real per-Stormer positions and 5 groups wired in** (`instances/lebros_supplies.lua`): the 12
  Stormers previously all shared one placeholder `npc_list` position (never actually scattered
  around the map). This capture's NPCLogger gives 12 distinct real positions that cluster into
  exactly 5 groups of sizes 2/2/3/3/2 -- matching the wiki's "2 WSW, 2 SSW, 3 SE, 3 NW, 2 N" group
  layout exactly once mapped by relative position to the entrance, which is a strong confirmation the
  clustering (and the existing `IMPERIAL_STORMER1-12` numbering, which already happens to be ordered
  by cluster) is right. Compass labels (WSW/SSW/etc.) are a best-effort geometric read, not
  independently confirmed against a real zone map -- cosmetic only, doesn't affect the mechanic.
- Mission completion is unchanged structurally (`onInstanceProgressUpdate` still gates on
  `progress >= 12`) but progress now means "12 Stormers fed to full," not "12 Stormers talked to
  once."

**Not yet tested live.** Untested judgment calls worth flagging for a future retest: the 6-item
random-grant weighting (uniform 1-in-6, wiki doesn't specify real odds), the exact remaining-count
dialogue tier text for "2-3 left"/"1 left" (assigned by elimination from this capture's other 2
observed nag lines, not independently confirmed per-tier), and which of the 4 captured Imperial
Stormer lines plays in which exact state (assigned by the wiki's own described logic, not
independently re-verified against a second capture).

## LC-rank audit pass: Shanarha Grass Conservation, Breaking Morale, Evade and Escape, Shooting Down the Baron, Demolition Duty (2026-08-19)

Re-audited all 5 LC-rank missions (one per zone) against their real captures, focused on: (1) the
`onMobDespawn`-vs-`onMobDeath` progress-miscount bug already found and fixed in Extermination
earlier this session, (2) `ID.mob[N]` zone-index correctness, (3) exact-equality progress checks,
and (4) the two open capture-detail gaps flagged in Breaking Morale (Viscous Liquid, crate
threshold). All 5 missions' `ID.mob[N]` indexing and `progress >= N` completion checks were already
correct -- no bug found there this pass.

**Latent onMobDespawn miscount bug found and fixed in 3 of the 5 missions.** `Coney.lua` (Shanarha
Grass Conservation), `Dahak.lua` (Evade and Escape), and `Black_Baron.lua` (Shooting Down the
Baron) all counted progress from `onMobDespawn`, which fires on ANY despawn (including a leash back
to spawn), not just a real kill -- the exact bug already found and fixed for `Sagelord_Molaal_Ja.lua`/
`Broken_Troll_Soldier.lua`/`Frozen_Bones.lua`/`Gelid_Bhoot.lua` earlier this session.
`Black_Baron.lua`'s own header comment even cited "the progress-on-despawn pattern as
Sagelord_Molaal_Ja.lua" as the thing to match -- ironic, since that's precisely the pattern that got
fixed away from. All 3 moved to `onMobDeath` gated on a real killer (`if player then ... end`), plus
`mob:setMobMod(tpz.mobMod.NO_DESPAWN, 1)` in `onMobSpawn` so the mob can't leash away uncounted.
None of this affected the captures' own happy-path results (both showed exact real kill counts with
completion firing right after), but it was a real latent miscount risk for live play.

**Shanarha Grass Conservation (Leujaoam Sanctum): re-confirmed correct, no live bug beyond the one
above.** Counted exactly 20 "Thris defeats the Coney" lines in the capture, with "Mission objective
completed" firing immediately after the 20th -- kill-all-20 is exactly right. Also chased down the
capture's "Vegetation" NPCs (17060030-17060055, present in this capture's PathLog/widescan) since
the real objective text is "Protect the vegetation" and an earlier pass had flagged not finding a
protectable prop -- confirmed these are decorative flavor-text scenery only (MesNum 7573-7576,
ambient "Is each bunny assigned to specific vegetation?"-style barks), not an interactive/protectable
object. The original "no protectable prop found, modeled as kill-all instead" call holds.

**Breaking Morale (Mamool Ja Training Grounds): Viscous Liquid mechanic pinned down precisely,
still not implemented (needs a mechanic this codebase has no pattern for); crate threshold remains
unconfirmed.** Re-extracted and re-analyzed both available captures, including the "(4)" one
previously written off as "a loss, party wiped, no new data" -- it actually had one useful new data
point: an `eventview/simple` log showing 3 Viscous Liquid `CS Event 103` triggers, each immediately
followed by `NPC Chat Message: 7545`. Cross-referencing 7545 against the Mamool Ja Training
Grounds dat-extractor cache (`mamool_ja_training_grounds_6486.json`) gives its exact real text:
**"The supplies you seized are missing!"** -- confirming Viscous Liquid is the presumed steal-back
hazard. The primary capture (`breaking_morale_1`) then gave the full trigger mechanism via exact
timestamp correlation between combat barks, teleport text, and crate-loot/turn-in events: a Mamool
Ja Trainer periodically uses hate/aggro on the player ("Scaleless heathen... A taste of my wrath,
you shall have!"), which teleports the player onto Viscous Liquid ("You seem to have been brought
here by some strange magic...", "There is a curious liquid here.", "Thris is overcome by a peculiar
sensation."). Every single occurrence in the capture (7 total) lines up exactly: if the player was
holding an uncollected Supplies Crate temp item at that moment, it's removed ("The supplies you
seized are missing!"); if not (already turned in), nothing happens. Zero exceptions across 7
samples -- this is about as solid as single-capture evidence gets. **Not implemented**: the actual
trigger (a mob periodically teleporting its target to a fixed NPC and firing a CS-event dialogue
sequence) has no existing pattern anywhere in this codebase, and the exact trigger cadence/condition
(hate-based? fixed timer? a named TP-style move with its own recast?) isn't precisely pinned down by
a single capture -- implementing the *outcome* (steal on teleport) without a *confident* trigger
condition would mean guessing a mechanic parameter, which this pass was explicitly told not to do.
Documented in full in `breaking_morale.lua`'s header for whoever builds it next.

Also re-checked the "8 crates = complete" threshold: **still unconfirmed** -- both captures ended in
mission failure without ever completing. `breaking_morale_1` (solo) managed exactly 6 successful
Quhaaja turn-ins ("Great, you found some supplies!") in the real 15-minute time limit
(`instance_list.sql`'s `15` already matches the capture's own "You have 15 minutes" text) before
timing out; `breaking_morale_4` has no turn-in data at all. 6-in-15-minutes-solo is circumstantial
evidence 8 may be a tight ask for a solo run, but doesn't prove the real threshold is lower than 8 --
left unchanged pending a capture that actually completes.

Also re-verified `PLAYER_OBTAINS_TEMP_ITEM` (7310) is still correct per this session's task list --
`breaking_morale_1`'s raw packet log has an inline `MessageNumber: 7325` field on the crate-loot
event, which looked like a contradiction at first glance, but 7325's real client text (via
dat-extractor) is unrelated ("VIT Down removed."). This is the known CapLog MesNum mislabeling
artifact (see the `topaz_packet_log_decoding` project note) -- the capture's own *decoded* text
("Obtained temporary item: a wild rabbit tail!") matches 7310 exactly. No bug; 7310 stands confirmed
by a second, independent capture.

**Evade and Escape (Lebros Cavern): Switch NPC data exists but the kill-to-switch mapping is
ambiguous -- left unwired per this mission's own skip-if-ambiguous guidance.** The capture does
show 3 real Switch NPCs (17035481-17035483) transitioning through a lit/flickering/glowing-brightly
message sequence (MesNum 7451/7452/7454), but the timestamps don't cleanly map "1 kill = 1 switch
immediately" -- two switches update back-to-back right after the 3rd (final) Dahak kill rather than
one switch advancing per kill in sequence. Rather than fabricate a plausible-looking but unconfirmed
mapping, left this cosmetic gap as-is (mission completes correctly without it either way).

**Shooting Down the Baron (Periqia): re-confirmed correct**, kill-1 Black Baron model matches the
capture exactly (real 15-minute time limit, completion fires around the kill). One CapLog ordering
oddity noted for the record: the capture's `[HPTrack] Defeated Black Baron` addon-inference line and
the "Mission objective completed" system message both land 3 seconds *before* the actual "Thris
defeats the Black Baron" client text -- this is a benign display-ordering artifact (HPTrack
estimates death from HP-percent heuristics slightly early; combat text queues can render
out-of-order relative to system messages), not evidence of a different completion trigger.

**Demolition Duty (Ilrusi Atoll): capture re-read in full detail per this mission's explicit
"extract exact mechanics, implement only what's nailed down" instruction. No AI built (correctly
out of scope), but real Wreckage prop positions staged as groundwork.** Confirmed precisely, all
from the capture's CapLog plus its NPCLogger widescan DB (`Ilrusi Atoll.db`, read directly via
sqlite3):
- The Demolition Automaton (17002545) engaged exactly 5 distinct targets ("Demolition Automaton :
  Target acquired." x5) -- one per the 5 real Wreckage props (17002546-17002550). Real model_id=40
  per its last widescan sample (100 HP / 100 speed / 40 base speed at that moment -- a live combat
  snapshot, not necessarily its spawn stats). Automaton hits on Wreckage ranged ~23-86 damage, plus
  an occasional named TP move ("readies Slapstick" / "uses Slapstick").
- Exactly 2 full destroy-and-replace leash cycles happened (both ending in "Delete." followed by
  Uzhahn's scolding + replacement line), plus 2 more near the very end that resolved as a near-miss
  ("Safety program has been shut down" instead of "Delete.") -- confirming the leash break is
  forgiving (player has a window to get back in range before actual destruction), not a hard
  failure the instant it triggers.
- The completion line is spoken by **Uzhahn**, not the player as an earlier pass's paraphrase might
  have implied -- real MesNum 7561 confirmed via dat-extractor
  (`mamool_ja_training_grounds_6486.json`'s shared text isn't used here; this is Ilrusi Atoll's own
  cache), full real text: "Looks like you're done with demolition duty. I've given you a score of
  10 points on your work assessment. Time for you to head on home." This fires immediately before
  the Rune of Release unlocks.
- All 5 Wreckage had been engaged by completion time, and the score was exactly 10 -- a clean
  2-points-per-Wreckage fit, but this is one data point from one capture/one run, not a confirmed
  formula. Flagged as a hypothesis only; do not hard-code `2 * wreckageCount` off this alone.
- Real 30-minute time limit re-confirmed against `instance_list.sql`'s existing `30` (already
  correct, no fix needed).

**Groundwork staged, zero behavior change**: added `npc_list.sql` rows for the 5 real Wreckage props
(17002546-17002550, real PathLog-confirmed coordinates, corroborated by the widescan DB's rounded
values -- both agree these are invisible interaction points with `model_id=0`/no look data, same
"shipwreck is static zone geometry, NPC is just the hitbox" pattern as this zone's own
Mining_Point/Logging_Point and Mamool Ja's Viscous_Liquid), registered them plus **Uzhahn**
(17002656 -- a real, correctly-positioned `npc_list` row that had never actually been registered to
instance 44 at all) into `instance_entities.sql`, and added named `WRECKAGE1-5`/`UZHAHN` constants
to `Ilrusi_Atoll/IDs.lua`. All rows are status-hidden and **`demolition_duty.lua` itself is
untouched** -- this is pure data staging so a future controllable-pet-AI implementation pass doesn't
have to re-derive real position/ID data from scratch. Requires a DB reimport (`py -3 dbtool.py`) to
take effect, same as any `sql/*.sql` change, but has no player-visible effect either way since
nothing spawns or reveals these rows yet.

## Orichalcum Survey: Qiqirn Miners only aggro if already near the player at ore pickup (2026-08-20)

User reported: after grabbing the ore, only the Miner(s) already close by actually aggro -- running
to any other Miner afterward, it just ignores the player entirely, contrary to the intent that the
whole mining operation should turn hostile once the ore is stolen.

Traced through the engine's own AI state machine rather than guessing: `qiqirn:engage(...)`
(`Mining_Point.lua`'s ore-success loop, fires once on all 8 Miners) calls
`CAIContainer::Internal_Engage` (`src/map/ai/ai_container.cpp:165`), which constructs a real
`CAttackState` immediately. `CAttackState`'s own constructor (`src/map/ai/states/attack_state.cpp:30`)
calls `UpdateTarget()` right away, which validates the target via `IsValidTarget()` -- for a Miner
too far from the player at that exact instant, this fails, the state constructor throws, and that
specific `engage()` call silently no-ops (no error, no retry). Since the ore-pickup loop only fires
once, any Miner that missed its one window at that moment never gets another chance -- and since
this whole pool spawns with `mob_pools.aggro=0` (deliberately passive by design, so they don't
attack before the ore is stolen -- see the earlier "Qiqirn Miners" entry in this section), nothing
else in the engine ever makes a missed Miner hostile later either. It just sits there, aggro=0,
forever, regardless of how close the player later gets.

**Fix**: also call `qiqirn:setAggressive(true)` on every Miner in the same loop, right alongside the
existing `engage()` call. `setAggressive()` (`CLuaBaseEntity::setAggressive`,
`src/map/lua/lua_baseentity.cpp:11848`) directly flips `CMobEntity::m_Aggro` -- the exact field
`CMobController::CanAggroTarget()` (`src/map/ai/controllers/mob_controller.cpp:1012`) gates the
engine's own normal proximity-based aggro detection on. `engage()` is kept as-is and still handles
the immediate case for whichever Miner(s) are already in range at pickup time; `setAggressive(true)`
is what makes every *other* Miner genuinely hostile-on-sight from that point on, so running up to a
different one later now triggers real aggro through the engine's standard detection path instead of
silently doing nothing.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up. Not
yet live-tested.

## Lebros Supplies: Yazuhma/Imperial Stormer dialogue was displaying real Apkallu Breeding text (2026-08-20)

User live-tested Lebros Supplies and provided a screenshot: instead of Yazuhma's real food-hand-out
dialogue, chat log showed "The apkallu is already following you.", "You cannot lead any more
apkallu.", "You seem to have made a match!", "VIT Down removed." -- all real, recognizable **Apkallu
Breeding** (Lebros Cavern mission 26) text, not anything related to provisions/rations. User
correctly suspected ID drift from the capture sessions, "same as we've been seeing a lot of."

Verified directly against `dat-extractor`'s real client dialog table
(`D:\Claude\dat-extractor-cache\lebros_cavern_6483.json`) rather than re-trusting the capture:

```
7443 -> "You cannot take this apkallu with you."
7444 -> "You cannot lead any more apkallu."
7445 -> "The apkallu is already following you."
7446 -> "You seem to have made a match!"
7448 -> "The apkallu seem very happy together. Your existence seems to have been forgotten..."
7225 -> "VIT Down removed."
```

Confirmed: **every single one** of the 12 message ids assigned to Yazuhma/Imperial Stormer dialogue
in an earlier pass this session (`YAZUHMA_GRANT_1/2`, `_ALREADY_HAVE_RATION`, `_STILL_STARVING`,
`_HALFWAY`, `_DENT`, `_LEFTOVER`, `_TEMP_ITEM_OBTAINED`, and all 4 `IMPERIAL_STORMER_*` ids) was
wrong -- the entire block (7439-7449, plus 7225 for the temp-item message) pointed at real Apkallu
Breeding content instead. Not a one-off mislabel -- the capture's CapLog `MesNum` field was wrong
for this whole dialogue set, the same class of error already caught once this session on this same
zone's shared system-message block (see the "+15 drift" entry -- which, worth noting, turned out to
be a false alarm on cross-check below; this Yazuhma block was a real, separate, and much larger
error).

**Re-derived all 12 real ids from the ground-truth client table** (searched for the actual English
phrases -- "keep a whole unit filled up", "starving", "advance unit is depending on these
provisions", "eating my boots", etc. -- rather than trusting any capture label):

```
7424 -> IMPERIAL_STORMER_THANKS      "Thank Zahak you're here. I was about to start eating my boots!"
7425 -> IMPERIAL_STORMER_MORE        "You brought more supplies? Well, you can never have too much..."
7426 -> IMPERIAL_STORMER_PROVISIONS  "The provisions... Have you brought the provisions?"
7427 -> IMPERIAL_STORMER_FULL_BELLY  "There's nothing like a full belly..."
7428 -> YAZUHMA_ALREADY_HAVE_RATION  "Why don't you deliver the rations I already gave you?"
7429 -> YAZUHMA_GRANT_2              "The advance unit is depending on these provisions. Don't let them down!"
7430 -> YAZUHMA_GRANT_1              "This should keep a whole unit filled up for a while."
7431 -> YAZUHMA_STILL_STARVING       "There are still brave soldiers starving out there!"
7432 -> YAZUHMA_HALFWAY              "It looks like about half of the advance unit has received their rations."
7433 -> YAZUHMA_DENT                 "You've made a decent dent in my pile of rations..."
7434 -> YAZUHMA_LEFTOVER             "That's strange, there are some rations left over..."
7435 -> (new) YAZUHMA_ALL_DONE       "Thanks to you, the advance unit is now completely provisioned. Excellent work!"
```

All 12 land in one clean, contiguous, correctly-ordered block (7424-7435) -- strong independent
confirmation these are right, not another guess. `7435` is a bonus find: a real completion line
never wired into `Yazuhma.lua` at all -- flagged in the tracker as worth adding when the last
Stormer is fed.

For the temp-item-obtained message (`YAZUHMA_TEMP_ITEM_OBTAINED`, was wrongly 7225): found two
textually-identical candidates in the client table (7210 and 7233, differing only in their internal
parameter special-code encoding). Disambiguated by comparing byte-for-byte against Leujaoam
Sanctum's `PLAYER_OBTAINS_TEMP_ITEM` (7310), a message already confirmed working live in-game --
7210 matches its exact encoding pattern (`$` special code), 7233 doesn't. Corrected to 7210.

**While re-verifying, also resolved the previously-flagged "+15 drift" concern on the shared
system-message block** (`ASSAULT_22_START`/`TIME_TO_COMPLETE`/`RUNE_UNLOCKED_POS`/
`ASSAULT_POINTS_OBTAINED`/`TIME_REMAINING_MINUTES`) -- cross-checked all 5 against the same
dat-extractor table and every one matches exactly as currently assigned. That flag is now
**definitively resolved as a false alarm**, not left open -- matches the user's own screenshot,
where all 5 of these lines rendered correctly. Good reminder that a suspected drift on one block
doesn't mean a neighboring block is also affected -- each needs its own independent verification.

Fixed in `scripts/zones/Lebros_Cavern/IDs.lua`. Lua-only, no SQL/C++ touched, no DB reimport
needed -- a script reload/restart picks this up.

**User retested live 2026-08-20: confirmed correct dialogue now displays.**

## Lebros Supplies: confirmed mission-blocking impassable wall, same root cause as Brittle Rock 4/5 (2026-08-20)

User reported an impassable wall at approximately `-396, -9, 180`, blocking access to the Imperial
Stormers, mission uncompletable. Confirmed Gateway addon was off, ruling out the client-side
override that resolved several other door bugs this session.

Cross-checked the reported coordinate against `_1rj`/`_1rq` (the 2 wall props registered to this
instance earlier today, see the "full object/dialogue rescan" entry above) -- `_1rq`'s real
position, `-399,-13,-180`, is an extremely close match (X/Y near-identical, Z differing only in
sign, plausibly a transcription flip when reading the coordinate off the client).

**Diagnosed properly instead of guessing at a fix**, using the same methodology already proven for
Excavation Duty's Brittle Rock 4/5:
1. Had the user run `!checknav -399 -13 -180` and a point on the far side of the wall.
   `checkNavPath` returned `true` with 2 waypoints -- **the compiled navmesh already has a valid
   route through this point.** Same signature as Brittle Rock 4/5: clean navmesh, real block
   elsewhere.
2. Temporarily hid `_1rq` (`setStatus(DISAPPEAR)` instead of `NORMAL`) as a diagnostic -- the same
   decisive "remove the entity entirely" test that proved Brittle Rock 4/5's block was independent
   of any entity. **User confirmed**: hiding it removed the object from client-side entity tracking
   (a minimap radar addon that was showing a dot for it lost the dot entirely), but the wall itself
   remained completely solid and impassable. User also confirmed via Ashita's F11 zone-geometry
   highlight feature that a distinct object is still visibly rendered right at that spot, separate
   from the surrounding terrain -- ruling out "it's just part of the normal map, nothing is really
   there."

**Conclusion: this is static, baked-in client zone geometry, not `_1rq`'s (or any) entity
collision.** Identical root cause and identical proof methodology to Brittle Rock 4/5 -- no
server-side lever (status, animation, position, or entity presence/absence) reaches baked zone
geometry; the navmesh (the walkable-area mesh) and the actual 3D collision model are evidently
separate systems in this client, and only the collision model is blocking here.

Reverted the diagnostic hide back to `NORMAL` (`scripts/zones/Lebros_Cavern/instances/
lebros_supplies.lua`) -- hiding `_1rq` achieved nothing toward fixing the wall and only broke
radar-addon visibility for it, a real (if minor) regression not worth keeping.

**Not yet resolved.** Per Brittle Rock 4/5's own precedent, the only proven path forward for this
exact failure mode is relocating the affected objective(s) to reachable coordinates -- but that
needs real reference data (a capture or wiki source showing where retail actually places the
blocked Stormer(s)) that hasn't been gathered yet, and needs the user to confirm exactly which
Stormer(s)/group(s) this wall is actually cutting off before attempting anything. Flagged as a
confirmed mission blocker in `Assault_Issue_Tracker.md` (downgraded from green to red) rather than
guessed at further.

**Follow-up, same day**: user validated the food/dialogue mechanic itself is fully correct,
isolating it from the wall blocker by using `!giveitem` + wallhack to bypass the wall and reach
every Stormer directly. Confirmed: all 12 accept food correctly, show correct dialogue, refuse
further food once full, and once all 12 are full the Rune of Release and Ancient Lockbox both
unlock and work, with a normal exit. This confirms the mechanic/dialogue work from earlier today is
completely correct -- **the wall is now the sole remaining blocker** for this mission, not the
mission logic. Tracker updated to reflect this distinction (mechanic validated, wall still open).

## Sagelord Elimination: same door-in-the-way pattern (`_1k6`), and a zone-wide RUNE_UNLOCKED bug (2026-08-20)

User reported an impassable object blocking a doorway in Sagelord Elimination at
`(-339, -9, 198)` -- same category of report as Excavation Duty's Brittle Rock 4/5 and Lebros
Supplies' `_1rq`. Found the real object: `_1k6` ("Door_1k6") in `sql/npc_list.sql`,
`(-339.919, -18.703, 199.863)` -- a very close positional match. Not registered in
`instance_entities` for any instance and not referenced anywhere in this zone's scripts, suggesting
it may be persistent shared zone geometry rather than an instance-specific spawn. Given the
established pattern (2 for 2 this session on "closed object blocking a doorway" reports resolving
to baked client zone geometry, unfixable from any server-side lever), asked the user to run the
same fast confirming checks (`!checknav` + Ashita F11 highlight) before re-deriving the full
diagnostic from scratch -- result not yet back.

**Separately, user reported the Rune of Release completion text on this mission doesn't include
the grid position.** Checked `sagelord_elimination.lua` and found `messageSpecial(RUNE_UNLOCKED, 8,
8)` -- `RUNE_UNLOCKED` (7510 in this zone) takes no params; `RUNE_UNLOCKED_POS` (7509) is the one
that takes a grid letter index + number, matching the same bug class already fixed individually on
Excavation Duty and Lebros Supplies earlier today.

**Per user direction, checked all 50 missions instead of just this one** --
`grep -rn "ID\.text\.RUNE_UNLOCKED\b" scripts/zones/*/instances/*.lua` turned up **26 missions**
with this exact bug, across all 5 zones. Only Preemptive Strike and Imperial Agent Rescue (both
Mamool Ja Training Grounds) already used the correct constant. Fixed all 26 with a scripted
find-and-replace (`ID.text.RUNE_UNLOCKED,` -> `ID.text.RUNE_UNLOCKED_POS,`), leaving each mission's
existing params untouched -- verified 0 remaining wrong-constant call sites afterward, and spot-
checked several diffs (including one with non-default params, `wamoura_farm_raid.lua`'s `7, 8`) to
confirm the sed only touched the intended call and nothing else.

**Full list of the 25 other missions fixed**: `apkallu_seizure`, `bellerophons_bliss`,
`demolition_duty`, `deserter`, `desperately_seeking_cephalopods`, `lost_and_found`,
`searat_salvation` (Ilrusi Atoll); `troll_fugitives`, `wamoura_farm_raid` (Lebros Cavern);
`escort_professor_chanoix`, `shanarha_grass_conservation` (Leujaoam Sanctum); `azure_ailments`,
`blitzkrieg`, `breaking_morale`, `imperial_treasure_retrieval`, `marids_in_the_mist`,
`the_double_agent`, `the_susanoo_shuffle` (Mamool Ja Training Grounds); `building_bridges`,
`defuse_the_threat`, `operation_snake_eyes`, `saving_private_ryaaf`, `shooting_down_the_baron`,
`stop_the_bloodshed`, `the_price_is_right`, `wake_the_puppet` (Periqia).

**Important caveat, not resolved here**: the actual grid params passed on all 26 (`8, 8` almost
everywhere, `7, 8` on a couple) were left exactly as they already were -- carried over, not
independently verified against real capture data per mission. The suspiciously uniform repetition
of `8, 8` across missions with no documented capture-verified grid anywhere in this file (checked --
no entry exists confirming a real per-mission grid for any of these, including the 2 that were
already using the right constant) strongly suggests this was always a copy-pasted placeholder, not
real data. This fix only addresses the reported symptom (grid position missing from the message
entirely) -- it does not confirm the specific letter/number shown is retail-accurate for any given
mission. That would need a real capture or wiki source checked per mission, not attempted here.

Lua-only across all 26 files, no SQL/C++ touched, no DB reimport needed -- a script reload/restart
picks this up. Not yet live-tested on any of the 25 missions beyond Sagelord Elimination itself.

## Sagelord Elimination: real 4-stage boss mechanic implemented, real Rune/Lockbox positions found (2026-08-20)

User clarified the mission's actual mechanic, which the original build got completely wrong (it
was a plain kill-1 like Lamia No.13/Broken Troll Soldier -- reasonable given no evidence otherwise
at the time, but wrong): at every 20% HP lost (80/60/40%), Sagelord Molaal Ja uses Warm-Up then
flees at 200% speed, linking several nearby Mamool Ja Trainees against the player as he passes; at
20% HP he casts Warp and escapes -- **and that escape is the actual win condition**, not killing
him to 0 HP.

**Mined the real Thris capture for this mission** (`Mamool Ja Training Grounds SP - Sagelord
Elimination.zip`, downloaded earlier this session but never mined until now) rather than
implementing purely from the user's description alone:

- **Warm-Up confirmed real**: skill id 1924 (animation 1268, distinct from a generic "warm-up"
  registered to this family's normal skill list, id 1734/animation 1152 -- 1924 isn't in Sagelord's
  own family skill list at all, confirming this is a scripted special move, not organic AI skill
  selection). Observed twice in the capture ("Sagelord Molaal Ja readies/uses Warm-Up"), each
  followed by "gains the effect of Evasion Boost" and the player briefly losing him ("is out of
  range" / "You lose sight of Sagelord Molaal Ja") -- consistent with a brief flee after each use.
- **The escape really is a real player-spell cast, not a mob skill**: "[12:37:52]Sagelord Molaal Ja
  starts casting Warp." ... "[12:37:57]Sagelord Molaal Ja casts Warp. Sagelord Molaal Ja vanishes."
  -- a ~5s cast, matching `spell_list` id 261's real 4000ms base cast time closely. Checked whether
  a commented-out mob skill literally named `warp_out` (`sql/mob_skills.sql`, id 1024) might be the
  right mechanism instead -- it isn't; the capture clearly shows the real player Warp spell being
  cast, not a mob ability.
  - Checked `scripts/globals/spells/warp.lua` (the real spell's own effect script) before relying
    on it -- it adds a player-only `TELEPORT` status effect (home-point teleport), not something a
    mob entity can meaningfully resolve. `castSpell(261)` is used in the implementation purely for
    the correct client-visible cast animation/text matching the capture; the actual game-logic
    escape (mission progress + despawn) is handled explicitly in a timer instead of relying on the
    spell's own (player-only) effect.
- **This capture's own run is not fully conclusive on the exact final-escape design**: only one
  Warp cast is visible, occurring mid-fight, with combat clearly continuing a few seconds
  afterward (he's hit again and speaks more dialogue after "vanishes") -- ambiguous whether this
  was an interim defensive Warp or the real final escape cut short by capture/packet timing. The
  20%-triggers-final-escape structure and "the escape IS the win condition" come directly from the
  user's own clarification, not independently re-derived from this run alone.
- **Real Rune of Release / Ancient Lockbox positions**: found via the same capture's NPCLogger --
  `(-300,-3,284)` and `(-300,-3,287)` respectively. User had independently reported the position
  looked wrong and should be near `(-300,-4,295)` -- the capture data confirms that almost exactly
  (X identical, Y/Z within a few units), replacing the wrong zone-wide `npc_list` default position
  `(-55, 1.323, -103)` that this mission had been silently using.
- **Real grid-reference params**: while fixing the earlier zone-wide `RUNE_UNLOCKED_POS` bug
  (previous entry), this mission's own capture shows the actual decoded text "Unlocking Rune of
  Release (I-7)" -- corrected the params from the placeholder `(8, 8)` to the real `(8, 7)`.

**Implementation** (`scripts/zones/Mamool_Ja_Training_Grounds/mobs/Sagelord_Molaal_Ja.lua`, full
rewrite): `onMobFight` tracks a `fleeStage` localvar (0-4). At stages 0-2 (crossing 80/60/40% HP),
triggers `useMobAbility(1924)`, then after a 2s delay disengages, doubles his speed, `pathTo()`s
directly away from whoever engaged him, and links any of the mission's 9 Mamool Ja Trainees within
12 yalms of his position at that moment (`setAggressive(true)` + `engage()`, the same pattern
already proven for Orichalcum Survey's Qiqirn Miners). Speed resets after 4s. At stage 3 (20% HP),
disengages, casts Warp for the correct visual, and 5s later (matching the real capture's cast time)
sets instance progress and despawns him -- the real win condition. `onMobDeath` is kept as a
fallback completion path (gated on `fleeStage < 4` so it can't double-fire) for an outright kill
before he successfully escapes -- the capture shows he takes real damage throughout, including
during his casting windows, so this is clearly possible.

**Not independently re-verified / flagged as estimates**: flee distance (15 yalms), Trainee link
range (12 yalms), and how long the speed boost lasts before resetting (4s). The deterministic
"always links if in range" Trainee behavior was checked with the user and confirmed correct as
implemented -- "usually" in their original phrasing described the practical range-dependent outcome
(a Trainee only links if it happens to be in range when he flees past), not a separate random
chance on top of that.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up. This
is a full rebuild of the mission's core mechanic and has **not been live-tested at all** yet.

## Lebros Supplies: Seafood Stewpot corrected from a fixed group to a real distance check (2026-08-20)

User confirmed the Seafood Stewpot ("Temporary Seafood Stewpot," added to retail 2015-05-14) is a
real item that "fully feeds all surrounding soldiers," and asked whether that was captured
correctly. It was wired in (item 5238, granted at the same 1-in-6 odds as the 5 point-value foods,
instantly fills a target Stormer instead of adding points), but the "surrounding" behavior was
implemented as a fixed, pre-assigned 5-cluster group table (matching the wiki's WSW-2/SSW-2/SE-3/
NW-3/N-2 layout) rather than a real proximity check -- functionally similar in most cases since the
groups were built from real clustered positions, but not a literal "surrounding" implementation:
a player standing between two clusters wouldn't get a real radius check crossing the artificial
group boundary.

**Corrected per user direction** (`scripts/zones/Lebros_Cavern/npcs/Imperial_Stormer.lua`): removed
the static `STORMER_GROUPS` table entirely, replaced with a real distance check against every
Stormer's live position (`checkDistance()` <= 30 yalms). The radius wasn't guessed -- checked
against the real capture-derived positions already wired into `instances/lebros_supplies.lua`'s
`STORMER_POS`: the widest real intra-cluster spread is ~25 yalms (the SE group's 3 members), and
the narrowest gap between two *different* clusters is ~77 yalms (WSW to SSW) -- 30 yalms
comfortably covers the former while staying well clear of the latter, so this should produce
materially the same practical grouping as before in normal play, but via an actual proximity check
instead of a hardcoded lookup table.

Also confirmed with the user: the existing equal 1-in-6 grant-odds assumption (uniform across all
6 food items including the Stewpot) is fine as-is -- no evidence of a special rarer chance for the
Stewpot specifically, despite it being a later content addition.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up.

## Sagelord Elimination: real fix for the flee/vanish not working (first live test) (2026-08-20)

First live test of the new 4-stage mechanic: Warm-Up triggered correctly at every 20% threshold,
but he never actually fled/ran, and at 20% HP he "just instantly vanishes, no animation."

**Root cause, same for both symptoms**: `disengage()` was called right before both `pathTo()` and
`castSpell()`, and both depend on state that `disengage()` tears down.

- `onMobFight` (`CMobController::DoCombatTick`, `mob_controller.cpp:531`) only fires while the mob
  is actively engaged in `CAttackState` -- once disengaged, it stops firing entirely. The flee logic
  called `pathTo()` exactly once, then disengaged, so there was no per-tick reinforcement -- and the
  idle/roam state the mob transitioned into afterward doesn't follow an externally-set path anyway.
  Checked the only real precedent for `pathTo()` in this codebase, Selh'teus
  (`Empyreal_Paradox/mobs/Selhteus.lua`) -- it calls `pathTo()` **every single `onMobFight` tick**,
  continuously, and never disengages at all. Fixed by dropping `disengage()` entirely and doing the
  same: a `fleeUntil` localvar timestamp gates a per-tick block that recomputes the direction away
  from the target's live position and calls `pathTo()` fresh every tick for the full flee window.
- `castSpell(spellId)` with no explicit target argument falls back to the mob's own *current battle
  target* (`CLuaBaseEntity::castSpell`, `src/map/lua/lua_baseentity.cpp:12251`) -- which
  `disengage()` had just cleared to 0, so the cast silently failed validation with no visible
  animation at all, while the independent 5-second completion timer fired anyway regardless of
  whether the cast actually succeeded -- producing exactly the reported "instantly vanishes, no
  animation." Fixed by dropping `disengage()` here too and passing the mob itself as an explicit
  self-target (`castSpell(WARP_SPELL, mob)`), since Warp is a self-effect spell and doesn't need a
  valid battle target regardless.

**Flee duration set to 30 seconds** (was an earlier placeholder guess of 6s) -- user confirmed via
a real video playthrough reference that this matches the real player Flee job ability's known
duration, and that he actively runs/paths away for the **full** 30 seconds (not just a buff
duration with optional continued fighting). Confirmed this doesn't risk runaway drift: `pathTo()`
just sets a steering target refreshed every tick, not a per-tick teleport -- his actual travel
distance over the window is governed by his real movement speed (doubled) times 30 seconds, not by
`FLEE_DISTANCE`'s 15-yalm waypoint offset, which just keeps the steering point far enough ahead of
him to produce a straight, continuous run rather than jittering near a fixed point.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up. Still
not fully live-tested (this fixes the specific bugs found in the first test; needs a fresh retest).
Separately, user also reported the Rune of Release appeared in an incorrect location despite the
real capture-derived position fix earlier today -- not yet actionable, needs the specific
observed-vs-expected location to investigate further rather than guessing again.

## Sagelord Elimination: flee clipped through the map boundary, second live test (2026-08-20)

Second live test, after the disengage()-removal fix above: "that was fun, he clipped outside the
map." Map-server log confirms exactly what happened: dozens of consecutive
`CNavMesh::findPath Couldn't find path` errors, each one's coordinates marching steadily further
out (`X` drifting from -500 toward -491, `Z` climbing from 353 to 428+ over about 20 seconds) --
he was walking a straight line in the flee direction the whole time, completely undeterred by the
navmesh repeatedly failing to find a path there.

**Root cause**: `pathTo()` has no built-in reachability or bounds check -- it just sets a raw
movement target (`CLuaBaseEntity::pathTo`, `src/map/lua/lua_baseentity.cpp:1367`,
`PAI->PathFind->PathTo()`). Once the "directly away from the target" direction happened to point
off the compiled navmesh (predictable near any arena edge -- fleeing is specifically directed
*away* from the player, who is usually somewhere near the middle of the playable area), each tick's
recomputed point landed further off the mesh than the last, and the underlying movement code kept
walking toward it in a straight line regardless of the repeated pathfinding failures, carrying him
straight through the boundary.

**Fixed**: every candidate flee point is now validated against the navmesh
(`zone:checkNavPosition()`, the same diagnostic built earlier this session for Excavation Duty's
Brittle Rock investigation) before `pathTo()` is ever called. If the direct away-from-target angle
fails, the code sweeps outward in both directions (±20°, ±40°, ±60°, ±90°, ±120°, ±150°, 180°) until
it finds a valid point, guaranteeing he can never be sent toward somewhere off the mesh even right
at an arena edge. If every angle in the sweep fails (fully boxed in, unlikely but possible), that
tick simply skips movement rather than picking an invalid point -- he'll try again next tick.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up. Still
needs a fresh retest to confirm the flee now stays in bounds for the full 30 seconds.

## Sagelord Elimination: third live test -- Rune position confirmed correct, mechanic works, two more real bugs found and fixed (2026-08-20)

Third live test: **user confirmed the Rune of Release position and all core mechanics are correct**
-- Warm-Up and flee trigger at every 20%, Warp casts and he disappears at 20% HP (animation "cuts
out a little at the end but passable"). Two remaining real bugs found:

1. **Still clips up walls** -- `checkNavPosition()` alone wasn't a strong enough check. It only
   confirms a navmesh polygon exists near the candidate point; it doesn't verify a genuinely
   walkable, surface-following ROUTE from his current position actually gets there. Added a
   `checkNavPath()` check as well (the same real pathfind used for the earlier map-boundary fix) --
   it requires an actual connected route between the two points, which should reject a candidate
   that merely happens to sit near an isolated wall polygon that `checkNavPosition` alone was
   willing to accept.
2. **He always stops and casts spells if the player stays close while he flees** -- confirmed this
   is a real engine-level gap, not a Lua logic bug: `CMobController::DoCombatTick`
   (`mob_controller.cpp:531`) tries special skills, spells, and TP moves in C++ immediately after
   `luautils::OnMobFight` returns, completely independent of what the Lua script does -- returning
   early from `onMobFight` only skips the script's *own* logic, not the engine's normal combat
   readiness checks, and a successful cast/skill/TP-move makes `DoCombatTick` return before ever
   calling `Move()`. Traced each path to find a real, controllable off-switch instead of guessing:
   - `CanCastSpells()` (`mob_controller.cpp:422`) has a genuine, confirmed status-effect gate --
     `HasStatusEffect({EFFECT_SILENCE, EFFECT_MUTE})` returns false immediately. Applied Silence to
     the mob for the flee's exact duration (`addStatusEffect(SILENCE, 0, 0, FLEE_DURATION)`,
     auto-expiring in sync with the flee window).
   - `IsSpecialSkillReady()` (`mob_controller.cpp:1084`) returns false immediately if
     `MOBMOD_SPECIAL_SKILL == 0` -- a clean, directly Lua-settable mob mod. Set to 0 for the flee,
     restored to 1 when it ends.
   - `MobSkill()` (`mob_controller.cpp:272`) looks up `battleutils::GetMobSkillList()` using
     `MOBMOD_SKILL_LIST` and returns false immediately if that list is empty -- confirmed via the
     one other real precedent for swapping this mod at runtime, `Wyrm.lua`'s ground/flying skill-set
     swap. Temporarily set to `0` (empty) for the flee, restored to his real list (`176`, confirmed
     earlier this session via `mob_pools` poolid 3437) once it ends.
   All three restored together in the same place the flee window naturally ends, alongside the
   existing speed-reset logic.

**Also confirmed by design, not changed**: user required that even if he loses "his flee status
effect," he should keep pathing away for the rest of the timer. The actual flee/`pathTo()` movement
logic was already governed purely by the `fleeUntil` battle-time check, with no dependency on any
status effect's presence -- so this was already correctly decoupled before this fix, and remains so
now that Silence has been added for the (separate) purpose of blocking spellcasting.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up. Still
needs a fresh retest to confirm both fixes hold.

## Sagelord Elimination: Warp escape could get permanently skipped if HP crossed 20% while Silenced (2026-08-20)

User found a real, confirmed design flaw: "when his hp drops to under 20% while silenced, he skips
this and once silence wears off will not resume."

**Root cause**: the Warp-escape check was gated behind `fleeStage == 3` -- only reachable once all
3 Warm-Up/flee/Silence cycles (80/60/40%) had each individually run their **full** 30 seconds, one
at a time, in strict sequence. If a player's damage dropped his HP under 20% *before* that
sequence formally finished (entirely possible -- he keeps taking real damage throughout, including
during his own Silence/flee windows), the check simply never re-evaluated the condition again until
`fleeStage` naturally reached 3 through the normal staged progression -- meaning the escape could
be delayed by up to 90 seconds (3 full flee cycles) past the point his HP had already dropped low
enough, or in the reported case, silently missed if the timing lined up wrong.

**Fixed**: restructured `onMobFight` so the `hpp <= 20` check is now the single highest-priority
condition, evaluated first on every tick regardless of what `fleeStage` currently is. If he's not
mid-animation and not Silenced, it fires the Warp cast immediately. If it can't fire yet (still
Silenced from whichever cycle was active when HP crossed the threshold), it does **not** give up --
it keeps evading (steering away from the player, same as a normal flee) and re-checks the exact
same condition on every subsequent tick, firing the instant a clean window appears (Silence expires
naturally after its own 30s, same duration as the flee cycle it was applied for). Once HP is at or
under 20%, the normal 80/60/40% trigger logic is also fully bypassed (an `escaping` localvar flag
short-circuits the whole function once the Warp cast actually starts) -- so a big burst of damage
can no longer cause a *new* Warm-Up/flee/Silence cycle to start on top of an already-critical HP
state, which would have only delayed the escape further.

Refactored the per-tick flee-steering logic (direction-away-from-target + navmesh-validated sweep +
Trainee linking) into a shared `stepFlee()` helper, since it's now called from both the normal
80/60/40% flee cycles and the "waiting for a clean window to Warp" holding pattern.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up. Still
needs a fresh retest to confirm the escape now always lands, including under a fast-burst-damage
scenario.

## Sagelord Elimination: mined his real dialogue from the same capture (2026-08-20)

User asked whether the Sagelord Elimination capture had ever been checked for his own dialogue,
noting it likely plays around his HP-threshold reactions or the Warp escape, and asked about the
real Warp animation id while at it.

**Warp animation**: already correct as implemented -- the capture's own `[AView]` line
(`Actor: 17047590 (Sagelord Molaal Ja), ID: 261, Animation: 261, Message: 93`) confirms the
animation value for a real spell cast is driven directly by the spell id itself (261 = Warp), which
is exactly what `castSpell(WARP_SPELL, mob)` already produces -- nothing to change here.

**Dialogue**: found 3 spoken lines from Sagelord Molaal Ja in the capture
(`Sagelord Molaal Ja : ...`). Same mislabeling pattern already caught multiple times this session --
the capture's own inline CapLog `MesNum` values (7545/7546/7547) were wrong for all 3, matching
completely unrelated real text ("The supplies you seized are missing!", an Imperial Stormer line,
and a Qiqirn decoy hint respectively). Found the real ids by searching the client dialog table
directly for the actual spoken text -- a clean, contiguous, correctly-ordered block: **7530/7531/
7532**.

Checked the relative timing of each against the real "starts casting Warp" -> "casts Warp...
vanishes" sequence before wiring anything in:
- **7530** ("<Cough, cough>... Pay for...insulting the Sagelord...you shall...") fires the exact
  same second he starts casting Warp (12:37:52) -- wired into the Warp-escape trigger in
  `Sagelord_Molaal_Ja.lua`, right alongside `castSpell()`.
- **7531**/**7532** both fire *after* "vanishes" (6s and 9s after cast start respectively), with
  clear combat continuing in between (he's hit again at 12:38:00, speaks again at 12:38:01). This
  capture's specific Warp cast is very likely an interim/non-final escape in that particular
  playthrough, not the true 20%-threshold escape this mission's mechanic implements (which
  despawns him for good once the cast completes) -- wiring these two in would mean they'd try to
  fire *after* he's already been removed from the world in this build. Left unwired, added to
  `IDs.lua` with a note for reference in case a cleaner capture surfaces later.

Also spotted (and confirmed already correct, no change needed): `ASSAULT_13_START` (7459,
"Commencing...! Objective: Defeat Sagelord Molaal Ja") -- found while searching for the dialogue
text above, already matches the real client table exactly.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up.

## Sagelord Elimination: fifth live test -- rubber-banding/wall-clipping and delayed Warp escape (2026-08-20)

User confirmed the mined dialogue plays correctly at 20% HP, but reported two more real bugs:

1. **Still clips into walls, and the flee itself "rubber bands or skips around."** Root cause:
   `stepFlee()` was called and issued a brand new `pathTo()` on **every single** `onMobFight`
   tick. If ticks fire faster than he can meaningfully travel between them, each new `pathTo()`
   interrupts him mid-step before he's covered real ground toward the previous target -- a
   plausible cause for exactly this kind of janky, discontinuous movement, and for a client/server
   desync during that constant retargeting to glitch him through geometry that a single continuous
   run would have correctly avoided. Fixed by throttling `stepFlee()` to at most once every 2
   seconds (`FLEE_STEP_INTERVAL`) via a `nextFleeStep` localvar -- frequent enough to keep tracking
   a moving player, infrequent enough to let him actually complete each leg of the run smoothly.

2. **He runs for a while before Warping at 20% HP instead of doing it instantly.** Root cause: when
   HP first crossed 20%, he was very likely still inside whichever flee cycle's 30-second Silence
   window was active at that moment (from the 80/60/40% suppression logic) -- the escape-retry
   logic correctly kept evading and re-checking every tick, but since it only checked
   `hasStatusEffect(SILENCE)` (never actively removed it), he had to wait out the **remainder** of
   that Silence window naturally, up to the full 30 seconds, before the escape could fire. Per user
   suggestion, fixed by actively stripping Silence the instant HP is confirmed critical
   (`delStatusEffect(SILENCE)`) rather than passively waiting for it to expire -- the only
   remaining gate is `notBusy()` (mid-animation), which resolves within a tick or two, not up to 30
   seconds.

Lua-only, no SQL/C++ touched, no DB reimport needed -- a script reload/restart picks this up. Still
needs a fresh retest to confirm both fixes hold.

## Sagelord Elimination: sixth live test -- Warp animation still cuts off, still clips through walls (2026-08-20)

Pushed as `1e9ab072c2` and confirmed: mined dialogue plays correctly, and (implicitly, not called
out as regressed) the throttled `stepFlee()` fixed the rubber-banding. But 2 issues remained:

1. **Delayed Warp's vanish animation cuts off.** `setStatus(DISAPPEAR)` was firing the instant the
   `WARP_CAST_MS` (5000ms, matches the real capture's cast time) timer completed -- removing the
   entity from the world the moment the cast resolves, with no time for whatever vanish
   animation/effect is supposed to play after "casts Warp." Fixed by adding a second, nested timer
   (`WARP_VANISH_MS`, 3000ms) between the cast completing and the actual `setStatus(DISAPPEAR)` call
   -- mission-completion (`setProgress`) still fires at the original moment (matching the capture's
   real "casts Warp" timing), only the despawn itself is delayed. 3000ms is an estimate, not
   confirmed against capture data (the capture only pins down the ~5s cast time, not how long the
   vanish effect itself takes) -- worth tuning after a live look at whether it's now too long/short.

2. **Still clips through walls despite the checkNavPosition()/checkNavPath() validation already in
   place.** Found the real root cause this time by reading `pathTo()`'s own C++
   (`src/map/lua/lua_baseentity.cpp:1367`): when called with no explicit `flags` argument -- which
   every call in this file was -- it defaults to
   `PATHFLAG_RUN | PATHFLAG_WALLHACK | PATHFLAG_SCRIPT`. `PATHFLAG_WALLHACK` (`0x02`,
   `src/map/ai/helpers/pathfind.h:44`, "run through walls if path is too long") was silently
   overriding collision on every single flee step, which made all of the earlier navmesh-sweep
   validation moot regardless of how correct it was -- the mob was never actually constrained by the
   geometry it was being validated against. Fixed by passing the flags explicitly:
   `PATHFLAG_RUN | PATHFLAG_SCRIPT` = `9` (no `PATHFLAG_WALLHACK`). Neither flag constant is exposed
   to Lua anywhere in this codebase (checked) -- `transport.lua`'s own bare `PATHFLAG_WALLHACK`
   reference is an undefined global, a separate pre-existing issue, not a real binding to copy from
   -- so passed as the raw numeric value with a comment explaining the bit math. The earlier
   navmesh-sweep work is still worth keeping (it picks a genuinely reachable point instead of an
   arbitrary one 15 yalms away), it just wasn't the thing actually stopping him from going through
   walls.

Both fixes are Lua-only (`scripts/zones/Mamool_Ja_Training_Grounds/mobs/Sagelord_Molaal_Ja.lua`),
script reload only, no DB reimport needed. Not yet retested live.

## Sagelord Elimination: seventh live test -- Warp animation and wall-clipping confirmed fixed; new blocker found (2026-08-20)

User retested. Both sixth-round fixes hold: the Warp vanish animation now plays correctly, and no
wall-clipping was observed. AI flee pathing is "a little off" but user judged it good enough to
leave as-is -- not treated as a bug to chase further right now.

**New blocker reported: a door is closed and blocking progress.** Not yet investigated -- user
explicitly asked to mark this for a later fix rather than attempt one now. No cause found yet; could
be the same class of bug seen elsewhere this session (missing `instance_entities` registration, a
door prop never revealed in `onInstanceCreated`, an `entityFlags`/targetability issue, or -- less
likely given the Gateway-addon correction earlier this session -- a genuine server-side door state
bug). `sagelord_elimination.lua`'s `onInstanceCreated` currently touches only Rune of
Release/Ancient Lockbox and the mob spawns -- no door/gate prop of any kind is referenced anywhere
in this mission's instance or mob scripts, so if a real door exists in this zone for this mission it
has never been wired in at all. Needs investigation (probably starting with a capture/widescan of
the blocked doorway's real npc_list entry) before attempting a fix.

## Troll Fugitives: full live-test pass, fixed the 25-75% start-HP mechanic (2026-08-20)

User confirmed a full playthrough: all 15 mob positions correct, real 2-hour ability, Rune of
Release position correct, Ancient Lockbox works. One real bug found and fixed:

**Trolls should spawn already wounded (25-75% HP), per the real mechanic ("They start out somewhat
wounded, making them easier to kill. They range in health from 25% to 75%.").** The HP-randomizing
roll already existed in `mobs/Broken_Troll_Soldier.lua` -- `MaxHP / (8/bonus)` with `bonus =
math.random(2, 6)`, which is the right math for 25-75% (2/8 to 6/8) -- but it was wired to
`onMobEngaged`, not `onMobSpawn`. Two real consequences: they spawned and sat at full HP until first
engaged, and re-engaging after losing aggro (leash, disengage, etc.) would re-roll and could
partially heal an already-damaged Troll back up, since the roll always computed off current HP at
whatever point it fired rather than being a one-time thing. Moved to `onMobSpawn` (simplified to
`mob:setHP(mob:getMaxHP() * math.random(25, 75) / 100)`, same effective range, clearer math) so it
applies exactly once, at spawn, and stays for the rest of the fight.

Lua-only, script reload only, no DB reimport needed. User-confirmed live as part of the same
playthrough that surfaced this bug -- Troll Fugitives is now fully signed off, no outstanding
issues.

## Troll Fugitives: HP-percentage fix confirmed against a real capture (2026-08-20)

Sanity-checked the fix above against `Lebros Cavern PSC - Troll Fugitives (Thris).zip`'s
`HPTrack/Lebros_Cavern.log` (real per-mob HP ranges from a live fight, not a formula guess) --
values spread roughly 2,700-8,700 HP across the 15 Trolls, consistent with 4 different jobs
(PLD/WAR/RDM/MNK, `sql/mob_groups.sql` zone 63 groups 6-9) each spawning wounded somewhere in the
real 25-75% window. **User confirmed live in-game the same day**: HP percentages meeting
expectations, all 15 randomly generating in the real 25-75% range. Troll Fugitives is now fully
complete with no outstanding issues.

## Saving Private Ryaaf: rebuilt with the real 5-room random-pattern mechanic (2026-08-20)

The original 2026-08-18 build modeled this as a plain, static trigger-all-3 mission (the 3 survivor
NPCs each sitting at one fixed spot). User supplied a community wiki writeup (ffxiclopedia) showing
the real mechanic is much richer: 5 rooms (North/West/South/East/Center), each with a hunched-over
figure that resolves into one of the 3 real survivors or an Experimental Undead (Fomor), plus 3
ambient Cursed Chigoe per room. Exactly 5 possible room-assignment patterns exist, picked randomly
per instance -- always 3 rooms get a real survivor, 2 get a Fomor. The occupant's facing direction
before you approach hints at which it is (except in the East room, where both face East).

**Real data cross-check, not a blind wiki port.** Pulled `Periqia SP - Saving Private Ryaaf.zip`
(NPCLogger + CapLog) and found:
- 15 `Cursed_Chigoe` spawn points already sitting unwired in `mob_spawn_points.sql`, clustering into
  exactly 5 groups of 3 -- real room positions, never registered to this instance.
- 8 `Experimental_Undead` spawn points (job variants thf/brd/blm, `mob_groups` rows 10-12) near
  those same 5 clusters -- the real Fomors.
- The original static `npc_list.sql` data for Ryaaf/Balarahb/Rhagmakah, and this fresh capture's
  own (different!) positions for the same 3 IDs, land in 2 *different* subsets of the 5 clusters --
  direct proof the mechanic really is randomized per instance, and that retail repositions the same
  3 NPC ids per run rather than using 5 separate decoy entities.
- Laying the 5 clusters out as North/East/South/West/Center by rough geometry (entrance sits right
  next to the "North" cluster, matching the user-provided map image), **both real capture samples
  match a wiki pattern exactly with zero adjustment** -- the static data matches pattern 3, the
  fresh capture matches pattern 1. That's strong, non-coincidental confirmation the room/compass
  layout is right, not an arbitrary guess.
- The fresh capture's NPCLogger `dir` field gives 3 real facing-byte samples for pattern 1: North+NPC
  (Balarahb)=90, East+NPC (Rhagmakah)=133, Center+NPC (Ryaaf)=254. User separately supplied the
  engine's real rotation-byte convention (0=N/64=E/128=S/192=W, atan2-based) -- checked the 3 real
  samples against it and they don't line up with a single fixed offset, meaning per-room facing
  bytes are dungeon-segment-relative, not directly derivable from the absolute-compass formula.
  Used the real captured bytes directly for the 3 confirmed cases; South+NPC (wiki: faces West, a
  documented quirk) and West+NPC have no real sample, left as the engine's plain West byte (192) as
  a placeholder, clearly flagged as unconfirmed.
- Also found a clean, contiguous 13-line dialogue block (7557-7569) -- 5 real lines for Ryaaf, 4 for
  Balarahb, 4 for Rhagmakah -- previously wired as completely silent triggers. Wired in, staggered
  the same way multi-line dialogue is paced elsewhere in this codebase, with the despawn/progress
  increment correctly delayed until after the last line (same class of bug already caught once this
  session on Sagelord Molaal Ja's Warp animation -- firing it immediately would cut the dialogue
  off).
- Bonus: `RUNE_UNLOCKED_POS` was using the generic `(8, 8)` = I-8 default guess; this capture
  confirms the real grid is **I-7**. Fixed.

**Implementation**: `scripts/zones/Periqia/instances/saving_private_ryaaf.lua` rewritten --
`onInstanceCreated` now picks 1 of 5 patterns via `math.random`, and per room either repositions the
real survivor NPC there (existing `Ryaaf.lua`/`Balarahb.lua`/`Rhagmakah.lua` trigger flow untouched,
still just `setStatus`+`setProgress`) or `SpawnMob`s the room's assigned Fomor. All 15 Chigoe spawn
unconditionally as ambient obstacles; 3 of the 8 Experimental Undead (not assigned to any room) spawn
as separate ambient roamers. `IDs.lua` gained `mob[33]` (15 Chigoe + 8 Experimental Undead ids) and
the 13 real dialogue text ids.

**Known, deliberate simplifications** (not full retail fidelity, functional gaps flagged rather than
silently shipped):
- The room occupant is the real, already-named entity from the moment it's positioned -- real
  retail's figures are anonymous/hard-to-see until approached. No dedicated decoy entity was built;
  would need one to fully hide identity pre-trigger.
- The wiki's separate "roaming tunnel Fomors move according to where the NPCs are" behavior is not
  modeled -- explicitly described as fully avoidable ambient content, and there's no real path data
  for it. The 3 unused Experimental Undead just roam ambiently with no room-hint AI.
- South/West room facing bytes are unconfirmed placeholders (see above).

Needs a DB reimport (`py -3 dbtool.py`) for the new `instance_entities` rows, plus a script
reload/restart. Not yet tested live.

## Saving Private Ryaaf: first live test -- the "turns into" reveal was completely broken (2026-08-20)

User retested after the rebuild above. Two real bugs, both root-caused (not guessed at):

1. **The 3 real-NPC rooms never responded to trigger at all.** Ryaaf/Balarahb/Rhagmakah's
   `npc_list.sql` rows have `entityFlags=2075` -- decoded, that includes `FLAG_UNTARGETABLE`
   (`0x800`, `src/map/entities/baseentity.h:163`). This has been true since the original
   2026-08-18 build; it was never caught because nobody live-tested trigger interaction on this
   mission until now. Exact same bug class already found and fixed once this session on Lamia
   No.13's Ancient Lockbox (`entityFlags` 3715 -> 1667, same bit). Cross-checked against a real
   working trigger NPC in the same zone (Imperial Stormer, `entityFlags=1179`, bit not set) to
   confirm. Fixed: `entityFlags` 2075 -> 27 (bit removed, rest of the value untouched) for all 3.
2. **The 2 Fomor rooms showed a live Experimental Undead from the moment the instance started**,
   instead of a disguised figure that only reveals as a Fomor on approach. This was a real gap in
   the rebuild, not a data bug -- the previous pass directly `SpawnMob`'d the Fomor at
   `onInstanceCreated` and explicitly flagged this as a known simplification, on the assumption a
   dedicated decoy wasn't worth building. User's live test showed it does matter (the "turns into"
   moment is part of the puzzle). Fixed properly: 2 new `npc_list` rows (`17006818`/`17006819`,
   reusing Ryaaf's own look bytes for a consistent hunched-cloaked appearance, `entityFlags=27`
   from the start) act as `HUNCHED_FIGURE` decoys positioned in whichever 2 rooms the pattern
   assigns as Fomor rooms. New `npcs/Hunched_Figure.lua` -- on trigger, hides itself and
   `SpawnMob`s + `engage()`s the real Experimental Undead at the same spot, using
   `updateClaim()`/`getShortID()` the same way Golden Salvage's `Cursed_Chest.lua` (wrong chest ->
   live mimic) already does. The decoy's own pre-trigger facing uses `FOMOR_FACING`, not the
   room's NPC-facing byte -- the facing hint has to be visible *before* the trigger to mean
   anything, matching the wiki's "check their facing before approaching" tip.

`instances/saving_private_ryaaf.lua`, `npcs/Hunched_Figure.lua` (new), `sql/npc_list.sql`,
`sql/instance_entities.sql`, `IDs.lua`. Needs a DB reimport (both the `entityFlags` correction and
the 2 new rows) and a script reload. Not yet retested live.

## Saving Private Ryaaf: second live test -- the reveal fixes above didn't actually take, 3 more real bugs (2026-08-20)

User retested after the previous round's fixes with a full map-server error log attached. Turned
out the "turns into" reveal was still completely broken -- 3 real, distinct bugs, all confirmed
directly from the log rather than guessed at:

1. **The 2 `HUNCHED_FIGURE` decoys never worked at all.** Map-server log: `[Warning]
   luautils::onTrigger - No Valid Function for HunchedFigure1 in Periqia` (and `HunchedFigure2`).
   This engine resolves a trigger script by exact match between the npc_list `name` field and the
   script filename (same mechanism proven earlier by `Imperial_Stormer` sharing one file across 12
   rows, all named exactly `Imperial_Stormer`). The 2 new decoy rows were named
   `'HunchedFigure1'`/`'HunchedFigure2'` (no underscore, digit suffix) against a file named
   `Hunched_Figure.lua` -- never a match, so the decoy's `onTrigger` (the code that's supposed to
   spawn the real Fomor) never ran even once. This alone explains both "the hunched NPCs don't
   trigger" and "the Fomor NPCs do not spawn" from the user's report -- same root cause. Fixed:
   renamed both rows to `'Hunched_Figure'`.
2. **Cursed Chigoe were untargetable.** Their `mob_pools` row (865) has `entityFlags=2689`, which
   also includes `FLAG_UNTARGETABLE` (`0x800`) -- same bug class, but a separate table from the
   `npc_list.entityFlags` fixed last round. Confirmed real (not a namevis/server-side gate --
   `IsTargetable()` in `src/map/entities/baseentity.cpp:124` only checks the `namevis` column,
   which was already fine here at `24`) -- `entityFlags` is what's packed into the client's entity
   spawn packet and separately governs whether the client lets the player select it at all.
   Cross-checked against a real working sibling in the same family: plain `Chigoe` (poolid 714,
   identical model) already uses `entityFlags=641` with no issue. Fixed: 2689 -> 641.
3. **The 3 real survivors still showed their real name and could be told apart by name alone.**
   Traced why the earlier `entityFlags` fix (which does include `FLAG_HIDE_NAME`, `0x008`) didn't
   suppress this: this engine's nameplate rendering isn't gated by that bit the way `IsTargetable()`
   is gated by `namevis`'s `FLAG_UNTARGETABLE` bit -- there's no separate display-name field at all,
   `name` is the only thing the client ever sees, and it's also the exact field bug #1 above proved
   drives script lookup. Real fix: renamed all 3 survivors' `npc_list.name` to the identical
   `'Hunched_Figure'` too, and consolidated what were 4 separate files
   (`Ryaaf.lua`/`Balarahb.lua`/`Rhagmakah.lua`/`Hunched_Figure.lua`) into one --
   `npcs/Hunched_Figure.lua` -- which tells all 5 rooms' occupants apart by `npc:getID()` instead of
   by name. Genuinely achieves the wiki's "figures do not show names" for the first time, rather
   than relying on a flag that doesn't do what its name implies in this engine.

Also silenced 2 harmless-but-noisy log errors the user flagged (`onMobDeath` undefined for both
`Cursed_Chigoe`/`Experimental_Undead`) -- neither file existed at all; added minimal stub files
with just an empty `onMobDeath`, matching the pattern already used elsewhere in this codebase for
ambient mobs with no custom behavior (e.g. `Troll_Combatant.lua`).

**Not resolved, flagged rather than guessed at**: the user's screenshot shows `Obtained temporary
item: !` (blank item name) alongside `You find a sparkling object.` / `You find nothing of
interest.` -- classic HELM-style gathering flavor text. Searched this mission's own capture
(`Periqia SP - Saving Private Ryaaf.zip`) end to end for these exact phrases and found **no
match at all** -- nothing in Saving Private Ryaaf's own real data produces this text, so it's very
likely an unrelated pre-existing system (a real HELM point nearby, or some other zone-wide
gathering mechanic) coincidentally firing during the same test session, not something this
mission's own scripts caused. Not touched -- would need to know which system actually owns that
message before attempting a fix.

`sql/npc_list.sql` (name renames), `sql/mob_pools.sql` (Cursed_Chigoe entityFlags), new
`npcs/Cursed_Chigoe.lua`/`Experimental_Undead.lua` stubs, consolidated `npcs/Hunched_Figure.lua`
(replaces the deleted `Ryaaf.lua`/`Balarahb.lua`/`Rhagmakah.lua`),
`instances/saving_private_ryaaf.lua` (header only, logic unchanged). Needs a DB reimport (name and
entityFlags changes) and a script reload. Not yet retested live.

## Periqia zone-wide: timeout black-screen hang, a real Zone.lua bug, not a repeat of the 2026-08-18 one (2026-08-20)

User noticed this on Saving Private Ryaaf specifically, but recognized the symptom (black screen
hang on instance timeout) from the earlier 2026-08-18 system-wide fix and asked whether it was the
same bug recurring. It wasn't -- checked directly and found a real, distinct cause:

`scripts/zones/Periqia/Zone.lua`'s `onEventFinish` (the fallback the engine's event-script lookup
chain resolves to whenever an instance file itself has no handler -- confirmed via the earlier
system-wide fix's own trace that this fallback is what actually calls `setPos()` on timeout) read:

```lua
zone_object.onEventFinish = function(player, csid, option)
    local chars = instance:getChars()
    if csid == 102 then
        for i, v in pairs(chars) do
            v:setPos(0, 0, 0, 0, 79)
        end
    end
end
```

`instance` is never defined anywhere in this function -- it only receives `player`, `csid`,
`option`. Referencing an undefined global here throws a Lua error on every single call, so
`setPos()` never runs and the player is never actually teleported out of the failed/timed-out
instance -- the exact black-screen-hang symptom, but from a completely different root cause than
the 2026-08-18 fix (which was about empty stubs *shadowing* this fallback; this bug is *in* the
fallback itself).

**Checked all 5 Assault zones' `Zone.lua` directly, not just Periqia**, since this class of
mistake could plausibly have been copy-pasted elsewhere:
- `Leujaoam_Sanctum`, `Mamool_Ja_Training_Grounds`, `Lebros_Cavern` all already use the correct,
  simple pattern -- `player:setPos(0, 0, 0, 0, <zoneid>)` directly, no `instance` reference at all.
- `Ilrusi_Atoll` uses a differently-styled but valid version -- `local instance =
  player:getInstance()` defined properly before `instance:getChars()`, so it's not broken.
- **Only Periqia had the undefined-variable bug.**

Also re-confirmed no Assault instance file (any of the 5 zones) has regressed the 2026-08-18
empty-`onEventFinish`-stub issue.

**Fix**: `Periqia/Zone.lua`'s `onEventFinish` rewritten to match the proven single-`player`
pattern used by 3 of the other 4 zones:

```lua
zone_object.onEventFinish = function(player, csid, option)
    if csid == 102 then
        player:setPos(0, 0, 0, 0, 79)
    end
end
```

This is zone-wide -- affects all 10 Periqia Assault missions' timeout/failure handling, not just
Saving Private Ryaaf. Lua-only, script reload only, no DB reimport needed. Not yet confirmed fixed
live.

## Saving Private Ryaaf: third live test -- double-trigger progress bug, name still visible, a real unrelated mob-job bug (2026-08-20)

User retested with screenshots and a terminal error log. Three more real bugs, plus one flagged
rather than guessed at:

1. **Mission completed after finding only 1 real survivor (not necessarily Ryaaf -- any of the
   3), confirmed by the user to be from re-interacting with the same NPC more than once.** Real
   root cause: `Hunched_Figure.lua`'s survivor branch had no "already triggered" guard --
   `setStatus(DISAPPEAR)`/`setProgress(+1)` were correctly delayed until after the 8-10s staggered
   dialogue (to avoid cutting it off, per the previous round's fix), but that same delay left the
   NPC triggerable again during that whole window. An impatient re-click before the delayed block
   fired queued a second full set of timers, each with its own `setProgress(+1)` -- multiple
   increments from a single real survivor, completing the mission well before all 3 were actually
   found. The Fomor branch was never affected (it already sets `DISAPPEAR` immediately, before the
   mob even spawns). Fixed with the same localvar guard pattern already used elsewhere in this
   codebase (`Ancient_Lockbox.lua`'s `"opened"`, `Cursed_Chest.lua`'s `"triggered"`).
2. **The name/identity was still visible even after last round's rename to a shared
   `'Hunched_Figure'`.** The static `namevis` default (72, already includes `FLAG_HIDE_NAME`)
   apparently isn't sufficient on its own -- possibly reset at spawn, possibly never actually
   applied the way the raw SQL column implies. Fixed by calling the real runtime `hideName(true)`
   (`CLuaBaseEntity::hideName` -> `CBaseEntity::HideName()`,
   `src/map/lua/lua_baseentity.cpp:4074`) explicitly on all 5 room occupants right after
   positioning them in `onInstanceCreated`, rather than relying on a static default.
3. **Terminal log**: `mobutils::CalculateStats Mob (17006656) has no mp for casting spells!` /
   `CMagicState::ValidCast Mob (17006656) tried to cast magic with no mp!`. `17006656` is the
   South-room `Experimental_Undead_blm` (poolid 5469) -- a real, pre-existing `mob_pools` data bug,
   not something this session introduced, just the first content to ever actually spawn/engage
   this specific row. Its `mJob`/`sJob` were set to `2` (`JOB_MNK`,
   `src/map/entities/battleentity.h`'s `JOBTYPE` enum) despite the row's own name saying "_blm" --
   MNK has essentially no real MP pool, yet the row's `spellList` (1) still assigns it spells to
   cast. Its siblings (`Experimental_Undead_thf`=6/THF, `_brd`=10/BRD) already had the correct,
   matching job set. Fixed: `mJob`/`sJob` 2,2 -> 4,4 (`JOB_BLM`).

**Not resolved, flagged rather than guessed at**: the user also reported "text is still incorrect
across all npcs," with 2 screenshots showing lines like "The door is locked. You might be able to
open it with (temporary item)." and "You lift the switch on the bridge mechanism." -- but those
are Building Bridges' (Periqia mission 35) own `BridgeSwitch` mechanic text, not anything in Saving
Private Ryaaf's own scripts or capture data, and neither screenshot shows an actual
Ryaaf/Balarahb/Rhagmakah spoken line at all (correct or otherwise). Given the same test session's
terminal log showed repeated `!warpassault` zone changes across several different missions, this
looks like leftover chat scrollback from testing a different mission in the same sitting, not a
real bug in this mission's own dialogue. Asked the user to confirm before investigating further --
don't want to "fix" unrelated Building Bridges text under this mission's banner.

`sql/mob_pools.sql` (`Experimental_Undead_blm` job fix), `npcs/Hunched_Figure.lua` (trigger guard),
`instances/saving_private_ryaaf.lua` (`hideName()` calls). Needs a DB reimport (mob_pools change)
and a script reload. Not yet retested live.

## Saving Private Ryaaf: survivor dialogue was drifted +15, confirmed and fixed against dat-extractor (2026-08-20)

User asked to specifically re-check the survivor dialogue against `dat-extractor`'s real client
dialog table dump rather than trusting the capture's raw `MesNum` values again -- correctly
guessing this dialogue block (added a few rounds back, sourced straight from
`CapLog`/`PacketLogger` on "Periqia SP - Saving Private Ryaaf.zip") might be the same class of
cross-client-version DAT renumbering drift already flagged (but left unapplied, for lack of
dat-extractor confirmation) on Lebros Cavern's system-message block earlier this session. Newer
client builds renumber some dialog tables relative to older ones, so a script written against one
client's raw capture can be silently wrong against another -- exactly the kind of drift that needs
an independent check every time, not just once per zone.

Pulled `D:\Claude\dat-extractor-cache\periqia_6476.json` (real dialog table dump for this exact
zone) and checked every one of the 13 survivor dialogue lines already in `IDs.lua` against it,
content-by-content, not just index-by-index:

- **Confirmed drifted, exactly +15, all 13 lines**: e.g. `RYAAF_LINE1` was `7557` ("Y-you're not a
  zombie...?") -- dat-extractor shows that exact text sitting at **7542**. Same 15-unit gap held
  for every single line across all 3 survivors (`RYAAF_LINE1-5`: 7557-7561 -> 7542-7546;
  `BALARAHB_LINE1-4`: 7562-7565 -> 7547-7550; `RHAGMAKAH_LINE1-4`: 7566-7569 -> 7551-7554).
- **Confirmed this is NOT a zone-wide shift**: this zone's own shared system-message block
  (`TIME_TO_COMPLETE`=7507 through `PARTY_FALLEN`=7515, already in `IDs.lua` from earlier work)
  matches dat-extractor **exactly**, zero drift -- so the correction only applies to this specific
  dialogue block, not everything in Periqia's `IDs.lua`.

Fixed: all 13 constants corrected to their real, dat-extractor-confirmed values. This also
incidentally re-confirms the earlier third-round diagnosis that the "door is locked"/"bridge
mechanism"/"sparkling object" text the user saw is real, unrelated content sitting in the *same*
shared per-zone dialog table (indices 7559-7569, right next to this mission's own corrected
range) -- not a drift bug in this mission's own dialogue, just neighboring strings for other
Periqia missions (Building Bridges, Defuse the Threat) that happen to sit nearby in the table.

`scripts/zones/Periqia/IDs.lua`. Lua-only, script reload only, no DB reimport needed. Not yet
retested live.

## Orichalcum Survey: Rune of Release grid text wrong letter (2026-08-20)

User-reported: showed "C-8" instead of the real "H-8". `instances/orichalcum_survey.lua`'s
`messageSpecial(ID.text.RUNE_UNLOCKED_POS, 2, 8)` used letter param `2` -- under this session's
confirmed 0-indexed encoding (A=0), that renders as C, not H (which is `7`). Fixed: `(2, 8)` ->
`(7, 8)`. Lua-only, script reload only, no DB reimport needed. Not yet retested live.


## Orichalcum Survey: `_1XO` corridor fixed, mining logic rebuilt, mission now fully passes (2026-08-21)

User confirmed live: mission fully passes. Two separate real fixes landed together this round.

**`_1XO` corridor obstruction, root cause found.** Same failure mode already diagnosed for Miners
5-8 earlier this session: `_1XO` (the rock prop blocking the corridor) had a real `npc_list` row
but was never registered in `sql/instance_entities.sql` for instance 2, so `GetNPCByID()` could
never see it inside a live instance no matter how correct its other data was. The
`zone:checkNavPath()` diagnostic added last round (`pathFound=true, waypoints=2`) had already
proven the compiled navmesh itself was never the blocker -- this confirms it: once the prop is
actually registered and its status/animation set, the corridor opens. Renamed `_1XO` ->
`ROCK_PROP_1XO` for clarity while in there. `npc_list` row 17060142 (`_1XN`, Leujaoam Cleansing's
own door) also renamed `-> ROCK_PROP_1XN` and registered into instance 1's `instance_entities` the
same way -- was previously unregistered there too.

**Mining_Point.lua / Mulwahah.lua rebuilt.** Real distance check before allowing a mining attempt,
messaging for every roll outcome (tool break, silent miss, "move closer," node depleted, no
pickaxe), and Mulwahah gained a 3rd ore-turn-in line plus new post-completion "go away" dialogue
that previously didn't exist (re-triggering Mulwahah after the instance was already complete
played nothing at all).

**Mining animation switched from a raw emote packet to real cutscene events**
(`player:startEvent(1041)`, resolved in `onEventFinish`) instead of the `sendEmote()`-based
approach from earlier rounds (which had a real, fixed C++ bug of its own -- see the prior "Mining
animation" entries below -- but never got the animation to visibly play regardless). **The new
CSIDs (1041-1048) are not currently mapped to real packets on stock Topaz** -- the client will sit
in a frozen animation state until manually cancelled if tested on an unmodified Topaz build.
**Confirmed working on Valhalla specifically** -- this fork's actual target.

Two minor cleanup items noticed while reviewing, both non-blocking:
- `IDs.lua` now defines `MINING_TOOL_BROKE` twice (7527, then 7531) -- Lua silently keeps only the
  last table assignment, so 7531 is what's actually live and 7527 is dead. Not wrong, just leaves
  unreachable code sitting in the file.
- `ITEM_OBTAINED` was repointed from the zone's old generic "Obtained: <item>." (6388) to the
  temp-item template (7526) -- confirmed via grep it isn't referenced anywhere else in this zone,
  so no collision with another mission's usage, but worth knowing since that constant name is
  normally shared/generic across zones.

`scripts/zones/Leujaoam_Sanctum/{IDs.lua,npcs/Mining_Point.lua,npcs/Mulwahah.lua,
instances/leujaoam_cleansing.lua,instances/orichalcum_survey.lua}`, `sql/npc_list.sql`,
`sql/instance_entities.sql`. Needs a DB reimport for the `npc_list`/`instance_entities` changes.


## Zone-wide cross-reference: NPCLogger captures vs SQL vs Lua (2026-08-21, ongoing)

User reorganized `D:\Claudessault_captures` (uncompressed, one folder per mission) and provided
a new `combined_entities.csv` (`D:\Claude\dat-extractor-cache\`, real entity names from the
client DAT files -- the authoritative naming source, per user direction) and asked for a full
cross-reference: every real capture's `NPCLogger` data against `npc_list`/`mob_spawn_points`
(does a real SQL row exist), `instance_entities` (is it registered to the right instance), and
each zone's `IDs.lua` (is it referenced in Lua) -- flagging anomalies and adding anything missing.

Built a pipeline: parsed all 5 zones' `IDs.lua`/`npc_list.sql`/`mob_spawn_points.sql`/
`instance_entities.sql`, mined every `NPCLogger` SQLite DB across all 63 mission capture folders
(1333 total entity observations, matched to their real `instanceid` by folder name), and
cross-referenced against `combined_entities.csv`. Full raw dataset and findings persisted to
`D:\Claude\DSP-Topaz Information
pclogger_crossref\` (both CSVs tagged with instance id,
mission, zone, and the exact source DB per row, per user request) rather than left as scratch --
re-derivable any time, doesn't require re-reading the captures.

**Result: 539 real gaps found** across the 5 zones -- entities with real capture data that are
missing a `npc_list`/`mob_spawn_points` row entirely, missing their `instance_entities`
registration, and/or never referenced in `IDs.lua`. Categorized:
- 134 have real SQL data but are missing only their `instance_entities` registration (the exact
  bug class already found and fixed repeatedly this session -- Miners 5-8, `_1XO`, `_1XN`).
- 91 more of the same, also missing an `IDs.lua` reference.
- 307 have no SQL row at all yet (`MISSING_SQL_ROW`) -- higher risk, needs individual review
  before adding (NPCLogger captures everything visible, not just real assault content).
- 46 real name mismatches between the capture and the existing `npc_list`/`mob_spawn_points` row
  (some are real anomalies, some are just client-side name truncation in the capture tool, e.g.
  "MamoolJaExecu" vs the real "Mamool_Ja_Executioner" -- not all 46 are bugs).

**Caught and fixed a real bug in the cross-reference tooling itself before trusting its output**:
`instance_entities.sql` has 22 rows (all of Preemptive Strike's) formatted with a space after the
comma (`VALUES (12, 17047570)`) against 1305 rows with no space -- the first version of the parser
missed all 22, which would have produced 22 false "missing registration" findings for a mission
that was actually already fully registered. Fixed the parser (optional whitespace) before acting
on any findings, not after.

**First real fix applied from this pass -- Preemptive Strike's door props.** The 20 items the
buggy parser had flagged for this mission were mostly the false positives above, but 4-5 survived
the parser fix and turned out to be completely real: this mission's entire door/wall prop family
(`_1u9`-`_1uj`, 9 real props, real capture-confirmed positions/animations) had **zero**
`instance_entities` registrations and were never referenced in `preemptive_strike.lua` at all --
not a regression, never wired since the mission was first built. This directly explains the
user-reported "door in closed state" from earlier in the session, previously suspected to be part
of a shared/global regression alongside Sagelord Elimination and Leujaoam Cleansing. Fixed:
registered all 9 real props into `instance_entities` for instance 12, filled in real
capture-derived data for 2 that were still `NOT_CAPTURED` placeholders (`_1uc` `17047871`, `_1uh`
`17047876`), added both to `IDs.lua`, and added a reveal loop to `onInstanceCreated`
(`setStatus(NORMAL)`, no animation override -- which value means open vs. closed for this specific
prop family isn't independently confirmed yet). 2 siblings (`_1ud`/`_1ue`) remain `NOT_CAPTURED` --
no real data in any available capture. **Not yet live-tested.**

One entity (`17047836`) was deliberately **not** added despite having real capture coordinates --
it appears identically (same position, blank name, no dat-extractor match) in both Preemptive
Strike's and Blitzkrieg's captures, which reads as a generic always-present zone fixture rather
than mission-specific content. Flagged rather than guessed at.

`sql/npc_list.sql`, `sql/instance_entities.sql`, `scripts/zones/Mamool_Ja_Training_Grounds/{IDs.lua,
instances/preemptive_strike.lua}`. Needs a DB reimport. **This cross-reference pass is ongoing** --
534 more findings remain across the other 4 zones, to be worked through the same way (verify
against real capture data before adding, flag rather than guess on anything ambiguous).


## Cross-reference pass, batch 2: 215 real registrations + 78 real prop rows filled across 20+ missions (2026-08-21)

Continuing the cross-reference pass (see the entry above). Two mechanical, low-risk batches applied:

1. **215 entities with real `npc_list`/`mob_spawn_points` data already, just missing
   `instance_entities` registration** -- the same bug class proven repeatedly this session, now
   applied in bulk across every mission that had it, not just the ones a user report happened to
   surface. Initial filter mistakenly excluded ~147 of these for having a blank raw `Name` field in
   the capture -- that's normal for decorative props (NPCLogger doesn't log a display name for
   them), not a sign of missing identity. Corrected to check `combined_entities.csv`'s real name
   too (the authoritative source per user direction) before excluding anything; only 5 entities
   remained genuinely unidentifiable from any source and were skipped (2 pairs identical across
   sibling missions, e.g. the same blank-named fixture at the same coordinates in both Preemptive
   Strike and Blitzkrieg -- reads as a generic always-present zone object, not assault content).
2. **78 door/wall props with real capture position/animation data but no SQL row at all yet.**
   Confirmed these are reserved slots, not new content -- `npc_list.sql` has 3028
   `NOT_CAPTURED` placeholder rows (a known-but-unconfirmed id from the original data scaffold),
   while `mob_spawn_points.sql` has zero such placeholders -- so for NPCs/props, "missing SQL row"
   almost always means "an already-reserved slot, now getting filled in," not something created
   from nothing. Filled in real position/animation/flags data for all 78 (uncommenting the
   `NOT_CAPTURED` line), then registered each into `instance_entities` for its real instance.
   Added the newly-real ones to their zone's `IDs.lua` too, matching each zone's existing lowercase
   naming convention (caught and fixed a mistake here -- an early pass generated these as
   uppercase, e.g. `_1U4` instead of `_1u4`, which would have been a silently-dead duplicate key
   space since Lua table keys are case-sensitive and every sibling in the file is lowercase).

One duplicate `instance_entities` row was introduced and caught before commit (a stale
cross-reference snapshot re-flagged an id that was already correctly registered) -- removed.

Total this batch: 293 new `instance_entities` registrations, 78 new/filled `npc_list` rows, 48 new
`IDs.lua` entries across Mamool Ja Training Grounds/Lebros Cavern/Ilrusi Atoll. All persisted to
`sql/npc_list.sql`, `sql/instance_entities.sql`, and the 3 zones' `IDs.lua`. Needs a DB reimport.
**None of this batch has been live-tested** -- it's real, capture-confirmed data being wired in,
not guessed at, but "the entity now exists and loads" is a different claim from "the mission plays
correctly" -- especially for door/wall props, where (per user report) even a correctly-registered,
repositioned, animation-cycled prop has already failed to resolve at least one closed-door case
this session. Treat every prop fix in this pass as a candidate contributor, not a confirmed fix,
until retested.

**Remaining**: 222 entities (mostly real named mobs -- Lamia Necromancer, Draugar's Wyvern, Fairy
Apkallu, Red/Blue/Yellow Badge Mamool Ja, LebrosApkallu, Vegetation, MiningPoint/HarvestingPoint
variants for still-unbuilt missions like Supplies Recovery/Shanarha Grass Conservation/Counting
Sheep) have no `mob_spawn_points` row at all and no reserved-slot convention to fall back on --
each needs a real `mob_pools`/`mob_groups` lookup before adding, higher effort and higher risk of
getting wrong than the mechanical batches above. Continuing.


## Cross-reference pass: closing this pass out, handoff documented (2026-08-21)

Closing out this session's cross-reference pass (see the two entries above for the SQL/Lua
changes applied). Final state:

**Applied and committed**: 293 `instance_entities` registrations + 78 real `npc_list` rows filled
from reserved `NOT_CAPTURED` slots + 48 new `IDs.lua` entries, across 20+ missions in 3 zones.
Includes a likely real root-cause fix for both Preemptive Strike's and Sagelord Elimination's
door-blocker reports (both had their entire door/wall prop family completely unregistered, never
referenced in their instance script at all) -- framed as candidate fixes, not confirmed, since the
user has already found a different door in this same mission family that resisted repositioning
and animation-cycling, meaning static geometry rather than wiring may be the real blocker in at
least one case.

**Deliberately not attempted this pass**: 222 entities with no SQL row at all and no
reserved-slot fallback to lean on. Assessed a representative sample (Lamia
Necromancer/Toxophilite/Chaukidar/Fatedealer, Draugar's Wyvern, Karakul, Mamool Ja's Lizard) --
most have a clean existing `mob_pools` match and real capture positions, genuinely ready to add,
but 2 of them (Necromancer/Toxophilite) have ambiguous zone-variant pool choices that risk a
subtle wrong-stats bug if guessed at, so held back along with the rest rather than applying an
inconsistent partial pass. The largest chunk of this remainder (Apkallu/Harvesting Point/Mining
Point/Vegetation/Qiqirn Mine, ~98 entities across Apkallu Breeding, Egg Conservation, Supplies
Recovery, Shanarha Grass Conservation, Counting Sheep, Defuse the Threat, Apkallu Seizure) has no
existing pool/npc_list match under its captured name at all -- user flagged this cluster for a 2nd
independent capture source before adding, for cross-confirmation rather than single-source trust.

**Real, well-organized handoff for whoever continues this**: full raw dataset (1333 capture
observations) and findings (327 rows, tagged instance/mission/zone/confidence) persisted to
`D:\Claude\DSP-Topaz Information
pclogger_crossref\`, including the pipeline scripts
themselves (promoted from session scratch) and a README covering how to re-run them. See
`TODO.md`'s "Cross-reference pass, remaining work" entry for the full breakdown by confidence
tier -- this is a ready-to-execute list with real data already extracted, not a "go find the data"
task for next time.


## Ilrusi Atoll: Rune of Release name visibility, zone-wide (2026-08-22)

Continuing the cross-reference work with two new angles requested directly by the user:
`namevis`/`legacy_namevis` diff (motivated by "I've seen some Rune of Release with names and some
without") and a `mob_groups` level-range sanity check (motivated by "I've seen level 1 mobs...
placeholder data").

**`namevis` cross-reference, real finding**: compared every `Rune_of_Release`/`Ancient_Lockbox`
row's current `namevis` against its real capture data across all 5 zones. `Ancient_Lockbox` is
consistent everywhere (`namevis=0`). `Rune_of_Release` is consistent at `namevis=112` in 8 of 9
zones -- **Ilrusi Atoll's copy alone had `namevis=0`**, and critically, Ilrusi Atoll's own capture
data agreed 112 was correct -- this wasn't SQL drifting from a capture, it was Ilrusi Atoll's row
being the one outlier among 9 otherwise-identical siblings. Directly explains a user-observed
inconsistency previously assumed to be random ("some with names, some without") -- it was
zone-consistent the whole time. Fixed: `sql/npc_list.sql` 17002655 `namevis` 0 -> 112. Affects all
9 Ilrusi Atoll missions. Needs a DB reimport, not yet retested live.

**Level-range check, two real placeholder-level bugs found** (same pattern the user described --
`mob_groups.minLevel`/`maxLevel` left at their table defaults, rendering as level 1 in-game):
- `Clavauert_B_Chanoix` (Escort Professor Chanoix, poolid 739) -- `minLevel=maxLevel=1`, real
  capture shows level 70.
- `D5S1-MERROW` (Deserter, poolid 887) -- `minLevel=maxLevel=0`, real capture shows level 77.

Also found 70 `mob_groups` rows where a real observed level fell outside the *configured range*
entirely (not just landed somewhere inside a range that's supposed to vary per spawn, which is
expected and not a bug on its own). Most are minor (a few levels past the edge, likely just needs
widening); a handful are larger and look like genuinely wrong data (`Augmented_Chigoe` in Stop the
Bloodshed configured at level 50, real captures show 72-74). 70 entries need individual review
before bulk-editing level ranges, unlike the namevis fix which was a single unambiguous zone-wide
outlier -- 6 reviewed and fixed by the user 2026-08-22, the rest still open:

- `Augmented_Chigoe` (Stop the Bloodshed, poolid 285, zone 56) -- 50-50 -> **73-75**, user-confirmed.
- `Kelp_Pugil` (Apkallu Seizure, poolid 2208, zone 55) -- 55-55 -> **67-70**, per real capture data.
- `Kelp_Kulshedra` (Lost and Found, poolid 2207, zone 55) -- 54-54 -> **67-69**, per real capture data.
- `Kudagitsune` (Imperial Code, poolid 2290, zone 69) -- 76-77 -> **80-81**, per real capture data.
- `Clavauert_B_Chanoix` (Escort Professor Chanoix, poolid 739, zone 69) -- 1-1 (placeholder) ->
  **70-70**, user-confirmed -- at level 1 this mission's escort/protect objective would be
  impossible (he'd die instantly), independently confirming 1 was never a real value.
- `D5S1-MERROW` (Deserter, poolid 887, zone 55) -- 0-0 (placeholder) -> **75-77**, user-confirmed
  (wider than the single capture's own 77-77 observation -- user's own broader knowledge of the
  real range, not just this one capture's snapshot).

All 6 applied to `sql/mob_groups.sql`. Needs a DB reimport, not yet retested live.

**Remaining 64 reviewed and closed, 2026-08-22 -- user-confirmed none look like real outliers.**
Consistent with what the check was designed to expect: most of these are a real observed level
landing a few points past a configured range's edge, which reads as the range needing minor
widening at most, not wrong data -- qualitatively different from the 6 fixed above, which were
either drastically off (Augmented_Chigoe configured 23+ levels below its real range) or literal
unset placeholders (0-0 / 1-1). No further action on this batch.

**Orphaned `mob_spawn_points` check, clean result**: checked whether any assault-zone mob's
`groupid` fails to resolve to a real `mob_groups` row for its zone (would mean `SpawnMob()` fails
silently, no error, mob never appears) -- both for every mob currently wired into a live instance
(1068 rows) and every `mob_spawn_points` row in the 5 assault zone id ranges regardless of whether
it's registered yet (834 rows). Zero orphans in either pass. Worth recording as a real negative
result, not just an absence of findings -- this specific failure mode isn't present anywhere in
the current assault content.

All raw data (level ranges, namevis diffs, orphan checks) and the scripts that produced them
persisted to `D:\Claude\DSP-Topaz Information
pclogger_crossref\`.

## SYSTEMIC: instance timeout ejects players to the wrong zone, all 5 Assault zones (2026-08-22)

User asked, after fixing Golden Salvage's specific "stuck after 30-minute timeout" report, whether
this needed checking across every instance zone -- it did. The 2026-08-18 systemic fix (empty
`onEventFinish` stubs shadowing the real fallback) and the 2026-08-20 Periqia fix (an undefined
`instance` variable crashing the fallback) both only verified their fix *ran without erroring* --
neither ever checked whether the destination zoneid the fallback teleported players to was
actually correct.

It wasn't, in all 5 zones:

| Zone | Own zoneid | Was sending players to | Real zone name |
|---|---|---|---|
| Ilrusi Atoll | 55 | 54 | Arrapago Reef |
| Leujaoam Sanctum | 69 | 79 | Caedarva Mire |
| Mamool Ja Training Grounds | 66 | 52 | Bhaflau Thickets |
| Lebros Cavern | 63 | 61 | Mount Zhayolm |
| Periqia | 56 | 79 | Caedarva Mire |

Every zone's `Zone.lua` `onEventFinish` (`csid == 102`, the timeout/failure ejection path) called
`player:setPos(0, 0, 0, 0, <wrong zoneid>)` -- a plausible copy-paste-from-template origin (`79`
recurring in 2 zones, matching the also-`79` `onInstanceLoadFailed` fallback sitting right next to
it in the same file; `54`/`52`/`61` each look like simple off-by-a-few typos of the real zoneid).
Since `setPos()` never throws for a valid-but-wrong zoneid, this class of bug is invisible to any
check that only verifies "did the code run" -- it silently sent players to a random unrelated
overworld zone (via `0,0,0` coordinates in that zone, likely landing them somewhere broken/
inaccessible) instead of back to their own zone, which likely explains the original
"stuck/black-screen" symptom being observed as a hang rather than a visible mis-teleport.

Fixed all 5: each zone's `csid == 102` branch now targets its own real zoneid. Lua-only, reload
only, no reimport needed. Not yet confirmed fixed live for any zone except Golden Salvage
(Ilrusi Atoll), which prompted this pass.

## Imperial Agent Rescue: 3 more real bugs, live retest after the door/Pot Hatch rebuild (2026-08-22)

1. **Dilapidated Gate shows its nameplate, should be hidden.** `mob_pools` poolid 1037's
   `namevis` was `0`. Traced `src/map/entities/baseentity.cpp`'s `IsNameHidden()`
   (`namevis & FLAG_HIDE_NAME`, `0x008`) -- that bit was clear, so the name rendered. Set
   `namevis = 8` (just the hide-name bit).
   **Correction 2026-08-22 (later, post-live-retest)**: the first attempt at this edit miscounted
   `mob_pools`' 25 columns and set `spellList` (col 22) to 8 instead of `namevis` (col 23) --
   `namevis` stayed at its original `0` (fix never actually took effect) and the gate, a static
   prop with no real MP pool, was left with a bogus non-zero `spellList`, producing new
   `mobutils::CalculateStats ... has no mp for casting spells!` warnings for all 3 Dilapidated Gate
   instances on the next zone load. Also separately caused an `ERROR 1136 ... Column count doesn't
   match value count` on the dbtool import right after the original edit (this same edit had
   trimmed the row to 24 values instead of 25) -- fixed that import-blocking issue first, then
   caught this second, non-import-blocking mistake on live retest. Corrected: `spellList` back to
   `0`, `namevis` actually set to `8`.

2. **Brujeel spawns facing the wrong direction** (east, regardless of where the player searching
   the hatch actually is) -- `_pot_hatch_common.lua` positioned him using the hatch prop's own
   static `pos.rot` instead of orienting him toward the player. Added `brujeel:lookAt(player:getPos())`
   right after positioning, same pattern already used elsewhere in this codebase
   (`Mining_Point.lua`, `Ifrits_Cauldron/qm4.lua`).

3. **Rune of Release activates before Brujeel finishes his ~25s rescue dialogue.**
   `_pot_hatch_common.lua` called `instance:complete()` immediately after the reveal, *before* any
   of the 6 scheduled dialogue-line timers even started (they're scheduled via `brujeel:timer()`
   right after, but `instance:complete()` ran synchronously first). Moved the `instance:complete()`
   call into the callback of the last (25.5s) timer, so it only fires once the full dialogue
   sequence has actually played out.

4. **Firespit/Stave Toss splash damage never actually hit any Dilapidated Gate** -- user reported
   10 real Firespit casts, zero "Dilapidated Gate takes damage" log lines. Root cause in both
   `scripts/globals/mobskills/firespit.lua` and `stave_toss.lua`'s instance-11-guarded splash
   logic (see the 2026-08-18 entries above for the original build): the proximity check measured
   distance from `target` (the player who got hit by the skill) to the gate, not from `mob` (the
   Warder actually casting it, which is the entity realistically stationed near its own gate pen).
   If the player is fighting at range or kiting away from the gate when hit, the check almost
   never passes even though the Warder itself is right next to the gate -- explains "zero damage
   ever," not "damage too rare/low." Fixed both files to check distance from `mob` instead.

None of these confirmed fixed live yet except the pending retest.

## Evade and Escape: rebuilt from FFXIclopedia, real switch mechanic added (2026-08-22)

The 2026-08-18/19 build modeled this mission as kill-all-3-Dahak, "confirmed" by a real Thris Nov
2025 capture showing 3 Dahak kills immediately followed by mission completion. FFXIclopedia
(https://ffxiclopedia.fandom.com/wiki/Evade_and_Escape) describes a different real mechanic
instead: 3 switches randomly placed among 7 possible small rooms, each stays active 5 minutes once
hit, all 3 active simultaneously spawns Rune of Release -- the Dahaks are explicitly "not worth
killing" and meant to be evaded/escaped from, not farmed for kills.

Flagged this as a real conflict for the user rather than resolving it unilaterally. User's answer:
"Both are true. kill or hit all switches" -- the existing kill-path and the wiki's switch-path are
independently valid, not mutually exclusive (most likely explanation for the original "confirmed"
capture: a player who fought a path to a switch and coincidentally timed their 3rd Dahak kill with
their 3rd switch hit).

Implementation:
- `scripts/zones/Lebros_Cavern/npcs/Switch.lua` (new): `onTrigger` guards on a per-npc
  `activated` localvar, increments `instance:setProgress(instance:getProgress() + 1)` -- the exact
  same shared counter `mobs/Dahak.lua`'s kill path already writes to, so `evade_and_escape.lua`'s
  existing `onInstanceProgressUpdate` (`if progress >= 3 then instance:complete() end`) needed zero
  changes to support both paths.
- `sql/npc_list.sql`: filled the 3 previously-`NOT_CAPTURED` Switch placeholder rows
  (17035481-483). First pass placed all 3 at the instance entry point (no real position data
  existed); user then provided a real hand-drawn position-map image of the Lebros Cavern layout
  ("switches are not in same location see map") showing ~7 candidate rooms spread across the map.
  Repositioned to interpolate across that spread instead of clustering at the entrance -- still
  flagged as approximate/unconfirmed, not a capture-verified exact position.
- `sql/instance_entities.sql`: registered all 3 Switch npcs to instance 24.
- `scripts/zones/Lebros_Cavern/IDs.lua`: added `SWITCH1/2/3` constants for consistency with this
  codebase's documentation convention (not required for trigger resolution, which is name-based).
- Deliberately simplified the wiki's exact "5-minute expiry, must be simultaneously active"
  mechanic down to a flat cumulative counter, matching the model this codebase already uses for
  Dahak kills -- documented as a known simplification in `Switch.lua`'s header rather than
  attempting an unrequested per-switch-timer state machine.

Not yet live-tested. Switch positions in particular should be treated as a placeholder pending a
real capture, per the file's own header comments.

## Shooting Down the Baron: 2 live-test bugs + 1 gap found from Solo Assault Guide cross-reference (2026-08-22)

User reported the Black Baron rendered as a green nameplate and could not be attacked, mobs
otherwise in place.

**Bug 1: untargetable.** `sql/mob_groups.sql` row 13 (Black Baron's group) had a malformed column
layout: `...,0,0,0,75,78)` -- comparing to every sibling row's
`(respawntime,spawntype,dropid,HP,MP,minLevel,maxLevel,allegiance)` shape, this reads
`minLevel=0, maxLevel=75, allegiance=78`, clearly meant to be
`minLevel=75, maxLevel=78, allegiance=0` (a normal boss level range with the trailing `allegiance`
byte dropped/shifted). This is pre-existing data, not introduced this session (confirmed via `git
log`/`git diff` -- this row was never part of any edit made this session before this investigation).
Traced the actual mechanism: `CBattleEntity::ValidTarget()` (`battleentity.cpp:1255`) requires
`allegiance <= ALLEGIANCE_TYPE::PLAYER` (<=1) for normal PvE enemy targeting -- `78` fails every
branch (Teams PVP: not >= WYVERNS(5); Nation PVP: not in SAN_DORIA(2)-WINDURST(4); PVE: not <=
PLAYER(1)) and falls through to `return false`, making the mob permanently untargetable as an
enemy regardless of any other flag. Fixed the row to `minLevel=75, maxLevel=78, allegiance=0`.

**Bug 2 (separate, unrelated to targetability): nameplate/Wide Scan.** Cross-referenced this
mission against FFXIclopedia's *Solo Assault Guide by Korvana* while resuming other mission-
building work, which explicitly states "He does not show up on Wide Scan" -- not previously built.
`CMobEntity` has no dedicated wide-scan flag (only `CNpcEntity` does, via its own `widescan`
column); `CBaseEntity::isWideScannable()` (`baseentity.cpp:129`) falls back to
`!IsNameHidden() && IsTargetable()`, so `mob_pools` poolid 431's `namevis` FLAG_HIDE_NAME bit is
the only lever this engine exposes to exclude a mob from Wide Scan. Set `namevis = 8`. Side
effect: also hides his nameplate -- not separately confirmed by the source, but there is no way to
have one without the other in this codebase, and it's a reasonable fit for a hide-and-seek-style
NM boss.

**Gap, not built:** the same guide describes "One of his possible TP moves will Warp him to a
different location on the map... an avatar, beast, or automaton will track his new location." No
capture data pins down which specific TP move triggers this or under what condition -- flagged in
the tracker, not attempted blind.

**Note on the mob_pools editing mistakes earlier this session** (Dilapidated Gate's `namevis`/
`spellList` mixup, see above): applied the same fix to Black Baron's row with the column count
double-checked this time -- `mob_pools` poolid 431 went from 25 values to 25 values (only
`namevis`, position 23, changed 0 -> 8), confirmed by re-reading the row before and after the edit.

## Imperial Agent Rescue: gate revert bug found and fixed, Pot Hatch lids traced but unresolved (2026-08-22)

User reported (with screenshot) that gates still don't stay broken -- observed that interacting
directly with the `_ju7`/`_iu7` door prop opens the gate (plays the animation, briefly passable),
then it reverts to impassable. Also reported Pot Hatch lids not animating, "used to work at one
point."

**Gate revert -- root cause found and fixed.** `sql/npc_list.sql`'s `_ju7` (17047902, paired with
GATE_3 -- confirmed by exact x/z position match against `Dilapidated_Gate.lua`'s documented
GATE_1/_ju3, GATE_2/_ju5, GATE_3/_ju7 pairing) had `entityFlags = 4099`. Its siblings `_ju3`
(17047898, paired with GATE_1) and `_ju5` (17047900, paired with GATE_2) both have `entityFlags =
6147` -- the difference is exactly 2048 (`FLAG_UNTARGETABLE`, `0x800`), missing on `_ju7` only.
That made `_ju7` directly clickable by players (its siblings correctly are not), firing the
engine's default door-toggle animation on click -- completely independent of
`Dilapidated_Gate.lua`'s real gate-break logic (`onMobDeath` -> `setStatus(DISAPPEAR)` on the
paired door prop). The player-triggered toggle has nothing backing it, so it reverts. Fixed
`_ju7`'s `entityFlags` to `6147`, matching its siblings.

**Pot Hatch lids -- traced, not resolved.** Checked the script logic
(`npcs/_pot_hatch_common.lua`): unchanged, calls `npc:setAnimation(90)` on search, same animation
id used by the confirmed-working `Leujaoam_Sanctum/Ancient_Lockbox.lua`.
`CLuaBaseEntity::setAnimation()` (`lua_baseentity.cpp:4252`) only sends an update packet when the
value changes, which it does here (static `9` -> `90`). Checked full git history for the 3 Pot
Hatch npc_list rows (`_jul`/`_jum`/`_jun`, 17047916-918) -- `entityFlags = 4099` has never changed,
not a regression from anything edited this session. Their `look` field is a completely different
model byte pattern than `Ancient_Lockbox`'s, so the "same convention" in `_pot_hatch_common.lua`'s
header only ever meant the shared animation id (90), not the same visual model -- can't rule out
the model itself lacking a reachable open-animation state, the same category of dead end hit with
Golden Salvage's Mimic lid. Since this test session also had the gate bug and a stale-DB issue
active at the same time, recommended the user retest fresh (post `_ju7` fix, post DB reimport)
before concluding this needs the same AltanaView/capture-based investigation the Mimic lid got.

## Leujaoam Cleansing + Orichalcum Survey: the real `_1X*` corridor bug, both confirmed live (2026-08-22)

User asked to check Leujaoam Cleansing for the same class of bug found on Imperial Agent Rescue's
`_ju7` (a missing/mislinked helper prop blocking a corridor). Initial investigation found only 6 of
~50 real `_1x*`/`_jx*` door/terrain props in this zone were registered to Cleansing's instance, and
`leujaoam_cleansing.lua` had unexplained leftover debug scaffolding (`[Cleansing NAV DEBUG]` print
statements, a forced `setPos()`/`setAnimation(7)` override) targeting one specific prop,
`ROCK_PROP_1XN` (17060142) -- assumed to be a bug and initially "fixed" by just removing the
override.

**User corrected this**: the override wasn't an accidental bug, it was the user's own deliberate
test -- substituting `ROCK_PROP_1XO` (confirmed working elsewhere) at `_1XN`'s position to test
whether a known-good prop would open that corridor. It did not, which ruled out "missing/mislinked
helper" as the cause and initially pointed toward the same "baked collision, entity-independent"
dead end as Excavation Duty's Brittle Rock 4/5.

**Real root cause, found by running the NPCLogger cross-reference pipeline fresh** (per the user's
suggestion -- "we found the missing helper items in our packet captures... just adding them to the
ids lua and instance list made them function," referring to how Imperial Agent Rescue's real fixes
were found) against 2 independent real Leujaoam Cleansing captures:

1. **`_1XN` was never real for Cleansing at all.** It doesn't appear in either capture. It's a real
   entity, just for different missions: **Shanarha Grass Conservation** (instance 4) and
   **Supplies Recovery** (instance 6), captured at `~198,-11,139` in both.
2. **Why it looked like a Cleansing match**: `_1XN`'s `npc_list` row had been sitting at
   `357.198,-7.931,59.770` -- **`_1XO`'s real position, not its own** (a stale copy/mixup, likely
   from an earlier pass investigating `_1XO`). That's exactly why substituting entities at that
   spot seemed plausible -- the *listed* coordinates matched a real corridor, just under the wrong
   npcid.
3. **The actual bug**: Cleansing's real door-prop set is `_1XO` (17060143), `_1XW` (17060151),
   `_1XX` (17060152) -- all 3 had wrong `npc_list` positions:
   | Prop | Real (capture) | Was in `npc_list` |
   |---|---|---|
   | `_1XO` | 357, -7, 59 | -460.054, -32.172, 120.370 (= `_1XP`'s real spot) |
   | `_1XW` | 240, -12, 139 | 281.197, -40.077, 220.323 |
   | `_1XX` | 280, -40, 220 | -360.001, -8.482, -379.952 |

   `_1XX`'s case is notable: an existing comment already documented this exact 877.8-yalm-drift fix
   as applied via an earlier coord-diff pass, but the value in the file was still wrong when
   re-checked -- almost certainly caught in the session-wide bulk coordinate-drift revert
   (`ok wait... undo all the changes made just now`) along with everything else in that batch,
   despite having been individually validated correct beforehand.

**Fixed**: all 3 positions corrected in `npc_list.sql` (also `_1XN`'s and `_1XW`'s `animation`
field where the capture showed a different value than what was stored). `_1XN`'s incorrect
`instance_entities` registration to instance 1 removed (instances 4/6 were already correct).
Removed all dead `_1XN` handling from `leujaoam_cleansing.lua`. **User confirmed live: the
Cleansing corridor is now open.**

**Follow-up catch (user's own question)**: `_1XO` is registered to *both* Cleansing (instance 1)
*and* Orichalcum Survey (instance 2) -- and `orichalcum_survey.lua` never called `setPos()` on it,
relying entirely on the same shared global `npc_list` position I'd just moved. That file's own
"`_1XO` corridor" investigation (2026-08-20, extensive dead-end diagnostics: animation-state
toggling produced no visible change, a `checkNavPath()` query, an unguarded-`GetNPCByID()` crash
fix) had actually been chasing this same misplaced-position bug the whole time -- it was really
`_1XP`'s corridor, not `_1XO`'s, and `_1XP` (real position `-460,-32,120`, already registered and
already correct/unchanged) was the true fix. **User confirmed live: Orichalcum Survey's corridor is
also passable** with `_1XO` no longer referenced there at all. All dead `_1XO` diagnostic code
(debug prints, navmesh query, animation-toggle calls) removed from `orichalcum_survey.lua`; both
missions' tracker entries corrected to reflect `_1XP` (not `_1XO`) as the real fix.

Net result: 2 real, previously-misdiagnosed corridor bugs closed with live confirmation on both,
zero remaining open door-prop issues for either mission as of this pass.

## UNRESOLVED: both Leujaoam Cleansing and Orichalcum Survey corridors regressed after live confirmation (2026-08-22)

Both corridors above were confirmed open live, together with the user. A later retest -- with no
further edits to `_1XO`/`_1XW`/`_1XX`/`_1XP` or their `instance_entities` registrations in between
-- found both blocked again. Full re-verification, all clean:

- Connected directly to the live MySQL database (not just source `.sql`) and confirmed `npc_list`
  position/animation/entityFlags for the whole `_1XN`/`_1XO`/`_1XP`/`_1XW`/`_1XX` cluster exactly
  match the fixed values, live.
- Confirmed `instance_entities` registrations live-match source for both instances.
- `status` confirmed `0` (NORMAL) for `_1XO` -- correctly visible.
- No other entity found within 15 yalms of `_1XO`'s exact position.
- User performed a full server bring-down/restart (not just reimport/reconnect) -- still blocked.
- Confirmed via normal NPC entry, not the GM `!warpassault`-style command -- ruled out an
  instance-creation-path quirk.
- **Tested and ruled out**: `_1XO` simultaneously registered to both instance 1 and instance 2.
  Removed from instance 1 only, reimported, retested -- Orichalcum Survey showed no change.
  Reverted back to dual-registration.
- User explicit this isn't a misattributed-alternate-route situation (unlike Preemptive Strike) --
  corridor was specifically re-tested after the `_1XO`/`_1XN` instance-move work and confirmed
  working at that point.

**Every lever checked is confirmed correct or ruled out.** Real cause not found. Both missions'
`Assault_Issue_Tracker.md` entries reverted to 🔴 pending a resolution -- do not mark either ✅
again without a fresh live confirmation. Worth investigating next: something zone-wide (a
different Leujaoam Sanctum edit, a migration, a cache/reload behavior) rather than continuing to
focus on this specific entity cluster's own data, which has now been exhaustively re-verified
correct multiple times across both the source files and the live database.

---

## Leujaoam Sanctum: door-prop position-mixup fixes, Golden Salvage Mimic fixes (2026-08-22)
`_1xo`/`_1xw`/`_1xx` (Leujaoam Cleansing) and `_1xn` (Shanarha Grass Conservation/Supplies
Recovery, mistakenly registered to Cleansing) had swapped/wrong `npc_list` positions vs real
capture data -- fixed. Removed dead `_1xn`/`_1xo` diagnostic code from `leujaoam_cleansing.lua`
and `orichalcum_survey.lua` now that `_1xp` alone was believed the real Orichalcum Survey blocker
(see the "UNRESOLVED" entry above this one for how that later turned out to be wrong). Added
`Test_Wall.lua`, an experimental user-requested diagnostic mob (not retail data) to test whether a
killable mob paired with `_1xo` could clear the still-blocked corridor.

Golden Salvage: Mimic modelid/look/engage/duplicate-slot fixes from an AltanaView/packet-capture
investigation (259->258, chest look 961->960, targid collision fix, duplicate `17002901` removed).

## Imperial Agent Rescue gate fixes; Breaking Morale built out (2026-08-22)
Imperial Agent Rescue: fixed the real reasons gate splash damage never connected --
`firespit.lua`/`stave_toss.lua`'s proximity check now measures from the casting Warder (mob)
instead of the hit player (target), and the zone-scope guard switched from
`instance:getID() == 11` (a runtime instance-slot number, not a fixed mission id) to
`mob:getZoneID() == 66`. Dilapidated Gate/Brujeel facing/dialogue-timing fixes included.

Breaking Morale: rebuilt from FFXIclopedia -- real 8-crate loot pool, Quhaaja's "give up"
completion path, a new Viscous_Liquid.lua costume/DoT mechanic, and Mamool Ja Trainer
catch/teleport/item-strip logic.

## Excavation Duty rocks 4/5 + Qiqirn Mine rebuild; Evade and Escape switches (2026-08-22)
Excavation Duty: re-added Brittle Rock 4/5 (killable again -- real capture confirms their data was
always correct; the wall-open dead-end for these 2 remained at this point, believed real
client-side collision). Fully rebuilt the Qiqirn Mine mechanic from real capture data. Evade and
Escape: switch mechanic work.

## Saving Private Ryaaf: dialogue-breaking rename regression + auto-ambush Fomors (2026-08-22)
Added a real `setName()` Lua binding and used it to restore survivor names, which had gone blank
mid-dialogue. Fixed a stale `PTarget` bug causing unprovoked ranged attacks, and an invalid NPC
cast inside `untargetable()`. Closed out Sagelord Elimination's door TODO item (confirmed no
longer blocked).

## GM tooling + engine fixes; fix log/tracker sync (2026-08-22)
New position/model-lookup GM commands added, plus a full `GM_Commands_Reference.md` and 3 bug
fixes discovered while building them. Fix log and issue tracker synced with the day's work, and a
door-prop diagnostic guide added for future investigations.

## Saving Private Ryaaf: Speaker Name blank token, Fomor decoy nameplate glitch, Rhagmakah rename race (2026-08-23)
Three related rendering bugs, same underlying class (rename/dialogue packet timing races):
survivor dialogue showed a literal blank `<Speaker Name>` token; the Fomor decoy's nameplate
glitched because the transform fired before its stand animation finished; Rhagmakah's own name
similarly rendered blank due to the same rename/dialogue packet race. All three fixed.

## Saving Private Ryaaf: roaming-Fomor difficulty mechanic added, then disabled after live-testing (2026-08-23)
Added a new mechanic: roaming Fomors converge on the Rune of Release once all survivors are found,
raising difficulty. Iterated through several real bugs found live: constant navmesh pathfinding
failures (fixed), targeting switched from nearest-active to random-active, `MOBMOD_ROAM_COOL`
shortened so wandering was actually noticeable. **Ultimately disabled** after live-testing surfaced
2 further real bugs judged not worth chasing for a difficulty-only addition -- mission dropped back
to its already-working baseline and marked complete without this mechanic. The Speaker Name gap
noted above was flagged as a non-blocker in the same pass.

## Shanarha Grass Conservation built from 2 real captures, then found broken live (2026-08-23)
Built out from 2 independent real captures. Live-tested the same day and found broken -- see
TODO.md's zone-69 corridor/navmesh investigation entry for the connection this discovery made:
Shanarha has zero mission-specific script/SQL of its own that could explain a corridor block,
which became strong evidence the real cause is Leujaoam Sanctum's shared zone-level navmesh data,
not any one mission's script. Also corrected a stale assumption that the old client-side Gateway
addon was still a factor -- user confirmed it has been fully removed client-side for a while.

## Evade and Escape rebuilt from a real capture; instance was completely empty (2026-08-23)
Found and fixed: the instance had no real content wired in at all. Rebuilt from a real capture.

## Shooting Down the Baron: Black Baron's real warp mechanic built, cross-confirmed 3 times (2026-08-23/24)
Built Black Baron's real warp mechanic from a real capture, then independently cross-confirmed it
against 2 more captures from separate sources (a Discord archive find, and a 3rd from user Siknawz)
before trusting the warp-point data. **2026-08-24 cleanup**: pruned `WARP_POINTS` of coordinates
that had been mistakenly borrowed from Seagull Grounded's own escort-path data (a cross-mission
data contamination bug), and improved the warp telegraph using the same `kesu`/`deru` FourCC
animation mechanism found elsewhere this session (real one-shot clips, not `setAnimation()`
pose-flips). Issue tracker closed this mission out as live-tested and confirmed -- initially left
at the wrong status emoji (green circle instead of checkmark) and missed the separate summary grid
table entirely in the first pass; both corrected in an immediate follow-up commit.

## Defuse the Threat + Apkallu Seizure: real mechanics built from capture data (2026-08-23)
Defuse the Threat: built the real mine-detector proximity mechanic. Apkallu Seizure: built the real
capture-net mechanic from a 2nd WIN capture, cross-confirming the first.

## Wake the Puppet: full automaton system built, then tuned through live-testing (2026-08-23)
User provided the complete real walkthrough directly. Built `scripts/globals/wake_the_puppet.lua`
hooking `tpz.player.onPlayerEmote` (same pattern discovered earlier for Full Speed Ahead/Apkallu
Seizure): `/salute` (activate, register master), `/clap` (single-hop move, no auto-follow),
`/hurray` (toggle assisting master's combat target), `/goodbye` (deactivate, counts toward the real
"retrieve at least 4 of 6" threshold), and a periodic gesture-response loop. All 12
gesture->response pairs independently cross-confirmed word-for-word against Adeeha's own in-game
help dialogue via dat-extractor (official client text, not inferred from gameplay logs). All 6
Maymun given real `npc_list` rows from 3 independent captures; all 31 Wight `mob_spawn_points` rows
(previously all `(0,0,0,0)` placeholders) filled from combined capture data (28/31 real, 3
interpolated), hidden at spawn and revealed 4-nearest-to-activated-Maymun on `/salute`.

**3 live-test bugs found and fixed**: Maymun's crouched spawn animation never returned to standing
on activation (added `setAnimation(0)`); Adeeha never appeared because her real `npc_list` row has
a non-zero static `status` that needed an explicit `setStatus(NORMAL)` call, never made (same bug
class as Yazuhma in Lebros Supplies); Wights were pre-spawned and merely hidden rather than not
existing server-side at all until activation as intended -- removed the pre-spawn loop, now
spawned live via `SpawnMob()` only for the nearest 4 by real position, checked via
`GetMobByID()`/`isSpawned()` rather than module-level state (this module is shared across
concurrent instances, so per-module state would leak between separate parties).

**Wight-per-activation count tuned twice from further evidence**: a design-only guaranteed guard
Wight near Adeeha was added first (not capture-confirmed, a judgment call from the plotted layout).
Then the wiki's "roughly four" per activation was corrected to 6 after the user directly counted
Wights on real retail footage. Bumped once more to 7 after simulating the full pool against every
possible 4-of-6 activation combination -- 6+1 guard left the pool occasionally short; 7+1 uses all
31 Wights exactly, every time, in a minimal 4-activation playthrough.

Missing 10' range check added to `/hurray` (every other command already had it).

## Seagull Grounded: real Excaliace checkpoints + 3 route-blocking props (2026-08-23/24)
Correlated each "Someone's been eating too much garlic..." CapLog line against Excaliace's own
per-tick position history (not just a final snapshot) to find 9 real, exact checkpoint coordinates
directly, rather than approximating. A 2nd independent capture (Siknawz) found 6 more real garlic
timestamps but only had a single final-position snapshot, yielding no additional coordinates.
Recorded the user's full precise walkthrough of the still-unbuilt room-investigation/fleeing
mechanics for later. New `!logpos` GM command built specifically for this kind of live
coordinate-gathering task (reports like `!pos` but also prints an easy-to-copy CSV line to the
map-server log). Used it to find and fix 3 real route-blocking door/prop entities (a "rock" that
was really `Door_1k6`, plus 2 non-interactable doors) -- same missing-`instance_entities`-
registration bug class as several other missions this session. **2026-08-24 checkpoint**:
escort branch/escape state machine fixes (escape fatigue, a softlock fix), B1/B2 branch positions
shifted south, crab/pugil aggro flags enabled.

## Batch: 5-zone door/mob-position pipeline fixes, multi-session work committed (2026-08-25)
A large accumulation of work spanning multiple prior sessions that had never been committed:
door/prop identifier-drift fixes (Mamool Ja, Leujaoam Sanctum, Lebros Cavern, Ilrusi Atoll) using
FFXI-DATS cross-reference and real PathLog captures as ground truth; missing mob spawn positions
filled in across Operation Black Pearl, Azure Ailments, Blitzkrieg, Double Agent, Apkallu Breeding,
Egg Conservation, Better Than One, Defuse the Threat, Operation Snake Eyes, Apkallu Seizure, Lost
and Found, Demolition Duty, and Mamool Ja's Lizard; new named-quest-NPC/mob scripts added matching
real capture/cross-reference data; dialog ID off-by-one fixes across Lebros Cavern, Periqia, and
Ilrusi Atoll (same class of bug found again in Leujaoam Sanctum and Periqia's `ITEM_OBTAINED`
2026-08-27, see below -- this class of bug has now recurred often enough to be worth a dedicated
audit pass, per TODO.md).

## Excavation Duty closed out live; Evade and Escape/Lebros Supplies cleanup (2026-08-25)
Excavation Duty's 5-rock win condition passed a live retest after the door/prop identifier-drift
fix above -- closed out in the tracker. Evade and Escape: a real capture (Thris PathLog) used to
correct 8 mislabeled/mispositioned `_1r*`/`_ir*` door-prop rows, restoring `17035553`'s instance
registration alongside the already-corrected `17035552`. Lebros Supplies: `17035530`/`17035522`/
`17035523` were mislabeled `_1rq`/`_1ri` in `npc_list.sql`/`IDs.lua`, corrected to their real
`_1rp`/`_1rh`/`_1ri` identities per 2 independent captures -- did not resolve the still-open rock
wall blocker at the time (its position was already correct under the wrong name; that blocker was
separately resolved shortly after, see TODO.md's Done section). Removed 5 phantom duplicate
`npc_list` rows (2 npcids mapped to the same real client object, confirmed via FFXI-DATS
rotation/scale data) and consolidated Evade and Escape's registrations onto the surviving ids.

## Lamia No.13: real charm-mob tactic built end-to-end, new engine feature (2026-08-25)
Built the real "charm the Fallen, dispel them, they turn hostile on Lamia" tactic (Ilrusi Atoll
mission 42) -- previously impossible, since `battleutils::unCharm()` had zero `TYPE_MOB` handling
at all. Added real `applyCharm()`/`unCharm()` `TYPE_MOB` support (including a real C++ crash fix,
an unsafe charmer type cast found via live testing), gave the `charm()` Lua binding a real duration
parameter (previously silently defaulted to 0s, fatal for a charmed mob), and made the Fallen
companions start pre-charmed with native mob AI correctly excluding any charmed entity from
autonomous aggro. Belly Dance rebuilt: real hate-based retargeting, corrected
`mob_skill_distance` (7.0 -> 15.0), and an `onMobSkillCheck` semantics correction after an initial
misdiagnosis had broken it (reverted to the correct return value, confirmed via live diagnostic
logging). HP corrected to 10000. Also this pass: Wamoura Farm Raid's real Ranch Wamoura -> Ranch
Wamouracampa maturation mechanic; Egg Conservation's 16 real Lebros Apkallu (previously entirely
missing) and a corrected Qiqirn kill-15 wave mechanic; Lebros Supplies' Stormer shield-based
identification and the face-player-on-interact convention's first pilot.

## Imperial Agent Rescue: gate destruction, Warder skills, Brujeel/Pot Hatch -- mission complete (2026-08-26)
User-confirmed live end-to-end. Dilapidated Gates: fixed `FLAG_UNTARGETABLE` (confirmed real
intended design, not a bug), gate-splash damage math (was computing against the player instead of
the gate), a `Rest()`/`MOBMOD_NO_REST` regen exploit letting gates heal faster than chip damage, and
door passability after destruction (`setAnimation()` was never actually called). Restored real
per-job Mamool Ja Warder skills (Axe Throw/Stave Toss/Rushing Drub/etc.) that existed fully
stat'd in SQL but disabled/unwired, cross-referenced against LandSandBoat upstream, and split
BST/WHM/BLM onto their own skill lists after live-reported cross-job animation/weapon mismatches.
Fixed wrong `mob_anim_id` values for several skills, confirmed against LSB reference data. Brujeel:
fixed his name never showing in dialogue (a `messageText()` object-arg semantics bug), added his
real Warp/vanish sequence (his own `isAlive()` check was undefined behavior on a `TYPE_NPC` entity,
silently corrupting the callback), and built this session's first client-animation-diagnostic GM
tooling (`!fourccanim`) -- confirmed via live A/B testing that `deru`/`kesu`/`open` FourCC
transitions are real and working, while `castSpell()` is architecturally impossible on `TYPE_NPC`
entities. Pot Hatch and Ancient Lockbox both got the same real fix -- `setAnimation(90)` was never
a real one-shot clip; switched to the real captured `open` FourCC, ported to every zone sharing the
lockbox mechanic. Reverted a real `npc_list.sql` corruption from an earlier batch commit that had
shifted door-prop identities by one across the whole zone, affecting 4 missions. Two known-good,
non-blocking issues left open and logged: an animation-hang bug specific to
`ACTION_MOBABILITY_FINISH`-style weaponskill packets, and BST Warder pet-summon being
non-functional game-wide (a real missing engine feature, `PMob->PPet` is never assigned anywhere).

## Appraiser real dialogue fix; entity rename persistence, new engine feature (2026-08-26)
Appraisal (Drahbah/Chochoroon/Memeroon) now shows a real client "thinking" line
(`messageSpecialFrom`, verified against the actual client ROM dialog tables) followed 2s later by
the item result. Tried and ruled out along the way: wrong Topaz `IDs.lua` text ids, raw item-name
substitution via `CMessageSpecialPacket` (unimplemented client special codes), and an LSB-style CS
re-trigger (live-tested, disproven -- Topaz doesn't honor that param-branching convention). Ported
LandSandBoat's `isRenamed`/`packetName` persistence (`CMobEntity`, `renameEntity()` in
`lua_baseentity`, `entity_update.cpp`) so a mob's name is re-sent on every update packet instead of
just once -- fixes Ranch Wamoura's maturation and the Golden Salvage Mimic's reveal, both of which
were showing a generic "NPC" nameplate after a runtime rename.

## Face-the-player-on-interact convention rolled out across Assault (2026-08-26)
Piloted on Imperial Stormers the prior session; rolled out `npc:lookAt(player:getPos())` at the
start of `onTrigger` across all 29 Assault instance NPCs spanning Lebros Cavern, Mamool Ja Training
Grounds, Periqia, Ilrusi Atoll, and Leujaoam Sanctum. Overworld hubs (Whitegate/Al Zahbi/Nashmau)
deliberately left untouched.

## Aht Urhgan Whitegate: mercenary rank promotion system rework (2026-08-27)
Discovered and fixed a chain of real bugs in the LC-Captain (rank 4-11) promotion placeholder added
earlier: an off-by-one in the promotion-event lookup table left SP->LC promotion completely
unreachable through Naja Salaheem; the generic promotion check ran *before* every other
mission/quest dialogue check in `onTrigger`, hijacking real content (confirmed live against the
real Falzum/Nafiwaa Alchemists' Guild questline dialogue) whenever a player had 25+ points --
moved to fire only as a last resort; a duplicate-badge bug traced to `npcUtil.giveKeyItem()`
already firing its own `messageSpecial(KEYITEM_OBTAINED, ...)` inside `promoteRank()`, with a
second, redundant call in `onEventFinish` producing the visible double message; the SP-offer branch
could fire before the player had actually received the PFC badge, since it only checked
`AssaultPromotion >= 25` (which isn't reset until a badge is actually granted) with no check that
PFC was already owned. Real client event-disassembly (`mission_toolkit.py`) further revealed that
Naja's compiled script only genuinely owns events 5030/5031 -- the LC Wildcat Badge quest (SP->LC)
turned out to be a real, substantial multi-zone Mythralline Wellspring/test-tube questline spanning
Naja/Abquhbah/Nafiwaa, not a single-NPC interaction; researched but not implemented, blocked on
unverified key item IDs (raw dat-index collided with an already-assigned, unrelated Topaz key
item). Given the scope gap between the real quest and the placeholder, **all LC-Captain
badge-granting was commented out** (not deleted) ahead of a first handover stage covering only the
already-real, already-working PSC/PFC/SP quests. Also fixed: the Dark Rider Hoofprint temp key item
was never removed on SP promotion.

New GM commands `!addassaultpoints`/`!resetmercrank` added for testing the promotion chain without
running assault missions repeatedly.

## Orichalcum Survey: mining logic dead code, ore turn-in, 2 live crashes, text-ID bug (2026-08-27)
The mining roll (`resolveMining()` in `Mining_Point.lua`) was correctly implemented but almost
never actually ran: `player:startEvent(CSID_MINE_START)` has no real client packet mapping on this
build, so the client just showed a frozen animation with no way to naturally finish it --
`onEventFinish` only fired if a player manually canceled out, meaning the pickaxe-break/ore/hazard
roll rarely executed at all. Live-confirmed by the user reporting they'd never seen a pickaxe break
or a Zinc Ore. Fixed: the CSID-based flow commented out (not deleted, restorable on a build where
it's mapped), replaced with a `player:timer()` delay that calls `resolveMining()` directly.

Ore turn-in never actually removed the ore from inventory -- Qiqirn Miners (who aggro on ore
possession) kept attacking through the whole turn-in dialogue and mission cleanup. Fixed with
`player:delItem(ORE_ITEM, 1, tpz.inventoryLocation.TEMPITEMS)`, called immediately when Mulwahah
first sees the player holding the ore.

That fix, and the pre-existing pickaxe-removal-on-break logic, both called a `delTempItem()`
function that was never real (`lua_baseentity.cpp` only exposes `addTempItem()`) -- live crash,
`attempt to call method 'delTempItem' (a nil value)`. Both switched to the real
`delItem(itemID, 1, tpz.inventoryLocation.TEMPITEMS)` pattern.

`mobs/Mineral_Eater.lua` didn't exist at all -- live crash on kill, `undefined procedure
onMobDeath`. Created with standard stub handlers (it's a pure interruption/aggro hazard, not a
mission-progress kill target).

`ITEM_OBTAINED` in this zone's `IDs.lua` was set to 7526 -- the same index as `TEMP_ITEM_OBTAINED`,
a genuinely different message meant for real temp items (the pickaxe). Every permanent `???` item
from the Ancient Lockbox displayed as "obtains the temporary item: ..." as a result. Fixed to the
real value, 6388 ("Obtained: <item>."), confirmed against the real client dialog table. Same bug
class found and fixed in Periqia's `IDs.lua` (`ITEM_OBTAINED` was 6389, off by one).

Mulwahah's dialogue was missing her name prefix on several lines (`npc:messageText()` doesn't
attribute a speaker) -- switched to `player:messageSpecialFrom(npc, ...)`, matching the existing
pickaxe-grant dialogue's pattern.

Mining odds tuned per user feedback after confirming the roll logic was correct but too grindy: at
the original 2% ore chance, expected swings to find ore was ~75 (with a 33% pickaxe-break chance
consuming a pickaxe roughly every 3 swings). Pickaxe-break chance for this mission specifically
lowered to 20% (decoupled from the shared, global `MINING_BREAK_CHANCE` setting used by regular
overworld HELM mining, so this doesn't affect mining anywhere else) -- `ORE_CHANCE_PCT` itself left
at the original 2%.

## Lebros Cavern: Wamoura Farm Raid's shared-spawn Wamouracampa mechanic identified (2026-08-27)
2 mob ids (`17035373`/`17035374`) had sat unwired since 2026-08-25, found registered to the
instance but never referenced in `IDs.lua`'s spawn list, with no confirmation of what they were
for. User identified them from the FFXI Atlas map: they're the map's cyan "share a spawn (only one
will spawn)" markers, both at the mission's 2 northernmost branch points -- a deliberate mechanic
forcing the player to gamble which branch to check, not dead rows. Wired up in `IDs.lua` and
`wamoura_farm_raid.lua`'s `onInstanceCreated` (random pick of exactly one via `math.random`).
`17035373` (northeast branch) left commented out -- user confirmed it sits past this mission's
still-open pathway-misregistration blocker (see the Overall status note above); re-enable once that
blocker is resolved.

## Golden Salvage (Ilrusi Atoll, mission 41): Cursed Chest/Mimic architecture rebuilt end-to-end, 3 real engine bugs found and fixed (2026-09-01)

**Status: WORKING.** Full write-up with every dead end preserved at
`documentation/research/Golden_Salvage_Mimic_Architecture_Fix_Scope.md` -- this entry is the short
version. Chest reveal, correct model/animation, mob skills, draw-in, golden-chest completion, and
the chest's own "lid open" visual are all confirmed live.

**Starting bug**: a prior session's fabricated `mob_spawn_points` id range (`17002950-17002968`,
invented 2026-08-22, no basis in any capture -- confirmed via `git blame`, commit `23a3d09001`)
made each wrong chest spawn a *second*, separate mob entity instead of the real chest itself
changing state. User correctly identified from 2 independent real packet captures
(`Ilrusi Atoll PSC - Golden Salvage [L] - Mimic despawn mechanics` /
`... - Mimic with party member`) that the real retail mob shares the exact same 32-bit id as the
chest (`17002509`, `17002513` both directly re-verified byte-for-byte from raw `0x00E.log`
packets) -- confirmed by reading LandSandBoat's own real, shipped implementation too (their
`sql/mob_spawn_points.sql` registers these 18 ids as mobs directly, no `npc_list` row at all).

**Three separate, real Topaz engine bugs had to be found and fixed before that single-entity
design could actually work** -- each found by reading C++ source after a live-test failure, not
guessed:

1. **`src/map/packet_system.cpp`'s trigger-action packet handler** (`SmallPacket0x01A`,
   `case 0x00: // trigger`) hardcoded `PChar->GetEntity(TargID, TYPE_NPC)` -- a `TYPE_MOB` target
   always resolved to `nullptr`, so a mob could never receive a trigger/check action at all.
   Widened to `TYPE_NPC | TYPE_MOB` (same combined-filter idiom already used by this file's own
   WideScan handler).
2. **The `status` byte** (packet offset `0x20`) -- `CBaseEntity::Spawn()` auto-sets
   `status = STATUS_TYPE::MOB` whenever `allegiance == MOB` (the pool's default); this is what the
   *client's own menu logic* uses to decide whether to offer a check action at all (confirmed live:
   without this, the client only ever sent Attack/Disengage/Weaponskill, never Trigger). Fixed in
   Lua -- force `STATUS_TYPE::NORMAL` while disguised (`mob:setStatus(tpz.status.NORMAL)`), flip
   back to `MOB` (`setStatus(1)` -- `tpz.status` has no `MOB` entry) once revealed.
3. **`luautils::OnTrigger()` vs `luautils::OnEntityLoad()` folder mismatch** -- `OnEntityLoad()`
   (`luautils.cpp:567`, the function that actually loads a script into the Lua cache) is
   type-aware: `npcs/<name>.lua` for `TYPE_NPC`, `mobs/<name>.lua` for `TYPE_MOB`. `OnTrigger()`
   (`luautils.cpp:1603`) unconditionally built the `npcs/` path regardless of type -- so even
   after fix #1 let the packet reach `OnTrigger`, it was looking in a file that had never been
   loaded into the Lua cache at all (`GetCacheEntryFromFilename()` doesn't load anything itself,
   it just navigates/auto-creates an empty table). Fixed to mirror `OnEntityLoad`'s own branch.

**Also found and fixed, post-live-test:**
- `renameEntity()` only ever sets `packetName` (display-only), never the real `name` field
  `GetName()`/`getEntityCachedFunction()` actually resolve scripts by -- conflated with the
  separate Ranch Wamoura investigation's `setName()` finding (which *does* redirect resolution).
  Draw-in (`onMobFight`) had been split into a separate `mobs/Mimic.lua` on the wrong assumption
  that the rename would redirect future events there; it never did. Consolidated everything into
  one file, `mobs/Cursed_Chest.lua`, keyed by the entity's real, never-changing name.
- Self-despawn-during-own-`onTrigger` crash hazard: the golden-chest branch looped `DespawnMob()`
  over all 18 chest ids including its own -- `PAI->Despawn()` forcibly changing the currently-
  executing entity's own AI state while its own event handler was still on the call stack. Fixed
  by excluding `npcID` (self) from that loop. (Hypothesis, not stack-trace-confirmed, but safe
  either way and matches the reported symptom -- crash on zoning out after a golden-chest
  completion.)
- Golden-chest branch never set the `triggered` localvar (every other branch did) -- chest could
  be re-triggered/re-complete the mission endlessly. Fixed.
- `setAnimationSub()`/`setAnimation()` only ever persist a pose flag, not a one-shot animation
  clip -- confirmed already known and fixed the same way for this exact mission's Ancient Lockbox
  (`scripts/globals/assault_lockbox.lua`'s `chestTrigger`, real capture-confirmed): the actual
  "opens" visual (with baked-in VFX) needs `entityAnimationPacket("open")`
  (`CEntityAnimationPacket`, FourCC `"open"`), not `setAnimationSub()`. Applied the same real
  mechanism to the golden chest's reveal.
- `!mobsub`'s GM command (`scripts/commands/mobsub.lua`) had a real bug unrelated to this mission
  but found while debugging it: passed the mob-id argument straight to `GetMobByID()` as a raw
  string instead of `tonumber()`-converting it first (the animation-id argument right below it did
  convert) -- fixed.

**Final architecture**: one persistent `TYPE_MOB` entity per chest (`mob_pools` poolid `864`,
`mob_groups` groupid `39`/zone 55, ids `17002505-17002516`/`17002900`/`17002902-17002906` --
same ids used throughout, no second id, no `npc_list` row at all). Everything --
`onMobSpawn`/`onTrigger`/`onMobFight`/`onMobDeath`/`onMobDespawn` -- lives in one file,
`scripts/zones/Ilrusi_Atoll/mobs/Cursed_Chest.lua`. Real capture-confirmed values: closed chest
`modelid=960`/`animationsub=4`; revealed Mimic `modelid=258`/`animationsub=5`.

**Cleanup after confirming it worked**: removed the now-orphaned `mob_groups` groupid `2`
(poolid `2664`, only ever referenced by the fabricated id range, itself already removed) and a
stale comment pointing at the deleted `mobs/Mimic.lua`.

## Lamia No.13 (Ilrusi Atoll, mission 42): live-tested, confirmed passing (2026-09-01)

Three real fixes found via user-provided LOGPOS during live testing, cross-checked against
`npc_list.sql`/`mob_spawn_points.sql`/both real captures (`Ilrusi Atoll - Lamia No.13 (Thris
Nov2025)` and `Ilrusi Atoll PFC - Lamia No.13`, though neither capture's NPCLogger data actually
covered this part of the map -- nearest logged entity was 108+ yalms from either reported
position, so the fix relied on direct SQL/position cross-referencing instead):

- **Two door props, `_1jb` (`17002717`) and `_1ji` (`17002724`), existed in `npc_list.sql` but
  were never registered to this instance at all** (missing from both `instance_entities.sql` and
  the Lua wiring) -- same class of gap already found for `_1jd`/`_jj1`/`_jj2` in this same mission
  earlier. Registered both (`instance_entities.sql`, `IDs.lua` -- `_1ji` had no `ID.npc` entry at
  all) and wired them into `onInstanceCreated`. Initially set to animation `8` (open) matching the
  established default for a newly-wired door; live-tested and corrected to `9` (impassable) after
  the user confirmed both should block the path, not open it.
- Added a one-shot debug print to `onInstanceCreated` reporting which of the 4 `LAMIA_SPAWNS`
  sites got randomly picked each instance run, since "did she wander far from her real spawn"
  previously had to be inferred from distance after the fact. Left in permanently (fires once per
  instance, not spammy).
- Using that print, confirmed live that "alternate 1" (`LAMIA_SPAWNS[2]`) was off from her real
  position -- corrected from `(18.0263, -3.7332, -58.6985)` to a user-provided LOGPOS,
  `(23.9906, -6.0649, -68.0578)`.

All four `LAMIA_SPAWNS` sites, the charm mechanic, both lockbox/rune positions, and all 5 door
props for this mission are now confirmed live-working end to end.

## Extermination (Ilrusi Atoll, mission 43): full regression test passed (2026-09-01)

No new fixes -- full regression retest after this session's other Ilrusi Atoll work (Golden
Salvage's architecture rebuild, Lamia No.13's door/spawn fixes) confirmed nothing regressed.

## Demolition Duty (Ilrusi Atoll, mission 44): full regression test passed (2026-09-01)

No new fixes -- full regression retest confirmed nothing regressed, no outstanding issues.

## Rank-10 sweep: Bloody Rondo / Susanoo Shuffle / Better Than One / Price is Right / Bellerophon's Bliss (2026-09-01)

Ran `mission_toolkit.py` across all 5 remaining zones (Leujaoam Sanctum, Mamool Ja Training
Grounds, Lebros Cavern joining the already-pulled Periqia/Ilrusi Atoll) and dispatched a parallel
investigation per each zone's rank-10 (First Lieutenant) mission -- these had entrance/kill-target
already fixed from earlier this session but nothing else audited. Same real gap found in **4 of
the 5**: Rune of Release/Ancient Lockbox were never given a mission-specific position at all
(`onInstanceCreated` only ever toggled `setStatus`), sitting at a shared zone-default nowhere near
the real mission area. Real capture-confirmed positions existed for all 4 and were simply never
wired in -- fixed via `setPos()`:
- **The Susanoo Shuffle** (Mamool Ja, 20): `RUNE_OF_RELEASE`/`ANCIENT_LOCKBOX` positioned from 2
  agreeing captures.
- **Better Than One** (Lebros Cavern, 30): same gap, positioned from `Lebros Cavern FL - Better
  Than One (Thris)`'s per-entity PathLog.
- **The Price is Right** (Periqia, 40): same gap, positioned from 2 agreeing captures. Also
  resolved a previously-flagged **open gap**: `Bloody_Daggers` (`17006802`) was sitting at
  `(0,0,0)` with a note that no dedicated capture existed for it -- a sweep found 2 real dedicated
  single-mission captures that had been overlooked; fixed in `mob_spawn_points.sql`.
- **Bellerophon's Bliss** (Ilrusi Atoll, 50): same gap, positioned from real per-entity PathLog
  CSVs. Also confirmed Martial Maestro Megomak is real and relevant (not a stray reference) --
  a live combat NPC with his own script, spawn row, and dialogue visible in both captures.

**Bloody Rondo** (Leujaoam Sanctum, 10) was different -- its `Ancient_Lockbox`/`Rune_of_Release`
rows aren't shared zone-defaults, they're unique to this mission, but the *values themselves* were
wrong (`z=39`/`z=40`, nowhere near the real fight area). Fixed directly in `npc_list.sql` to the
real capture-confirmed cluster (`z≈-302`, right next to Count Dracula's and Cursed_Doppelganger's
own already-confirmed positions) -- independently corroborated by a second capture showing a real
player interaction with the Rune of Release NPC during that run.

All 5 missions' `RUNE_UNLOCKED_POS` grid params remain the known, already-documented `8,8`
placeholder (see the cross-cutting note above) -- no capture across any of the 5 missions'
available data revealed the real retail grid text, so this stays open. instance_entities.sql
cross-checks were clean for all 5 (no orphaned or missing registrations either direction), and no
unwired dialogue was found in any of the 5 zones' dat-extracted dialog tables.

## Content-completeness sweep: Counting Sheep / Supplies Recovery / Azure Experiments (Leujaoam Sanctum, missions 5/6/7) (2026-09-02)

Same methodology as the rank-10 sweep above, run against the 3 remaining Leujaoam Sanctum missions
still marked 🔴 in the tracker's summary grid. Priority order followed: query
`ffxi_zone_database.db` first, fall back to `mission_toolkit.py`/real capture data under
`D:\Claude\assault_captures\Leujaoam Sanctum\`, never fabricate. Checked for all 3: NPC/prop
registration completeness (`npc_list.sql`/`instance_entities.sql`/instance `.lua`), mob position
completeness (`mob_spawn_points.sql`), dialogue text-id sourcing, Rune of Release/Ancient Lockbox
positioning, and door-prop (`_1x*`/`_jx*`) registration/state.

**Supplies Recovery (6) -- real gap found and fixed.** Same bug class as 4 of the rank-10 sweep's
5 missions: `instances/supplies_recovery.lua`'s `onInstanceCreated` never called `setPos()` for
`RUNE_OF_RELEASE`/`ANCIENT_LOCKBOX` at all -- both entities sat at this zone's shared `npc_list`
default (`504/506, -302`), which is actually **Bloody Rondo's own confirmed mission-specific
position** (see that mission's rank-10 sweep entry above), not a generic placeholder -- hundreds
of yalms from Supplies Recovery's real start area. The real value had already been correctly
identified and written into this same file's own header comment on 2026-08-18
(`182.691/183.69, -3.364, 141.424`) but never actually applied via `setPos()` -- a documented-but-
not-wired gap, not a data gap. Re-confirmed independently against real PathLog rows for both
entities in `Leujaoam Sanctum - Supplies Recovery (Thris Nov2025)`
(`Rune_of_Release/17060015.csv`: `182.691,-3.364,141.424,dir 135`;
`Ancient_Lockbox/17060014.csv`: `183.691,-3.364,141.424,dir 135`) -- matches the header comment to
3 decimal places. **Fixed**: `scripts/zones/Leujaoam_Sanctum/instances/supplies_recovery.lua`
(`onInstanceCreated`, 2 new `setPos()` calls added before the existing `setStatus(DISAPPEAR)`
calls). No SQL edit needed -- per-instance `setPos()` override, matching this codebase's
established treatment of shared Rune/Lockbox ids elsewhere in this zone (Counting Sheep, Azure
Experiments already do the same).

- Also found, **not fixed** (real, but out of scope for a position-only fix and would need
  fabricated dialogue to wire): `Kuihlud` (`17060101`), the real NPC who explains the supply-
  package-race objective ("you must recover more supplies than the Immortals"), is registered in
  both `npc_list.sql` and `instance_entities.sql` (instance 6) but has **zero Lua wiring** --
  no `IDs.lua` entry, no `npcs/Kuihlud.lua` script file, nothing referencing the name anywhere in
  `scripts/zones/Leujaoam_Sanctum/`. Per this codebase's NPC-name-to-script-lookup rule, triggering
  him live would currently produce "No Valid Function for Kuihlud" in the map-server log. Left
  unwired -- the zone database has no decoded dialog-text table (only raw event bytecode), so his
  real trigger line can't be sourced without a dedicated dat-extractor/event-decompile pass, and
  the mission's own core race mechanic (player-side supply-package counter vs. a simulated rival
  counter) is already correctly flagged as an unbuilt real gap in the tracker, unconfirmed drop
  rate/threshold from the one available capture -- not attempted here per the no-fabrication rule.
- `instance_entities.sql` registration for instance 6 double-checked complete against every real
  entity found in the capture (`Kuihlud`, `qmqmqm`/103, `Achieve_Master`/104, the 10-NPC `Moogle`
  group/110-119, and all 10 real door props `_1xf`-`_1xu`/134-149 plus `_jxa`/165) -- all present,
  no gaps. (Note: the capture's own NPCLogger-logged CSV filenames for these door props are all
  +1 vs. their real `npc_list` id -- e.g. `_1xu` logged as `17060150.csv` but its real id is
  `17060149` -- the known client/capture id-offset drift documented elsewhere in this session, not
  a registration bug; the folder name, which is reliable, was used to cross-check instead.)
  `mob_spawn_points.sql` for all 12 real mobs (10 Imp + Gasharyad + Salimuhl) already carry real,
  non-zero, individually-captured coordinates -- no fix needed.

**Counting Sheep (5) -- re-confirmed correct, no new fix.** Already had real `setPos()` calls for
both `RUNE_OF_RELEASE` (`-59, -3, 197, 192`) and `ANCIENT_LOCKBOX` (`-55, -3, 189, 74`) wired in
from 2026-08-24. Cross-checked against the same real capture's own PathLog
(`Rune_of_Release/17060015.csv`: `-59.543,-3.499,197.311,dir 193`;
`Ancient_Lockbox/17060014.csv`: `-56.188,-3.5,190.055,dir 75`) -- Rune matches to within rounding;
Lockbox is off by roughly 1.2 yalms on x/z and 1 degree on facing, well within normal
interaction/trigger range and consistent with the existing value having been averaged/rounded
across the 3 independently-cross-referenced captures the header documents -- not treated as a bug,
left as-is. The mission's real remaining gaps (3 of 5 Karakul/QiqirnMine ids never captured, Ice
Cage "broken" visual state unconfirmed, dice-game/shepherd-follow mechanics needing new engine
precedent) were already correctly and thoroughly documented in the existing header/tracker entries
-- re-verified accurate, nothing to add or fabricate.

**Azure Experiments (7) -- re-confirmed correct, no new fix.** Already had real `setPos()` calls
for both `RUNE_OF_RELEASE` and `ANCIENT_LOCKBOX` (`82.787, -3.086, 323.746, 145` for both) wired in
from 2026-08-18, sourced from the mission's own win-capture data per the file's header. The
Nareema 4-successive-graft mechanic, real mob roster (10 Lamia, all real non-zero positions,
re-verified in `mob_spawn_points.sql`), Assault points (1650), and lockbox reward were all already
built and documented as real-capture-confirmed. No gaps found beyond the two already-flagged in
the tracker (Nareema's ~90s graft cooldown is an estimate, not precisely confirmed; the 10 Lamia's
exact gameplay role beyond ambient population is unconfirmed) -- both left as-is, already correctly
marked open.

**File changed**: `scripts/zones/Leujaoam_Sanctum/instances/supplies_recovery.lua` (2 `setPos()`
calls added to `onInstanceCreated`). Structural balance check: 7 `instance_object.` function
assignments, 7 `end` -- balanced (this file has no top-level `entity.`/`local function` entries).
No SQL files touched this pass, so no `dbtool.py` re-import is required for this specific change
-- it's a pure Lua per-instance override, live on next map-server restart/script reload.

Not yet SQL-reimported or live-tested.

## The Double Agent (15) and Marids in the Mist (18) -- content-completeness sweep (2026-09-02)

Both missions were flagged 🔴 in the tracker. Re-ran the same real-capture-driven sweep used for
missions 6/7/10/20/30/40/50: cross-referenced `instance_entities.sql`, `npc_list.sql`,
`mob_spawn_points.sql`, and each instance's own `.lua` against the real Thris Nov2025 captures for
both missions (`Mamool Ja Training Grounds - The Double Agent (Thris Nov2025)` and
`... - Marids in the Mist (Thris Nov2025)`, both with a `NPCLogger` sqlite DB) plus
`ffxi_zone_database.db`'s `door_props` table for ground-truth prop positions.

**The Double Agent (15) -- found NOT actually empty, contrary to the tracker's 2026-08-24 "entirely
empty on entry" report.** Checked every piece the report could plausibly be blaming:
- All 26 Qiqirn Spy (`17047628`-`17047653`) and all 9 Puk (`17047654`-`17047662`) are registered
  to instance 15 in `instance_entities.sql` (lines 645-682). Puk positions are the real non-zero
  ones from the 2026-08-25 fix, confirmed still correct in `mob_spawn_points.sql`.
- `npcs/Qiqirn_Spy.lua` (rebuilt 2026-08-24, after the "empty" report) implements a full real
  per-NPC-CSID capture/question menu, materially more built-out than the tracker's older bullets
  described -- the mechanic itself is not the empty-instance cause.
- Cross-checked the `_1u*` door props near the spy cluster (ids `17047860`-`17047863`,
  `17047892`-`17047894`) against both the capture's NPCLogger and `ffxi_zone_database.db`'s real
  `door_props` ground truth. The capture's own live entity ids for these props are consistently
  +1 vs. their real `npc_list` id (confirmed by exact-position match against `door_props`, e.g.
  capture id `17047861` at `(-397,-8,-378)` matches `_1u1`'s real ground-truth position exactly,
  which is `npc_list` id `17047860`, not `17047861`) -- the documented zone-wide capture-id-offset
  issue, not a data bug. Once that offset is accounted for, every one of these props is present
  and correctly registered to instance 15.
- Conclusion: nothing found to explain a genuinely empty instance as of this pass. The 2026-08-24
  report predates the Puk-position and (per the tracker's own history) some of the registration
  fixes, so it may already be stale -- flagged for the user to re-test rather than assumed fixed.

**Real gap found and fixed in both missions: Rune of Release / Ancient Lockbox never had their own
`setPos()` call**, so both defaulted to Imperial Treasure Retrieval's shared coordinates
(`301, 2, -417` / `299, 2, -420`) instead of their own mission's real spot -- the same class of bug
already fixed for every other Mamool Ja mission (e.g. `the_susanoo_shuffle.lua`,
`lebros_supplies.lua`). Real positions pulled directly from each mission's own capture NPCLogger:

- The Double Agent: Rune of Release `(-222, 1, -384)`, Ancient Lockbox `(-220, 2, -385)`, dir 192.
- Marids in the Mist: Rune of Release `(340, 14, 142)`, Ancient Lockbox `(340, 14, 145)`, dir 192.

**Marids in the Mist (18) -- also not empty.** All 26 real mobs (8 Marid, 3 Chigoe, 15
Breeder/Mahout/Farrier) and Zimahd (17047840, the real mission-giver) are registered to instance 18.
The `_1u*` door props near this mission's area (`17047878`-`17047879`, `17047890`-`17047892`) show
the same +1 capture-id-offset pattern as mission 15's props and, once corrected for, are all
present and correctly registered. Zimahd exists in `npc_list.sql`/`instance_entities.sql` but has
no `npcs/Zimahd.lua` script -- no interaction/dart-hand-out logic exists, consistent with the
already-documented "temporary-item capture mechanic not built" gap (needs an engine feature this
codebase doesn't have; out of scope for this content-completeness pass).

Checked the 8 Marid's `mob_spawn_points.sql` positions against the capture's live snapshot: all are
real non-zero, individually distinct positions, but differ from the capture's live positions by up
to ~110 yalms in one case (id `17047724`). Left unchanged -- a single live NPCLogger snapshot
reflects wherever the mob had wandered/aggroed to at capture time, not necessarily its spawn point,
and overwriting a plausible existing value from one ambiguous data point would risk the same kind
of error this session's methodology is built to avoid. Documented as an open item, not fixed.

**Files changed**: `scripts/zones/Mamool_Ja_Training_Grounds/instances/the_double_agent.lua` and
`.../marids_in_the_mist.lua` (2 `setPos()` calls added to each `onInstanceCreated`, immediately
before the existing `setStatus(DISAPPEAR)` calls). Structural balance check on both: 7
`instance_object.` function assignments, 7 `end` -- balanced. No SQL files touched this pass, so no
`dbtool.py` re-import is required for this specific change -- pure Lua per-instance overrides, live
on next map-server restart/script reload.

Not yet live-tested.

## Supplies Recovery mechanic built; Counting Sheep/Azure Experiments stale-status corrections (2026-09-02)

Follow-up pass on top of the Leujaoam Sanctum 5/6/7 sweep above, done directly (not delegated) per
explicit instruction. Re-read every instance/npc Lua file for all 3 missions against the tracker's
own claims before touching anything, since the sweep above had already found one case (Supplies
Recovery's Rune/Lockbox `setPos()`) where documented-but-never-applied real data was the actual bug.

**Supplies Recovery (6) -- the real supply-package race mechanic is now built**, on top of the
sweep's `setPos()` fix. Real data source: `Leujaoam Sanctum - Supplies Recovery (Thris Nov2025)`'s
CapLog (`Thris/CapLog/*.log`), read directly this pass (not just the header's prior summary of it):
- The Immortals' own announcement ("The Immortals have recovered N supply package(s) thus far.")
  ticks on the CapLog at *exactly* 30-second intervals throughout
  (`20:59:07/:38, 21:00:08/:38, 21:01:08/:38, ...`) -- confirmed real, not estimated.
- The observed count progression across those ticks: `0,0,0,0,1,1,1,1,1,2,3,3,3,3,3,3` (win fires
  ~58s after the last "3" tick, with no further player item pickups after the player's 4th).
- The player's 4 "Obtained temporary item" lines (gold ingot, handful of armored arrowheads, pinch
  of cluster ash, pickaxe -- in that order) land within a single ~94s window (21:01:26-21:03:00)
  against a total of 8 kills for the run (this session's earlier "4 of 8 kills dropped nothing
  extra" note, re-derived from the same log) -- so ~50% drop chance per kill.
- Real item ids cross-checked against `item_basic.sql`'s own name column (not guessed):
  `gold_ingot`=745, `handful_of_armored_arrowheads`=1627, `pinch_of_cluster_ash`=1630,
  `pickaxe`=605.

**Built**:
- New `scripts/zones/Leujaoam_Sanctum/npcs/supplies_recovery_common.lua` -- holds the 4 real item
  ids (rotated in capture order, not random, so a full run realistically sees all 4 like the
  capture did), the real 50% drop chance, the real 30s tick constant, and
  `grantSupplyPackage()` (uses `addTempItem()` + `messageSpecial(PLAYER_OBTAINS_TEMP_ITEM, itemId)`
  -- the same real text-id pattern already established for Counting Sheep's ore trade-in in
  `Qiqirn_Mine_Baron.lua`, confirmed real text id 7310).
- `scripts/zones/Leujaoam_Sanctum/mobs/Imp.lua`: `onMobDeath` now rolls the drop chance and calls
  `grantSupplyPackage()`.
- `scripts/zones/Leujaoam_Sanctum/instances/supplies_recovery.lua`: `onInstanceCreated` now seeds
  `playerSupplies`/`immortalSupplies`/`nextSupplyTick` instance localvars (same
  `instance:setLocalVar()` pattern already used elsewhere in this codebase, e.g. Ilrusi Atoll's
  Demolition Duty); `onInstanceTimeUpdate` now drives a 30s tick off the engine's own `elapsed` ms
  clock (no separate timer needed -- this callback was already firing regularly for the time-limit
  check), announces the Immortals' count via `PrintToPlayer` using the real capture's own wording,
  and completes the instance the first tick the player's count exceeds the Immortals'.
- **NOT capture-confirmed, documented as an open approximation rather than fabricated**: the
  Immortals' own per-tick increment probability (a single capture's realized sequence doesn't
  reveal the underlying formula -- approximated at a flat 20%/tick, chosen only to roughly
  reproduce the observed pace of 3 increments across ~16 ticks) and whether the real completion
  check genuinely happens exactly on the 30s tick (assumed here since it matches the observed ~58s
  gap, but a single data point can't rule out a separate, faster completion-check cadence).
- Structural balance check: `supplies_recovery.lua` 7 `instance_object.` / 7 `end` (unchanged
  count, edits were inside existing functions plus one new block); `Imp.lua` 2 `entity.` / 2 `end`;
  `supplies_recovery_common.lua` 1 top-level function (`grantSupplyPackage`) / 1 `end`. All
  balanced.
- `Kuihlud` (`17060101`) remains unwired (no dialogue source available, see the sweep entry above)
  -- doesn't block the mechanic, which fires independent of his dialogue.

**Counting Sheep (5) and Azure Experiments (7) -- both tracker Overall statuses were stale, not
actually broken.** Read both missions' full instance + npc Lua files directly (not just the
tracker's summary of them) to check the sweep's "re-confirmed correct, no fix" conclusion against
the specific claims the tracker made:
- **Counting Sheep**: the tracker's 🔴 status carried a 2026-08-24 note claiming the mine-triggered
  ice-cage-break mechanic was "not yet wired to any mission logic". That's no longer true --
  `npcs/Qiqirn_Shepherd.lua` (hire, follow, `mineStep()` break sequence) and `npcs/Karakul.lua`
  (paired-cage check, `instance:setProgress()`, Rune-of-Release reveal on the first free) are both
  present, complete, and reference `counting_sheep_common.lua`'s `ROOM_PAIRS`/`ALL_CAGE_IDS`
  correctly -- built 2026-08-29, after the note that's still driving the tracker's status. Verified
  by reading all 3 files start to finish, not by re-deriving from a capture (the mechanic itself
  was already correctly built from real data by the earlier pass -- this was a documentation-sync
  fix, not a code fix). Downgraded 🔴->🟡 in the tracker: not ✅/🟢 because 3 of the real 5
  Karakul/QiqirnMine ids genuinely have no captured position anywhere (real data gap, honestly
  already documented in the file's own header), so only 2 of 5 rooms are actually completable.
- **Azure Experiments**: the tracker's 🔴 status (2026-08-25) claimed "NPC mapping and mission
  logic still need to be built out". Also stale -- `npcs/Nareema.lua`'s 4-successive-graft
  completion logic and `instances/azure_experiments.lua`'s Rune/Lockbox `setPos()` were both built
  2026-08-18, a week before that note. Read both files start to finish to confirm; nothing missing
  or stubbed. Downgraded 🔴->🟡 rather than back to 🟢: it's genuinely unclear whether the
  2026-08-25 note referred to a real regression that's since been reverted, or was simply an error
  in that pass -- flagged in the tracker for a live test to settle either way rather than assuming
  either direction.

**Files changed this pass**: `scripts/zones/Leujaoam_Sanctum/npcs/supplies_recovery_common.lua`
(new), `scripts/zones/Leujaoam_Sanctum/mobs/Imp.lua`,
`scripts/zones/Leujaoam_Sanctum/instances/supplies_recovery.lua`. No SQL touched -- no
`dbtool.py` re-import needed for this pass; live on next script reload/map-server restart. Not yet
live-tested by the user.

## Apkallu Breeding (Lebros Cavern, mission 26): re-audited against real captures, found the
## 2026-08-29 "correction" was itself wrong -- npc positions never actually written (2026-09-02)

Content-completeness sweep, same methodology as the earlier 5-zone pass. Re-checked this
mission's own real capture (`Lebros Cavern S - Apkallu Breeding (Thris)`) from scratch rather than
trusting the existing documentation, since the mission is still marked 🔴.

**Found**: the 2026-08-18 fix log entry claims "13 real Lebros Apkallu positions found" from this
capture's NPCLogger db, but that data was never actually applied to `npc_list.sql` -- all 16
`17035336`-`17035351` rows were still the generic `0,0,0` stub pattern. Queried the capture's
NPCLogger sqlite db directly (`Thris/NPCLogger/Lebros Cavern.db`, table `entries`, rows where
`name='LebrosApkallu'`) and got exactly 13 real positions back, ids `17035337`/`17035338`/
`17035340`/`17035342`-`17035351` -- confirms the documented "13 of 16, a few gaps" claim was
accurate, just never written to SQL. Filled in `pos_rot`/`pos_x`/`pos_y`/`pos_z` for those 13 rows
from the capture, and set `status`/`entityFlags` to match the real-spawned-NPC convention already
used for `Rhap_Nelhah` in the same file (`status=0`, `entityFlags=27`, vs the stub pattern's
`status=7`, `entityFlags=3`). `17035336`/`17035339`/`17035341` have no capture data and are left
as unpositioned stubs.

**Found, more serious**: separately, a 2026-08-29 pass ("6 more missions confirmed" entry, and
IDs.lua's own history comments) had moved 16 *different* real ids (`17035380`-`395`) into this
mission's `instance_entities.sql` registration and `IDs.lua` block, believing them to be Apkallu
Breeding's pairing NPCs. They are not -- `17035380`-`395` is Egg Conservation's (mission 28) real
mob family, built 2026-08-25 (`mob_groups.sql` groupid 23, poolid 197, `mobs/Lebros_Apkallu.lua`).
The two id ranges share the "Lebros Apkallu" name coincidentally and appear to have been confused
by the 2026-08-29 pass. Consequences of that mistake, both fixed this pass:
- `sql/instance_entities.sql`: `17035380`-`395` were registered to instance 26, and NOT to
  instance 28 at all -- meaning Egg Conservation's real mobs have never spawned in that mission
  either, the whole time. Moved to instance 28; registered the real 13 `17035337`-`351` ids to
  instance 26 instead (previously unregistered to any instance).
- `scripts/zones/Lebros_Cavern/IDs.lua`: the 2026-08-29 pass nested `LEBROS_APKALLU_MALE1-3`/
  `LEBROS_APKALLU_FEMALE1-13` inside a new `npc[26]` sub-table. But `mobs/Lebros_Apkallu.lua`
  (`MALE_IDS`) and `mobs/Qiqirn_Eggler.lua` (female id list) both read these as flat
  `ID.npc.LEBROS_APKALLU_*` keys, not `ID.npc[26].*` -- so every reference has resolved to `nil`
  since 2026-08-29, meaning Egg Conservation's male-engage/female-protect AI (`isMale()`,
  `onMobDeath`'s alive-female counter) has silently never worked even on a build where the mobs
  did spawn. Flattened the 16 constants back to top-level (matching how the consumers actually
  read them, and matching the flat-key convention already used for `ANCIENT_LOCKBOX`/
  `RUNE_OF_RELEASE` etc in the same table), and replaced the vacated `npc[26]` sub-table with the
  real Apkallu Breeding mapping (`APKALLU1`-`APKALLU13` = `17035337`...`17035351`), matching the
  `ID.npc[N]` nested-indexing pattern already used correctly elsewhere in the codebase (e.g.
  `Arrapago_Remnants/IDs.lua`).

**Confirmed unchanged / already correct**: Rune of Release (`17035479`, `49.999,-40.837,96.999`)
and Ancient Lockbox (`17035478`, `50.000,-40.070,99.999`) already have real, non-zero positions
from an earlier pass -- no fix needed. Entrance (`86.852,-29.464,256.080`, dir 22) and the lockbox
reward table were already fixed in earlier passes (2026-08-18/19) and re-confirmed correct.

**Still open, not fixed (real gaps, not guessed around)**:
- The pairing/compatibility minigame mechanic itself is still not built -- the 13 real NPCs now
  exist, have real positions, and spawn in the correct instance, but nothing lets a player trigger
  or pair them yet. This is why Overall status stays 🔴 despite the fixes above.
- Rhap Nelhah (`17035485`, confirmed real position, registered to instance 26) has no
  `npcs/Rhap_Nelhah.lua` script at all -- no onTrigger, so interacting with it currently falls
  through to the default handler. The real quoted lines ("The slightly smaller ones are the
  girrrls, and the bigger ones are the guys...") were hand-decoded from raw `0x2A` MessageSpecial
  packets (this capture has no plain-text CapLog), so there's no confirmed numeric text id to wire
  a script to without guessing -- left undone.
- Doors/props: this instance is documented as "walkable, no objective content" and no capture
  evidence points to a specific missing/misplaced door prop for this mission specifically, so none
  were touched this pass.

**Files changed**: `sql/npc_list.sql` (13 rows, `17035337`-`17035351`), `sql/instance_entities.sql`
(instance 26/28 registrations), `scripts/zones/Lebros_Cavern/IDs.lua` (flattened
`LEBROS_APKALLU_*`, new real `[26]` block). Structural balance check on
`instances/apkallu_breeding.lua` (7/7, unchanged this pass), `mobs/Lebros_Apkallu.lua` (4/4),
`mobs/Qiqirn_Eggler.lua` (3/3) -- all balanced; `IDs.lua` brace count 17 open / 17 close --
balanced. **SQL changes need `py -3 dbtool.py update full` from `C:\topaz\tools` to take live
effect** -- not run this pass. Not yet live-tested.

## Ilrusi Atoll rank sweep: Searat Salvation / Lost and Found / Desperately Seeking Cephalopods data-completeness pass (2026-09-02)

Ran the same real-capture-driven data-completeness methodology as the earlier Rank-10 sweep across
Ilrusi Atoll's 3 remaining 🔴 missions. Note: a concurrent session was independently auditing the
same 3 missions in parallel this same day -- several findings below (the Rune of Release/Ancient
Lockbox position gap for Desperately Seeking Cephalopods, its real `G-9` grid ref, and the Ulbuun/
Walagarim flavor-NPC find) were reached independently by both passes and agree; this write-up
covers the additional ground: Lost and Found's real win-trigger, and Searat Salvation's clean
audit.

**Searat Salvation (mission 45): clean data audit, no fix needed.** Re-verified all 5 Qiqirn Diver
(`17002565`-`17002569`), all 7 Giant Orobon (`17002570`-`17002576`), and the Chief Diver
(`17002564`) against `npc_list.sql` -- all have real, non-zero positions from the 2026-08-24
rebuild and are fully registered in `instance_entities.sql`. Rune of Release/Ancient Lockbox
already had real per-instance `setPos()` calls from that same rebuild
(`instances/searat_salvation.lua:39-40`). No zero-position entities, no missing registrations, no
unwired door props found. The mission's only remaining gap is the documented one: the autonomous
Diver/Orobon AI escort system itself, out of scope for a data-completeness pass.

**Lost and Found (mission 47): real win-trigger found and wired.** A previously-unreviewed capture,
`Ilrusi Atoll SM - Lost and Found (2)` (player Giichi), covers a full search all the way to a real
win -- unlike the other 2 captures for this mission, which both ended mid-search. The CapLog shows
the actual pickup: triggering `id 17002672` (npc_list's shared placeholder `'qm6'`, client-visible
name "???") at its real logged position (`-182.053, -4.959, -175.018`) fires MesNum 7580, "This is
it! The Eye of Zahak!", immediately completes the mission ("Mission objective completed. Unlocking
Rune of Release (I-9)"), and Tian Tian follows with MesNum 7602 ("Oh, this is most excellent!...").
This entity had a real `npc_list` row but was never registered to instance 47 at all -- registered
in `sql/instance_entities.sql`, positioned via `setPos()` in `lost_and_found.lua`'s
`onInstanceCreated`, and given a new trigger script, `scripts/zones/Ilrusi_Atoll/npcs/qm6.lua`,
that calls `instance:complete()` directly (same pattern already used by `QiqirnDiver_Common.lua`
for Searat Salvation). A sibling placeholder, `'qm7'`/`17002673`, also had a real logged position
in the same capture but never triggered a win in that run -- left unregistered, role unconfirmed.
Also fixed from the same capture: real per-instance Rune of Release/Ancient Lockbox positions
(`-190.869,-7.500,-374.403`/`-189.059,-7.500,-371.731`, agreeing with the other 2 captures'
rounded-precision NPCLogger dumps) -- these had never been positioned for this mission at all,
sitting at the shared zone-default. `IDs.lua` gained `ID.npc.TIAN_TIAN`/`EYE_OF_ZAHAK` (both
already had real SQL rows, just no Lua-side reference) and a full block of Tian Tian's real
hint-cycle message IDs (`TIAN_TIAN_GREET` through `TIAN_TIAN_NO_HINTS_YET`, `7574`-`7597`), read
directly off the capture's decoded NPC Chat (0x036) lines. **Not built**: the hot/cold proximity
escalation that guides the player to the ring -- the message IDs are real, but the distance-to-tier
mapping isn't confirmed from a single run, and 2 lines ("...the person closest to the ring
is...<name>!" / "...move our search <direction>...") never showed their own distinct message ID in
the CapLog text at all -- documented as an open gap rather than guessed. `Kelp_Crab`
`17002590`/`17002592` re-checked against all 3 available captures including this newly-reviewed
one -- still zero-position, still no data anywhere; remains a genuine open gap, not fixed.

**Desperately Seeking Cephalopods (mission 49): confirmed by 2 independent audits.** Cross-checked
this session's own findings against the concurrent session's parallel pass on the same file and
they agree: real per-instance Rune of Release/Ancient Lockbox positions (`-20.0,-7.0,250.0`/
`-18.0,-7.0,249.0`, from the `Ilrusi Atoll SL - Desperately Seeking Cephalopods` capture) and the
real `G-9` grid ref (was the generic `8,8`/H-8 placeholder) are now wired in
`desperately_seeking_cephalopods.lua`. Independently re-confirmed the fishing-encounter mechanic
itself (MesNum 7661, "You find an ahtapot in the belly of the Orobon!", mid-fight; killing that
Orobon completes the mission) and the 1100-point reward, both matching the original 2026-08-18
capture read. Found 3 real named flavor NPCs -- Ulbuun ("Captain Ulbuun of the 41st Fighting
Beavers", mission-giver, real greeting text fired via CSID 55 in the CapLog: "You've been sent by
the Empire to catch ahtapot, no?"; fires MesNum 7630 "A fine specimen!" on a successful catch) and
rival hunters Walagarim/Bhjaama (1-line fishing-luck barks -- MesNum 7634 "Damn... Nothin'..." on a
failed catch) -- all 3 already had real, correct `npc_list.sql` positions and were already
registered to `instance_entities`, just never referenced anywhere in the Lua build. Added to
`IDs.lua` (`ULBUUN`/`WALAGARIM`/`BHJAAMA`) for whenever the fishing-encounter engine feature gets
built -- the CS-event 55 flow itself wasn't decompiled this pass, so this is data-completeness
only, not a new mechanic. Overall status correctly stays 🔴: the fishing-encounter system remains
the real, out-of-scope engine gap, unchanged from the original 2026-08-18 judgment call.

**Files changed**: `scripts/zones/Ilrusi_Atoll/IDs.lua` (new `TIAN_TIAN`/`EYE_OF_ZAHAK` npc ids +
Tian Tian hint-cycle text block + `BHJAAMA` npc id), `sql/instance_entities.sql` (registered
`47,17002672`), `scripts/zones/Ilrusi_Atoll/npcs/qm6.lua` (new file), `lost_and_found.lua`
(setPos for Rune/Lockbox/Eye of Zahak, `ringFound` localvar, updated header/progress comments).
Structural balance checks: `lost_and_found.lua` 7/7, `desperately_seeking_cephalopods.lua` 7/7,
`searat_salvation.lua` 7/7 (unchanged), `npcs/qm6.lua` 1/1 -- all balanced. **SQL changes need
`py -3 dbtool.py update full` from `C:\topaz\tools` to take live effect** -- not run this pass.
Not yet live-tested.

## Searat Salvation: stale tracker correction, real WALLHACK bug fixed, zero-position audit closed out (2026-09-02, same-day follow-up)

Independently re-verified the "clean data audit, no fix needed... only remaining gap is the
autonomous AI escort system" conclusion two entries above by actually reading the mission's Lua
files rather than trusting the existing tracker bullet, and found that conclusion itself repeats a
stale error: `scripts/zones/Ilrusi_Atoll/instances/searat_salvation.lua`'s own header documents a
**2026-08-24 FULL REBUILD** that explicitly supersedes the "autonomous NPC-AI, no engine
precedent" read with the real mechanic (a player-guided escort) and states it was built. Confirmed
this is true by reading the actual implementation, not just the header comment:
`scripts/zones/Ilrusi_Atoll/npcs/QiqirnDiver_Common.lua` (talk to an idle diver to make it follow
you; a nearby Giant Orobon scares it into fleeing; deliver it to the Chief Diver to complete) and
`npcs/GiantOrobon_Common.lua` (the sight-range scare check) are both complete, non-stub scripts,
correctly wired via `IDs.lua`'s `QIQIRN_DIVER`/`GIANT_OROBON`/`QIQIRN_CHIEF_DIVER` tables. The
Assault_Issue_Tracker.md bullet describing this as "not built... needs an AI system this codebase
has no precedent for" was the OLD, pre-2026-08-24 read, never updated after the rebuild landed --
corrected in the tracker this pass (mission upgraded 🔴->🟢, matching the grid table).

**Real bug found and fixed while re-reading the escort script**: both of
`QiqirnDiver_Common.lua`'s `pathTo()` calls (following the guide; fleeing a scaring Orobon) used
bare `tpz.path.flag.RUN + tpz.path.flag.SCRIPT`, with no `WALLHACK`. This project's own established
default for `pathTo()` (documented in prior-session findings) is `RUN + WALLHACK + SCRIPT` --
a strict no-wallhack path is a known, previously-confirmed failure mode against real navmesh gaps
elsewhere in this codebase. Added `WALLHACK` to both calls (lines calling `npc:pathTo(...)` in
`tick()` and `entity.scare()`) as a preventive fix matching the known-good default; not yet
observed failing live on this specific mission; but matches an exact known bug class.

**Also fixed this pass** (found independently, before discovering the concurrent session's own
write-up above): the same 13 zero-position Searat Salvation entities
(`17002564`-`17002576`, Qiqirn Chief Diver/5 Diver/7 Giant Orobon) were fixed with real x/y/z/r
values pulled directly from the Siknawz 2023.06.19 `[W]` win capture's own NPCLogger database
(`Ilrusi Atoll C - Searat Salvation`) -- same real data source and same fix already independently
converged on by the concurrent pass; no conflict, values agree.

**Lost and Found, additional fixes on top of the concurrent pass above** (found independently
before merging): `Kelp_Crab` `17002591` (one of the two previously "no data in any capture" ids)
does have real data in the "(2)" Giichi capture's own NPCLogger database --
`x=-130.468, y=-1.962, z=-422.920, rot=235` -- fixed in `mob_spawn_points.sql`. `17002590`/
`17002592` re-checked, genuinely still no data anywhere -- remain open. `onInstanceComplete`'s
`RUNE_UNLOCKED_POS` call was still using the generic `8,8` placeholder despite the real `I-9` grid
ref already being confirmed elsewhere in this pass's own write-up -- fixed to `(8, 9)` (letter
param 0-indexed, same convention as Imperial Code's confirmed `G-8` fix). Also added a minimal
`scripts/zones/Ilrusi_Atoll/npcs/Tian_Tian.lua` -- she had a real, registered, player-facing
`npc_list` row but **no script file at all**, meaning a player clicking her directly would produce
"No Valid Function for Tian_Tian" in the map-server log (this codebase's own established
npc-name-drives-script-lookup failure mode). The stub only sends her real confirmed greeting line
(`TIAN_TIAN_GREET`) via `messageSpecialFrom` -- it does not simulate the still-unbuilt hot/cold
hint escalation.

**Files changed this follow-up**: `sql/npc_list.sql` (13 rows, `17002564`-`17002576`),
`sql/mob_spawn_points.sql` (`17002591`), `scripts/zones/Ilrusi_Atoll/npcs/QiqirnDiver_Common.lua`
(2 `pathTo()` calls), `scripts/zones/Ilrusi_Atoll/npcs/Tian_Tian.lua` (new),
`scripts/zones/Ilrusi_Atoll/instances/lost_and_found.lua` (`RUNE_UNLOCKED_POS` grid fix),
`scripts/zones/Ilrusi_Atoll/instances/desperately_seeking_cephalopods.lua` (header consolidated),
`documentation/Assault_Issue_Tracker.md` (Searat Salvation section rewritten + grid cell
🔴->🟢). Structural balance checks: `QiqirnDiver_Common.lua` 6/6, `Tian_Tian.lua` 1/1,
`lost_and_found.lua` 7/7, `desperately_seeking_cephalopods.lua` 7/7 -- all balanced. **SQL changes
need `py -3 dbtool.py update full` from `C:\topaz\tools` to take live effect** -- not run this
pass. Not yet live-tested.
