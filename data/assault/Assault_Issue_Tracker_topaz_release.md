# Assault Issue Tracker

Running list of known bugs/gaps in the Assault build-out, organized by **Assault rank** (lowest to
highest, matching in-game unlock order), then sub-grouped by mission within that rank -- kept
separate from `Assault_Fix_Log.md` (which is a chronological history of what was found and
fixed). This file is the "what's still broken right now" view -- update it whenever something new
is reported or fixed. Each entry links back to the fuller writeup in the fix log where one exists.

Status legend, **for individual bullets within a mission** (tracking one specific reported bug or
data point): 🔴 confirmed broken, not fixed · 🟡 root cause found, fix not yet applied ·
🟢 fixed, not yet tested in-game · ✅ fixed and confirmed working in-game.

**Important distinction, corrected 2026-08-19**: almost every mission below was built or repaired
using real capture/packet data -- that is a strong signal the *data* is correct, but it is **not**
the same thing as a user actually playing the mission through in this build and confirming it
works. Earlier passes of this file used ✅ for individual bullets in a way that could read as "this
mission is done" when really only the underlying data point (an entrance position, a reward table,
etc.) had been confirmed against a capture. To fix that, every mission section below now starts
with a separate **Overall status** line using the same 4 markers, but meaning something stricter:
- **✅ Overall** = the user has personally played this mission through in this build, start to
  finish, and confirmed it works. As of 2026-08-21 this is true for **4 of 50 missions**
  (Requiem, Extermination, Troll Fugitives, Orichalcum Survey) -- Preemptive Strike was
  previously in this group but has since regressed (see its own entry) -- each explicitly called out as
  full playthroughs, no issues.
- **🟢 Overall** = built and believed correct from real capture data, but **not yet live-tested**.
  This is most missions. Treat as "should work, needs a real test," not "done."
- **🟡 Overall** = built, but a real known gap or unresolved uncertainty remains even before
  considering live-testing.
- **🔴 Overall** = the core mechanic is still wrong, unbuilt, or a known-broken scaffold.

The individual bullets under each mission keep their original narrower meaning (did this *specific
fix* land correctly against the data available) -- only the new Overall line speaks to "is the
whole mission actually confirmed playable."

## Status grid (zone x rank, Overall status only)

Each cell links to that mission's own subsection below. (Anchor links depend on standard
GitHub-flavored-markdown heading slugs -- they work on GitHub and most markdown viewers, but may
not resolve in every renderer.)

|             | PSC | PFC | SP | LC | C | S | SM | CS | SL | FL |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Leujaoam    | [✅](#leujaoam-cleansing-leujaoam-sanctum-mission-1) | [✅](#orichalcum-survey-leujaoam-sanctum-mission-2) | [✅](#escort-professor-chanoix-leujaoam-sanctum-mission-3) | [✅](#shanarha-grass-conservation-leujaoam-sanctum-mission-4) | [🟡](#counting-sheep-leujaoam-sanctum-mission-5) | [✅](#supplies-recovery-leujaoam-sanctum-mission-6) | [🟡](#azure-experiments-leujaoam-sanctum-mission-7) | [✅](#imperial-code-leujaoam-sanctum-mission-8) | [🟡](#red-versus-blue-leujaoam-sanctum-mission-9) | [🔴](#bloody-rondo-leujaoam-sanctum-mission-10) |
| Mamool Ja   | [✅](#imperial-agent-rescue-mamool-ja-training-grounds-mission-11) | [✅](#preemptive-strike-mamool-ja-training-grounds-mission-12) | [✅](#sagelord-elimination-mamool-ja-training-grounds-mission-13) | [✅](#breaking-morale-mamool-ja-training-grounds-mission-14) | [✅](#the-double-agent-mamool-ja-training-grounds-mission-15) | [🟡](#imperial-treasure-retrieval-mamool-ja-training-grounds-mission-16) | [🟡](#blitzkrieg-mamool-ja-training-grounds-mission-17) | [🟡](#marids-in-the-mist-mamool-ja-training-grounds-mission-18) | [🟡](#azure-ailments-mamool-ja-training-grounds-mission-19) | [🟢](#the-susanoo-shuffle-mamool-ja-training-grounds-mission-20) |
| Lebros      | [✅](#excavation-duty-lebros-cavern-mission-21) | [✅](#lebros-supplies-lebros-cavern-mission-22) | [✅](#troll-fugitives-lebros-cavern-mission-23) | [✅](#evade-and-escape-lebros-cavern-mission-24) | [✅](#siegemaster-assassination-lebros-cavern-mission-25) | [🟢](#apkallu-breeding-lebros-cavern-mission-26) | [✅](#wamoura-farm-raid-lebros-cavern-mission-27) | [🟡](#egg-conservation-lebros-cavern-mission-28) | [🟢](#operation-black-pearl-lebros-cavern-mission-29) | [🟢](#better-than-one-lebros-cavern-mission-30) |
| Periqia     | [✅](#seagull-grounded-periqia-mission-31) | [✅](#requiem-periqia-mission-32) | [✅](#saving-private-ryaaf-periqia-mission-33) | [✅](#shooting-down-the-baron-periqia-mission-34) | [✅](#building-bridges-periqia-mission-35) | [✅](#stop-the-bloodshed-periqia-mission-36) | [🟢](#defuse-the-threat-periqia-mission-37) | [🟢](#operation-snake-eyes-periqia-mission-38) | [🟢](#wake-the-puppet-periqia-mission-39) | [🟢](#the-price-is-right-periqia-mission-40) |
| Ilrusi      | [✅](#golden-salvage-ilrusi-atoll-mission-41) | [✅](#lamia-no13-ilrusi-atoll-mission-42) | [✅](#extermination-ilrusi-atoll-mission-43) | [✅](#demolition-duty-ilrusi-atoll-mission-44) | [🟢](#searat-salvation-ilrusi-atoll-mission-45) | [🟢](#apkallu-seizure-ilrusi-atoll-mission-46) | [🟡](#lost-and-found-ilrusi-atoll-mission-47) | [🟡](#deserter-ilrusi-atoll-mission-48) | [🔴](#desperately-seeking-cephalopods-ilrusi-atoll-mission-49) | [🟢](#bellerophons-bliss-ilrusi-atoll-mission-50) |

15 cells are ✅ (Periqia/PFC = Requiem, Ilrusi/SP = Extermination, Lebros/SP = Troll
Fugitives, Mamool Ja/PFC = Preemptive Strike -- re-confirmed 2026-08-22 after a real regression and
fix in between, Mamool
Ja/SP = Sagelord Elimination, Periqia/SC = Saving Private Ryaaf -- user-confirmed complete
2026-08-23; the roaming-Fomor difficulty mechanic was attempted and rolled back, not blocking;
Leujaoam/SP = Escort Professor Chanoix -- user-confirmed complete 2026-08-30 after a
junction-graph pathing rebuild, real destination/Rune-of-Release position corrections, and a
gentle-fadeout fix; Ilrusi/PSC = Golden Salvage -- user-confirmed complete 2026-08-30, with the
Mimic's lid-animation cosmetic issue knowingly deferred, not blocking; Mamool Ja/LC = Breaking
Morale -- user-confirmed complete 2026-08-30, real csids found for both 2-option menus (Viscous
Liquid/Quhaaja) and the missing Assault-points table entry fixed; Lebros/C = Siegemaster
Assassination -- user-confirmed complete 2026-09-01; Lebros/LC = Evade and Escape --
user-confirmed complete 2026-09-02, after a full switch-mechanic rebuild (real 5-min timer + 60s
expiry warning + 3-of-7 room randomization, real dialog text replacing chat-print), Dahak HP/
Draw-In fixes, and a Rune of Release position + grid-ref text correction; re-confirmed live
2026-09-12 after fixing the switch's real lamp animation (packet-capture-confirmed
animationsub 4/5 + namevis 36, not the guessed 0/1/32) plus a stray rotation-to-player bug and a
despawn/blink workaround that was the actual cause of the earlier visual complaint; Lebros/S = Wamoura Farm
Raid -- user-confirmed complete 2026-09-02, after a larva/moth naming+modelid+skill-list fix, 7
real rock-passability fixes, a 3rd real northern shared-spawn candidate, and a switch to a random
3-of-18 maturation mechanic; Periqia/C = Building Bridges -- user-confirmed complete 2026-09-02;
same real lamp-animation fix as Evade and Escape's Switch (animationsub 4/5 + namevis 36, no
forceRespawn/lookAt) applied to Bridge_Switch.lua 2026-09-12, carried over from the cross-zone
capture confirmation rather than a Building-Bridges-specific capture;
Mamool Ja/C = The Double Agent -- user-confirmed complete 2026-09-02, after a real startEvent
padding revert, an onEventUpdate/onEventFinish selection-tracking fix, a real option-value shift
correction, and 4 door-prop fixes; Leujaoam/S = Supplies Recovery -- user-confirmed complete
2026-09-02, after a full Immortal hunting-AI/drop-mechanic rebuild, a real enmity-timing bug fix,
a loss-condition fix (was silent, now exits the Assault), and a messageSpecial parameter-slot fix
for the supply-count announcement).
Everything else, including every 🟢, still needs a
real playthrough before it should be considered done.

Rank order used below: **PSC** (Private Second Class) → **PFC** (Private First Class) →
**SP** (Superior Private) → **LC** (Lance Corporal) → **C** (Corporal) → **S** (Sergeant) →
**SM** (Sergeant Major) → **CS** (Chief Sergeant) → **SL** (Second Lieutenant) →
**FL** (First Lieutenant). Each zone's 10 missions map 1:1 onto these 10 ranks in order (e.g. every
zone's 5th mission is Corporal rank) -- confirmed against BG Wiki's Corporal/Sergeant mission
lists and this project's own build history (all "SP-rank" missions built this session were each a
zone's 3rd mission). Within each rank, missions are ordered by zone: Leujaoam Sanctum, Mamool Ja
Training Grounds, Lebros Cavern, Periqia, Ilrusi Atoll.

---

## System-wide (all zones, all ranks)
- **⚠️ Dependency: replacement navmeshes required for correct pathing in several zones.** Several
  mission fixes in this document (notably Escort Professor Chanoix's junction-graph escort, carrier
  pathing in Blitzkrieg/Imperial Treasure Retrieval) assume the denser navmesh bake from
  [EdenServer/navmeshes](https://github.com/EdenServer/navmeshes), not this repo's original
  `navmeshes` submodule content (`topaz-next/xiNavmeshes`). User replaced the `.nav` files locally
  for Ilrusi Atoll, Lebros Cavern, Leujaoam Sanctum, Mamool Ja Training Grounds, and Periqia
  2026-08-29/30 and confirmed carrier pathing in Mamool Ja Training Grounds now works correctly
  without wallhack workarounds as a direct result. **This swap is NOT committed to git** -- the
  `navmeshes` submodule only has a remote for the original `topaz-next/xiNavmeshes` repo (no
  `valhalla` fork exists to push the replacement to), so it's being handled locally/out-of-band per
  user decision (2026-08-30). Anyone rebuilding this server from a fresh clone needs to manually
  pull the replacement `.nav` files from EdenServer/navmeshes into the `navmeshes/` directory for
  these zone-specific fixes to behave as described.
- 🟢 **User-reported 2026-08-18**: instance timeout hangs at a black screen forever, player never
  removed from the (failed) instance. Root cause: 54 of 56 instance files had an empty
  `onEventFinish` stub that shadowed each zone's working `Zone.lua` fallback in the event-script
  lookup chain -- `setPos()` never fired. Affected every Assault mission, not just one. Fixed by
  removing the empty stubs (Lua-only). See Assault_Fix_Log.md for the full trace. Not yet
  confirmed fixed live.
- ✅ **User-reported 2026-08-20 (noticed on Saving Private Ryaaf, but zone-wide)**: same
  black-screen-hang-on-timeout symptom, a *different* real bug -- `Periqia/Zone.lua`'s own
  `onEventFinish` referenced `instance:getChars()` but never actually defined `instance` anywhere
  in that function (which only receives `player`, `csid`, `option`) -- a Lua error on every single
  call, so `setPos()` never ran. Checked all 5 Assault zones' `Zone.lua` directly: Periqia was the
  only one broken this way (Leujaoam_Sanctum/Mamool_Ja_Training_Grounds/Lebros_Cavern all use the
  correct single-`player:setPos()` pattern already; Ilrusi_Atoll uses a valid, differently-styled
  `player:getInstance()`-then-loop version). Fixed to match the proven pattern -- affects all 10
  Periqia Assault missions, not just this one. Confirmed no instance file has regressed the
  2026-08-18 empty-stub issue either. See `Assault_Fix_Log.md` for the full trace. Not yet
  confirmed fixed live.
- ✅ **User-directed 2026-08-22, found via a systematic `namevis` cross-reference (not a live-test
  report)**: Ilrusi Atoll's `Rune_of_Release` (`npc_list` 17002655) was the only one of 9 zones'
  copies of this entity with `namevis=0` -- every sibling zone already has `namevis=112`, and
  Ilrusi Atoll's own real capture data confirms 112 is correct there too, so this wasn't drift
  between SQL and capture, it was Ilrusi Atoll's row itself being the outlier relative to every
  other zone. Explains a user-observed inconsistency ("some Rune of Release with names, some
  without") that turned out to be zone-consistent rather than random -- every zone except Ilrusi
  Atoll correctly hid the name; Ilrusi Atoll always showed it. Fixed: `namevis` 0 -> 112. Affects
  all 9 Ilrusi Atoll missions (Golden Salvage, Lamia No.13, Extermination, Demolition Duty,
  Apkallu Seizure, Lost and Found, Deserter, Desperately Seeking Cephalopods, Bellerophons Bliss).
  Needs a DB reimport. Not yet confirmed fixed live.
- ✅ **User-directed 2026-08-22**: after confirming Golden Salvage's own timeout-stuck bug was
  fixed, asked whether it needed checking zone-wide. It did -- both the 2026-08-18 and 2026-08-20
  fixes above only verified their code *ran without erroring*, neither checked whether the
  destination zoneid was actually correct. All 5 zones' `csid==102` timeout handler sent players
  to the wrong zone: Ilrusi Atoll -> 54 (Arrapago Reef, should be 55), Leujaoam Sanctum -> 79
  (Caedarva Mire, should be 69), Mamool Ja Training Grounds -> 52 (Bhaflau Thickets, should be
  66), Lebros Cavern -> 61 (Mount Zhayolm, should be 63), Periqia -> 79 (Caedarva Mire, should be
  56). Fixed all 5. Confirmed fixed live for Ilrusi Atoll (Golden Salvage); the other 4 not yet
  retested.
- 🟡 **User-reported 2026-08-28/29, diagnosed via direct field-by-field `npc_list` comparison
  against a confirmed-working NPC (`Quhaaja`, status=0)**: mobs/NPCs registered correctly in
  `instance_entities` and visible to a GM via `!navdebug` (real server-side position/tracking) were
  nonetheless completely invisible to normal players and absent from the radar/minimap, blocking
  mission objectives outright (couldn't turn in items, couldn't engage required kills). Root cause:
  `npc_list.status = 6` (`tpz.status.CUTSCENE_ONLY`) never renders client-side or shows on radar,
  even with no explicit C++ branch found gating it in `entity_update.cpp` (likely a client-side
  protocol rule) -- distinct from `entityFlags`/`FLAG_UNTARGETABLE`, the previously-known cause of
  this symptom class. Fixed status 6 -> 0 (`NORMAL`) for: all 16 Imperial Treasure Retrieval
  entities (6 carriers, 9 coffers, Governor -- Mamool Ja Training Grounds, mission 16), all 26
  Qiqirn Spies (The Double Agent -- Mamool Ja Training Grounds, mission 15), Zahakahm (Imperial
  Treasure Retrieval's turn-in NPC), and a further systematic sweep of every Assault-zone
  `npc_list` row with `status=6` that is actually registered to a live instance and isn't a
  deliberately-hidden environmental fixture (Mining/Harvesting Points, GoalPoint, Moogle, Switch,
  Armoury Crate) -- 82 additional rows fixed across Ilrusi Atoll, Lebros Cavern, Leujaoam Sanctum,
  and Mamool Ja Training Grounds (see per-mission sections below for the ones with an identified
  section: Demolition Duty, Red versus Blue, Lamia No.13, Lebros Supplies, Excavation Duty, Wake
  the Puppet, Operation: Black Pearl, Azure Ailments, Imperial Code, Defuse the Threat, Breaking
  Morale, Orichalcum Survey). **Deliberately skipped**: Mamool Ja Training Grounds' 5
  `Hunched_Figure` rows -- these may be an intentional reveal-mechanic hide similar to Saving
  Private Ryaaf's Fomor decoys, not this bug; needs its own script check before touching. Reimported
  live both times. Awaiting user retest across all affected missions.

---
## Whitegate (Aht Urhgan Whitegate hub NPCs, not rank-specific)

Fixes to the shared hub infrastructure in Whitegate that every Assault mission depends on --
mission-giver NPCs, the appraisal system, and the runic portal -- rather than any one mission.

- ✅ **Runic Portal sending players to the wrong Assault zone**: `Runic_Portal.lua` does arithmetic
  on `tpz.teleport.id.AZOUPH_SP + offset` (offset from key-item order), but the teleport-ID enum in
  `teleports.lua` declared the 5 staging points in a different order than the key items -- "+2"
  landed on the wrong zone. Fixed by reordering the enum to match key-item order. **User-confirmed
  fixed.**
- ✅ **Appraisal system (Drahbah/Chochoroon/Memeroon) was entirely unimplemented** -- trading a
  "???" item did nothing. Built `scripts/globals/appraisal.lua` as a proof-of-concept
  (`tpz.appraisal.tryAppraise`), wired into all 3 NPCs. Real weighted reward data for `??? Earring`
  and `??? Box`; the other 7 "???" types politely reject with "cannot be appraised yet" (item
  returned, nothing lost) since no real odds data exists for them yet.
- ✅ **Appraisal live-test bug: wrong item obtained message** ("Obtained 1108 gil." instead of the
  item name) -- `npcUtil.giveItem`'s own notification used the player's *current zone's*
  `ITEM_OBTAINED` text id, which was wrong for Aht Urhgan Whitegate. Fixed by using
  `player:addItem({ silent = true })` directly instead, since the appraisal's own message already
  tells the player what they got.
- ✅ **Appraisal live-test bug: Drahbah introduced himself as the player's own name, "0 gil" fee** --
  `onTrigger` never passed the fee parameter the event template expects. Fixed
  (`startEvent(678, 500)` / `startEvent(260, 50)` / `startEvent(272, 500)` for
  Drahbah/Chochoroon/Memeroon respectively). **User-confirmed fix, working** -- all 3 NPCs tested
  in-game.
- 🟡 **Appraisal result was raw `PrintToPlayer` chat text, not real client dialogue** -- user
  recalled this was always a known placeholder ("pending changes to the ??? item rewards"). Root
  cause: the real result CS lines exist in the client (confirmed via dat-extractor against
  Drahbah's own dialog-table file, ROM4\0\123.DAT -- indices 5213/5214, "Hmmm... this seems to
  be..." / "I have finished appraising your item. It is `<item>`!"), and the SAME 9/10-line
  structure was confirmed to exist for Chochoroon (Al_Zahbi, ROM4\0\121.DAT, 7919-7927) and
  Memeroon (Nashmau, ROM4\0\126.DAT, 10570-10579) at different index offsets -- full mapping in
  `scripts/globals/appraisal.lua`'s header. Three fix attempts, in order:
  1. `messageSpecialFrom()` with Topaz's own `IDs.lua` text ids -- wrong number space entirely,
     rendered an unrelated message ("You currently posess 5353 scylds").
  2. `messageSpecialFrom()` with the real client ROM index (5214) directly -- sent without error,
     but the item-name substitution embedded in that line (several undecoded "Possible Special
     Code" markers -- POLUtils' own placeholder for bytes it can't interpret) never resolved;
     rendered a blank where the name should go. `CMessageSpecialPacket` only carries 4 raw uint32
     params with no per-message spec anywhere in this codebase for what those special codes
     consume -- genuinely unimplemented plumbing, not a param-ordering bug.
  3. LandSandBoat-style CS re-trigger -- `player:startEvent(appraisalCsid, 1, appraisedItem)`,
     hypothesizing the client's own event bytecode would branch to the result lines given a
     different option/param, same as LSB's own `appraiseItem()`/`appraisalOnEventFinish` pattern.
     **Live-tested and disproven**: the client just replayed the intro dialogue from scratch, with
     "1" read as the fee parameter ("...for the low, low price of 1 gil!") instead of a branch
     selector -- Topaz's `startEvent`/event execution does not honor LSB's param semantics here.
  **Final compromise, user-confirmed working**: `messageSpecialFrom()` for the "thinking" line only
  (5213/7926/10578 per zone -- no item-name substitution needed in this one, so it renders as real
  client dialogue), followed 2 seconds later (`npc:timer`) by the existing `PrintToPlayer` result
  text with the actual item name. Real item-name substitution in client dialogue remains
  unimplemented -- would need a proper reverse-engineering pass on either the special-message
  packet's control codes or the CS event bytecode's real branching mechanism. Not pursued further
  this session.
- ✅ **Rytaal's mission-complete/failed dialogue used wrong text ids** (`RYTAAL_MISSION_COMPLETE`/
  `RYTAAL_MISSION_FAILED` in `IDs.lua`, 5658/5659 -> corrected to 5652/5653) -- same class of
  client-version text-ID drift found across the 5 Assault zones' own dialogue this session.
- 🟢 **New feature, 2026-08-19**: user asked to restrict which Assault mission ranks are offered by
  the 5 mission-giver NPCs (Yahsra/Isdebaaq/Famad/Lageegee/Bhoy_Yhupplo) -- currently PSC+PFC only,
  ahead of releasing higher-rank missions. Added a single toggle, `ASSAULT_MAX_RANK` in
  `scripts/globals/settings.lua` (currently `2`); all 5 NPCs now pass a capped rank to the client's
  mission-selection menu via a new `tpz.besieged.getAssaultRank()` helper instead of the real
  badge-based rank. Change that one setting to unlock more ranks later -- no other file needs
  touching. See Assault_Fix_Log.md for the full trace. Not yet tested live.
- **Note**: `Sorrowful_Sage.lua` (a 6th Whitegate NPC using the same rank-passing pattern, event
  278) was deliberately left untouched -- **user recalled it's for Nyzul Isle missions**, not one
  of the 5 real per-zone Assault mission givers, and Nyzul Isle hasn't been touched this session.

---

## WarpAssault (`!warpassault` GM debug command, Lua + C++)

`scripts/commands/warpassault.lua` -- bypasses the assault officer NPC and runic portal entirely
for testing, letting a GM enter/exit any of the 50 Assault instances (plus 6 pre-existing
non-Assault ones sharing the same table) directly by id. Built and hardened entirely this session;
several of the bugs found were real engine crashes, not just script mistakes.

- ✅ **`onInstanceCreated` defined in the command file itself silently never ran.**
  `createInstance()`'s ready callback resolves via `GetCacheEntryFromFilename(PChar->m_event.Script)`,
  which is only ever populated for NPC-triggered events -- command scripts are re-executed fresh
  every invocation through `commandhandler.cpp` and are never cached under that lookup path. Fixed
  by moving the real handler to each destination zone's own `Zone.lua` (the engine's fallback when
  `m_event.Script` doesn't resolve) instead of the command file -- see `Leujaoam_Sanctum/Zone.lua`
  for the reference implementation, replicated across all 8 zones the command can target.
- ✅ **Command silently failed unless already standing in the mission's own zone.** Same root cause
  as above -- the fallback resolves via the character's *current* zone, so entry only works if
  you're already there. Fixed by having the command auto-detect a zone mismatch, warp the player
  there, and ask them to re-run the command (zoning is asynchronous, so warp-then-enter can't be
  chained in one call).
- ✅ **`!warpassault leave` didn't actually end the instance.** Only cleared the assault-log flag
  and warped the player away, without ever calling `instance:fail()` -- the engine's own zone-in
  recovery (`CharRegistered()`) would silently reattach the player to the same stale, never-cleaned
  instance the moment they walked back into that zone by any means. Fixed to properly call
  `instance:fail()` (real `INSTANCE_FAILED` state + cleanup) before warping out, and to check the
  *live* instance (`player:getInstance()`) rather than the possibly-already-cleared assault-log
  flag.
- ✅ **Re-entering the exact instance you're already standing in crashed the server.** Calling
  `createInstance()` again while still registered to that same instance id created a second live
  `CInstance` with the same id -- the client got confused about which one it was leaving vs.
  entering when `setPos()` fired. Fixed by guarding against this case in Lua before ever calling
  `createInstance()`.
- ✅ **Real C++ crash: same-zone-id transition tripped a hard debug assert.**
  `CZone`/`CZoneInstance::IncreaseZoneCounter` both opened with
  `TPZ_DEBUG_BREAK_IF(PChar->loc.zone != nullptr)` -- on MSVC Debug builds this expands to
  `__debugbreak()`, killing the process outright with no debugger attached. The invariant holds for
  every *ordinary* zone transition, but every `!warpassault` handler calls
  `player:setPos(0, 0, 0, 0, <thisZoneId>)` -- a same-zone-id transition required because
  `createInstance()`'s ready callback only resolves via the character's *current* zone, so the
  player has to already be standing in the destination zone. Nothing else in the codebase exercises
  this path, so `loc.zone` isn't guaranteed nulled out yet when zone-in machinery re-enters. Fixed
  by recovering (clear `loc.zone`, log a warning) instead of asserting.
  `src/map/zone.cpp`, `src/map/zone_instance.cpp` (`CZoneInstance::IncreaseZoneCounter`).
- ✅ **Real C++ crash: stale double-registered character, delayed access violation.** Diagnosed from
  a live Visual Studio repro -- an access violation in `PChar->PRecastContainer->Check()` during
  `CZoneEntities::ZoneServer`'s periodic tick, with a freed-memory pointer signature. Root cause:
  `CLuaBaseEntity::setInstance()` (called by every `!warpassault` handler as
  `player:setInstance(instance)`) unconditionally overwrote `PChar->PInstance` to the new instance
  *before* the old instance's own zone-out cleanup (`DecreaseZoneCounter`) got a chance to run --
  that cleanup then read `PInstance`, found the *new* instance, and cleaned up the wrong one,
  leaving the character permanently stuck in the old, abandoned instance's `m_charList`. That
  instance never reached `CharListEmpty()`, so it was never reaped -- it kept ticking a character
  that had since moved on, and once the real `CCharEntity` was eventually freed (e.g. a later
  disconnect), that tick dereferenced freed memory. A pre-existing, never-fixed TODO comment in
  `CZoneEntities::DecreaseZoneCounter` already flagged this exact same-zone-id edge case in Russian
  ("проблемы с переходом между одной и той же зоной") -- `!warpassault` was simply the first caller
  to actually hit it. Fixed: `setInstance()` now detaches the character from any previous *live*
  instance (running its real `DecreaseZoneCounter`) before attaching to the new one, whenever old
  and new instances differ and the character is still physically in the old instance's zone.
  `src/map/lua/lua_baseentity.cpp` (`CLuaBaseEntity::setInstance`).
- **All of the above are believed fixed and were validated against real repros during this session's
  capture-mining work** (used constantly as the primary tool to jump directly to any mission for
  testing), but none have a dedicated final confirmation pass of their own -- flag here if
  `!warpassault` ever crashes or double-registers again.

---

## Misc (non-Assault fixes, needs retesting)

Everything below predates this conversation's visible history (found by walking `git log`/`git
show`, not from memory) -- surfacing it now so it's tracked somewhere and can get a real retest
pass, since none of it has a dedicated confirmation entry anywhere.

### Puppetmaster automaton attachments -- real dispatch/caching bugs fixed
Root cause, in two parts: automaton mob-skill scripts (Shock Absorber, etc.) were being routed
through the wrong C++ dispatcher (`luautils::OnPetAbility`, meant for regular pet abilities) instead
of automaton skills' own path -- and separately, neither the automaton mob-skill scripts
(`scripts/globals/abilities/pets/*.lua`) nor the attachment scripts
(`scripts/globals/abilities/pets/attachments/*.lua`) were ever pre-cached at boot the way
`ability.cpp`'s boot loop caches player-job-ability scripts from the `abilities` SQL table --
meaning every Lua lookup into them silently came back empty. Net effect before the fix: the
skill's animation would play, but its actual Lua logic (Stoneskin from Shock Absorber, Provoke from
Strobe, etc.) never ran.
- `src/map/entities/mobentity.cpp` -- routes `PET_TYPE::AUTOMATON` skills to a new
  `luautils::OnMobAutomatonWeaponSkill` instead of `OnPetAbility`.
- `src/map/lua/luautils.cpp`/`.h` -- new `OnMobAutomatonWeaponSkill`, explicitly caches the script
  file before looking it up, tries `onMobWeaponSkill` then falls back to `onPetAbility` (existing
  scripts use both export conventions inconsistently).
- `src/map/utils/puppetutils.cpp` -- attachment scripts explicitly cached before
  `OnAttachmentEquip` is called (same missing-cache bug, attachment side).
- `src/map/utils/petutils.cpp` -- **separate related bug**: `OnAttachmentEquip` (which binds each
  attachment's `AUTOMATON_ATTACHMENT_CHECK` listener) only ever ran at the moment an attachment was
  physically equipped -- since Lua listener bindings live only in VM memory (unlike the equipped
  attachment IDs themselves, which persist via DB) and equip/unequip is locked while an automaton is
  summoned, a *previously*-equipped attachment's listeners were never rebound after a relog, zone,
  or server restart. Fixed by re-firing `OnAttachmentEquip` for every already-equipped slot on
  every pet summon, not just first-time equip.
- Individual attachment scripts (`flashbulb.lua`, `reactive_shield.lua`, `shock_absorber.lua`,
  `strobe.lua`) also got real per-attachment cooldown timers added (`VanadielTime()`-based, e.g.
  Strobe/Provoke previously had **no cooldown enforcement at all** and would fire every tick
  indefinitely; Shock Absorber's old cooldown var name (`stoneskin`) collided with the Stoneskin
  buff's own duration value, an unrelated bug baked into the same local var).
- 🔴 **Needs cleanup, not yet done**: heavy `print()`/`ShowInfo("DEBUG_AUTOMATON: ...")` debug
  logging was left in throughout this whole chain (every attachment script, `automaton.lua`,
  `mobskill_state.cpp`, `mobentity.cpp`) -- functional but noisy, worth stripping before calling
  this fully done.
- 🔴 **Unclear/incomplete**: `automaton.lua`'s new `tryAutomatonAttachments(pet, target)` function
  (its own comment: "Master router called by C++ during combat ticks to check active attachments")
  currently only logs and unconditionally `return false`s -- looks like a stub or abandoned WIP,
  not confirmed whether anything in C++ actually calls it or depends on it.
- `scripts/globals/automatonweaponskills.lua` -- `calcParams.attackInfo`/`calcParams.skillType`
  added to both physical and ranged automaton weaponskill calc params. No comment explaining why;
  purpose/necessity not independently verified from the diff alone.
- Two new debug GM commands added alongside this work: `scripts/commands/loadattachment.lua`
  (bulk-reloads attachment scripts without a server restart) and `scripts/commands/stats.lua`
  (`!stats pet` -- prints an automaton's HP/MP/active status effects). Both debug-only tools, not
  meant for players.
- **Not yet retested end-to-end** since these fixes were made -- worth confirming Shock
  Absorber/Reactive Shield/Strobe/Flashbulb all actually fire their effects now, and that a relog
  or zone change doesn't silently drop a previously-working attachment again.

### `tools/dbtool.py` -- Python 3.12 compatibility fix
Used `distutils.spawn.find_executable()` to locate the `mysql` binary -- `distutils` was removed
from the Python standard library in 3.12, so this would hard-fail on any current Python install.
Replaced with the standard-library equivalent, `shutil.which()`. Low-risk, mechanical swap; no
functional behavior change if it worked before.

### Housekeeping (not a bug fix, no retest needed)
`.gitignore` updated to exclude local `conf/default/*.conf` files (contain real DB credentials),
SourceTrail project/cache files, and a few manual scratch backup files that had been accidentally
tracked (`_272.lua backup`, `_273.lua BACKUP`, two stray `shock_absorber - *.lua` scratch copies).

---

## PSC (Private Second Class)

### Leujaoam Cleansing (Leujaoam Sanctum, mission 1)
**Overall status: ✅ -- User-confirmed live 2026-08-24: the ice wall blocker is removed.** The
long-running "regression, real cause unknown" saga (below) is resolved -- root cause was the
`_1x*`/`_jx*` door-prop identifier drift bug (see the 🟡 entry further down), not a mysterious
regression. (The 🔴/🟡 bullets immediately below are earlier investigation history that led to the
original fix and the since-superseded "regressed again" theory; kept for the record.)
- ✅ Fully validated 2026-08-18 by a real capture, real WIN. Entrance, kill-all-15, and Lockbox
  reward table all confirmed exactly right. Assault points corrected (1000 guess -> real 1100).
- 🔴 *(superseded, see ✅ below)* **User-reported 2026-08-20**: blocked by a closed door, same
  symptom as Preemptive Strike and Sagelord Elimination -- a 3rd mission now showing this, and
  (like Preemptive Strike) not a mission this session ever touched directly. Reinforces the
  working theory that this is a shared/global regression, not anything mission-specific. Not
  investigated -- see the deferred deep-dive in `TODO.md`.
- 🟡 *(superseded, see ✅ below)* **2026-08-21, partial progress while investigating Orichalcum
  Survey's near-identical `_1XO` corridor bug**: assumed this mission's own door prop was `_1XN`
  (renamed `ROCK_PROP_1XN`) and gave it the exact same fix as `_1XO` -- a real `npc_list` row that
  was never registered in `sql/instance_entities.sql` for instance 1. `zone:checkNavPath()` across
  this corridor separately returned `pathFound=true, waypoints=1`, so the navmesh was never the
  blocker either. **This assumption turned out to be wrong -- see 2026-08-22 below.**
- 🟡 *(superseded, see ✅ below)* **2026-08-22, user-tested, ruled out the missing-registration
  theory for `_1XN`**: user substituted `ROCK_PROP_1XO` (confirmed working correctly elsewhere) at
  `_1XN`'s position specifically to test whether a known-good prop would open it there. It did not.
- ✅ **2026-08-22 (later), root cause fully resolved via fresh NPCLogger cross-reference mining**:
  ran the crossref pipeline fresh against 2 independent real Leujaoam Cleansing captures (Thris
  Nov2025 + FL rank). Both agree: **`_1XN` never appears in either capture at all.** It was never
  part of this mission's real path -- the entire `_1XN` investigation (2026-08-21 fix attempt,
  2026-08-22 substitution test, the earlier "same as Brittle Rock 4/5" theory) was chasing an
  entity that simply isn't real for Cleansing. The mission's actual real door-prop set is exactly
  3 entities, and **all 3 were already correctly wired with no changes needed**: `_1XO`
  (17060143, real captured position/animation/entityFlags -- `357.0,-7,59.0`, anim `8`, flags
  `6147` -- match its own `npc_list` row exactly), `_1XW` (17060151), `_1XX` (17060152). This also
  resolves the long-standing open question left in `IDs.lua`'s `ROCK_PROP_1XO` comment ("Is this
  even right? ... Should be 1xn??") -- yes, `_1XO` was correct all along. All dead `_1XN` handling
  removed from `instances/leujaoam_cleansing.lua`; the stale uncertainty comment in `IDs.lua`
  resolved. This mission needed zero further SQL/Lua changes -- the "blocked door" symptom
  reported 2026-08-20, whatever its real cause, was not the `_1XN` prop; if it recurs on retest,
  it's a different, not-yet-identified cause and should be investigated fresh rather than
  reopening the `_1XN` line of inquiry.
- **User follow-up, resolved: where did `_1XN` actually come from?** It genuinely wasn't invented
  data -- `_1XN` (17060142) is a real entity, just for different missions. It's confirmed real for
  **Shanarha Grass Conservation** (instance 4) and **Supplies Recovery** (instance 6), captured at
  `~198,-11,139` in both. Its `npc_list` row, though, had been sitting at `357.198,-7.931,59.770`
  -- **`_1XO`'s real position, not its own** -- likely a stale copy/mixup from an earlier pass
  investigating `_1XO`. That's exactly why it looked like a Cleansing match: its (wrong) listed
  coordinates happened to sit right on top of a real Cleansing corridor. Fixed: `npc_list.sql`'s
  position corrected to the real `198.000,-11.000,139.000` (also corrected `animation` 8 -> 9 to
  match the real capture), and the incorrect `instance_entities` registration to instance 1
  removed (instances 4 and 6 were already correctly registered and untouched). Neither
  Shanarha_Grass_Conservation.lua nor Supplies_Recovery.lua reference this entity manually, so it
  spawns from its own now-correct `npc_list` defaults with no override needed, same pattern as
  every other correctly-working door prop this session.
- Worth noting for the deferred `TODO.md` "shared/global door regression" theory: this result is
  evidence *against* a single shared cause across Preemptive Strike/Sagelord Elimination/Cleansing
  -- Cleansing's reported block, whatever it was, wasn't `_1XN`-related at all, so grouping these 3
  reports together may have been a coincidence of symptom description rather than a shared root
  cause. Re-examine that theory with this in mind.
- ✅ **THE ACTUAL ROOT CAUSE, found and confirmed 2026-08-22 (later)**: earlier in this pass it was
  claimed `_1XO`'s own `npc_list` position already matched its real capture -- **that was wrong**,
  a misread during the `_1XN` investigation. Re-verified all 3 real Cleansing door props against
  fresh capture data directly:
  | Prop | Real (capture) | Was in `npc_list` |
  |---|---|---|
  | `_1XO` (17060143) | 357, -7, 59 | -460.054, -32.172, 120.370 (= `_1XP`'s real spot) |
  | `_1XW` (17060151) | 240, -12, 139 | 281.197, -40.077, 220.323 |
  | `_1XX` (17060152) | 280, -40, 220 | -360.001, -8.482, -379.952 |

  All 3 were wrong. `_1XO` in particular had been sitting at a remote, unrelated part of the map
  instead of the corridor it's meant to unlock -- this is the real cause of the reported blocked
  corridor, not any registration or `_1XN` issue. `_1XX`'s wrong value is notable: an earlier
  session comment already documented this exact 877.8-yalm-drift fix as applied, but the value in
  the file was still wrong -- almost certainly caught in the earlier session-wide bulk
  coordinate-drift revert along with everything else in that batch. All 3 corrected to their real
  positions in `npc_list.sql`. **User confirmed live: the corridor is now open.**
- 🔴 **REGRESSED, 2026-08-22 (later), root cause not found.** User re-tested and the corridor is
  blocked again, at the same spot, with **no further edits to `_1XO`/`_1XW`/`_1XX` or their
  `instance_entities` registrations at any point between the confirmed-open test and this one.**
  Full re-verification performed, all clean:
  - Connected directly to the **live MySQL database** (not just the source `.sql` files) and
    confirmed `npc_list` positions/animation/entityFlags for all of `_1XN`/`_1XO`/`_1XP`/`_1XW`/
    `_1XX` exactly match the fixed values, live, right now.
  - Confirmed `instance_entities` for instance 1 live-matches source (`_1XO`/`_1XW`/`_1XX`
    registered).
  - `status` field confirmed `0` (`tpz.status.NORMAL`) for `_1XO` -- correctly visible, not hidden.
  - Checked for any *other* entity within 15 yalms of `_1XO`'s exact spot that could be a
    conflicting duplicate -- none found.
  - User performed a full server bring-down/restart (not just a reimport or reconnect) and
    re-tested -- still blocked.
  - Confirmed via normal NPC-triggered entry (not the custom `!warpassault`-style GM command) --
    ruled out a GM-warp-specific instance-creation quirk.
  - **Tested and ruled out**: `_1XO` being simultaneously registered to both instance 1 (Cleansing)
    and instance 2 (Orichalcum Survey) -- removed from instance 1 only, reimported, retested.
    Orichalcum Survey (which was also separately reported blocked again around the same time -- see
    that mission's own entry) showed **no change** with `_1XO` singly-registered. Reverted back to
    dual-registration (not the cause, and Cleansing needs the entity present regardless).
  - User was explicit that this is not a misattributed-alternate-route situation (unlike Preemptive
    Strike's resolution) -- the corridor was re-tested specifically after the `_1XO`/`_1XN`
    instance-move work, confirmed working at that point, and has since regressed with nothing
    relevant changed in between.
  **Status: open, real cause unknown.** Every lever checked so far (position, animation, flags,
  status, registration, duplicate-entity check, dual-instance-registration) is confirmed correct
  or ruled out. Whatever changed between the confirmed-open test and now has not been identified.
  Orichalcum Survey regressing at the same time, sharing the same `_1XO` entity, is a strong hint
  the two are related -- but the shared-entity theory (dual registration) has itself been tested
  and ruled out. Worth considering next: whether something *else* changed zone-wide around the
  same time (a different SQL/Lua edit to Leujaoam Sanctum, a migration, a cache/reload quirk not
  yet identified) rather than continuing to focus on this specific entity's own data, which has now
  been exhaustively re-verified correct multiple times.
- 🟡 **Likely real root cause found, fix applied 2026-08-24, pending live validation**: this
  "regression with no identified cause" was likely never a regression at all -- it's the exact
  same `_1x*`/`_jx*` door-prop identifier drift bug root-caused and fixed for Mamool Ja Training
  Grounds (Breaking Morale) the same day, which the user has since confirmed live and working
  there. The mystery `_1XO` entity is exactly this class of prop. Applied the same methodology
  here: cross-referenced this zone's `_1x*`/`_jx*` rows in `npc_list.sql` against `FFXI-DATS`'s
  real client door/object positions (`D:\Claude\FFXI-Tools\FFXI-DATS\Info\Door or Objects.json`)
  via one-to-one nearest-neighbor XZ matching (confirmed identity transform for X/Y/Z, see
  `ffxi_client_to_topaz_coord_transform` memory), using the new general-purpose script
  `D:\Claude\FFXI-Tools\fix_zone_door_props.py 69 --apply`.
  **Important correction mid-pass**: this tracker's own prior entries for `_1XO`/`_1XW`/`_1XX`
  claimed exact real-capture-verified values that directly contradicted the FFXI-DATS-driven fix
  for 2 of those 3 rows (`_1XO`/17060143, `_1XX`/17060152) -- FFXI-DATS is confirmed to be from a
  *different client version* than ours (see `ffxi_zone_database` memory's `id_drift` finding), so
  trusting it blindly risked undoing already-correct work. **Decision**: rather than trust either
  source's documentation over the other (this tracker's own claims have flip-flopped multiple
  times across this investigation), applied the fix in full and left it to the user to validate
  live and report back what's actually broken/working -- real gameplay testing is more reliable
  at this point than any written record on either side. **51 of 52 candidate rows fixed**
  (renamed to the correct real identifier + full-precision real X/Y/Z, or -- for rows with no
  confident real-position match that would otherwise collide with a confident row's new name --
  renamed to a `_dup<npcid>` placeholder rather than silently overwritten; see the script's own
  collision-safety logic). Backup at
  `D:\Claude\FFXI-Tools\ffxi\reference\npc_list.sql.bak-before-all-assault-zones-fix`. **1 row
  left genuinely untouched** (`17060146` `_1xr`, no candidate within confidence threshold).
  **User confirmed live 2026-08-24: Leujaoam Cleansing and Orichalcum Survey's ice wall blockers
  are removed.** User continuing a full pass through the rest of Leujaoam Sanctum's missions to
  identify what's still broken vs fixed and report back -- **do not mark any other Leujaoam
  mission's door-prop status resolved until that live report comes in for each.**
  This confirms Preemptive Strike's and Sagelord Elimination's
  earlier "closed door" reports (both in Mamool Ja Training Grounds, already fixed via the same
  root cause) and Orichalcum Survey's `_1XO`-sharing regression here were **all the same bug**,
  not independent issues or a shared-entity registration problem.

### Imperial Agent Rescue (Mamool Ja Training Grounds, mission 11)
**Overall status: ✅ COMPLETE** -- **User-confirmed live 2026-08-27**: gates break and open
correctly, Brujeel's full reveal/dialogue/fade sequence plays cleanly, Pot Hatch lid animates
correctly, per-job Warder skills (Axe Throw/Stave Toss/Rushing Drub/etc.) work as intended. Two
real, non-blocking issues remain open and are intentionally left logged below for future
reference rather than resolved here (user explicitly asked to keep them on record): the
`Axe Throw`/`Stave Toss` animation-hang bug (cosmetic only, skill/damage still applies correctly)
and the BST Warder pet-summon engine gap (`call_beast` non-functional game-wide, not specific to
this mission). Neither blocks the mission itself.
- ✅ Entrance position was wrong -- **user-reported 2026-08-18** ("spawn location incorrect, no
  mobs in the zone"). Root cause: `instance_list.sql` was using the same generic zone-default
  placeholder as 8 other Mamool Ja missions, ~300+ units from the real gate/Warder cluster. Fixed
  using real capture PathLog data. Everything else (gates/Warders mechanic, lockbox rewards,
  Assault points) was independently validated correct by the same capture.
- ✅ **User-reported 2026-08-18**: invisible walls / unopenable doors at several specific
  coordinates along the corridor. All traced to real door props (`_1u5`/`_1u6`/`_1u7`,
  `_ju0`-`_ju7`) that already existed in `npc_list.sql` with correct real position data (three
  already wired into `Dilapidated_Gate.lua`'s door-hiding logic) but were never registered to
  this instance in `instance_entities.sql` at all -- none of them had ever actually spawned.
  Fixed by registering all 11. Not a position/data bug -- a missing wiring step.
- ✅ **User-reported 2026-08-18**: `_1u6` (159,2,-420) rendered open/passable but led into an
  unused area belonging to a different Assault mission in this shared zone -- wasn't actually
  paired to anything in this mission (unlike `_ju3`/`_ju5`/`_ju7`, which position-match the 3 real
  gates exactly). Removed from this instance's registration entirely.
- ✅ **User-reported 2026-08-18**: `_1u5` (121,2,-499) rendered closed/impassable but should be
  open (unlike `_1u6`, does belong here -- position matches a real reported passage, just isn't
  one of the 3 objective gates). DB default is already `animation=8` (open), forced explicitly at
  spawn to match the same treatment given the 3 real gates. Not yet confirmed fixed live.
- 🟡 The 3 real gates (`_ju3`/`_ju5`/`_ju7`) render open by default despite `animation=9`
  (closed) both in the DB and forced explicitly at spawn -- root cause still unconfirmed (traced
  the full spawn-packet code path, everything checks out server-side on paper).
- ✅ **User-reported 2026-08-18**: gates never took any damage at all, even from nearby Warder
  Firespit hits. Root cause: `firespit.lua`'s `onMobWeaponSkill` only ever damages the single
  engine-provided `target` -- the gate was never a candidate at all, so no amount of DEF/MDEF
  tuning could fix it. Added real splash-damage logic (instance-11-guarded) to that shared mob
  skill file -- see Assault_Fix_Log.md. Not yet confirmed working live.
- 🟡 Still open: confirm gates actually take real damage now and eventually break, and confirm
  the still-unresolved "renders open by default" item above -- mark fully resolved only once
  both are verified end-to-end in-game.
- ✅ **User-reported 2026-08-19**: luring a Warder too far from spawn despawns it (engine leash
  behavior) -- now load-bearing for the gate-splash mechanic. Fixed with `MOBMOD_NO_DESPAWN`,
  scoped to instance 11.
- ✅ **Re-confirmed 2026-08-19**: user recalled this same class of bug making the mission
  unclearable in an earlier playthrough (pulled Warders too far, they despawned, gates never took
  splash damage). Re-checked `Mamool_Ja_Warder.lua` -- the `NO_DESPAWN` fix directly above already
  covers all 11 Warders in this instance's roster (`mob[2]` in `IDs.lua`), so this was from before
  that fix landed. No further code change needed.
- ✅ **User-reported 2026-08-22**: Dilapidated Gate's nameplate was visible, should be hidden.
  `mob_pools` poolid 1037's `namevis` was `0` (bit `0x008`/`FLAG_HIDE_NAME` clear); set to `8`.
- ✅ **User-reported 2026-08-22**: Brujeel spawned facing an arbitrary direction (the hatch prop's
  static rotation) instead of the player who found him. Added `brujeel:lookAt(player:getPos())`.
- ✅ **User-reported 2026-08-22**: Rune of Release activated (`instance:complete()`) immediately on
  reveal, before Brujeel's ~25s rescue dialogue sequence even started playing. Moved the
  `instance:complete()` call into the last dialogue timer's callback.
- ✅ **User-reported 2026-08-22**: gate-splash damage (Firespit/Stave Toss) still never actually
  hit a gate -- 10 real Firespit casts, zero damage logged. Root cause: the proximity check
  measured distance from `target` (the player who got hit), not `mob` (the Warder actually
  casting the skill, realistically stationed near its own gate). Fixed both files to check
  distance from `mob` instead. This directly follows up the still-unconfirmed 2026-08-18 splash
  fix above -- that one built the mechanism, this one fixes why it never actually triggered.
- ✅ **User-reported 2026-08-22 (later)**: gate would open (correct animation, briefly passable)
  then revert to impassable on its own. Root cause found via screenshot showing the door prop
  itself was targetable and clickable: `_ju7` (paired with GATE_3, position-confirmed) had
  `entityFlags = 4099`; its siblings `_ju3`/`_ju5` (paired with GATE_1/GATE_2) both correctly have
  `6147` -- the difference is exactly `FLAG_UNTARGETABLE` (`0x800`/2048), missing only on `_ju7`.
  That let players click it directly, firing the engine's default door-toggle animation
  independent of `Dilapidated_Gate.lua`'s real `onMobDeath` break logic, which then reverted since
  nothing backed the state change. Fixed `_ju7`'s `entityFlags` to `6147`.
- ✅ **User-reported 2026-08-22 (later)**: even after the `_ju7` fix and the earlier splash-damage
  distance-check fix, gates still never took damage. Real root cause: both `firespit.lua` and
  `stave_toss.lua`'s splash logic gated on `instance:getID() == 11` -- `CInstance::GetID()`
  (`instance.cpp:64`) returns `m_instanceid`, the runtime per-zone-session instance *slot* number
  (increments arbitrarily as instances are created since server boot), not a fixed mission
  identifier. `== 11` only ever matched by coincidence in one earlier test session. Switched to
  `mob:getZoneID() == 66` (Mamool_Ja_Training_Grounds), matching this codebase's existing
  convention for scoping shared mobskill files to a zone (`foul_breath.lua`/`frost_breath.lua`/
  `ice_roar.lua`). Gate splash damage/breaking is now believed fully functional end-to-end.
- 🟡 **Pot Hatch lids not animating on search** -- traced but not conclusively resolved. Script
  logic (`_pot_hatch_common.lua`) is correct and unchanged, calls `setAnimation(90)` matching the
  confirmed-working `Ancient_Lockbox.lua` convention; the 3 Pot Hatch `npc_list` rows'
  `entityFlags=4099` has never changed in git history, not a regression. Their `look` model byte
  pattern is completely different from `Ancient_Lockbox`'s, so can't rule out the model itself
  lacking a reachable open-animation state -- same category of dead end as Golden Salvage's Mimic
  lid. Since this symptom was observed during the same window as a stale-DB issue and the `_ju7`
  bug above, worth a clean retest before assuming it needs the same AltanaView/capture
  investigation the Mimic lid got.
- **Note on 2 self-inflicted mistakes while fixing the nameplate item above**: first pass
  miscounted `mob_pools`' 25 columns and trimmed the Dilapidated_Gate row to 24 values (import-
  blocking `Column count doesn't match value count` error) -- fixed. Second pass then set the
  wrong column (`spellList` instead of `namevis`), leaving the nameplate fix never actually applied
  and adding a bogus `spellList` that caused new `mobutils::CalculateStats ... has no mp for
  casting spells!` warnings -- caught on live retest and fixed for real (`spellList` back to `0`,
  `namevis` correctly set to `8`). Both self-contained to this one row; not user-facing beyond the
  temporary import failure and log spam.
- ✅ **User asked 2026-08-26**: do the Mamool Ja Warders lack per-job weapon skills (Axe Throw for
  BST, Stave Toss for WHM) for the same reason as the Lamiae's shared-skill-list gap? Confirmed
  yes for the DATA (all 3 job variants -- bst/whm/nin -- shared one skill_list_id, 176), but
  checked against LandSandBoat upstream and this is NOT the same architectural engine limitation
  Lamiae has -- LSB genuinely implements this via a separate per-job `skill_list_id` (its own
  `176`='MamoolJa' base list for bst/nin, `177`='MamoolJaMage' for whm), and Topaz's schema
  already supports that fine; the data was just incomplete/miswired. Found Topaz already had the
  real missing skills (`javelin_throw`/`axe_throw`/`vorpal_blade`/`rushing_slash`/`rushing_stab`,
  same `mob_skill_id`s as LSB) sitting fully-stat'd but commented out in `mob_skills.sql`/
  `mob_skill_lists.sql` -- same disabled-content pattern already seen elsewhere this session.
  Uncommented and wired all 5 into list `176` (BST/NIN Warders now have the real 9-skill
  'MamoolJa' set). `177` itself was already reserved for a different Mamool Ja variant
  (`Mamool_Ja_Hussar`/`Searing_Vogaal_Ja`, Paladin-class per user) with an empty list -- used a
  fresh id (`1149`) for a new `MamoolJaMage` list instead, matching LSB's real composition
  (`rushing_drub`/`forceful_blow`/`somersault_kick`/`firespit` 30' range/`warm-up`/`stave_toss`)
  built from Topaz's own existing skill ids, and repointed `Mamool_Ja_Warder_whm`
  (poolid 5466) to it. `pw_groundburst` (1738) deliberately left disabled for both lists --
  confirmed real (FFXIclopedia: "Expels a fireball... only used by notorious monsters, and from
  any Mamool Ja in besieged") but out of scope for regular Warders, matching LSB.
- ✅ **Found while restoring the above**: `stave_toss.lua` already had the exact same real
  splash-damage mechanic and the exact same root-cause-#3 bug as `firespit.lua` (computed damage
  against the player, not the gate) -- but was previously unreachable dead code since no Warder
  could ever actually use `stave_toss` at all. Now that the WHM Warder genuinely has it (via the
  new `MamoolJaMage` list above), fixed the same way as Firespit: separate physical-damage
  calculation against the gate's own DEF. `firespit.lua`'s own fix (mob skill hooks resolve by
  skill *name*, not id) automatically covers the WHM Warder's `firespit` variant (id `1923`) too,
  no extra wiring needed.
- ✅ **User asked 2026-08-26 (later)**: since the WHM Warder needed its own skill list, does the
  rest of the Mamool Ja family (66 pools, familyid 176) have the same gap? Cross-referenced every
  member's `mJob` against the real FFXIclopedia job split for Firespit (`(BLU, BST, DRG, NIN,
  THF)` = base skillset, `(BLM, WHM)` = Mage skillset) and found 18 more pools (7 more WHM, all 10
  BLM) still wired to the base `176` list -- repointed all to `1149`. Also caught and fixed a real
  data error surfaced along the way: `Mamool_Ja_Farrier` had `mJob=1` (WAR) in Topaz, but real wiki
  data confirms its actual job is White Mage (LSB's own skill-list assignment for Farrier had been
  right all along) -- corrected `mJob`/`sJob` to 3 and moved it onto the Mage list too, for 20
  total pools on `1149`. Also gave `axe_throw`/`javelin_throw` their real thrown-weapon range
  (7.0 -> 15.0, matched a placeholder-vs-LSB mismatch caught while cross-checking). Per user
  direction, Axe Throw/Stave Toss now destroy a Dilapidated Gate in one hit (custom override,
  `nearbyMob:getMaxHP()`, applied only to the gate) while Firespit takes 3-4 hits (30% max HP per
  hit) -- new `axe_throw.lua` built (previously had no script at all, real skill was just
  disabled/unwired), `stave_toss.lua` updated to match. All data-only (SQL + Lua), no C++ rebuild
  needed. Not yet live-tested.
- ✅ **User live-tested 2026-08-27**: Axe Throw, Stave Toss, Rushing Drub confirmed used and
  dealing damage; gate confirmed destroyed by both Stave Toss and Axe Throw. Also surfaced 3 new
  real bugs from that same test, all addressed:
  - Weapons not visually lost on use for either skill (Stave Toss's existing `setAnimationSub(1)`
    apparently isn't rendering as disarmed for this model; added the same call to `axe_throw.lua`,
    which had none at all). Server-side flag write looks correct by static reading; whether
    `animationsub=1` is really this model's "no weapon" state is unconfirmed -- use `!mobsub <id>`
    on a live Warder to test other values if 1 still doesn't show anything.
  - Vorpal Blade/Axe Throw/Rushing Stab render as a "dice roll + number over head" placeholder
    instead of a real swing. Root cause found: `mob_anim_id` (not `mob_skill_id`) was wrong for
    all 3 -- 1480/1481/1584, a completely different numeric range from every other skill in the
    family (1147-1155). Corrected to LSB's real values (1154/1155/1148).
  - Gate visually destroyed but stayed impassable. `Dilapidated_Gate.lua` only ever hid the door
    prop (`setStatus(DISAPPEAR)`), never touched `animation` -- the field that actually governs
    collision (same finding as this session's other door-prop work). Added explicit
    `setAnimation(8)` on gate death, a real persisted change (unlike the old client-side
    click-toggle the user saw revert on its own in an earlier bug-era test).
  - Also fixed, unrelated to the gate itself: Brujeel's name never prepended in his rescue
    dialogue -- `messageText`'s C++ sources the shown-name decision from the *object* argument
    passed in, not the speaker (its own comment: "if a character is passed as the object, we will
    not display the name"); `_pot_hatch_common.lua` was passing `player` as that argument.
    Fixed to `brujeel:messageText(brujeel, ...)`, the working convention used elsewhere in this
    codebase.
  - ✅ Firespit still reported not breaking a gate after 4 hits despite the 30%/hit math making
    that should-be-impossible -- the added diagnostic (`[FIRESPIT GATE HIT]`) found the real
    root cause: the gate genuinely recovered 866 HP (maxHP*0.1 x2, exact) in the 46s between two
    logged hits. `CMobEntity`'s idle-roam AI (`mob_controller.cpp`) calls `Rest(0.1)` -- a real
    10%-of-maxHP heal -- on its roam cooldown for any mob not gated by `MOBMOD_NO_REST`, and the
    gate (`NO_MOVE`, autoattack disabled, never truly "in combat") kept landing in that idle
    branch between Warder casts. Never disabled since a destructible prop was never expected to
    rest at all. Fixed with `mob:setMobMod(tpz.mobMod.NO_REST, 1)` in `onMobSpawn`. Same latent
    bug found and fixed on Excavation Duty's `Brittle_Rock.lua` too (identical pattern, likely
    much less noticeable there since real player damage typically dwarfs a 10% heal). Diagnostic
    print left in place pending one more live confirmation, then remove.
- ✅ **User-corrected 2026-08-27, real regression in the per-job restoration above**: per the real
  FFXIclopedia "Aht Urhgan Areas" special-abilities table, `<Weapon> Throw` and
  `Rushing Drub/Slash/Stab or Vorpal Blade` are each exactly ONE variant per mob matching its
  actual wielded weapon -- NOT a shared pool every non-mage job draws from, which is how the
  176 list had been built. Confirmed live: NIN Warders (no axe, no spear) were using both Axe
  Throw and Rushing Stab. Checked whether `mob_pools.modelid` encodes per-slot equipment (would
  give the real weapon per job directly) -- every slot past the base model id is zero for these
  pools, so weapon appearance is baked into the model asset itself, not derivable as data. Pulled
  `javelin_throw`/`axe_throw`/`vorpal_blade`/`rushing_slash`/`rushing_stab` back out of the shared
  176 list (back to the universal-only 4: forceful_blow/somersault_kick/firespit/warm-up -- this
  is what Warder_nin now uses). Split `Warder_bst` (poolid 5465) onto its own new list
  (`MamoolJaAxe`, 1150) with axe_throw specifically, since that one WAS user-confirmed correct --
  scoped to just this one pool, not rolled out to the other 9 mJob=9 family members yet pending
  more confirmation. `javelin_throw`/`vorpal_blade`/`rushing_slash` remain unassigned to any
  Warder pool until real per-job weapon data is available -- open follow-up, not urgent since
  nothing currently uses them incorrectly.
- 🟡 Still open, not yet fully re-tested end-to-end after all of the above -- worth one full
  clean playthrough to confirm all 3 gates break correctly, weapon-loss visuals, and the 3 fixed
  animations. Pot Hatch lid animation also still needs a clean retest (see above).
- 🔴 **User asked 2026-08-27: BST Warder should summon a pet -- confirmed real engine gap, not a
  quick fix.** `Mamool_Ja_Warder_bst` (poolid 5465, mJob 9) is in this mission's roster.
  `SetupJob()` (`src/map/utils/mobutils.cpp`) correctly defaults `MOBMOD_SPECIAL_SKILL` to 1017
  (`call_beast`) for any JOB_BST mob, and the AI does periodically try to use it -- but
  `call_beast.lua`'s own `onMobSkillCheck` blocks it unless `mob:getPet()` is non-nil, and
  `spawnPet()`'s `TYPE_MOB` branch (`lua_baseentity.cpp:10877`) requires `PMob->PPet` to already
  be a valid pointer or it just logs an error and does nothing. **`PMob->PPet` is never assigned
  anywhere in this entire codebase** -- no Lua binding writes to it, no C++ init path sets it, and
  a full-codebase grep for `spawnPet()` usage in every mob script turns up zero callers besides
  `call_beast.lua` itself. This means Call Beast is currently non-functional for every BST-job mob
  in the whole game, not just this Warder -- a genuine missing piece (no way to define/link a
  specific pet identity to a mob), not a data-wiring gap like the skill-list fixes above. Real fix
  needs a new Lua-callable "set this mob's pet" mechanism plus real data on what pet each BST
  Mamool Ja should actually summon -- scoped but not started, flagged here rather than attempted
  as a quick patch given the size. Not urgent to game-breaking-ness of this mission (BST Warder
  still fights and uses its other skills fine without a pet).
- 🔴 **User-reported 2026-08-27: real animation-hang bug on `Axe Throw`/`Stave Toss`, unresolved,
  needs a packet capture to pin down.** The FIRST use of either skill in a fresh instance plays
  correctly; every SUBSEQUENT use (by any Warder, not just the same one) hangs after a windup
  with no finishing animation (mechanically the skill/effect still applies); leaving and
  re-entering the instance resets it, and exactly one more use then plays correctly again.
  **CORRECTED, 2026-08-27 (later)**: originally suspected this was a cross-cutting bug shared
  with Pot Hatch/Brujeel's `entityAnimationPacket()` FourCC calls (`"open"`/`"deru"`/`"kesu"`) too,
  reasoning that two different packet systems hitting the same "first-only" pattern implied one
  shared cause. **Ruled out via live testing**: `!fourccanim` A/B testing confirmed `"deru"`/
  `"kesu"` genuinely work correctly and repeatably (they're simply state-dependent transitions --
  `"deru"` only animates an entity actually in `DISAPPEAR` status, not a no-op bug) -- the Pot
  Hatch and Brujeel warp fixes both landed clean on that basis (see their own entries) and the
  Ancient Lockbox's real "light/sparkle then disappears" animation is now user-confirmed working
  across every zone sharing it. This narrows the animation-hang bug to `ACTION_MOBABILITY_FINISH`-
  style weaponskill/mobskill-finish packets specifically (`src/map/packets/action.cpp`) -- NOT a
  shared FourCC/`CEntityAnimationPacket` issue. Checked `action.cpp` for an obvious static/shared
  counter -- none found. Tried comparing against LSB upstream, but LSB has since fully
  restructured its packet code into per-opcode `c2s`/`s2c` files (e.g. `0x028_battle2.cpp`), so a
  direct diff isn't the quick win it was for `entity_update.cpp` -- nothing suspicious found there
  either in a targeted search. **Next real step, not started**: a live packet capture across a
  repro -- one working first-use and one broken second-use of the same skill, byte-compared -- to
  find what actually differs. Not attempting further guesses given the real client crash caused
  by an earlier unverified animation-value guess this same session (see the gate-destruction-
  animation entries above).
- 🟢 **3 real `Mamool_Jas_Lizard` mobs fixed 2026-08-25** (`17047555`/`17047558`/`17047562`) via
  the npclogger cross-reference pass -- real `mob_spawn_points` rows already existed but 2 of 3
  were still placeholder positions and none were registered to this instance. Fixed positions and
  registered all 3. Not yet SQL-reimported or live-tested.

### Excavation Duty (Lebros Cavern, mission 21)
**Overall status: ✅ -- User-confirmed live 2026-08-25: full 5-rock completion retested and
passed. No further blockers. Mission complete.** The 2026-08-25 zone-wide door/object-prop
identifier-drift fix across Lebros Cavern (see Leujaoam Cleansing's entry for the methodology
writeup, and this zone's own "36 fixes + `_ir*`→`_jr*` prefix drift" finding) cleared what had
been assumed a permanent "baked client-side collision" dead end at rock 5's wall (`_ir1`/now
correctly `_jr1`). Completion threshold reverted from the temporary workaround value **4** back
to the real **5** (`excavation_duty.lua`'s `onInstanceProgressUpdate`) -- user's live retest
confirms the 5-rock win condition is correct and functions end to end. Qiqirn Mine mechanic fully
rebuilt from real capture data 2026-08-22 and user-confirmed working (damage + wall break) -- see
the Qiqirn Mine entry below.
Full round-by-round investigation history is in `Assault_Fix_Log.md` if needed -- this entry is
kept to current state only.

**✅ Confirmed fixed:**
- **2026-08-22, THE REAL Qiqirn Mine bug**: user reported mines detonate (countdown/message all
  play correctly) but produce no explosion and no damage. Root cause:
  `scripts/globals/mobskills/mine_blast.lua`'s `onMobSkillCheck` was an unconditional
  `return 0` -- a never-filled-in stub, not something broken by this session. Confirmed via
  `mob_controller.cpp:310`: `luautils::OnMobSkillCheck(...) == 0` is treated as "skill invalid,
  don't use it," silently blocking every `mob:useMobAbility(1838, rock)` call `Qiqirn_Mine.lua`
  makes -- the skill's real damage/animation logic (`onMobWeaponSkill`) was never even reached.
  Confirmed skill 1838 isn't referenced in any `mob_skill_list`, so nothing autonomously rolls it
  via AI -- only this codebase's own explicit calls ever invoke it -- so changing the check to an
  unconditional `return 1` carries no risk of unexpected use elsewhere. Also cross-checked the
  mine mob's own data (poolid 5872) against a real capture found this pass (`Lebros Cavern PSC -
  Excavation Duty`) -- exact match on model/entityFlags/animationsub/namevis, confirming that side
  was always correct. The visible mine model + this skill's own animation (`mob_skills` 1838,
  animation id 1221) together are exactly the "visual mine + bomb explosion" combination
  requested -- one fix should restore both the visual and the damage. Lua-only, no reimport
  needed.
  **Retest result: still nothing** (user reported a use-time sound now plays, new since the fix,
  but still no explosion/damage after the countdown) -- confirmed the `onMobSkillCheck` fix was
  real and had an effect, but wasn't the whole story. **2nd real bug found**: a units mismatch.
  `qiqirn_mine.lua` stored `target:getID()`/`rock:getID()` (the full 32-bit global entity id, e.g.
  17035282) into the mine's `PlayerID`/`RockID` localvars, but `Qiqirn_Mine.lua`'s detonation timer
  reads them back through `mob:getEntity()`, whose C++ binding (`lua_baseentity.cpp:8958` ->
  `CBaseEntity::GetEntity(uint16 targid, ...)`, `baseentity.cpp:134`) expects a **targid** (12-bit
  local id, 0-4095), not the full id -- passing the full id truncates/wraps into garbage, so
  `player`/`rock` resolved to `nil` every single time, silently failing the whole "still engaged
  with this rock" `if` block with no error and no message. This is why the countdown/sound played
  fine (never touches this lookup) but nothing happened after. Fixed: `qiqirn_mine.lua` now stores
  `getShortID()` (the real targid getter) instead of `getID()`. That in turn required fixing
  `Qiqirn_Mine.lua`'s own "still targeting this rock" check, which compared the raw `rockID`
  localvar (now correctly a targid) against `player:getTarget():getID()` (a full id) -- switched
  to compare against the already-resolved `rock:getID()` instead, correct regardless of the raw
  localvar's format. Both fixes needed together -- either alone would have left it broken.
  **User confirmed live: damage works, wall breaks.** Remaining gaps at this point: wrong
  countdown cadence, and no explosion sound/animation.
  **2026-08-22 (later), fully resolved via real capture data** (`Assault-ExcavationDuty-2026-7-2_17`,
  6 real runs, multiple clean complete successful detonations with full EView packet timestamps --
  the first real evidence of an actual successful Mine Blast found this session):
  - **Countdown cadence, re-confirmed**: `10...` at +2s after placement, then a genuine 5-second
    gap before `5...`, then `4/3/2/1/0` each 1s apart -- identical across every instance in the
    batch. Rewritten to match exactly (was firing every second 10 down to 1).
  - **Real two-phase detonation structure, previously unknown**: at `0...`, the mine "readies Mine
    Blast" -- this text is engine-auto-generated from `mob_skills.mob_prepare_time` via the normal
    TP-move state machine `useMobAbility()` already routes through, not something Lua needs to
    generate. Real capture shows a consistent ~5-second gap between "readies" and "uses"; our
    `mob_prepare_time` was `1500` (1.5s) -- corrected to `5000`. This is very likely why the skill
    "worked" once the other 2 bugs were fixed but felt like nothing happened -- the real cycle was
    running, just 3x faster than retail.
  - **The actual missing explosion, found**: a `FourCCString: "bom0"` animation packet (self-cast,
    mine->mine), fired ~2 seconds into the readies/prepare window in every real instance --
    entirely separate from the skill's own `mob_anim_id` field, and never fired by any previous
    version of this file. Added via `mob:entityAnimationPacket("bom0")`.
  - Total real time from mine placement to detonation: ~18 seconds, not the original 10.
  - Real damage from the skill itself is modest (8 in the cleanest observed instance) -- the
    instant full-kill layered on top (`rock:takeDamage(rock:getMaxHP())`) is user-confirmed to
    stay regardless, matching the wiki's "destroys the wall instantly" and the capture's
    near-immediate objective completion right after "uses Mine Blast."
  - `mine_blast.lua`'s `mob_anim_id` (253) was never directly capture-confirmed on its own, but
    **user confirmed live 2026-08-22: a real explosion plays before the Brittle Rock's own
    destroy animation** -- the full mechanic (countdown, readies/uses timing, `bom0` packet,
    damage, explosion visual, instant kill) is working end-to-end. Nothing further to fix here.
  Lua + 1 SQL field (`mob_prepare_time`) -- required `py -3 dbtool.py` for the SQL side.
  **User-confirmed fully functional.**
- Drahbah's appraisal event id (678 -> 679).
- Qiqirn Mine detonating without killing the rock (`rock:setHP(0)` doesn't route through the real
  death pipeline) -- fixed to `takeDamage()`.
- `_1rx`'s (Rock 1's wall) stale wrong Y coordinate -- reverted to the real, capture-confirmed
  `-43.362`.
- Rune of Release completion message switched from the generic `RUNE_UNLOCKED` to
  `RUNE_UNLOCKED_POS` (2026-08-20), matching the pattern every other Assault mission in the
  codebase uses, and now states the real grid location, F-10.

**🔴 Brittle Rock 4/5 -- confirmed real, unfixable-from-this-layer dead end (re-confirmed 2026-08-20):**
- The 2026-08-19 investigation exhausted every Lua/SQL lever (status, animation, position -- all
  byte-identical to the working rocks 1-3, confirmed via debug log) and, separately, proved the
  block persists even with **no entity of any kind** registered at those 2 coordinates --
  concluding this is static collision baked into this server's Lebros Cavern zone geometry, outside
  server-side reach.
- A 2026-08-20 restore (commit `478eb89f65`) assumed the same-day Gateway-addon discovery (the real
  fix for rocks 1-3 and several other zones' doors) also explained rocks 4/5, and re-registered them
  without re-testing that assumption specifically. **User retest confirmed it did not fix them** --
  still impassable after a confirmed kill, same as before Gateway was ever found. This regression is
  reverted: rocks 4/5 (`17035288`/`17035290`) and their wall props `_ir0`/`_ir1`
  (`17035540`/`17035541`) are removed from `instance_entities` for instance 21 again, and the
  completion threshold is back to `progress >= 3` (`excavation_duty.lua`). **Needs a DB reimport**
  (`py -3 dbtool.py`) for the SQL side to take effect.
- Mission is fully completable as-is (3 rocks). If revisited: the "removed entirely, still blocked"
  test proves the block travels with the *coordinate*, not the entity, so the likely path forward is
  relocating the Brittle Rock 4/5 objective to different coordinates -- needs real reference data
  (capture or wiki) for where retail actually places these 2 obstacles, not yet gathered.
- **2026-08-22, re-checked against a newly-found bug class**: Imperial Agent Rescue's gates had a
  real, fixable bug where one door prop (`_ju7`) was missing `FLAG_UNTARGETABLE` on its
  `entityFlags` (`4099` instead of its siblings' `6147`) -- letting players click it directly and
  trigger the engine's default door-toggle animation, independent of the real break logic, which
  then reverted. Re-examined Excavation Duty's 5 wall props for the same bug class: all 5
  (`_1rx`/`_1ry`/`_1rz`/`_ir0`/`_ir1`) already have the correct, consistent `entityFlags = 6147` --
  no odd-one-out. Also re-verified the mob-to-prop pairing itself (position match) for all 5,
  including rocks 4/5 specifically -- all exact matches, `Brittle_Rock.lua`'s `onMobDeath` maps all
  5 uniformly with no missing/broken link. **Ruled out**: this is not the same bug, and there is no
  unlinked-helper-object explanation for rocks 4/5's block. The standing 2026-08-19/20 diagnosis
  (client-rendered model collision baked into zone geometry, independent of navmesh and any
  server-side entity/state, confirmed by the "removed entirely, still blocked" test) remains the
  correct explanation. No changes made this pass.
- ✅ **2026-08-22, RE-ADDED (user request) + confirmed against a real capture for the first time**:
  user recalled rocks 4/5 being present/interactable and asked to check. No real capture existed
  for this mission at the time of the earlier investigations; user found and provided one this
  pass (`Lebros Cavern PSC - Excavation Duty`, an older-format Windower NPCLogger capture, not the
  Thris Nov2025 batch). Cross-checked `_ir0`/`_ir1` directly against it:
  | Prop | Real (capture) | `npc_list` |
  |---|---|---|
  | `_ir0` (17035540) | 300.000,-32.910,341.000, anim 9, flags 6147 | 300.000,-32.909,341.000, anim 9, flags 6147 -- exact match |
  | `_ir1` (17035541) | 339.000,-32.901,300.000, anim 9, flags 6147 | 339.000,-32.901,300.000, anim 9, flags 6147 -- exact match |

  Unlike every other case resolved this session (Imperial Agent Rescue's `_ju7`, Leujaoam
  Cleansing's `_1xo`/`_1xw`/`_1xx`), **there is no data bug here** -- both props already exactly
  match real capture data. This is the first time the "baked client-side collision, independent of
  entity" diagnosis has been checked against real data rather than just inference from a
  removed-entity test; it holds up. Re-registered rocks 4/5 + `_ir0`/`_ir1` to `instance_entities`
  for instance 21 (unchanged data, no fix applied since none was needed/possible) and restored
  `excavation_duty.lua`'s completion threshold `3` -> `5` to match the real "break all 5 walls"
  objective. The rocks are real, killable mobs again, matching user expectation -- the wall-open
  half of the mechanic for these 2 remains the same confirmed-unfixable-from-this-layer dead end,
  now with real data backing that conclusion instead of just a removed-entity test.

- 🔴 **2026-08-29: 6 Lebros Cavern door/prop ids have no capture data anywhere, mission unknown**
  -- `_1r1` (17035505), `_1r2` (17035506), `_1rj` (17035523), `_1rk` (17035524), `_1rq` (17035530),
  `_1rr` (17035531). Real `npc_list.sql` rows exist for all 6 with real positions, but none are
  registered to any `instance_entities` row, and none have an `IDs.lua` constant. Swept every
  NPCLogger capture `.db` for this zone (17 files total, including 3 Excavation Duty runs from a
  capturer, "Nobutadas," whose captures had never been mined into
  `D:\Claude\DSP-Topaz Information\npclogger_crossref`'s CSV dataset at all -- a real gap in that
  pipeline, now known) -- zero hits for all 6 raw (shift-corrected) ids in any of them. Not fixable
  from capture data; would need a live in-game `!checknav`/`!logpos` walkthrough, or a future
  capture that happens to cover them. Left unregistered rather than guessed.

### Seagull Grounded (Periqia, mission 31)
**Overall status: ✅ -- User-confirmed complete 2026-09-12.** The real escort/flee/branch/fork/fail
mechanic is fully built and has been extensively live-tested (2026-09-09/09-10/09-12), with many
real bugs found and fixed along the way (see the dated blocks below).
- ✅ Entrance position was already correct (pre-existing, mature build) -- checked 2026-08-18.
- ✅ Escort/completion mechanic and lockbox rewards (LSB-ported) both validated correct by a real
  capture. Only the zone-wide Assault-points gap applied -- fixed, real value 1210 (see
  Assault_Fix_Log.md for a later correction to 2198 from a cleaner capture read).
- 🔴 **User-reported 2026-08-19**: mission-name text showed "Commencing Leujaoam Cleansing!"
  instead of "Commencing Seagull Grounded!" -- wrong numeric param (`1` instead of `31`) passed to
  `messageSpecial`. Fixed.
- 🔴 **Major rebuild needed, in progress**: the real escort mechanic (Excaliace cannot be
  controlled, moves at checkpoint-gated speed tiers, garlic-stop/escape-catch behavior, paired-room
  investigation, aggro-triggered fleeing) was never actually implemented -- `Excaliace.lua`'s
  waypoint table had a fatal Lua syntax error (missing every comma), so the whole file failed to
  load. Fixed the syntax and built the core checkpoint/garlic/escape state machine for real (see
  Assault_Fix_Log.md). Checkpoint positions are still an approximation (sampled at a fixed 18-yalm
  spacing, not individually confirmed retail checkpoint coordinates), but **2026-08-23: the
  underlying real path data got much better** -- found the same local capture's own full PathLog
  (`Excaliace/17006593.csv`, 648 raw waypoints across 24 real movement legs spanning the actual
  full mission) sitting unused; previously only a single ~67-point starting segment was being used
  (sourced from a more limited capture read). `FULL_PATH` now covers the real full route instead
  of just its first leg, so the sampled checkpoints span the whole mission, not just the opening
  stretch.
  **2026-08-23, 9 real checkpoints found**: user suggested correlating "Someone's been eating too
  much garlic..." lines against Excaliace's position at that moment, to find real checkpoints
  directly rather than approximating. Applied retroactively to the existing capture's per-tick
  NPCLogger position history (not just a final snapshot) -- found 9 real, exact checkpoint
  coordinates this way (of the real "about 30"). `Excaliace.lua`'s `CHECKPOINTS` now snaps the
  nearest sampled-approximation point to each real one instead of leaving it approximate, upgrading
  fidelity at exactly those 9 spots while the rest of the route still uses the fixed-spacing
  approximation. Downloaded a 2nd, genuinely independent capture (Siknawz) hoping for more --
  found 6 more real garlic timestamps, but that capture's format only has a single final-position
  snapshot (no per-tick history), so no additional coordinates could be extracted from it. 2 more
  zips the user added this same pass were confirmed duplicates of already-used captures.
  User also provided a full, precise walkthrough of the room-investigation (3 room pairs, 9
  Arrapago Crabs total across possible occupied rooms) and second-half fleeing mechanics (100%-
  speed flee for "about two map squares" then a real ~40s rest, 3 more Debauchers with real
  spawn-side rules, win condition is the NW corner of F-11 specifically) -- documented in full in
  `Excaliace.lua`'s TODO block, much more precise than the wiki source already there, but still
  not built -- needs real per-room/per-path position data no available capture covers yet. Not yet
  confirmed working live.
  **2026-08-23, real route blocker found and fixed**: added a new `!logpos` GM command (reports
  position, prints an easy-to-copy CSV line to the map-server console) so the user could walk the
  real route and report exact blocker coordinates. Found 3 real door/prop entities blocking the
  route entirely -- all real `npc_list` rows with zero `instance_entities` registration, same bug
  class already fixed on several other missions this session. A full sweep of the whole route
  corridor confirmed these were the only 3 unregistered door/prop entities left; 2 other real Iron
  Gates the user confirmed already work correctly (part of the real mechanic, not blockers) share
  the exact same `entityFlags` and were already registered -- registration alone was the fix for
  the other 3 too, no `entityFlags`/animation changes needed. Fixed in `instance_entities.sql`.
  **User-confirmed live**: after the reimport, the rock and both doors are passable -- route
  blocker fully resolved.

- 🟡 **2026-09-09/09-10, full escort/flee/branch/fork/fail rebuild, extensive live iteration**:
  picked back up on the real escort mechanic (Excaliace cannot be controlled, checkpoint-gated
  speed, garlic-stop, escape/catch, branch detours, mob-aggro flee, fail condition). Many real bugs
  found and fixed via repeated live testing (each confirmed against `!logpos`/live debug logs, not
  guessed):
  - **Engine-wide bug found (not Seagull-specific)**: `math.random(n)` (single-arg form) is bound
    to a HALF-OPEN `[1,n)` range in this server's own engine (`src/map/lua/luautils.cpp:132-137` /
    `src/common/tpzrand.h`) -- it can **never return `n`**, confirmed by reading the actual binding.
    This is why Excaliace was never observed picking the "east" side of any west/east 50/50 choice,
    and silently dropped a few dialogue lines (`EXCALIACE_CRAB3`, `EXCALIACE_DEBAUCHER2`, `END2`,
    `PAIN5`) that could never be selected. Fixed every call site in `Excaliace.lua` to use the
    correctly-compensated two-arg form (`math.random(1,n)`); the real engine-level fix (one line in
    `luautils.cpp`) is still outstanding and affects every other script's `math.random(n)` calls
    server-wide, not just this mission -- flagged for the user to decide when/whether to fix
    centrally.
  - **Branch/crab-room detours (B1-B4)**: real bugs found in the west/east side-detour machinery --
    `isFollowingPath()` reads `true` indefinitely on a stalled `pathTo()` leg (added a real
    stall-watchdog with a capped retry count, tracking actual position independent of that flag);
    B1's real east intermediate point was simply unreachable (never caught before the
    `math.random` fix always forced west) -- replaced with a real user-provided center-of-room
    coordinate; B2's center position was corrected via fresh `!logpos`; B4's own trigger radius was
    too tight for where the real captured route actually passes (computed the true minimum
    segment-to-point distance and widened just that one branch's radius via a new optional
    `triggerRadius` field, rather than loosening the shared radius for all of them).
  - **B4 east fork built**: real user-provided waypoints (`EAST_FORK_PATH`), a genuine 50/50
    west-continues/east-diverges decision at B4, and a dedicated `resumeFork()` so getting caught
    mid-fork resumes the fork instead of silently switching him onto the west route (a real bug
    found live: "chooses east, flees, resumes on west").
  - **Post-B4 dead-end detour**: user requested and provided a real coordinate for a fixed (non-
    random) side-trip after B4. Built using the same branch-detour machinery; hit real trigger-
    geometry problems (the coordinate doesn't sit close enough to where the captured route actually
    runs) that couldn't be resolved without further real position data -- **removed at the user's
    request** rather than ship a detour that doesn't reliably fire. B4's own trigger-radius fix
    above was a byproduct of debugging this.
  - **Flee/tired/catch/fail mechanic corrected against the user's real walkthrough**: the tired
    ("<Pant>...<wheeze>") pause happens exactly once per flee (was repeating every ~50 yalms);
    catching him during the pause resumes escort, letting the pause expire uncaught sends him on
    one final real leg toward the confirmed `FLEE_FAIL_POS` (not an instant fail) at 75% speed
    (`SPEED_ESCAPE`, which turned out to be defined identically to normal escort speed -- given its
    own real 0.75 ratio, distinct from the escort tier's already-tuned 0.55); mob-aggro flee range
    and recapture range both tightened from a vague ~20/~10 yalms down to real 5-yalm values per the
    user; catching him now requires ~1s of sustained proximity (not a single-tick pass-by) so
    incidentally standing on his own walked corridor no longer counts as "catching" him.
  - **Breadcrumb system removed and replaced**: the original flee-retrace used a growing, per-
    instance breadcrumb log: repeated catch/flee cycles over the same stretch of corridor
    duplicated and overlapped points in that log with no way to tell "already recorded" from "new
    ground," and the next flee's retrace walked the whole bloated, looping history instead of a
    clean path back -- confirmed live (growing route lengths across successive flees, eventually a
    full loop back past the win-condition end of the map before wallhacking to the fail point).
    Replaced with index-based retracing directly against the real, fixed `FULL_PATH`/
    `EAST_FORK_PATH` arrays (`buildWalkedPathFallback()`/`buildForkLeg()`) -- indices can't
    duplicate or accumulate, so this bug class is now structurally impossible, not just mitigated.
  - **Wallhacking on the backtrack**: STATE_ESCAPING_TIRED's uncaught-timeout resume used to jump
    straight into the final `FLEE_FAIL_POS` leg regardless of how far into the retrace he actually
    was, discarding the rest of the real route and producing a multi-hundred-yalm straight line
    through geometry -- fixed to only take that final leg once the retrace has genuinely reached the
    entrance, resuming the in-progress retrace otherwise.
  - 🟡 **"Zipping"/teleport-looking flee movement, extensively investigated, root cause NOT
    server-side -- likely a client rendering/interpolation limitation**: user reported Excaliace
    appearing to teleport 10+ yalms during a flee, badly enough the player can't keep pace. Several
    real server-side causes were checked and ruled out or fixed in order:
    1. `npc:clearPath()` before the retrace `pathTo()` (an earlier session's attempted fix) was
       confirmed to be a no-op -- `CPathFind::PathTo()` (`src/map/ai/helpers/pathfind.cpp:75`)
       already defaults `clear=true` and clears the path internally on every call, so that line
       never changed behavior. (The earlier note above claiming this fixed the zip was wrong --
       corrected here.)
    2. Added real instrumentation (`debugPathTo()` wrapping every flee-related `pathTo()` call, plus
       a 10-tick per-server-tick position trace armed right after) and confirmed via two full live
       test logs that **every individual movement step is smooth and proportional** (~4.5 yalms per
       server tick, whether the total leg is 5 or 30 yalms) -- there is no single-tick engine-level
       position jump anywhere in either trace.
    3. Found and fixed a real, confirmed contributing bug: `nearestPathIndex()`
       (`buildWalkedPathFallback()`/`buildForkLeg()`) was picking the nearest `FULL_PATH` checkpoint
       by straight-line distance, but a flee starting mid-branch-detour (`STATE_BRANCHING`) or from
       his live position generally meant that "nearest checkpoint" could be 20-30 real yalms away --
       confirmed live (`reqDist=22.30`/`27.19`/`30.95` in successive tests) -- sending him on a real
       full-speed sprint before the retrace visually "settled in," which the player (normal speed)
       couldn't keep pace with. Fixed by prepending his live position as the actual first target in
       both builder functions, and added `buildBranchLeg()` (mirroring the existing
       `buildForkLeg()`) so a branch-triggered flee routes through the branch's own known center
       point first instead of guessing from off-corridor. This reduced, but per the user's own
       follow-up test did **not** fully eliminate, the visual symptom.
    4. After the above fix, the user re-tested and described the remaining visual as "more of a
       pause then a catchup" rather than a hard teleport, and the trace data for that run again
       showed fully smooth, proportional server-side movement. Working theory (not proven, flagged
       as such): `SPEED_FLEE` (100%) sends `UPDATE_POS` packets with roughly double the per-tick
       position delta of normal escort speed (~4.5 vs ~2-3 yalms); if the client's animation/
       interpolation assumes a smaller typical delta between position updates, a consistently larger
       delta could read as periodic snapping even though the server motion is continuous. Confirming
       this would need client-side packet-timing capture (e.g. `Packetlyzer`,
       `D:\Claude\FFXI-Tools\Packetlyzer`), which is out of scope for server-side Lua work -- **user
       elected to log this and move on** rather than continue chasing it.
  - Also tuned per live feedback: branch/intermediate-point dwell time (~30s -> ~10s real,
    calibrated against confirmed real-vs-nominal tick drift), and a temporary `nextBranch=4` testing
    shortcut used to isolate B4 debugging (since reverted -- B1-3 fire normally again).
  - **Not yet done**: a single confirmed clean start-to-finish run (start -> all 4 branches ->
    win condition) hasn't been logged this session -- the extensive testing above exercised each
    mechanic individually/repeatedly but was interrupted by iteration, not run end-to-end once
    everything above landed together. The debug instrumentation added for the zip investigation
    (`debugPathTo()`, the per-tick TRACE block in `tick()`) is still in the file and safe to leave
    in place (low-volume, only active for ~3s after a flee-related `pathTo()` call).
  - 🟢 **2026-09-10, made Excaliace a real damageable target, user-requested now that the rest of
    the mission is solid**: he was already set up to take damage and die (`onTakeDamage` pain
    reaction, `onMobDeath` failing the mission) from an earlier pass, but no crab/pugil/debaucher
    could ever actually land a hit on him -- root cause is the same one already solved for
    `Clavauert_B_Chanoix.lua`'s `aggroNearbyThreats()` (Escort Professor Chanoix,
    `Leujaoam_Sanctum`): `CZoneEntities::SpawnMOBs()` (`src/map/zone_entities.cpp:460-495`), the
    engine's only passive mob-aggro scan, is hard-typed to real players (`CCharEntity`) and never
    evaluates other mobs as aggro candidates, regardless of allegiance or entity flags. Fixed the
    same way as that precedent: `checkMobAggro()` now calls `mob:updateEnmity(npc)` (the same real
    binding, `CEnmityContainer::AddBaseEnmity()`) on any real threat mob within
    `AGGRO_CHECK_RADIUS`, putting Excaliace on its actual enmity list so the engine's own
    `DoRoamTick()` auto-engages and attacks him for real. His existing `setAllegiance(1)` (set
    earlier so players can't attack him by accident) also already makes him a legal Cure/support
    target, so no separate change was needed for "cure him if he gets hurt" to work.
- ✅ **User-confirmed live 2026-09-12: mission passes end-to-end, no further outstanding issues.**
  Pathing is correct throughout, no freeze when cured, stops correctly at checkpoints, flees
  properly to `FLEE_FAIL_POS` on an uncaught timeout, and correctly flees from aggroing mobs. The
  zip/teleport-look flee movement (see the 2026-09-09/10 investigation above) was logged as a likely
  client-side rendering limitation, not pursued further, and does not block completion. **Mission
  passes end-to-end.**

### Golden Salvage (Ilrusi Atoll, mission 41)
**Overall status: ✅ -- User-confirmed complete 2026-08-30.** Core mechanic, targetability,
aggro/draw-in, model, duplicate-spawn-on-reentry, position data, and lockbox rewards all resolved
across a long investigation this session -- summarized below, full blow-by-blow in
`Assault_Fix_Log.md` and `D:\Claude\DSP-Topaz Information\altanaview_mimic_lookup.md`. **One issue
knowingly deferred, not blocking**: the Mimic's lid/mouth-open animation doesn't play on reveal --
see the dead-end investigation at the bottom (same "no server-reachable field controls this" class
of finding as Excavation Duty's Brittle Rock 4/5). A diagnostic C++ fix was built, tested live, and
fully reverted per user request; the shelved code is kept at
`D:\Claude\DSP-Topaz Information\shelved_setlook_code.md` for a future attempt if a real animation
hook is ever found for this model.
- ✅ **User asked 2026-08-27: Mimic shows "NPC" instead of its real name, only after triggering a
  wrong chest -- was this a regression?** Checked commit history for both `Cursed_Chest.lua`
  files -- no commit ever touched the `name` field or added any rename call. Checked every
  server-side data source (`mob_pools.name` correctly "Mimic", `instance_entities` registration
  correct for both chest and mimic, no targid collisions anywhere in the zone) -- all genuinely
  correct. Root cause found in the C++ spawn path instead, not a regression: `CBaseEntity::Spawn()`
  (`src/map/entities/baseentity.cpp`) only ever flagged `updatemask |= UPDATE_HP`, never
  `UPDATE_NAME`. Fine for the zone's initial bulk-load spawn (a separate code path,
  `zone_entities.cpp`, explicitly forces `UPDATE_ALL_MOB` there regardless) -- but the Mimic sits
  dormant until `SpawnMob()` reveals it mid-mission via a direct `Spawn()` call, which relies
  entirely on this accumulated mask for its first real packet to the client -- one that never
  included a name. Fixed by adding `UPDATE_NAME` to the mask (`updatemask |= UPDATE_HP |
  UPDATE_NAME`) -- a real, scoped, additive-only C++ change (needs a rebuild). This may also
  explain (or contribute to) the still-open Ranch Wamoura name-display mystery
  (`documentation/research/Ranch_Wamoura_Name_Display_Investigation.md`) -- worth a retest there
  too once rebuilt.
- ✅ Entrance position already correct (`instance_list.sql` row 41 matches real capture data
  within ~2 units) -- checked 2026-08-18, no fix needed here.
- ✅ Ancient Lockbox usable, real reward data wired (qItems ??? Earring / ??? Box, equal-split;
  regItems Hi-Potion +2, Hi-Potion Tank, Reraiser), real position/rotation and real Assault points
  (1210) all fixed. Root causes were an `entityFlags` targetability bug (shared with Lamia No.13,
  `npc_list.sql` 3715 -> 1667) and wrong widescan-derived coordinates -- both fixed.
- ✅ **The core Mimic identity bug, found via extensive AltanaView/packet-capture investigation**:
  `mob_pools` poolid 2664 ('Mimic') had `modelid` `0x0000030100...` (259) -- wrong. Real packet
  capture (a chest despawn/reveal sequence) shows a clean, sustained switch to `0x0000020100...`
  (258) once a chest reveals as a Mimic. 259 was wrong in *every* codebase checked (this server,
  topaz-reference, landsandboat-reference all agreed on the same wrong value) -- almost certainly a
  shared transcription error copied server-to-server for years, not something introduced locally.
  Fixed to 258. This single fix resolved the "wrong model," "blank model on reveal," and
  "gold-vs-brown/silver skin mismatch" symptoms all at once -- they were all downstream of the
  same wrong modelid.
- ✅ **Chest `look` value, found the same investigation**: the 19 real Cursed_Chest `npc_list` rows
  had `look` `961` (`0xC103`) -- corrected to `960` (`0xC003`), matching the closed-chest model
  Mimics are supposed to share before reveal.
- ✅ **Draw-in/engage bug, fully root-caused across 2 rounds**: (1) `npcs/Cursed_Chest.lua` only
  called `updateClaim()`, never `:engage()`, so the mimic waited passively on its own aggro tick
  instead of springing to life -- fixed with an explicit `:engage()` call. (2) That fix initially
  used the wrong ID type (`player:getID()`, a full id, where `:engage()` wants a targid) -- fixed
  to `player:getShortID()`. (3) `mobs/Cursed_Chest.lua` also had `CheckForDrawnIn` declared
  *below* the `onMobFight` that calls it, silently erroring the closure since the file's first
  version -- fixed by reordering. All 3 confirmed via live retest. (The same `getID()` vs
  `getShortID()` mistake was also proactively fixed in `Mining_Point.lua`, Orichalcum Survey, built
  the same session with the same copy-pasted pattern -- see that mission's own entry.)
- ✅ **Duplicate/respawn-on-reentry bug**: nothing marked a wrong chest as "already dealt with," so
  leaving and re-entering sight range re-triggered `SpawnMob()` and respawned a fresh mimic. Fixed
  with a `triggered` localvar guard on the NPC (same pattern as `Ancient_Lockbox.lua`'s `opened`
  guard).
- ✅ **Duplicate chest slot found and removed**: 17002901/17002963 was an accidental duplicate of
  17002506 (~7 yalms apart, discovered via live `!pos` testing) -- removed from `npc_list.sql`,
  `mob_spawn_points.sql`, `instance_entities.sql`, and `IDs.lua`'s `CURSED_CHEST_SLOTS`.
- ✅ **Targid collision, found and fixed**: the original chest npc and its on-trigger-spawned mimic
  mob shared the same numeric id, so both fought over one client-side render slot (`targid = id &
  0xFFF` for both NPC and Mob types) -- root cause behind several of the above visual glitches
  compounding each other. Fixed with genuinely separate ids.
- ✅ **Position audit, 19/20 confirmed**: of the (now) 19 real Cursed Chest slots, positions are
  confirmed correct against capture/live-test data. Draw-in range tuned 20 -> 22 to match observed
  behavior.
- 🔴 **Remaining, confirmed dead end**: the Mimic's lid/mouth-open animation doesn't play on
  reveal, even with the correct modelid (258) and multiple `animationsub` values tried (1, 5, 9 --
  9 matched a real client skin file found via AltanaView but still produced no visible lid
  animation). A diagnostic C++ `setLook()` build (tested live, then fully reverted per user
  request -- shelved at `D:\Claude\DSP-Topaz Information\shelved_setlook_code.md` if needed later)
  disproved the working hypothesis that `MODEL_EQUIPED`'s sub-model field could drive it -- that
  field is hardcoded to reinterpret those bytes as `{face,race}` for a player-shaped composite
  look, not a generic monster sub-model slot, so setting it just rendered a naked PC race/face
  instead. Conclusion: no server-reachable field (`animationsub`, `look`, or otherwise) attaches a
  genuine articulated lid animation for this model -- whatever drives it, if anything does, is
  baked into the client's own animation rig, unreachable from Lua/SQL. Same category of dead end as
  Excavation Duty's Brittle Rock 4/5 wall-collision issue. Cosmetic only -- does not block mission
  completion.

---

## PFC (Private First Class)

### Orichalcum Survey (Leujaoam Sanctum, mission 2)
**Overall status: ✅ -- User-confirmed live 2026-08-24: ice wall blocker removed.** The `_1XP`
corridor block is resolved -- root cause was the `_1x*`/`_jx*` door-prop identifier drift bug (see
Leujaoam Cleansing's entry for the fix writeup), not a mysterious regression. Mining roll logic and
dialogue branches were already separately confirmed correct and unaffected.

**✅ Confirmed fixed and live-tested:**
- Entrance position, Rune of Release/Ancient Lockbox position, and lockbox rewards (random pick of
  ??? Gloves/Necklace/Box + Remedy/hi-potion_+3). Rune of Release grid text corrected C-8 -> H-8.
- Real Assault points (1980). Item/dialogue text ids re-derived against `dat-extractor` (the
  zone's item/gil/key-item block was off by -1; two separate CapLog-label mismatches were found
  and corrected along the way).
- Qiqirn Miners: real `SpawnMob()`-based mobs (not the old untargetable `insertAlly()` PETs), real
  level range 76-82, `MOBMOD_NO_DESPAWN`, and `setAggressive(true)` on all 8 at ore pickup so a
  Miner missed at the initial `engage()` window still goes hostile-on-sight later instead of
  staying permanently passive.
- Mineral Eater (the mining hazard, real NM name): real `SpawnMob()`-based mob, spawns on-demand
  at whichever Mining Point triggers the hazard roll.
- 🔴 **`_1XO`/`_1XP` corridor obstruction -- REOPENED 2026-08-22.** Original (2026-08-21) diagnosis:
  missing `instance_entities` registration (the prop existed in `npc_list`/`mob_spawn_points` but
  was never wired into instance 2). This got the corridor passable, so it wasn't wrong that
  registering *something* at that position helped -- but it mis-identified *which* prop was
  actually doing the work. Real picture, found 2026-08-22 while investigating the same corridor's
  twin in Leujaoam Cleansing: `_1XO`'s `npc_list` position had been sitting at this corridor's real
  spot (`-460.054,-32.172,120.370`) by data-mixup coincidence -- that's actually `_1XP`'s real
  position, and `_1XO`'s own true identity belongs to Leujaoam Cleansing instead (see that
  mission's tracker entry, and `npc_list.sql`'s comment on 17060143). `_1XP` (registered to this
  instance in the same 2026-08-22 pass that added `_1XE`/`_1XF`) was believed the real, sole
  blocker, and was re-confirmed live passable at that time with `_1XO` no longer referenced at all.
  **Re-tested later the same day: blocked again**, with no further edits to this data in between.
  Full re-verification (live-DB check, dual-instance-registration test) all came back clean/ruled
  out -- see Leujaoam Cleansing's entry for the shared joint investigation, since both corridors
  regressed together at the same time. The helper prop (`_1XP`) is not currently opening the
  pathway. Real cause unknown. Do not mark this ✅ again without a fresh live confirmation.
- **Mining roll logic rebuilt (2026-08-21)**: real distance check (`checkDistance() > 2`) before
  allowing an attempt, real messaging for every outcome (tool break, silent miss, "move closer,"
  node depleted, no pickaxe), Mining Points cycle out via the existing HELM-style
  `hideNPC()`/`cyclePoint()` pattern, and Mulwahah now has a full dialogue set: pickaxe grant,
  already-holding-one, a 3-line ore turn-in (was 2), and new post-completion "go away" dialogue
  (previously nothing played once the instance was already complete).
- 🔴 **Mining animation CSID (1041) -- confirmed broken on stock Topaz, 2026-08-27.** The earlier
  note below claiming this "works on Valhalla" left the CSID-based flow live on this Topaz build
  regardless, meaning `resolveMining()` only ran if a player manually canceled the frozen
  animation -- in practice this meant nobody ever saw a pickaxe break or a Zinc Ore, not that the
  odds were low. **Fixed 2026-08-27**: `player:startEvent(CSID_MINE_START)` commented out (not
  deleted -- restore if testing on a build with the real CSID packet mapped) and replaced with a
  2-second `player:timer()` that calls `resolveMining()` directly. See `Mining_Point.lua`.
- **Ore never removed from inventory on turn-in -- fixed 2026-08-27, user-reported.** Talking to
  Mulwahah with the ore played the turn-in dialogue and completed the instance, but the
  `chunk_of_orichalcum_ore` item itself was never taken, so the 8 Qiqirn Miners (who go aggressive
  on ore possession) kept attacking through the whole sequence and mission cleanup. Fixed:
  `player:delItem(ORE_ITEM, 1, tpz.inventoryLocation.TEMPITEMS)` now runs immediately when Mulwahah
  first sees the player holding the ore, before the dialogue timers.
- 🔴 **Two live crashes from a nonexistent `delTempItem()` function -- fixed 2026-08-27.** Both the
  ore-removal fix above and the pre-existing pickaxe-removal-on-tool-break logic
  (`Mining_Point.lua`'s `removePickaxe()`) called `player:delTempItem(...)`, which was never a real
  binding (`lua_baseentity.cpp` only exposes `addTempItem()` to grant one) -- live error:
  `attempt to call method 'delTempItem' (a nil value)`. Both fixed to use the real pattern,
  `player:delItem(itemID, 1, tpz.inventoryLocation.TEMPITEMS)` (same as `Imperial_Stormer.lua`/
  `Quhaaja.lua`). `Mulwahah.lua` was also missing `require("scripts/globals/status")`, needed for
  `tpz.inventoryLocation` -- added.
- 🔴 **`Mineral_Eater.lua` (mob script) didn't exist at all -- fixed 2026-08-27.** Live error on
  kill: `undefined procedure onMobDeath`. The hazard mob spawned by `resolveMining()`'s hazard roll
  had no script file whatsoever. Created with standard stub handlers (`onMobSpawn`/`onMobDeath`/
  `onMobDespawn`) -- it's a pure interruption/aggro mechanic, not a mission-progress kill target,
  so no special death logic was needed.
- ✅ **`ITEM_OBTAINED` text-ID bug -- fixed 2026-08-27, user-reported.** Previously flagged below as
  "minor, non-blocking cleanup" but turned out to be a real, visible bug: every permanent `???`
  item from the Ancient Lockbox displayed as "obtains the temporary item: ..." because
  `ITEM_OBTAINED` was set to 7526, the same index as `TEMP_ITEM_OBTAINED` (a genuinely different
  message for actual temp items like the pickaxe). Fixed to the real value, `6388` ("Obtained:
  <item>."), confirmed against this zone's real client dialog table via `mission_toolkit.py`. Same
  bug found and fixed in **Periqia**'s `IDs.lua` too (`ITEM_OBTAINED` was `6389`, off by one).
- ✅ **Mulwahah's dialogue missing her name prefix -- fixed 2026-08-27, user-confirmed live.** All
  `npc:messageText(...)` calls (go-away lines, 3-line ore turn-in) replaced with
  `player:messageSpecialFrom(npc, ...)`, matching the pickaxe-grant dialogue's existing pattern.

**Resolved/superseded cleanup note** (previously listed as "minor, non-blocking," now actually
fixed above):
- `IDs.lua` defines `MINING_TOOL_BROKE` twice (7527, then 7531) -- Lua silently keeps only the
  last one (7531 is what's actually in effect); the first is dead. Still not deleted -- low
  priority, the live value is a real, valid message.

### Preemptive Strike (Mamool Ja Training Grounds, mission 12)
**Overall status: ✅ -- User-confirmed live 2026-08-22, full pass.** The "closed door blocker" that
prompted the deep `_1u9`-`_1uj` position audit turned out to be a real, correctly-closed door that
was never actually on the critical path -- user confirmed a working opening/exit already existed
elsewhere and it had been mistaken for the required route. Mission passes as-is. The position fixes
found and applied during the investigation (`_1ug`, `_1ua`) were real, confirmed-correct data
corrections regardless, and stay in.
- ✅ Fully validated 2026-08-18 by a real capture, real WIN. Kill-all-13 confirmed exactly right.
  Entrance corrected (was ~15 units off), Assault points corrected (1000 guess -> real 1100),
  Lockbox reward table extended with a real hi-potion +2 drop.
- ✅ **User-confirmed live in-game 2026-08-19**: full playthrough tested and passed, no issues.
- ✅ *(resolved, see the final bullet below)* **User-reported 2026-08-20**: a door in a closed
  state, blocking progress -- initially treated as a shared/global regression (same symptom seen
  on Sagelord Elimination and Leujaoam Cleansing around the same time). **That theory turned out
  to be wrong for this mission** -- a
  full cross-reference of this mission's real capture data against `npc_list`/
  `instance_entities`/`IDs.lua` (2026-08-21) found the real cause: this mission's own door/wall
  prop family (`_1u9`-`_1uj`, 9 real props with real capture-confirmed position/animation data)
  had **zero** `instance_entities` registrations, and `preemptive_strike.lua` never referenced any
  of them at all. Not a regression -- these props were never wired since the mission was first
  built; the 2026-08-19 sign-off evidently never required walking through that specific door.
  Fixed: registered all 9 into `instance_entities` for instance 12, filled in real capture data for
  2 that were still `NOT_CAPTURED` placeholders (`_1uc`/`_1uh`), and added a reveal loop to
  `onInstanceCreated`. 2 siblings (`_1ud`/`_1ue`) remain `NOT_CAPTURED` -- no real data found in
  any available capture. **Not yet live-tested** -- which animation value means "open" vs "closed"
  for this specific prop family wasn't independently verified, so this needs a real retest, not an
  assumed fix. See `Assault_Fix_Log.md` for the full writeup.
- This finding also **changes the shared-regression theory** -- see `TODO.md`, since 1 of the 3
  "affected" missions turns out to have had an unrelated, purely local cause.
- ✅ *(resolved, see the final bullet below)* **2026-08-22, user-reported**: a door still blocking
  near `-41,-6,20` after the above fix.
  Cross-referenced against 2 real captures of this whole `_1u9`-`_1uj` family (same methodology as
  Leujaoam Cleansing's `_1xo` fix): `_1uh` (17047876, real position `-39,-8,18`) is genuinely
  correct and already the real occupant of that spot -- not missing, not wrong. The real bug:
  `_1ug` (17047875) had the wrong position (`-40,-8.47,19.996`), landing it almost exactly on top
  of `_1uh` -- a redundant duplicate, not the intended blocker. `_1ug`'s real position (confirmed
  by both captures) is `-79,-5,19`, near `_1uf`. Fixed. Also found and fixed the same mixup on
  `_1u9`/`_1ua`: `_1u9`'s row was holding `_1ua`'s real captured value (`-239,-8,-138`) -- moved to
  the `_1ua` row where it belongs. `_1u9`'s own real position, and `_1uf`'s (which may already be
  correct as a paired anchor near `_1ug`'s real spot, unconfirmed), are not captured by either
  available source -- left unchanged, flagged for a future capture pass rather than guessed at.
- ✅ **Resolved, user-confirmed live 2026-08-22**: `_1uh` at `-41,-6,20` was never actually a
  blocker at all -- a real, working opening/exit already existed elsewhere in the room, and it had
  been mistaken for the required route. `_1uh`'s closed state (animation `9`, matching both real
  captures exactly) is genuinely correct retail behavior, not a bug. **Mission passes end-to-end
  as of this retest.**

### Lebros Supplies (Lebros Cavern, mission 22)
**Overall status: ✅ -- User-confirmed live 2026-08-25: the rock wall blocker is gone (resolved by
the same-day duplicate-object-registration cleanup), Stormer equipment/food delivery confirmed
working. Mission complete.** Real polish added the same day, not yet live-tested (see below).
- ✅ **2026-08-25**: Stormers now `lookAt(player:getPos())` on every interaction (feeding, "already
  full" nag, "no food" prompt) instead of staying frozen facing their spawn direction -- first
  application of a face-the-player-on-interact convention the user wants to spread to other NPCs
  next, starting here to validate the pattern (`npcs/Imperial_Stormer.lua`).
- ✅ **2026-08-25, real mechanic added: Stormers now roam within their own cluster.** User-reported
  they're meant to wander -- each has a visually distinct shield (npc_list's look-blob `sub` slot
  already varies for real across the 12 rows, 3 real values 0x702A/0x702C/0x702D, confirmed real
  data, not invented), and if they never move, the player can just memorize "this spot = this
  Stormer" instead of reading the shield. Implemented per the user's own suggestion: periodically
  shuffle which member of a cluster occupies which of that cluster's own real position slots (all
  positions are real capture-confirmed spots, no new coordinates invented, no navmesh risk since
  it's a position swap not a walked route). `SHUFFLE_INTERVAL` (25s) is an unconfirmed judgment
  call -- no real source gives an exact timing. Not yet SQL-reimported (Lua-only, needs map-server
  restart) or live-tested.
- 🟡 **2026-08-25, investigated but NOT built: feed-reaction emotes.** User reported watching a
  Thris capture where Stormers visibly "bow" (happy, successfully fed) or "stagger" (player has no
  food) -- confirmed the engine mechanism exists and is proven elsewhere in this exact codebase
  (`entity:entityAnimationPacket("code")`, e.g. `Qiqirn_Mine.lua`'s `"bom0"`, `Black_Baron.lua`'s
  `"kesu"`), so this is real and buildable. But checked this mission's own capture (both the
  parsed EventView log and the raw `PacketLogger/incoming/0x038.log`) and found only 2 unrelated
  animation events in the whole session (Crimson_Eruca's `"kesu"`, Ancient_Lockbox's `"open"`) --
  no Stormer-feed animation was ever recorded in this specific playthrough. No FourCC lookup table
  exists anywhere in this codebase or the dat-extractor cache either, so the real codes for "bow"/
  "stagger" are still unknown. Not guessed at -- wrong codes could silently no-op or trigger the
  wrong animation. Needs either a fresh capture that happens to record the feed reaction, or the
  real codes sourced some other way (e.g. a PacketViewer/Ashita animation table).
  **2026-08-25 follow-up**: checked Windower/Resources (already mirrored locally,
  `D:\Claude\FFXI-Tools\Resources\resources_data\emotes.lua`) per the user's request -- confirms
  `bow`=emote id 1, `stagger`=emote id 18, but this is the **numeric emote-id system**
  (`CCharEmotionPacket`, the real `/bow`/`/stagger` slash-commands), a completely different
  mechanism from the FourCC animation-packet system (`entityAnimationPacket`, `"kesu"`/`"open"`)
  investigated above -- Windower's resource doesn't cover FourCC codes at all, so it doesn't
  directly solve the original search. Checked how the numeric system is wired in this engine:
  both real call sites that construct `CCharEmotionPacket`
  (`lua_baseentity.cpp`'s `sendEmote` and `packet_system.cpp`'s incoming-emote handler) hardcode a
  `CCharEntity*` (player) as the packet's source -- there is currently no code path for an NPC or
  mob to source one of these packets itself. Two real options going forward, not yet chosen:
  (a) extend the engine (`CCharEmotionPacket`'s constructor + a new Lua binding, e.g.
  `npc:sendEmoteSelf(emoteID)`) to let an NPC source a numeric emote using the ids now confirmed
  real (bow=1, stagger=18) -- clean semantics, but a real C++ engine change, not pure Lua/SQL;
  (b) keep trying to find the FourCC codes for "bow"/"stagger" specifically for the already-proven
  NPC/mob-compatible `entityAnimationPacket` system instead, avoiding any engine change.
  **2026-08-25, 2nd follow-up (user asked to check LandSandBoat/topaz source + legacy community
  docs directly)**: confirmed by reading `packets/entity_animation.cpp` itself -- there is NO
  server-side FourCC lookup table anywhere in this codebase, only one named constant
  (`Fade_Out = "kesu"`); every other caller just passes a raw literal string. These are literal
  client motion-pack identifiers, not something the server enumerates -- genuinely not
  discoverable from source alone. A web search of LandSandBoat's own GitHub (the current name for
  this same codebase lineage) turned up a 3rd, separate animation system worth knowing about:
  `injectActionPacket` (`lua_baseentity.cpp:630`, exposed via the already-live GM command
  `!injectaction <actionID> <animationID> {speceffect} {reaction} {message}`,
  `scripts/commands/injectaction.lua`, permission tier 1) -- built specifically for **testing and
  discovering numeric animation ids by trial**, explicitly documented as "used for testing and
  finding animations, not production use". This is a real, concrete path forward: the user (or
  live guidance from a future session) can use `!injectaction` in-game to empirically find the
  real numeric animation id that looks like a bow/stagger pose, the same way the original devs of
  this engine discovered ids like 261. Two caveats: (1) `injectActionPacket` itself is
  player-source-only (`TYPE_PC` restricted, same restriction as everything else checked) --
  finding the right id this way still requires a small follow-up change to actually play it from
  an NPC in production, either via a new Lua binding or by translating the found numeric id back
  to its corresponding FourCC/action-type if one exists; (2) `ACTION_MOBABILITY_FINISH` (action
  type 11) already exists and is mob-sourced by design elsewhere in the engine, so once a real
  animation id is found, that's the most likely clean path to actually playing it from an NPC/mob
  without inventing new plumbing.
- ✅ **Full mechanic validated end-to-end, 2026-08-20** (via `!giveitem` + wallhack to bypass the
  wall blocker below, isolating the mechanic itself from the blocker): all 12 Stormers correctly
  accept food, show correct dialogue, and refuse further food once full; once all 12 are full, Rune
  of Release and Ancient Lockbox both unlock correctly, the lockbox works, and the instance can be
  exited normally. The mechanic and dialogue work are fully correct -- **the only remaining problem
  is the wall blocker**, not the mission logic itself.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 1320 points.
- ✅ Real Rune of Release / Ancient Lockbox staging positions fixed (were left at zone-default).
  Lockbox reward table extended with a real hi-potion +2 drop.
- ✅ **Full object/dialogue rescan of the same capture, 2026-08-20**: 2 wall props (`_1rj`/`_1rq`)
  had real position data but were `NOT_CAPTURED` placeholders never registered to this instance --
  filled in and wired. Yazuhma (the mission-giver NPC) had a real `npc_list` row but was **never
  registered to this instance at all** -- added. Also fixed the `RUNE_UNLOCKED`-with-wrong-params
  bug (same class as Excavation Duty) -- switched to `RUNE_UNLOCKED_POS` with the real confirmed
  grid, H-8.
- ✅ **Real food hand-out/turn-in mechanic built, 2026-08-20**, replacing the old
  trigger-once-per-Stormer placeholder: Yazuhma hands out 1 of 6 real point-valued/group-fill temp
  items (sticky per player until delivered), each of the 12 Imperial Stormers now needs 6 or 7 real
  points of food (randomized per Stormer) delivered by simply talking to them while holding food.
  Real per-Stormer positions (previously all 12 shared one placeholder spot) are now wired in too.
  Full real dialogue for both Yazuhma and Imperial Stormer. See `Assault_Fix_Log.md` for the full
  mapping and the judgment calls (random-grant weighting, 2 of 4 Yazuhma nag-tier lines, which
  Stormer line plays in which state) that still want a live retest to confirm.
- ✅ **Seafood Stewpot mechanic confirmed and corrected, 2026-08-20**: user confirmed this is a
  real retail item ("Temporary Seafood Stewpot," added 2015-05-14) that "fully feeds all
  surrounding soldiers." Initially implemented as filling a fixed, pre-assigned 5-cluster group
  (matching the wiki's WSW-2/SSW-2/SE-3/NW-3/N-2 layout) -- corrected per user direction to a real
  distance check instead (any Stormer within 30 yalms of whoever received it, checked against
  every Stormer's live position), since "surrounding" describes actual proximity, not a fixed
  group membership. The 30-yalm radius was picked to comfortably cover the widest real
  intra-cluster spread (~25 yalms, the SE group) while staying well under the narrowest gap
  between two different clusters (~77 yalms, WSW-SSW) -- checked against the real capture-derived
  positions, not guessed. Confirmed with the user: equal 1-in-6 grant odds alongside the 5
  point-value foods are fine as-is, no special rarer chance needed.
- ✅ **Caught in review before commit, 2026-08-20**: `Imperial_Stormer.lua`'s `delItem()` call for
  consuming the delivered food was missing the `TEMPITEMS` container argument -- it defaults to
  main inventory, but food granted via Yazuhma's `addTempItem()` lives in `LOC_TEMPITEMS`. Without
  the fix, `delItem` would have silently no-op'd every time, letting one food item feed unlimited
  Stormers while Yazuhma perpetually refused to grant a new one (its own `hasItem()` check would
  never see the "consumed" item actually removed). Fixed with
  `tpz.inventoryLocation.TEMPITEMS` before this ever reached a live test.
- ✅ **RESOLVED 2026-08-20**: the "+15 drift" flag below (previously an open, unconfirmed concern)
  is now definitively **disproven**, not just left uncertain -- cross-checked all 5 shared
  system-message ids directly against `dat-extractor`'s real client dialog table
  (`lebros_cavern_6483.json`) and every one matches exactly as currently assigned
  (`ASSAULT_22_START`=7368, `TIME_TO_COMPLETE`=7407, `RUNE_UNLOCKED_POS`=7409,
  `ASSAULT_POINTS_OBTAINED`=7411, `TIME_REMAINING_MINUTES`=7412). Also matches the user's own live
  screenshot -- all 5 rendered correctly in-game. No change needed; this block was right all along.
- ✅ **User-reported 2026-08-20, live screenshot; fixed and re-confirmed live same day**: Yazuhma's
  dialogue displayed real **Apkallu Breeding** (mission 26) text instead -- "The apkallu is already
  following you", "You seem to have made a match!", "VIT Down removed", etc. Confirmed via direct
  `dat-extractor` lookup: **every single one** of the 12 message ids assigned to Yazuhma/Imperial
  Stormer dialogue above (originally 7439-7449 + 7225) was wrong, all pointing at real Apkallu
  Breeding text -- the capture's CapLog MesNum labels were mislabeled for this entire block, the
  same class of error already caught once on the shared system-message block (resolved above as a
  false alarm; this block, unlike that one, genuinely was wrong). **Fixed**: re-verified all 12 ids
  directly against the real client dialog table instead of trusting the capture again -- the 12
  real lines form one clean, contiguous, correctly-ordered block (7424-7435).
  `YAZUHMA_TEMP_ITEM_OBTAINED` corrected from 7225 to 7210 (confirmed via exact encoding match
  against Leujaoam's already-working `PLAYER_OBTAINS_TEMP_ITEM`, 7310). **User retested live and
  confirmed correct dialogue now displays.** Bonus, still open: `7435` is a real, previously-unwired
  Yazuhma "all done" line ("Thanks to you, the advance unit is now completely provisioned.
  Excellent work!") -- not yet used in `Yazuhma.lua`, worth wiring in on the last Stormer feed.
- ✅ **RESOLVED (see the 2026-08-25 entries below) -- was: CONFIRMED MISSION BLOCKER, user-reported
  2026-08-20**: an impassable wall at `_1rq`'s
  position (`-399,-13,-180`) blocks access to (some of) the Imperial Stormers, making the mission
  uncompletable. Gateway addon confirmed off, ruling out the earlier client-side explanation that
  fixed several other missions' door bugs this session. Diagnosed properly rather than guessed at:
  `!checknav` confirmed a path exists on the compiled navmesh right through this point
  (`checkNavPath` returned `true`, 2 waypoints) -- same signature as Excavation Duty's Brittle Rock
  4/5 (clean navmesh, real block elsewhere). Ran the same decisive test that resolved that case:
  hid `_1rq` entirely -- user confirmed this removed it from client-side entity tracking (a
  minimap radar addon lost its dot for it) but the wall stayed completely solid, and Ashita's own
  F11 zone-geometry highlight still shows a distinct object right there. **Correction 2026-08-25:
  the "confirmed static baked geometry, identical to Brittle Rock 4/5" conclusion above was wrong**
  -- Brittle Rock 4/5's own "unfixable baked collision" turned out to actually be the same
  `_1r*`/`_jr*`/`_ir*` door-prop identifier-drift bug found and fixed zone-wide this session, not
  a real engine limitation, so this entry's identical reasoning shouldn't have been trusted either.
- 🟢 **2 real bugs found and fixed 2026-08-25**, user-reported live:
  1. **`luautils::onMobDeath (Crimson_Eruca.lua): undefined procedure onMobDeath`** -- the script
     file didn't exist at all despite `mob_pools`/`IDs.lua` (`CRIMSON_ERUCA1-20`) already
     referencing it (poolid 837). These are real hostile obstacle mobs along the delivery route,
     not tied to mission progress (per this mission's own instance script comment) -- added a
     minimal `onMobDeath` stub, matching the established convention for ambient obstacle mobs.
  2. **Rock wall blocker at `-396.9156,-9.9934,-181.4043`** -- nearest real door prop is `_1rp`
     (`17035529`, dist 3.39), which already had correct real position data (fixed earlier this
     session) and is already registered to 2 neighboring missions (Evade and Escape, Wamoura Farm
     Raid) but was never registered to *this* instance. Registered it. No PathLog data exists in
     this mission's captures to confirm the full door set the way Bloody Rondo's did, so this is a
     targeted fix for the specific reported blocker, not a verified-complete door registration --
     if more blockers surface, check for the same missing-registration pattern first before
     assuming baked geometry again.
  Not yet SQL-reimported or live-tested. **The Stormer-unreachable-by-baked-geometry theory above
  should be re-tested after this fix, not assumed to still apply.**
- 🔴 **2026-08-25, user re-reported: same wall still blocking** at the original `_1rq` position
  (live navdebug: `!navdebug 15` at the wall found only `17035530` within range, `onMesh=true`,
  confirming the navmesh itself has a clear path through this point). User asked whether this was
  even the right object, recalling it had been "updated then reverted" -- correct recollection: the
  2026-08-25 fix above registered a *different* id (`17035529`) here based on a nearest-neighbor
  guess, later disproven and removed (see Evade and Escape's entry + TODO.md) -- `17035530` itself
  was never actually re-examined. Doing so now found a real bug: `17035530` was mislabeled `_1rq` in
  both `npc_list.sql` and `IDs.lua` -- **two independent real captures** (this mission's own PFC
  Thris capture + a separate Nov2025 Thris capture) both directly confirm the real name is `_1rp`.
  Same drift on its neighbors: `17035523` (`_1rj`) is really `_1ri`; `17035522` (previously named
  `_1ri`, occupying the wrong spot) is really `_1rh` and belongs at a completely different position,
  `(-500,-13.071,-40)` -- confirmed by 2 independent captures (this mission's + Troll Fugitives',
  which also legitimately shares this same npcid/position). All 3 corrected in `npc_list.sql` and
  `IDs.lua` (`instances/lebros_supplies.lua` updated to match the renamed constants).
  **This does NOT resolve the reported wall** -- `17035530`'s own position was already correct even
  under the wrong name, so the id-drift bug isn't what's blocking this specific corridor. The
  2026-08-20 hide-test (hiding the entity removed it from client-side/radar tracking but the visual
  wall stayed completely solid, and Ashita's F11 zone-geometry highlight still shows a distinct
  object there) still stands, and still points at real baked client geometry, not anything
  SQL/Lua controls -- unlike Excavation Duty's Brittle Rock 4/5, where that same signature turned
  out to be a fixable id-drift bug elsewhere in the chain, here the specific blocking id has now
  been directly verified correct. **Next diagnostic steps** (need live user testing, can't be
  done from captures/SQL alone): (1) confirm Gateway/any client mod is fully disabled, since several
  other "baked geometry" false alarms this session turned out to be client-side rendering; (2) try
  `!checknav` at the exact blocked point (not just `!navdebug`) to double-check the compiled
  navmesh truly connects through, the way it did for Brittle Rock 4/5 before that was found fixable;
  (3) check whether the wall is meant to open on a trigger this mission doesn't yet implement (no
  such mechanic is documented for Lebros Supplies in the wiki writeup used to build it, but the
  wiki coverage for this mission was already known incomplete going in). Not yet SQL-reimported.
- ✅ **RESOLVED 2026-08-25**: user confirmed live the wall is gone -- turned out to be a side
  effect of the same-day phantom-duplicate-object cleanup (17035517/17035520/17035527 consolidation,
  see Evade and Escape's entry), not anything specific to `_1rp` itself. Mission fully complete;
  Stormer equipment/food delivery also reconfirmed working.

### Requiem (Periqia, mission 32)
**Overall status: ✅** -- User-confirmed live in-game -- full playthrough tested and passed.
- ✅ Entrance position corrected (was close but not exact; fixed to real capture data).
- ✅ Kill-all-18 mechanic confirmed correct (23 real kills observed). Lockbox rewards
  (LSB-ported, validated) and Assault points (1100, real) now both confirmed/fixed.
- ✅ **User-confirmed live in-game 2026-08-19**: full playthrough tested and passed, no issues.
  Fully done -- no further work needed on this mission.

### Lamia No.13 (Ilrusi Atoll, mission 42)
**Overall status: ✅ -- User-confirmed live 2026-08-25.** The real "charm the Fallen, dispel to
turn them hostile" tactic (a genuine C++ engine change, the most invasive fix scoped this
session) is fully built and working end-to-end: spawn/positioning, the crash that briefly
followed it, Fallen responsiveness, and Belly Dance itself were all found broken in turn through
live testing and fixed one at a time. Full history below.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data).
- ✅ Kill-1 mechanic already correct. Lockbox rewards + Assault points (1320) now real.
- 🟢 **User-reported 2026-08-19**: Rune of Release/Ancient Lockbox not at the correct position --
  `onInstanceCreated` was never calling `setPos()` for either. Fixed with real widescan-confirmed
  coordinates (60,-3,-145 / 63,-3,-144). Not yet confirmed fixed live.
- 🟢 **User-reported 2026-08-19**: no companion mobs spawn with her, contradicting the "solo
  kill-target" assumption. Real widescan data confirms 3 real companions (Fallen Volunteer,
  Fallen Imperial Wizard, Fallen Imperial Trooper) whose SQL rows already existed but were never
  registered to this instance. Fixed, treated as ambient guards (not objective-relevant). Not yet
  confirmed fixed live.
- 🟢 **User-reported 2026-08-19**: invisible wall at (70,-4,-143) blocking half the map. Same
  missing-door-registration bug as Imperial Agent Rescue (`_1jd`, position-matched almost
  exactly). Fixed. Not yet confirmed fixed live.
- 🟢 **User-reported 2026-08-19**: Ancient Lockbox not targetable/usable. First attempt (removing
  the `setStatus` toggle) turned out to be a no-op -- `status` and the targetability flag are
  checked completely independently in the engine. **Real fix**: this npc's `npc_list.sql` row
  (17002654) had `entityFlags=3715`, the *only* Ancient Lockbox row in the entire game with
  `FLAG_UNTARGETABLE` set -- every other zone's lockbox uses `1667` (same base value, minus that
  one bit). Pure data-entry bug, corrected to `1667`. Since this npc is shared across all 10 Ilrusi
  Atoll missions, this likely fixes every other Ilrusi lockbox too, not just this one. Needs a DB
  reimport before it's live.
- 🟢 **User-reported 2026-08-19**: Lamia and her 3 companions stay at a static location instead
  of wandering the whole map. Root cause: `MOBMOD_ROAM_DISTANCE` was never set for any of the 4
  mobs -- defaults to 0 (zero roam radius) when unset. Set to an estimated 500-yalm radius for
  all 4; not measured against real zone dimensions, worth tuning after a live test.
- 🟢 **User-reported 2026-08-19, regressed and re-fixed 2026-08-20**: companions roaming
  independently instead of staying with Lamia. The 2026-08-19 fix (dropping their own
  `ROAM_DISTANCE` to 100/10 yalms) only anchored them to their own fixed spawn point, not to
  Lamia's *current* one -- since her own roam radius is much larger (500 yalms, needed for her own
  separate "doesn't wander like a real NM" fix), she drifts far from that shared spawn point over
  time while they stay tethered near it. User re-reported the gap had grown to 50+ yalms.
  **Real fix**: all 3 companions (`Fallen_Volunteer.lua`/`_Imperial_Wizard.lua`/`_Imperial_Trooper.lua`)
  now actively follow Lamia's live position using `pathTo()` (the same non-PC walk-toward-a-point
  primitive used by Selh'Teus in the CoP final fight) on a self-rescheduling 3-second timer,
  closing the gap whenever more than 10 yalms from her current position. Skipped while engaged so
  it doesn't interfere with actual combat positioning. `ROAM_DISTANCE` kept as a fallback.
- 🟡 **User-reported 2026-08-19**: Belly Dance charm (real Lamia NM signature move, per the mob
  skill's own header comment) added to her moveset -- was a fully commented-out stub, wired up in
  `sql/mob_skills.sql` + `sql/mob_skill_lists.sql` and implemented in
  `scripts/globals/mobskills/belly_dance.lua`. **CORRECTED 2026-08-20**: the fix log previously
  claimed this was "user-confirmed live" to also charm the Fallen companion mobs -- user has since
  confirmed **this was never actually tested**. Re-auditing the code: it can't produce that
  behavior as written. The original ask was specifically to charm the Fallen companions, but the
  implementation only loops `instance:getChars()` filtered by `player:isPC()` -- that only ever
  returns registered player characters (confirmed via `CLuaInstance::getChars()`, which reads
  `m_charList`), never mob entities (`getMobs()`/`m_mobList` is a separate, unused binding). The
  skill itself is real, correctly wired, and will charm players in range/facing Lamia -- but the
  actual requested feature (Fallen companions getting charmed too) is not implemented. Not yet
  live-tested at all.
- ✅ **BUILT 2026-08-25 -- was deferred, C++ engine change now implemented.** User clarified the
  real intended tactic 2026-08-20: Lamia charms both players and her own Fallen companions;
  dispelling a charmed Fallen makes it attack Lamia; if it then attacks a player, Lamia can charm
  that player too. This needed a real C++ change -- `battleutils::unCharm()` had no handling at all
  for a `TYPE_MOB` target. Added a new `TYPE_MOB` branch (mirrors the real, already-working
  pet-release path in `petutils.cpp`'s `DespawnPet` for restoring native `CMobController`, plus a
  new hostility step: 300 CE/VE hate on the former charmer and an immediate forced `Engage()`, per
  user direction that a freed Fallen should turn on Lamia right away, not just generally aggro).
  **Blast-radius check before building**: confirmed `unCharm()` has exactly one caller in the whole
  codebase (`effects/charm.lua`'s `onEffectLose`), and that no other charm-capable content in this
  game ever applies the CHARM status effect to a mob -- checked all 8 other charm-capable monster
  skills (Danse Macabre, Gala Macabre, Fanatic Dance, Luminous Drape, Entice, Wisecrack, Soothing
  Aroma all explicitly `isPC()`-gate their target; Beastmaster's own charm goes through a
  completely separate `tryToCharm()`/`CPetController::Tick()` path that never touches this
  function). One real exception found: Brainjack (Chariots) has no explicit guard and could in
  theory apply CHARM to a mob, but mobs never target other mobs in normal play, so this is a
  theoretical, not live, exposure. User confirmed comfortable proceeding given this scope.
  **One real bug identified, then a 2nd-pass correction after a live regression**:
  1. `belly_dance.lua`'s `onMobSkillCheck` was an unconditional `return 0` -- **initially
     misdiagnosed** as the same never-filled-in-stub bug class as Excavation Duty's Qiqirn Mine
     (changed to `return 1`), which seemed to work at first (a live test right after showed her
     charming the player, matching the disengage/wander description). **CORRECTED 2026-08-25,
     2nd pass**: that fix was wrong and broke a check that was never actually broken. Qiqirn
     Mine's fix was for a *different* C++ call site -- an explicit, scripted
     `mob:useMobAbility()` call (`mobskill_state.cpp`) -- not Lamia's normal autonomous AI skill
     selection (`mob_controller.cpp`'s `MobSkill()`), which uses the OPPOSITE convention: its own
     code comment is explicit, `luautils::OnMobSkillCheck(...) == 0 // A script says that the
     move in question is valid`. Confirmed live with temporary diagnostic logging: under
     `return 1`, `onMobSkillCheck` fired every combat round but `onMobWeaponSkill` never once
     ran afterward (the real server log only ever showed tail_slap/hypnotic_sway/ranged_attack
     actually being used, never belly_dance). Reverted to `return 0` -- genuinely correct for
     this call site. The original "very uncommon" rarity (the earlier live report of getting it
     to fire "twice") was real, from *before* any of today's fixes, and was never actually a
     stub-check bug -- just losing the random shuffle against Tail Slap/Hypnotic Sway's longer
     10.0 range at the old 7.0 disadvantage, which the distance fix below should genuinely help
     with now that the check isn't wrongly blocking it outright.
  2. **`belly_dance.lua`'s real `mob_skill_distance` was 7.0, not the header's claimed "15' radial"**
     -- explains why it was firing far less often than Tail Slap/Hypnotic Sway (both 10.0) even
     after the stub fix: the shuffle-based skill-selection loop (`mob_controller.cpp::MobSkill()`)
     picks the first skill in random order whose range covers the current target, so Belly Dance
     lost that race on almost every round she wasn't already in close melee range. Corrected to
     15.0 in `mob_skills.sql`.
  **Real mechanic corrections from a user-supplied reference for this exact fight**:
  - The Fallen start the encounter **already charmed** (fighting on Lamia's side), not as
    independent ambient guards -- `instances/lamia_no_13.lua`'s `onInstanceCreated` now applies a
    guaranteed (non-resisted) CHARM_I with a full-mission-length 1800s duration to all 3 on spawn,
    plus the real `mob:charm()` AI-link, so they can't lose it naturally -- only a real Dispel
    (going through the new `unCharm()` TYPE_MOB branch) frees them.
  - `belly_dance.lua` retargeting corrected: hits *whichever side currently holds her hate* (party,
    or a Fallen that's been freed and turned hostile), not both/either at random, and charmed
    regardless of facing -- the original "facing her" requirement was wrong.
  **User-confirmed live 2026-08-25**: Belly Dance now fires correctly (see the `onMobSkillCheck`
  2nd-pass correction further down), Fallen respond and fight properly, no crash. Full charm tactic
  working end-to-end.
- 📝 **Known architectural limitation, NOT fixed, logged for whoever picks this up next**:
  investigating why Arrow Deluge never fires found that `mob_skill_lists` id 171 (`'Lamiae'`) is
  shared by 40+ distinct named Lamia variants in this codebase's SQL (`Lamia_Bowyer`,
  `Lamia_Dartist`, `Lamia_Toxophilite`, `Lamia_Necromancer`, `Lamia_Deathdancer`,
  `Lamia_Palace_Guard`, `Euryale`, `Lamia_No2` through `Lamia_No34`, etc.) -- confirmed via
  `mob_pools`. Real retail Lamiae each have their own distinct skill kit by job/weapon (per
  FFXIclopedia's Lamiae category); this engine has no dynamic per-job/per-weapon skill selection
  at all -- `skill_list_id` is a static field fixed once per `mob_pools` row. All 40+ variants
  sharing one list is a blunt approximation: whichever skills are commented in/out in
  `mob_skill_lists.sql` for list 171 applies to literally every one of them at once, not per
  variant. The commented-out skills we found on Lamia No.13 (`arrow_deluge`, `pole_swing`,
  `tidal_slash`, the `pw_*` skills) are very likely real skills that belong to a *different*
  named variant (e.g. `Lamia_Bowyer` for Arrow Deluge) sharing this same list, deliberately kept
  off so they don't fire on the wrong Lamia -- not missing data, an architecture gap. A real fix
  would mean giving each variant its own dedicated `skill_list_id`, a large separate undertaking
  well beyond this mission's scope -- not attempted here. Mission stays marked complete; this is
  a forward-looking note, not an open blocker.
- ✅ **Real crash bug found and fixed 2026-08-25, user-reported live**: after the multi-site-spawn
  work above, Lamia and the Fallen stopped spawning at all (or, per the user's report, weren't
  spawning "on the correct map"), and the instance was force-failing after ~5 minutes. Real cause:
  `instances/lamia_no_13.lua` and `mobskills/belly_dance.lua` both referenced the 3 Fallen (and
  Lamia herself, in one spot) via `ID.npc.FALLEN_VOLUNTEER` etc -- wrong table path. These
  constants only exist under `ID.mob[42]`, not `ID.npc` (confirmed directly in `IDs.lua`). Using a
  `nil` value as a Lua table *key* (`FALLEN_OFFSETS[ID.npc.FALLEN_VOLUNTEER] = ...`) is a hard
  error, confirmed via the real map-server log: `table index is nil` at
  `lamia_no_13.lua:46`, which failed the *entire file's load* -- so none of `onInstanceCreated`
  ever ran (no spawns, no positioning, no charm setup, no real time limit applied), and the
  "mission failed after 5 minutes" was very likely just a generic engine-level fallback for an
  instance with no valid controlling script, not a separate bug. `belly_dance.lua`'s equivalent
  reference (used as array values, not a key) wouldn't have crashed but would have silently made
  Fallen-charm-retargeting non-functional. Both corrected to `ID.mob[42].*`. Swept the whole
  codebase for any other `ID.npc.FALLEN_*`/`ID.npc.LAMIA_NO_13` reference -- none found (the one
  other `FALLEN_*` hit, in `La_Theine_Plateau/globals.lua`, is an unrelated `FALLEN_EGG` constant
  in a different zone, correctly scoped already). Lua-only fix -- needs a map-server restart to
  pick up (these files are cached at load, not hot-reloadable), no SQL reimport required.
- ✅ **Real C++ hard-crash bug found and fixed 2026-08-25, user-reported live**: after the Lua
  fix above, the server crashed outright entering the zone instead of erroring cleanly. Root
  cause: `battleutils::applyCharm()`'s `TYPE_MOB`-victim branch unconditionally casts the
  *charmer* to `CCharEntity*` in 5 places (`BuildingCharAbilityTable`, `BuildingCharPetAbilityTable`,
  2 `pushPacket` calls, `PClaimedMob` alliance handling) -- code that was only ever written for a
  `TYPE_PC` charmer (a player using Beastmaster's Charm on a mob) and had genuinely never been
  exercised with a mob charmer before this session, despite an earlier session note claiming
  "applyCharm() fully supports a TYPE_MOB victim" -- that claim was only true for the victim side,
  not the charmer side. Lamia (a `CMobEntity`) calling `charm()` on a Fallen hit this exact path
  for the first time, reinterpreting her own object memory as a `CCharEntity` and dereferencing
  fields that don't exist there -- undefined behavior, confirmed crash. **Fixed**: wrapped all 5
  player-only calls in `if (PCharmer->objtype == TYPE_PC)` -- they only exist to sync a *player's*
  own pet-command UI/client state, meaningless for a mob charmer, so skipping them entirely for
  that case is correct, not a workaround. Also checked for a second latent crash from Lamia
  permanently holding a non-null `PPet` afterward (every other real usage of `PPet` in
  `mobentity.cpp`/`mob_controller.cpp` either already guards with `objtype == TYPE_PC` or only
  ever casts the *pet* side, never the master -- confirmed safe). Same C++ recompile as the
  `unCharm()` fix above covers this too -- not a separate build.
- ✅ **Real bug found and fixed 2026-08-25, user-reported live** (partial live test, before the
  C++ recompile above -- caught this on the pre-existing build): Lamia roamed to the player alone,
  without any of her Fallen -- looked like a despawn/leash bug but wasn't. Root cause:
  `mob:charm()`'s Lua binding never exposed a duration parameter at all, silently defaulting to
  `applyCharm()`'s own C++ default of `0s`. Harmless for a charmed player (players don't run
  through `CPetController`), but fatal for a charmed mob -- `CPetController::Tick()` despawns any
  charmed pet once `tick > charmTime`, so the Fallen (charmed at spawn per the entry above) were
  being auto-despawned within a tick or two of the instance starting, well before the player ever
  found Lamia. Fixed by adding a real optional duration parameter to `charm()`
  (`lua_baseentity.h`/`.cpp`) and passing it explicitly at both real call sites: 1800s for the
  Fallen's initial spawn-time charm (`instances/lamia_no_13.lua`), 150s for a live in-fight
  recharge (`mobskills/belly_dance.lua`, matching its own status-effect duration). Checked all 8
  other `:charm()` callers in the codebase -- all player-only, unaffected by this change. Still
  needs the same C++ recompile as the rest of this entry before it's fully testable.
- 🟢 **User-reported 2026-08-19**: aggroing Lamia, running away, then returning found her already
  despawned with the mission marked complete -- without a kill. Root cause: `onMobDespawn` fires on
  ANY despawn, not just death (confirmed via `luautils::OnMobDespawn`'s own doc comment, "death not
  assured"), including a leash-home-and-fade despawn after losing aggro -- which her new 500-yalm
  roam radius (above) made reachable for the first time. Fixed by moving progress tracking to
  `onMobDeath`, gated on a real killer being present, so only an actual kill can complete the
  mission. **Real fix (per user correction)**: applied `MOBMOD_NO_DESPAWN` on spawn so she can't
  despawn at all before being killed -- same mechanism already used for Imperial Agent Rescue's
  Warders. Despawn/respawn is intentional for ordinary mobs; only Assault objective mobs (death =
  win condition) need this. The `onMobDeath`-gated progress hook is kept as a secondary safety net.
  Also applied preemptively to the two other single-kill-target Assault mobs built this session
  (Sagelord Molaal Ja, Mamool Ja Executioner). **Not** a codebase-wide fix -- see memory note
  `topaz_progress_on_despawn_false_complete`.
- ✅ **User-reported 2026-08-25: HP was noticeably too low.** `mob_groups` had HP=0 (auto-calculated
  from level 77-78), producing far less than the real value. Set explicitly to 10000 (user-supplied).
- ✅ **Real mechanic added 2026-08-25: multi-site wandering spawn.** Per a user-supplied reference,
  she's meant to be found wandering on either of 2 islands, requiring the player to actually hunt
  for her (mitigated by her also appearing on widescan) -- previously always spawned at one fixed
  point. `instances/lamia_no_13.lua` now randomly picks 1 of 4 real sites per instance run (the
  original widescan-confirmed cluster + 3 new user-supplied LOGPOS alternates), with the 3 Fallen
  offset from her using the same relative deltas as the original confirmed cluster (not
  independently re-confirmed at the 3 new sites -- a documented, reasonable carry-over assumption).
- 🟡 **User-reported 2026-08-25: pathway blocked at `LOGPOS,,55,38.1529,-4.8423,-265.3134`.**
  Does not affect mission completion, only blocks a small portion of the map. Not yet investigated
  -- logged for follow-up, not urgent.

### Escort Professor Chanoix (Leujaoam Sanctum, mission 3)
**Overall status: ✅ -- User-confirmed complete 2026-08-30, all known issues resolved.** Fully
rebuilt 2026-08-29 as a junction-graph pathing engine (real user-mapped LOGPOS
junctions/dead-ends/dwell-fight-points, dedicated triggers for all 15 real dialogue lines, two
fixed-at-spawn destinations that both lead back to one real, shared Rune of Release location) --
see `mobs/Clavauert_B_Chanoix.lua`'s header for the full design writeup. **Live-tested through
many rounds this session**: fixed a leash-despawn near junctions (`NO_DESPAWN`), a false
double-back-to-start bug, immediate-double-back-to-last-junction, a stall/retry bug that could
leave him permanently stuck on a wallhack leg (own the-clock-kept-resetting bug, fixed), a
string-concat table-key bug that silently defeated the wallhack-exception lookup, 2 genuine
navmesh gaps needing new connector junctions (J22 between J3/J10, J23 between J12/J13) instead of
wallhack, 5 confirmed short-local wallhack exceptions (J0↔J1, J1↔J4, J4↔J8, J3↔J5, J23↔J13), a
zone-in race condition (now gated on player proximity, `MOBMOD_NO_MOVE` held until then), and
allegiance (`setAllegiance(1)`) so he reads as a friendly ally, not an attackable hostile mob.
- ✅ **2026-08-30, real root cause of "he just stands at spawn forever" found and fixed**: a Lua
  forward-reference bug, not a proximity/timer issue as first suspected. `local function
  tick(mob)` was declared textually AFTER `startMoving()`, but `startMoving()` references `tick`
  as an upvalue -- since `local function NAME()` is sugar for `local NAME; NAME = function() ...
  end`, that local didn't exist yet when `startMoving()` was defined, so `mob:timer(TICK_MS,
  tick)` inside it was silently capturing the GLOBAL `tick` (always nil), scheduling a timer with
  no callback. The very first `tick()` call after the 8s start delay never happened, with nothing
  ever logging an error for it. Fixed by forward-declaring `local tick` before `startMoving()` and
  changing the later definition to `tick = function(mob)` so it assigns to that same local.
  Diagnosed via targeted debug prints added at every spawn/timer/pathTo/dialogue call site (kept
  in the file for future debugging, tagged `[Chanoix DEBUG]`/`[Chanoix DIALOGUE]`).
- ✅ **2026-08-30, real infinite loop in the post-10-minute "beeline to destination" safety
  valve**: `beelineNext()` ignored `cameFrom` entirely and just picked whichever edge was
  raw-distance closest to the destination -- for a junction with a dead-end spur that happens to
  sit closer in a straight line than the real onward neighbors (confirmed live: J9 off J8), that
  drove him into the dead end, forced him back out (its only edge), and immediately re-picked the
  same dead end again forever (`LEG ISSUED: 8 -> 9` / `9 -> 8` repeating with no recovery). Fixed
  by giving `beelineNext()` a `cameFrom` parameter, same convention `nextJunctionFrom()` already
  used -- only returns to `cameFrom` when it's genuinely the sole edge.
- ✅ **2026-08-30, real bug: the mandatory dwell/fight junctions (J20/J21) were skippable once
  beelining engaged.** Dwell-point handling was gated on `not beelining` -- confirmed live via
  `LEG ISSUED: 21 -> 11` immediately upon arrival, no fight ever triggered -- meaning destination 2
  could never actually be reached once the 10-minute safety valve kicked in, exactly when it was
  supposed to guarantee completion. Fixed: dwell/fight handling now always runs regardless of
  beelining; only the ordinary random-junction-pause skip remains beelining-exempt.
- ✅ **2026-08-30, real root cause of excessive backtracking/wandering before beelining ever
  engaged**: the gradual "favor progress" forward-bias only measured raw straight-line distance,
  with no concept that a dead-end neighbor can never actually make progress (entering one always
  costs a forced round trip). Confirmed live: J14 and J16 (both dead ends off J10) are RAW-DISTANCE
  closer to destination 2 than J22 (the real through-route), so bias kept alternating between the
  two dead ends (blocked from repeating either one twice in a row by the existing `cameFrom`
  exclusion) for several minutes without seriously trying J22. Fixed in both `nextJunctionFrom()`
  and `beelineNext()`: a dead-end (single-edge) neighbor no longer receives the bias/closest-pick
  preference over a genuine through-route, though it's still occasionally chosen at base weight
  (matching "wanders erratically" per the wiki).
- ✅ **2026-08-30, real graph bug: J13 had a direct edge straight to the destination node [100],
  bypassing J20's mandatory fight entirely.** Confirmed live (`LEG ISSUED: 13 -> 100`, no fight
  ever triggered). Removed the direct edge -- the only route to destination 1 is now through J20's
  `leadsToDestination` handoff, same mechanism destination 2 already used via J21.
- ✅ **2026-08-30, real bug in `instances/escort_professor_chanoix.lua`: `RUNE_OF_RELEASE` was
  never repositioned at all**, only revealed (`setStatus`) -- it's a single npc_list entity shared
  across every mission in this zone, each responsible for its own `setPos()` (same convention
  Imperial Code's instance script already uses), so it was appearing wherever the last-run mission
  in this zone left it. Fixed with a `setPos()` keyed off which of Chanoix's 2 destinations the
  instance rolled (`chanoixDestIndex`, set from `mobs/Clavauert_B_Chanoix.lua`'s
  `chooseDestination()`). Went through 3 real rounds of coordinate correction: the first value
  (100.8230,-3.1525,-18.2932) came from an older, wrong capture reading; superseded by
  (17.5632,-3.5000,-219.4710) from a different, real WIN capture ("Leujaoam Sanctum SP - Escort
  Professor Chanoix", 1210 Assault points, right next to J13) cross-checked against a
  user-provided live LOGPOS; then user confirmed live that the Rune sits at a single central
  location near the J13 branch point and the player is meant to **backtrack** to it regardless of
  which destination Chanoix's own dialogue/walk ends at -- so `DESTINATION_POS[2]` was corrected
  to share `[1]`'s exact coordinates instead of using its own (previously wrong) value.
  `ANCIENT_LOCKBOX` uses the same fixed position with a small offset, same as Imperial Code's
  Rune/Lockbox pairing convention.
- ✅ **2026-08-30, abrupt fadeout fixed**: Chanoix's arrival `setStatus(DISAPPEAR)` fired with no
  visual fade at all. Copied the real, user-tuned two-step mechanic from Brujeel's reveal/fade
  (`Mamool_Ja_Training_Grounds/npcs/_pot_hatch_common.lua`, Imperial Agent Rescue): fire the
  `"kesu"` client-side fade animation first, then `setStatus(DISAPPEAR)` 2000ms later so the fade
  clip has room to actually play before the entity is removed (firing both instantly cuts the
  animation short -- confirmed during Brujeel's own tuning history in that file).
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ **No kill quota** -- the 2026-08-29 junction-graph rebuild replaced the placeholder
  kill-all-16 mechanic with the real one: Chanoix walks his own real captured path autonomously,
  the 16 Frozen Bones/Gelid Bhoot threats aggro along the route exactly as in the real capture, and
  players just need to keep him alive to the end (`onMobDeath` on Chanoix -> `instance:fail()`).
  Lockbox rewards + Assault points (1210) real and confirmed.
- ✅ **All 16 threat positions now real.** 11 fixed 2026-08-25 from the original Thris Nov2025
  PathLog capture. The remaining 5 (`17059876`/`78`/`82`/`83` `Frozen_Bones`, `17059888`
  `Gelid_Bhoot`) sat at `(0,0,0,0)` with genuinely zero data in any capture on file through
  2026-08-30's full pipeline re-mine -- disabled rather than fabricated, then fixed for real once
  the user added 3 more Tacocat-format capture folders ("Escort Professor Chanoix 1/2/3") that had
  never been mined before (the pipeline's mining step only read sqlite `.db` captures and silently
  skipped this older Lua-table format -- fixed in `step2_mine.py` itself so future re-mines won't
  repeat the miss). These are roaming aggro mobs, so position genuinely varies capture-to-capture
  -- not a static-prop precision concern.
- ✅ **User-confirmed live 2026-08-24: ice wall blockers removed**, same `_1x*`/`_jx*` door-prop
  identifier drift fix as Leujaoam Cleansing/Orichalcum Survey (see that entry for the writeup).

### Sagelord Elimination (Mamool Ja Training Grounds, mission 13)
**Overall status: ✅ -- User-confirmed live 2026-08-22, full pass.** Core mechanic, Warp animation,
and wall-clipping all confirmed fixed through 7 rounds of live testing; the door blocker found
after that is now also resolved -- see the bottom bullet.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data).
- 🟢 **Real win-condition mechanic implemented 2026-08-20** (previous "kill-1" was wrong -- the
  real mechanic is a 4-stage HP-threshold fight, not a plain kill). Per user clarification: at
  every 20% HP lost (80/60/40%), he uses Warm-Up then flees at 200% speed, and any Mamool Ja
  Trainee he passes links against the player; at 20% HP he casts Warp and escapes, and **that
  escape is the actual win condition**, not killing him to 0 HP. Confirmed via a real Thris
  capture: Warm-Up is real mob skill 1924 (observed twice, each followed by Evasion Boost + the
  player briefly losing him), and he really does cast the real player Warp spell (id 261,
  "starts casting Warp" -> ~5s -> "casts Warp. Sagelord Molaal Ja vanishes."). The 20%-triggers-
  final-escape design and "warp = win" come directly from the user, not independently re-derived
  from this specific capture run (it only showed one Warp cast, mid-fight, with combat
  continuing shortly after -- read as ambiguous on its own). `onMobDeath` kept as a fallback
  completion path for an outright kill before he successfully escapes. Flee distance, trainee
  link range, and speed-reset timing are reasonable estimates, not capture-verified.
- ✅ **Rune of Release / Ancient Lockbox real positions found 2026-08-20**, same capture:
  `(-300,-3,284)` / `(-300,-3,287)`, replacing the wrong zone-wide `npc_list` default
  (`-55, 1.323, -103`) -- user-reported this should be near `(-300,-4,295)`, and the capture
  confirms that almost exactly.
- ✅ **`RUNE_UNLOCKED_POS` grid params corrected 2026-08-20**: was `(8, 8)`, real capture text
  shows "Unlocking Rune of Release (I-7)" -- corrected to `(8, 7)`.
- ✅ Lockbox rewards + Assault points (1320) now real.
- 🟢 **First live test (2026-08-20) found and fixed a real bug**: Warm-Up triggered correctly at
  every 20% threshold, but he never actually fled, and at 20% HP he "instantly vanishes, no
  animation." Root cause for both: `disengage()` was called before `pathTo()`/`castSpell()`, and
  both depend on state `disengage()` tears down -- `onMobFight` (where the flee's `pathTo()` calls
  live) only fires while engaged, and `castSpell()` with no explicit target falls back to the
  mob's *current battle target*, which disengage had just cleared, silently failing the cast.
  Fixed by dropping `disengage()` entirely: `pathTo()` now recomputes and re-fires every tick
  while a flee window is active (matching the only other real precedent in this codebase,
  Selh'teus), and the Warp cast now explicitly self-targets. Flee duration corrected from a 6s
  guess to 30s (confirmed by the user via a real video playthrough reference -- matches the real
  player Flee job ability's known duration, and he actively runs for the full 30s, not just a
  buff duration). See `Assault_Fix_Log.md` for the full technical writeup.
- 🟢 **Second live test (2026-08-20) found and fixed a real bug**: "he clipped outside the map."
  `pathTo()` has no built-in reachability/bounds check -- once the away-from-target flee direction
  happened to point off the compiled navmesh (predictable near an arena edge), each tick's
  recomputed point landed further off the mesh than the last, and he kept walking a straight line
  into it regardless (confirmed via the map-server log: dozens of consecutive navmesh pathfinding
  failures tracking his position marching steadily out of bounds). Fixed by validating every
  candidate flee point against the navmesh (`zone:checkNavPosition()`) before ever calling
  `pathTo()`, sweeping outward in both directions from the direct away-from-target angle until a
  valid point is found -- he can no longer be sent anywhere off the mesh. Still needs a fresh
  retest to confirm he now stays in bounds for the full 30s flee.
- ✅ **Third live test (2026-08-20): Rune of Release position and core mechanic both confirmed
  correct.** Warm-Up/flee trigger at every 20%, Warp cast + disappear at 20% HP all work as
  intended (Warp animation "cuts out a little at the end but passable"). Two more real bugs found
  and fixed:
  1. Still clips up walls -- `checkNavPosition()` alone only confirms a polygon exists near the
     point, not that a real walkable route gets there. Added a `checkNavPath()` check too (the same
     one used for the map-boundary fix), which requires an actual connected route and rejects
     candidates that merely sit near an isolated wall polygon.
  2. He always stopped to cast spells if the player stayed close while fleeing -- confirmed as a
     real engine-level gap: `DoCombatTick` tries spells/special skills/TP moves in C++ right after
     `onMobFight` returns, completely independent of the Lua script, so returning early from
     `onMobFight` never stopped them. Traced each path to a real, controllable off-switch instead
     of guessing: Silence (a genuine, confirmed gate in `CanCastSpells()`) blocks spellcasting,
     `MOBMOD_SPECIAL_SKILL=0` blocks special skills, and swapping `MOBMOD_SKILL_LIST` to empty
     blocks TP moves -- all three applied for the flee's exact duration and restored when it ends.
  Also confirmed by design (already correct, no change needed): the flee/`pathTo()` movement was
  already governed purely by elapsed time, with no dependency on any status effect's presence, so
  losing a status effect mid-flee was never going to stop him from continuing to path away.
- 🟢 **Fourth live test (2026-08-20) found and fixed a real design flaw**: "when his hp drops to
  under 20% while silenced, he skips this and once silence wears off will not resume." The Warp
  escape check was gated behind `fleeStage == 3`, only reachable once all 3 Warm-Up/flee/Silence
  cycles had each individually run their full 30 seconds in sequence -- if damage dropped HP under
  20% before that sequence formally finished, the escape could be delayed by up to 90 seconds or
  silently missed depending on timing. Restructured so `hpp <= 20` is now the single highest-
  priority check, evaluated first on every tick regardless of current stage -- it fires the Warp
  cast the instant he's not busy and not Silenced, and if it can't fire yet, keeps evading and
  retries every subsequent tick rather than waiting for the staged sequence to complete. Once HP is
  critical, the normal 80/60/40% trigger logic is fully bypassed too, so a big damage burst can no
  longer start a *new* suppression cycle on top of an already-critical HP state.
- ✅ **Real dialogue mined and wired, 2026-08-20**: found 3 spoken Sagelord Molaal Ja lines in the
  same capture. Same mislabeling pattern caught repeatedly this session -- the capture's own inline
  MesNum labels (7545/7546/7547) were wrong for all 3; real ids found by searching the client
  dialog table directly: **7530/7531/7532**. Checked real timing before wiring anything in: 7530
  fires the same second he starts casting Warp -- wired into the escape trigger. 7531/7532 both
  fire *after* "vanishes" with combat clearly continuing (he's hit and speaks again afterward) --
  read as an interim/non-final escape in that specific playthrough, not the true 20%-threshold one
  this mechanic implements (which despawns him for good), so left unwired rather than force-fit
  somewhere they'd fire after he's already gone. Also confirmed (no change needed):
  `ASSAULT_13_START` (7459) was already correct. Warp's animation was also confirmed already
  correct as implemented -- the real capture shows the animation value is just the spell id itself
  (261), exactly matching the existing `castSpell()` call.
- 🟢 **Fifth live test (2026-08-20): dialogue confirmed working, two more real bugs found and
  fixed.** (1) Still clips into walls, and the flee itself "rubber bands or skips around" -- caused
  by issuing a brand new `pathTo()` on every single tick, interrupting him mid-step before he could
  cover real ground each time; throttled to at most once every 2 seconds, letting each leg of the
  run complete smoothly. (2) He ran for a while before Warping instead of doing it instantly --
  caused by passively waiting for whichever flee cycle's Silence was active when HP first crossed
  20% to expire naturally (up to the full 30s); per user suggestion, now actively strips Silence
  the instant HP is critical instead of waiting it out.
- 🟡 **Sixth live test (2026-08-20, pushed as `1e9ab072c2`): rubber-banding and delayed-Warp fixes
  confirmed working, two more real bugs found and fixed.** (1) The Warp vanish animation still cut
  off -- `setStatus(DISAPPEAR)` fired the instant the cast completed, with no time for the vanish
  effect to play; fixed by delaying the despawn 3s after the cast (mission-completion still fires at
  the original moment, only the entity removal itself is delayed -- the 3s buffer is an estimate,
  not capture-confirmed). (2) Still clipped through walls despite the round-3
  checkNavPosition()/checkNavPath() validation -- **real root cause found this time**: `pathTo()`
  defaults to `PATHFLAG_RUN | PATHFLAG_WALLHACK | PATHFLAG_SCRIPT` when called with no explicit
  flags (every call in this file), and `PATHFLAG_WALLHACK` literally lets him path through walls --
  the navmesh validation was real and correct, but irrelevant, since collision was being overridden
  regardless. Fixed by passing `PATHFLAG_RUN | PATHFLAG_SCRIPT` (no WALLHACK) explicitly. See
  `Assault_Fix_Log.md` for the full writeup.

- ✅ **Seventh live test (2026-08-20): both sixth-round fixes confirmed working.** Warp vanish
  animation now plays correctly; no wall-clipping observed. AI flee pathing judged "a little off but
  good enough" by the user -- not being chased further.
- ✅ **Door blocker resolved, user-confirmed live 2026-08-22**: the door is no longer blocking --
  Sagelord Molaal Ja can be reached, engaged, killed, and the mission completes. **Mission passes
  end-to-end.**
- ✅ **Level/HP correction, found via real capture data (2026-08-22)**: user asked to double-check
  his HP after this session's extensive flee-mechanic rework. Checked `Sagelord_Molaal_Ja.lua`'s
  git history first -- no HP-affecting code was ever touched (the file only ever *reads*
  `getHPP()` for the flee thresholds, never sets/scales HP). Real cause found in SQL: `mob_groups`
  row for this zone (groupid 10, poolid 3437) had `minLevel=82, maxLevel=84`; 2 independent real
  captures' `LevelRangeTrack` data for this exact entity (UniqueNo `17047590`, confirmed matching
  `ID.mob[13].SAGELORD_MOLAAL_JA` exactly) both agree the real level is a fixed `80` (not a range).
  Corrected to `80,80`. This was 2-4 levels too high, which inflates HP via the level-scaling
  formula -- likely the real source of whatever felt off. Not yet live-tested against this
  specific fix (mission was already confirmed passing at the higher level -- this is a fidelity
  correction, not a functional fix).
- 🟢 **2026-09-12, major AI overhaul (user-requested, not a bug fix): reinforcement-seeking flee
  behavior added.** Previously he just ran away from the player along a swept vector with no
  destination; now he actively seeks out the nearest living, not-yet-engaged Mamool Ja (9 trainees +
  5 lizard pets) and paths to it, transferring enmity on arrival so it becomes a real reinforcement,
  capped at 4 per flee cycle. Also added: NM convention (`hideHP(true)`, "impossible to gauge" per
  user request), flee duration raised 30s->60s to give the new seeking behavior room to work, a
  raw-HP stage-floor clamp (`clampToStageFloor`) so a single burst hit can no longer skip a stage,
  and a short (15s) separate invincibility window independent of the full flee duration. HP raised
  60000 flat (from the old level-scaled value) per user direction, sized for a level-90 server where
  players can weaponskill for 10-20k. Extensive live-test/fix cycle across many real bugs found this
  way: a DoT-bypasses-invincibility-mods gap (fixed via an HP-lock/restore), a permanent stuck-
  invincible deadlock from `MOBMOD_SKILL_LIST` not actually gating spellcasting (SILENCE does; fixed
  by applying it immediately/unconditionally instead of only once Warm-Up starts), a hard 8s timeout
  backstop for any remaining stuck-pending edge case, a bogus `MOBMOD_SPECIAL_SKILL` literal `1`
  causing a benign-but-real engine error (fixed to `0`), two separate "gets stuck pathing to a
  reinforcement near a thin navmesh wall" spots (both now trigger a return-home-then-flip-bias
  response instead of endlessly retrying), a random 50/50 east/west reinforcement-seeking bias
  (flips when a wall-trap spot is hit), and a getHPP()-rounding mismatch that could permanently
  desync the clamp from the threshold check (fixed by comparing raw HP throughout instead of
  percentages).
- ✅ **2026-09-12, user-closed as good enough.** After the raw-HP-clamp fix, remaining live tests
  showed the core sequence (clamp -> threshold -> invincible -> Warm-Up -> flee/reinforcement-
  seeking) firing correctly and in order across all 3 stages plus the 20% critical escape, including
  a stale-`nextFleeStep`-throttle bug (fixed by resetting it at the start of every new flee stage)
  that had briefly caused "Warm-Up/invincible fire but the flee itself never moves" on one run. A
  rarer variant of the same general HP-threshold-timing glitch may still exist under specific timing
  conditions (not fully root-caused), but user has confirmed all other mechanics (positions,
  dialogue, reinforcement AI, wall-trap recovery, Warp escape/despawn) are solid, judged this
  non-critical, and is moving on. **Mission passes end-to-end**, same as the 2026-08-22 baseline,
  now with the full 2026-09-12 AI rework on top.

### Troll Fugitives (Lebros Cavern, mission 23)
**Overall status: ✅** -- User-confirmed live in-game -- full playthrough tested and passed.
- ✅ Fully validated 2026-08-18 by a real capture: kill-all-15, entrance, and lockbox rewards all
  confirmed exactly right. Assault points corrected from a 1000 guess to the real 1100.
- ✅ **User-confirmed live in-game 2026-08-20**: all 15 mob spawn positions correct, real 2-hour
  ability, Rune of Release position correct, Ancient Lockbox works.
- ✅ **User-reported 2026-08-20, fixed**: Trolls should "start out somewhat wounded... range in
  health from 25% to 75%," per real mechanic. The 25-75% HP roll already existed in
  `mobs/Broken_Troll_Soldier.lua` but was wrongly applied on `onMobEngaged` instead of
  `onMobSpawn` -- meant they spawned at full HP and only got wounded on first engage, and would
  reset/partially heal back up on every subsequent re-engage after losing aggro. Moved to
  `onMobSpawn` so it applies once, at spawn, and stays for the fight.
- ✅ **User-confirmed live in-game 2026-08-20**: retested after the `onMobSpawn` fix -- HP
  percentages meeting expectations, all 15 randomly generating in the real 25-75% range.
  **Mission fully complete, no outstanding issues.**

### Saving Private Ryaaf (Periqia, mission 33)
**Overall status: ✅ (2026-08-23) -- user-confirmed complete.** Proximity reveal, targetability,
Fomor auto-ambush, survivor dialogue with real names, and mission completion (rune unlock on 3/3
found) all live-tested and working. The converging roaming-Fomor difficulty mechanic (see the
bottom entry) was attempted, live-tested, and rolled back after 2 real bugs -- disabled for now,
not a blocker. One known non-blocking cosmetic issue remains open (Rhagmakah's `<Speaker Name>`
self-reference), also see the bottom
entries.
- ✅ **User-reported 2026-08-22**: a "Bridge Switch" prop visible and interactable (disappears on
  trigger) with no apparent function in this mission. Real entity, but for a different mission --
  belongs to Building Bridges (instance 35), fully wired there (`Bridge_Switch.lua`, `IDs.lua`
  constants, `building_bridges.lua`). Zero references anywhere in this mission's own files. Cross-
  registered here (and, found while checking, also to Wake the Puppet) by mistake during the
  2026-08-21 NPCLogger cross-reference pipeline batch pass (`d7378fe101`) -- both missions share
  the same physical Periqia zone, and the pipeline appears to have matched this entity to multiple
  missions' captures by proximity without confirming it was actually load-bearing for each one.
  Removed the stray registration from `instance_entities` (instance 33). Building Bridges' own
  registration (instance 35) is untouched -- all 4 switches still function correctly there.
- ✅ Built this session (SP-rank), now validated by a real capture: entrance fixed (was on the
  Periqia shared placeholder). Lockbox reward (???_shield) and Assault points (1210) now real --
  previously fell through to XP/gil only.
- ✅ **User-provided 2026-08-19**: full lockbox data supersedes the single-item capture above --
  4 qItems (??? Axe / ??? Polearm / ??? Shield / ??? Box, equal-split, no odds given) and 4
  regItems (Hi-Potion +3, Hi-Reraiser, Hi-Potion Tank, Hi-Ether Tank). Wired into
  `Periqia/npcs/Ancient_Lockbox.lua`.
- ✅ **Rebuilt 2026-08-20** with the real mechanic (user-provided wiki writeup, cross-checked
  against a real capture): the old "trigger-all-3, one fixed spot each" build was wrong -- real
  mechanic is 5 rooms (N/W/S/E/Center), each with a hunched-over figure that resolves to one of the
  3 real survivors or an Experimental Undead (Fomor), randomly picked from 5 real wiki patterns per
  instance, plus 3 ambient Cursed Chigoe per room. 15 real Chigoe + 8 real Experimental Undead spawn
  points were already sitting unwired in this repo's SQL -- now wired in. Room/compass layout and
  facing-direction hints confirmed against 2 independent real captures both matching a wiki pattern
  exactly. Real 13-line dialogue block found and wired for all 3 survivors (previously silent).
  Bonus: `RUNE_UNLOCKED_POS` grid corrected from the generic `(8,8)`=I-8 guess to the real I-7. See
  `Assault_Fix_Log.md` for the full writeup.
- 🟢 **First live test (2026-08-20): the "turns into" reveal was completely broken**, both
  root-caused and fixed:
  1. The 3 real-NPC rooms never responded to trigger at all -- Ryaaf/Balarahb/Rhagmakah's
     `entityFlags` (2075) have had `FLAG_UNTARGETABLE` set since the original 2026-08-18 build,
     never caught because nobody live-tested trigger interaction until now. Same bug class already
     found once this session on Lamia No.13's Ancient Lockbox. Fixed: 2075 -> 27.
  2. The 2 Fomor rooms showed a live Experimental Undead from the start instead of a disguised
     figure -- the earlier "known simplification" (direct `SpawnMob` at instance creation, no
     decoy) turned out to matter for the puzzle. Fixed properly with 2 new `npc_list` rows acting
     as `HUNCHED_FIGURE` decoys (reusing Ryaaf's look) that only spawn/engage the real Fomor on
     trigger -- same shape as Golden Salvage's `Cursed_Chest.lua`.
  See `Assault_Fix_Log.md` for the full writeup. Not yet retested live.
- 🟢 **Second live test (2026-08-20, with a full map-server error log): the round-1 fixes above
  didn't actually take -- 3 more distinct real bugs**, all confirmed directly from the log:
  1. The 2 `HUNCHED_FIGURE` decoys never worked at all -- log: `No Valid Function for
     HunchedFigure1 in Periqia`. Their `npc_list.name` (`'HunchedFigure1'`/`'2'`) didn't match the
     script filename (`Hunched_Figure.lua`) -- this engine resolves triggers by exact name match.
     This alone also explains "Fomors don't spawn" (the decoy code that spawns them never ran).
     Fixed: renamed both rows to `'Hunched_Figure'`.
  2. Cursed Chigoe were untargetable -- separate bug, separate table: `mob_pools` `entityFlags`
     (2689) also had `FLAG_UNTARGETABLE` set. Fixed: 2689 -> 641 (matches a real working sibling,
     plain `Chigoe`, exactly).
  3. The 3 real survivors still showed their real name -- this engine has no way to hide a
     nameplate independent of the same `name` field that drives script lookup. Real fix: renamed
     all 5 rooms' occupants to the identical `'Hunched_Figure'` and consolidated 4 separate files
     into one, `npcs/Hunched_Figure.lua`, telling them apart by id instead of name -- genuinely
     achieves "figures do not show names" for the first time.
  Also silenced 2 harmless log-spam errors (`onMobDeath` undefined for `Cursed_Chigoe`/
  `Experimental_Undead` -- neither file existed; added minimal stubs).
  **Not resolved**: the screenshot's `Obtained temporary item: !` (blank name) alongside HELM-style
  "sparkling object" text doesn't match anything in this mission's own capture data at all --
  likely an unrelated system firing during the same test session, not this mission's own scripts.
  Flagged rather than guessed at; see `Assault_Fix_Log.md`.
- 🟢 **Third live test (2026-08-20, with screenshots + terminal log): 3 more real bugs**:
  1. Mission completed after finding only 1 real survivor -- user confirmed re-interacting with
     the same NPC more than once. Real cause: no "already triggered" guard on the survivor branch,
     so an impatient re-click during the 8-10s staggered dialogue queued a second full set of
     timers, each incrementing progress. Fomor branch unaffected (already despawns immediately).
     Fixed with the same localvar guard pattern used elsewhere in this codebase.
  2. Name/identity still visible despite last round's rename -- the static `namevis` default
     wasn't sufficient on its own. Fixed by calling the real runtime `hideName(true)` explicitly on
     all 5 room occupants after positioning them, instead of relying on a static SQL default.
  3. Real, pre-existing, unrelated bug surfaced by terminal log: the South-room
     `Experimental_Undead_blm` (`mob_pools` poolid 5469) had `mJob`/`sJob` set to `2` (MNK) instead
     of `4` (BLM) despite its own name -- MNK has no real MP, yet it's assigned a spell list,
     throwing `"has no mp for casting spells!"` the moment it engaged. First content to ever
     actually spawn this row. Fixed: 2,2 -> 4,4.
  **"Text still incorrect" -- confirmed real, found and fixed**: all 13 survivor dialogue lines
  were drifted **+15** -- sourced a few rounds back from a raw capture whose client build numbers
  this dialog table differently than dat-extractor's real dump for this zone
  (`D:\Claude\dat-extractor-cache\periqia_6476.json`). Confirmed line-by-line, not just
  index-shifted blindly. Also confirmed this is *not* a zone-wide shift -- Periqia's own
  system-message block (`TIME_TO_COMPLETE`, `RUNE_UNLOCKED_POS`, etc.) already matches
  dat-extractor exactly. Fixed: all 13 constants corrected in `IDs.lua`. This also confirms the
  door/bridge/sparkling-object text from the screenshots is real, unrelated content sitting nearby
  in the *same* shared dialog table (Building Bridges/Defuse the Threat's own strings) -- not a
  drift bug in this mission's dialogue, just neighboring indices.
- 🔴 **2026-08-23, attempted and rolled back after live-testing found 2 real bugs.** The wiki's
  "roaming tunnel Fomors move toward where the NPCs are" behavior -- user flagged this as key to
  the mission's real difficulty (rooms get progressively harder to reach as they're cleared, not
  just a race against the clock). Went through a few iterations (nearest-active -> random-active
  targeting, once user pointed out nearest just clusters all 3 in the center) before live-testing
  surfaced:
  1. Movement was erratic/way too fast. Root cause: the Lua side used the wrong engine hook --
     `entity.onMobRoam` is NOT gated by `ROAMFLAG_EVENT`/the normal roam-cooldown state machine at
     all. That's a real, separate hook, `onMobRoamAction` (`luautils::OnMobRoamAction`,
     `mob_controller.cpp`'s `ROAMFLAG_EVENT` branch). What actually ran was
     `luautils::OnMobRoam` (`luautils.cpp:2914`), an unconditional "every 3 real seconds,
     regardless of roam flags or whether the mob is still mid-path" hook -- so a fresh `pathTo()`
     was firing every 3s, constantly interrupting/restarting whatever path was already in
     progress.
  2. Reaching a room's doorway triggered an immediate, permanent despawn with no respawn --
     confirmed live, separate from bug 1, not root-caused (no `MOBMOD_NO_DESPAWN` on this pool).
  **Disabled rather than patched further** -- `mob_pools` poolid 1274's `roamflag` reverted
  `256 -> 0` (these 3 fall back to plain default wander), and the targeting/movement Lua left
  commented out in `mobs/Experimental_Undead.lua` with a full writeup of both bugs, for a future
  pass rather than guessing at a fix live. `MOBMOD_ROAM_COOL` kept at a slower-than-default 10s for
  the default wander they fall back to.
- 🟡 **Still-open, lower-priority simplification**: South/West room facing-direction bytes are
  unconfirmed placeholders (only North/East/Center have a real captured sample).
- **Needs a DB reimport** (`py -3 dbtool.py`) for the name renames, both `entityFlags` fixes, and
  the `Experimental_Undead_blm` job fix.
- 🔴 **Fourth live test (2026-08-20), reported but deliberately NOT fixed yet -- 4 more issues**:
  1. Self-referential dialogue lines render blank where the speaker's own name should be (e.g.
     Rhagmakah's real line 1 is "...My name is ≺Speaker Name≻. It wouldn't have been long
     before..." and Balarahb's line 2 is "...You came to rescue me after talking to ≺Speaker
     Name≻?" -- both confirmed straight from the dat-extractor dump). **Likely cause**: `Speaker
     Name` is a name-substitution placeholder, and `messageText()` (used for all of this mission's
     dialogue) can't source one -- same limitation already hit and fixed elsewhere this session
     (Mulwahah's item-name substitution, see `topaz_npc_item_name_substitution` project memory) --
     that fix needed a different call, `messageSpecialFrom()`, specifically because `messageText()`
     has no way to carry a substitution parameter. Plausible, not confirmed -- not investigated
     further yet.
  2. The room occupant never visually stands up into its real model on reveal -- it stays in the
     crouched/kneeling hunched-figure pose right up until it disappears, for both real survivors
     and Fomors.
  3. Rune of Release's position may be wrong -- needs confirming against the parser logs (not yet
     re-checked since the mechanic rebuild).
  4. **The whole "turns into" approach likely needs a real rework, not another patch** -- the
     nameplate is still visible even after `hideName(true)` (added last round), meaning that
     runtime call isn't achieving real anonymity either. Combined with issues 1-2 above, the
     current design (repositioning/revealing the real named entities directly, plus 2 synthetic
     decoys) may be fundamentally the wrong shape for this mechanic, not just missing a flag
     somewhere -- worth reconsidering the whole approach before patching further.
  5. **Correction, user-clarified 2026-08-22**: the `entityFlags` `FLAG_UNTARGETABLE` fix applied
     to Ryaaf/Balarahb/Rhagmakah earlier this session (2075 -> 27) was **wrong**. These 3 are meant
     to be genuinely untargetable/unseeable until the room's reveal happens -- being targetable
     lets players find the real survivor by scanning targets instead of actually solving the room
     puzzle, defeating the whole mechanic. Same principle confirmed on Imperial Agent Rescue's
     Brujeel (also flagged as a "bug" by a systematic cross-reference scan, also not one --
     Brujeel is intentionally hidden/untargetable until the pot lid opens, dialogue-only, no
     interaction). **Not reverted yet** -- this is exactly why item 4 above calls for a real
     rework rather than another flag flip: simply restoring `FLAG_UNTARGETABLE` without also
     solving the reveal-trigger mechanism would just reintroduce "can't interact with it at all."
     Revisit `entityFlags` alongside whatever the reworked approach turns out to be, not in
     isolation.
     **Why the earlier fix happened at all, user-clarified**: making them targetable was never
     meant to be the real mechanic -- it was the only way found to "activate" the reveal at the
     time, because **proximity alone wasn't triggering anything**. The real retail mechanic is
     very likely proximity-based (the wiki's own wording is "approach the hunched-over figure"),
     so the actual fix this mission needs is a working proximity-trigger (`onMobWeaponSkill`/
     `AGGRO_RANGE`-style zone or a `checkDistance()` poll, not a player-initiated target+interact),
     with `FLAG_UNTARGETABLE` staying set throughout. Worth investigating why a proximity check
     wasn't firing before assuming a new one from scratch is needed.
  None of the 4 above have been investigated or fixed -- flagged here per user request, to work
  through later rather than right now.
- ✅ **REWORKED 2026-08-22, real mechanic found via full capture history data (not just a single
  snapshot).** User asked whether captures had position/model transition data for the reveal --
  the NPCLogger `history` table (a per-tick delta log, not just a final-state snapshot) turned out
  to have exactly that, for all 3 real survivors, in both available captures:
  - **Before reveal**: `legacy_animation=33` (hunched pose), `legacy_flags=2075` (untargetable +
    hidden name), `legacy_namevis=72` (name hidden).
  - **At reveal** (all 3 changes land within ~3 seconds of each other, **with no click/trigger
    event anywhere in the delta stream beforehand**): `legacy_flags: 2075 -> 27` (targetable),
    `legacy_namevis: 72 -> 0` (name visible), `legacy_animation: 33 -> 0` (standing pose), then a
    `dir` change shortly after (faces the player).
  - The missing click event is the key fact -- this rules out a player-initiated trigger and
    confirms the reveal is proximity-based, exactly matching item 5's hypothesis above (which
    was never acted on). Confirmed identical for `Balarahb`/`Rhagmakah` too. The `look`/model
    field never changes in any delta -- only `animation` -- so this is a pose swap on the same
    model/equipment, not a model change.
  - User's design call (differs slightly from raw capture, deliberately): stay untargetable
    while hunched (matches capture), but **also correctly targetable after reveal** (also matches
    capture -- initial ask was "never targetable," corrected to "targetable after reveal, matching
    the data").
  - **Implementation**: `npc_list.sql`'s `entityFlags` for all 5 room occupants (3 survivors + 2
    Fomor decoys) reverted `27 -> 2075` (matching real captured default -- the 2026-08-20 "fix" to
    27 was itself the bug, made them permanently targetable from spawn). `instances/
    saving_private_ryaaf.lua` now explicitly forces `setAnimation(33)`/`untargetable(true)` at
    spawn (same "don't trust the static default alone" precedent as `hideName(true)` already used
    there), and polls proximity every real second via `onInstanceTimeUpdate` (the hook's own
    native 1s rate, `instance.cpp`'s `CInstance::CheckTime`) -- `checkDistance() <= 8` (an
    estimate, not capture-confirmed radius) triggers `revealOccupant()`:
    `untargetable(false)`/`hideName(false)`/`setAnimation(0)`/`lookAt(player)`. `Hunched_Figure.lua`
    got a defensive `revealed`-guard on `onTrigger` too, in case `untargetable()` doesn't also
    block the trigger action on its own. This directly resolves item 4/5's "needs a real rework"
    flag from the 4th round -- the missing piece was the proximity poll, not another flag flip.
  - **Same pattern applied to Cursed Chigoe** (the ambient obstacles in this mission), per a
    related user request: real FFXI Chigoes are classically undetectable/untargetable until they
    aggro. `mob_pools` poolid 865's `entityFlags` restored `641 -> 2689` (adds back
    `FLAG_UNTARGETABLE`, which a 2026-08-20 fix had removed entirely to solve "can't interact with
    it" the wrong way). `mobs/Cursed_Chigoe.lua` now has `onMobSpawn` (force untargetable/hidden)
    and `onMobEngaged` (reveal on real aggro) -- same reveal-on-event shape as the survivors above.
  - Not yet live-tested against this version. Needs `py -3 dbtool.py` (SQL changes across
    `npc_list.sql`/`mob_pools.sql`) before retesting.
- ✅ **Fifth live test (2026-08-22/23): confirmed working**, plus 2 real regressions found and
  fixed along the way:
  1. `setName()` (new binding, renames a survivor to their real name on reveal for the nameplate
     and outer dialogue prefix) was being called *before* the player could click -- broke
     `onTrigger` entirely (`luautils::OnTrigger` resolves the script by the entity's **live**
     name at click time, not a cached binding, so the click looked for a nonexistent
     `npcs/Ryaaf.lua`). Fixed by moving the rename to fire *after* the click already resolved.
  2. Fomor decoys required a click before ambushing, which isn't how an ambush should work. Moved
     their spawn/engage logic into the proximity-reveal path itself, firing automatically the
     moment they're revealed -- real survivors still require an actual click for their rescue
     dialogue.
  Also fixed: a visual glitch where the decoy's nameplate rendered at its feet mid-transition
  (stand animation and the mob-swap were firing in the same tick -- added a 1.5s delay so the
  animation actually plays out first), and the outer "Name: ..." dialogue prefix was blank for
  everyone (switched `messageText()` -> `messageSpecialFrom()` with `ShowName=true`, which embeds
  the source entity's live name in the packet -- `messageText()` has no name-embedding at all).
- 🟡 **Known non-blocker, still open**: Rhagmakah's self-referential dialogue line ("My name is
  ≺Speaker Name≻...") still renders the placeholder blank -- confirmed via dat-extractor the text
  ID itself isn't drifted, and confirmed the outer name-prefix mechanism (`messageSpecialFrom`'s
  `ShowName` flag, which fixed the prefix issue above) writes the name synchronously into the
  packet, so a timing/race explanation doesn't actually hold up under closer reading of
  `message_special.cpp` -- an earlier "fix" based on that theory did not resolve it live. Root
  cause of the *inline* placeholder specifically (as opposed to the outer prefix, which does work)
  remains unconfirmed. User explicitly marked this a non-blocker -- mission is otherwise complete.

### Extermination (Ilrusi Atoll, mission 43)
**Overall status: ✅ (2026-08-20) -- user played this mission through in this build, start to
finish, and confirmed it works. No outstanding issues.**
- ✅ Entrance position was already close; only rotation was off (149 -> real 64), fixed.
- ✅ Kill-all-20 mechanic confirmed correct (21 real kills observed). Lockbox rewards + Assault
  points (1210) now real.
- ✅ **Full live-test chain confirmed by user, 2026-08-20**: fixed a chain of 4 real bugs found
  during testing (see `Assault_Fix_Log.md` for the full trail) --
  (1) `onInstanceCreated` was pre-spawning the 4 dormant `UNDEAD_*` bonus mobs, breaking their
  1-in-5 boss-chance trigger and silently losing progress points;
  (2) all 4 Carrion family scripts referenced `ID.mob.UNDEAD_*` instead of the correctly-nested
  `ID.mob[43].UNDEAD_*`, crashing the trigger entirely;
  (3) `onInstanceProgressUpdate` checked `progress == 20` (exact equality) instead of `>= 20`;
  (4) Carrion Leech #7 (`17002537`) had a corrupted spawn Z coordinate (`3747.511`, later found to
  still be off-navmesh even after an initial correction) stranding it off the compiled navmesh --
  fixed for real using the new `!checknav` GM command to live-verify a walkable position (see
  `documentation`/memory on that tool). User confirms: Undead mobs now spawn correctly on trigger,
  progress correctly reaches 20/20 on a full clear, Rune of Release and Ancient Lockbox both
  trigger, and the instance can be exited normally. No outstanding issues.

---

## LC (Lance Corporal)

### Shanarha Grass Conservation (Leujaoam Sanctum, mission 4)
**Overall status: ✅ -- User-confirmed complete 2026-08-30.** Full real mechanic built this
session: 20 Coney spawn together in the start room, split into a north/south dash, then seek and
graze the Vegetation patches scattered through the dungeon -- see `mobs/Coney.lua`'s own header for
the complete design writeup (real capture-decoded 4-stage decay text, exclusive patch-claiming so
no two Coney graze the same one, a delayed dash so Sleepga-the-pack stays viable per the wiki, and
an explicit script-level link check to guarantee linking actually happens). All prior bugs
resolved: ice-wall corridor blockers, the false "Vegetation is just decorative scenery" call
(corrected below), Coney invisible on radar.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data).
- ✅ **User-confirmed live 2026-08-24: ice wall blockers removed**, same `_1x*`/`_jx*` door-prop
  identifier drift fix as Leujaoam Cleansing/Orichalcum Survey.
- ✅ **2026-08-30, real bug found: Vegetation was never actually visible**, contradicting this
  section's own earlier 2026-08-19 conclusion that it was "confirmed decorative flavor-text
  scenery" -- that call was wrong. Real cause: `npc_list`'s SQL default `status=2` (DISAPPEAR) for
  all 29 Vegetation rows, and `instances/shanarha_grass_conservation.lua` never set them to
  NORMAL. User confirmed live: visible under `!navdebug` but never on widescan or in the client.
  Fixed with a real `setStatus(NORMAL)` loop at instance creation.
- ✅ **2026-08-30, real 4-stage decay/eating mechanic built from scratch**, replacing the earlier
  "completely unimplemented" placeholder. User asked whether the Thris capture had real "grass
  eaten" warning dialogue -- it did, mislabeled by this zone's own known +15 capture-tool id drift
  (dat-extractor-confirmed real MesNums 7558-7561, "untouched"/"chewing"/"torn into
  most"/"almost destroyed"). Traced one specific Vegetation entity across a capture's full
  timeline to confirm the progression is genuinely monotonic, not a single instant "eat". Built:
  each Coney spawns together, dashes north/south after a real delay window, then seeks a free
  (unclaimed) patch and grazes it in real 30-second stages (4 stages = ~2 min/patch
  uninterrupted, per user's own "a few minutes total" spec) -- interrupted by combat, resumed by
  any Coney since decay state persists on the patch itself. Fail threshold: more than 20 of 29
  eaten (user-specified). Assault points: `50 * vegetation_remaining`, capped 1333
  (`Rune_of_Release.lua`).
- ✅ **2026-08-30, real oscillation bug found and fixed**: re-picking the nearest free target
  every AI tick made a Coney flip-flop between 2 patches forever whenever a closer one freed up
  or its current target got claimed mid-approach. Fixed by committing to a travel target and only
  re-evaluating on arrival (user's own fix direction).
- ✅ **2026-08-30, real linking bug found and fixed**: 2 Coney at the same patch, one attacked,
  the other never linked even at point-blank range. Root-caused to a real engine gap -- native
  `TryLink()` only adds enmity, it doesn't force engagement, and the natural roam-to-engage
  transition was likely being starved by this script's own continuous scripted movement. Fixed
  with an explicit, guaranteed script-level link check (force-`engage()` onto any nearby Coney
  that's already fighting), independent of the native transition's timing.
- ✅ **2026-08-30, real Wide Scan gap found and fixed with a new C++ capability**: Coney needed to
  stay named/targetable but disappear from Wide Scan specifically -- no existing SQL/entityFlags
  bit could express that split (every one that blocks `isWideScannable()` also hides the name or
  targetability). Added a real, scoped addition to `src/map/entities/baseentity.cpp`'s
  `isWideScannable()`, gated on a `wideScanHidden` localVar (uses the already-generic
  `setLocalVar`/`getLocalVar` Lua bindings, no new binding needed). User-confirmed live: Coney no
  longer appears on widescan. Same mechanism applied to `Black_Baron.lua` (Periqia, Shooting Down
  the Baron) and `Merrow_No16.lua` (Periqia, Operation: Snake Eyes) per user follow-up request --
  see those missions' own sections.

### Breaking Morale (Mamool Ja Training Grounds, mission 14)
**Overall status: ✅ -- User-confirmed complete 2026-08-30.** Every real gap tracked below (crate
loop, doors, Viscous Liquid mechanic, Quhaaja confirm, Assault points) has been resolved and
live-tested. See the bottom of this section for this session's closing fixes.
- ✅ Entrance position fixed 2026-08-18.
- ✅ Real mechanic (crate loot -> turn in to Quhaaja) replacing the old kill-all-18 placeholder.
- 🟡 **Viscous Liquid mechanic pinned down precisely 2026-08-19, still not wired in.** Re-analyzed
  both captures (including the previously-written-off "(4)" loss) with exact timestamp
  correlation: it is NOT a player-triggered prop. A Mamool Ja Trainer periodically uses hate/aggro
  on the player ("Scaleless heathen... A taste of my wrath, you shall have!"), which teleports the
  player onto Viscous Liquid ("You seem to have been brought here by some strange magic...",
  "There is a curious liquid here.", "Thris is overcome by a peculiar sensation."). If the player
  is holding an uncollected Supplies Crate temp item at that moment, it's removed ("The supplies
  you seized are missing!", real MesNum 7545 confirmed via dat-extractor); if not holding one,
  nothing happens. Every single occurrence across both captures matches this pattern with zero
  exceptions. Not implemented -- the actual trigger (a mob periodically teleporting its target to a
  fixed NPC + firing a CS-event sequence) has no existing pattern in this codebase, and the exact
  trigger cadence/condition isn't pinned down precisely enough by these captures to hard-code with
  confidence. See `instances/breaking_morale.lua`'s header for the full writeup.
- 🔴 The "8 crates = complete" threshold is still an assumption, not confirmed exactly by either
  capture -- **both available captures ended in mission failure/timeout without ever completing**
  (capture 1: 6 successful Quhaaja turn-ins in the real 15-minute limit, solo, then failed;
  capture "(4)": no turn-in data at all, consistent with its "party wiped" note). 6-in-15-min-solo
  is circumstantial evidence 8 may be a tight ask solo, but not proof the real threshold is lower.
  Left at 8 (matches the real physical crate count) pending a capture that actually completes.
- 🟢 **Follow-up 2026-08-19**: same `ITEM_OBTAINED`-instead-of-`PLAYER_OBTAINS_TEMP_ITEM` bug found
  in Orichalcum Survey also existed here (crate loot would have shown "Obtained <item id> gil").
  Fixed with real data from an already-downloaded capture + dat-extractor -- same shared
  system-wide message id (7310) confirmed for Leujaoam Sanctum. Also corrected this zone's own
  `ITEM_OBTAINED`/`GIL_OBTAINED`/`KEYITEM_OBTAINED`/`ITEM_CANNOT_BE_OBTAINED` block, off by the
  same -1 as Leujaoam's. Worked autonomously while the user was away -- not yet live-tested.
- ✅ **Re-verified 2026-08-19**: `PLAYER_OBTAINS_TEMP_ITEM` (7310) re-confirmed still correct
  against the capture's own decoded crate-loot text ("Obtained temporary item: a wild rabbit
  tail!"). The capture's raw inline `MessageNumber: 7325` field is a known CapLog mislabeling
  artifact -- 7325's real client text is unrelated ("VIT Down removed."), confirmed via
  dat-extractor. No bug here; the decoded plain text was right all along.
- ✅ **User-provided 2026-08-19**: real lockbox reward data received (previously fully missing,
  flagged in the missing-rewards audit). qItems ??? Polearm / ??? Sword / ??? Box (equal-split, no
  odds given); regItems Hi-Potion +2, Hi-Potion Tank, Reraiser. Wired into
  `Mamool_Ja_Training_Grounds/npcs/Ancient_Lockbox.lua`.
- 🔴 **User-reported 2026-08-24**: doorways throughout this level are impassable, caused by helper
  object (`_1u*`/`_ju*` door-prop family) placement or registration. Only one door (`_juf`,
  17047910) has ever worked, and even that one is intermittent, not reliably passable. Extensive
  live troubleshooting so far: confirmed all 4 real door props registered to this mission
  (`_jue`/`_juf`/`_jug`/`_juh`, 17047909-17047912) have correct positions, animation, and
  entityFlags matching real captures exactly; confirmed the server-side navmesh is fully walkable
  at the doorway tested (`checkNavPosition`/`checkNavPath` both true across a full Y-sweep at the
  same X/Z) -- ruling out both "prop drift" and "baked navmesh gap" as the cause. Root cause still
  not found. `_juh` has been repositioned multiple times live (`!logpos`-verified) without
  resolving it. Next diagnostic step: a `!navdebug` scan of each doorway's surroundings to check
  for an unaccounted-for entity physically blocking the space that isn't part of the known
  `_1u*`/`_ju*` set. Separately, this same live-testing pass found and fixed an unrelated real bug
  in this mission: all 8 Supplies Crates had `status=6` (CUTSCENE_ONLY) baked into their SQL rows,
  making them invisible/non-interactable the entire time -- fixed to NORMAL; crate positions
  themselves still awaiting live confirmation against fresh `!logpos` readings.
- 🟢 **User-reported crash 2026-08-24**: turning in a crate item to Quhaaja threw a hard Lua error
  and gave no NPC response (`stack index -1, expected number, received nil` inside `delItem`,
  `npcs/Quhaaja.lua:37`). Root cause: `Supplies_Crate.lua` grants loot via `addTempItem()`
  (`LOC_TEMPITEMS`), but Quhaaja's turn-in logic checked/deleted the item from regular inventory
  (no location arg). `delItem()`'s own C++ (`src/map/lua/lua_baseentity.cpp:3147`) unconditionally
  calls `.as<uint32>()` on the omitted 3rd argument without checking it's present first -- a real
  engine-side bug that crashes on exactly this kind of missing/nil trailing arg. Fixed by passing
  `tpz.inventoryLocation.TEMPITEMS` explicitly on both the `hasItem`/`delItem` calls, matching the
  already-established correct pattern used elsewhere in this codebase for temp-item turn-ins
  (`apkallu_seizure.lua`, Lebros Cavern's `Imperial_Stormer.lua`). Also fixes a second, quieter bug
  this uncovered: without the explicit location, the item was never actually being consumed on
  turn-in even before the crash was noticed. Lua-only, not yet live-tested.
- 🟡 **User-reported 2026-08-24**: Viscous Liquid grants the ILLUSION status icon but no visual
  costume change, and Mamool Ja Recruit/Trainer still attack while it's active. Root causes:
  (1) `globals/effects/illusion.lua` was a completely empty stub, calling nothing on gain/loss --
  fixed to call the real `player:setCostume(id)` binding, but the actual Mamool Ja costume id is
  an unconfirmed placeholder (0 = disabled) -- no real value found anywhere in this repo or the
  reference repos; needs live-testing via `!costume <id>` (also fixed this turn -- it was calling
  a dead, unregistered `player:costume()` method, same bug independently found in
  `globals/effects/costume.lua`, the shared script every real costume item in the game relies on,
  also fixed). (2) Aggro suppression while disguised was a known, already-documented gap
  (`Viscous_Liquid.lua`'s own header flagged it as "NOT implemented... follow-up") -- implemented
  via `onMobEngaged` on both `Mamool_Ja_Recruit.lua` (had none before) and
  `Mamool_Ja_Trainer.lua` (already had engage logic for the teleport-to-prison mechanic, just
  never checked the disguise first) -- both now immediately reset enmity against a
  ILLUSION-carrying target instead of engaging. Also fixed the same `hasItem`/`delItem` temp-
  storage bug from the Quhaaja fix above, found in `Mamool_Ja_Trainer.lua`'s own item-strip logic.
  **Follow-up same day, user provided the real Costume-effect wiki text**: DoT corrected 30 -> 22
  dmg/tick (user confirmed the DoT itself was already firing correctly, just at the wrong value);
  added the previously entirely-missing movement speed reduction (`globals/effects/illusion.lua`,
  `tpz.mod.HASTE_MAGIC` at -10, same convention `SLOW`'s own effect script uses -- the wiki only
  says "slightly decreased" with no real percentage, so this is a clearly-flagged estimate).
  **Open question, deliberately not resolved yet**: the wiki also states normal-sight mobs can't
  aggro through the illusion but true-sight mobs still can. `Recruit` (`true_detection=0` in
  `mob_pools.sql`) is correctly blocked. `Trainer` is ambiguous -- its own file header (written
  2026-08-22, from the mission walkthrough) claims "true sight," which would mean it should NOT
  be blocked, but `mob_pools.sql` also shows `true_detection=0` for it. Asked the user which
  source to trust; they asked to hold off rather than guess. Trainer's `onMobEngaged` currently
  still has the ILLUSION check applied (blocked) pending that answer -- may need to be reverted.
  **Follow-up same day, user flagged a scoping issue**: ILLUSION/costume is reused outside this
  mission for plain cosmetic "playful costume" changes -- the DoT was already correctly isolated
  to `Viscous_Liquid.lua`, but the speed reduction had been added to the *shared*
  `globals/effects/illusion.lua` instead, which would have wrongly slowed down any other, harmless
  use of the same effect id. Moved into `Viscous_Liquid.lua` alongside the DoT (removed via the
  same "effect gone" check `dotTick` already polls, so it clears correctly on both natural expiry
  and an early strip). `illusion.lua` itself now only ever touches the visual costume change --
  genuinely shared, genuinely harmless.
  **Trainer sight-type question resolved same day**: user provided the mission-specific wiki page
  (Viscous Liquid barrels / Mamool Ja costume, not the generic Costume-effect page used earlier).
  Confirms all Mamool Ja are true sight, but the costume specifically counteracts that ("no
  monsters will aggro you" while worn) -- Trainer's `ILLUSION` block in `Mamool_Ja_Trainer.lua`
  was correct as originally implemented, no revert needed. Same page also gives 30 dmg/tick for
  the DoT, not 22 -- reverted `DOT_DAMAGE` back to 30 (the mission-specific page is treated as
  more authoritative than the generic one for this exact mechanic).
  **Follow-up same day, user provided more mission-walkthrough wiki text**: (1) "if killed in one
  shot, you will not be sent to the prison" -- `Mamool_Ja_Trainer.lua`'s teleport sequence used to
  fire instantly and unconditionally on engage, before the player's own opening hit could ever
  land, making a one-shot escape impossible. Fixed by delaying the sequence behind a short window
  (`TELEPORT_DELAY_MS`, 1500ms estimate) and checking `mob:isAlive()` first. (2) "Trainers respawn
  in about ~5 minutes" -- `onMobDeath` had no respawn wired at all; added via
  `mob:spawn(nil, 300)`, same pattern as Siegemaster Assassination's `Old_Troll.lua` repop.
  **Known gap, deliberately not implemented**: "if you were carrying any supplies, they will be
  removed and placed back in the coffer(s) they were obtained from" -- the 8 Supplies Crates in
  this codebase aren't modeled as individually stateful/re-poppable objects, just a shared
  infinite roll table (`Supplies_Crate.lua`'s `LOOT_POOL`), so there's no "which crate did this
  come from" to put it back into. Implementing this properly would mean redesigning crates to
  track per-crate consumed state -- a real scope increase, not attempted here.
  Also confirmed, no change needed: crates already correctly auto-remove the disguise on open
  (user re-confirmed this matches the real mechanic after initially asking about a gate-instead-
  of-auto-remove alternative).
  🟡 **Teleport transition, deliberately left as-is**: a real playthrough video shows the
  Trainer's "teleport to prison" sequence as a smooth screen fade-out/fade-in, not the instant,
  abrupt reposition currently implemented (`Mamool_Ja_Trainer.lua`'s `setPos()` call). This is
  very likely a genuine CS (cutscene) event on the real client -- retail CS events carry their own
  scripted camera fade as standard behavior -- but no real CSID or event structure for this
  specific sequence has been located in any capture data available for this mission (same class of
  gap already flagged for Viscous Liquid's own "Take a sip?" menu). Checked this engine's two
  teleport primitives directly: `warp()` triggers a full zone-reload (wrong tool -- the prison is
  same-zone/same-instance, not a real zone change) and `teleport()`/`setPos()` is a bare position
  packet with no transition at all. Decided to keep the current instant-reposition implementation
  as-is rather than fabricate an unconfirmed CS event -- functionally correct (same destination,
  same item-strip behavior), just visually abrupt compared to retail. Revisit only if a real
  capture surfaces showing the actual CS event.
  Also fixed this pass: Quhaaja's captured look had race byte 5 (`TARU_M`) -- user reported this
  rendered as an unexpected appearance and asked for Hume Female instead; changed to race byte 2
  (`HUME_F`, per `tpz.race` in `globals/status.lua`), equipment slots left exactly as captured.
  A deliberate user-directed visual choice, not a real-capture-confirmed correction.
  **Follow-up same day, user reported 4 more issues after a DB reimport + script reload**:
  1. **Quhaaja's race change didn't visually apply.** Root cause found: `LoadNPCList()`
     (`src/map/utils/zoneutils.cpp:665`) only runs once at map-server boot, not per zone/instance
     load -- `npc_list` changes need a genuine process restart, not just `dbtool.py` (which only
     updates the database) or a script reload (Lua-only, separate mechanism). Confirmed the actual
     look-byte edit is structurally correct -- `entity_update.cpp`'s `MODEL_EQUIPED` case does a
     raw 20-byte `memcpy` of the SQL blob straight to the client, no reinterpretation -- the data
     just hasn't reached the live process yet. User re-testing after a genuine restart.
  2. **Recruit/Trainer still attack/teleport while ILLUSION is active, despite a script reload.**
     Effect id confirmed matching exactly between C++ (`status_effect.h:328`) and Lua
     (`status.lua:427`, both 258) -- not an id mismatch. Root cause not yet found; could be the
     same instance-must-be-freshly-entered-after-reload class of issue, or a genuine logic bug --
     awaiting a restart + fresh-instance retest before digging further, and whether it's
     Recruit-only, Trainer-only, or both.
  3. **Quhaaja's give-up ended the mission instantly, with no real confirmation.** Confirmed real
     bug, independent of the above: `onTrigger`'s give-up branch displayed "Do you want to give
     up?" text and then called `instance:complete()` unconditionally right after -- never actually
     waited for a player choice. Fixed with a genuine two-trigger confirm (`quhaajaGiveUpArmed`
     localvar, 30s window) instead of guessing at an unconfirmed CS-event menu structure -- first
     trigger arms it, a second deliberate trigger within the window actually completes, any other
     action (turning in another item, letting the window lapse) cancels it.
  4. **Viscous Liquid looked misaligned, prompting a fear of a zone-wide coordinate shift
     affecting the doors too.** Checked directly: its current SQL position (52, 0, -298) is an
     *exact* match to its own real capture -- no data bug found. Very likely the same boot-time
     `LoadNPCList()` caching issue as (1), not a new position bug -- would explain seeing stale
     pre-fix positions (including this morning's door-prop corrections) without any of that data
     actually being wrong. Awaiting confirmation after a genuine restart before treating this as
     a real position problem needing a second independent capture.
  **Follow-up same day, several more user-reported issues after a genuine restart**:
  - **Illusion visual costume REVERTED, real engine restriction found.** Costume id 1600 rendered
    correctly visually, but `setCostume()`/`m_Costume` isn't purely cosmetic --
    `src/map/packet_system.cpp:665` (`SmallPacket0x01A`, trigger action) silently refuses to
    process ANY NPC trigger while `m_Costume != 0`. Since opening a Supplies Crate (an NPC) is the
    *only* sanctioned way to remove Illusion, and Illusion is separately non-cancelable by design
    (`status_effects.sql` row 258, flags 8388640, no `EFFECTFLAG_ERASABLE`), this created an
    unbreakable soft-lock -- no way to ever remove the disguise once granted. Reverted
    `globals/effects/illusion.lua` back to fully inert. A real fix would need real per-slot
    `setModelId()` equipment-look ids (doesn't touch `m_Costume`) instead of `setCostume()` -- not
    attempted, no real ids confirmed for a Mamool Ja "outfit."
  - **Mob still attacking despite Illusion, fixed**: `resetEnmity()` alone wasn't reliably
    stopping an already-engaged mob's current combat tick. Added `disengage()` alongside it in
    both `Mamool_Ja_Recruit.lua` and `Mamool_Ja_Trainer.lua` (both check sites), matching the
    pattern already proven for `Black_Baron.lua`/`Sagelord_Molaal_Ja.lua`.
  - **Ancient Lockbox directly on top of Rune of Release**: confirmed correct, not a bug -- the
    real capture shows both at the exact same position (18, 2, -136) too.
  - **"Cannot activate lockbox with 1 item turned in"**: very likely just the two-trigger give-up
    confirm added last pass -- completing now requires speaking to Quhaaja twice within the 30s
    window, not once. Not yet independently confirmed as a real bug beyond that.
  **Follow-up same day, user-directed rework -- mechanic switched from ILLUSION to COSTUME**:
  since ILLUSION is confirmed unused anywhere else in this codebase or documented elsewhere, and
  real Costume items carry the same restrictions regardless (user-confirmed, not specific to this
  build), reworked the whole mechanic onto the real `tpz.effect.COSTUME` directly instead of
  fighting `m_Costume`'s side effects:
  - `Viscous_Liquid.lua` now grants `COSTUME` (power=1600, "Mamool Ja 1") instead of `ILLUSION` --
    reuses the already-correct `globals/effects/costume.lua` (`setCostume(power)`/`setCostume(0)`,
    both fixed from a dead-call bug earlier this session), no duplicate logic needed. DoT (30/tick)
    and speed reduction (-10 HASTE_MAGIC) both confirmed still fully wired, just repointed to
    check `COSTUME` instead of `ILLUSION`.
  - `Mamool_Ja_Recruit.lua`/`Mamool_Ja_Trainer.lua`'s aggro-suppression checks updated to match.
  - `Supplies_Crate.lua`'s costume-strip reworked from trigger-based to PROXIMITY-based (4-yalm
    tick check, same pattern as Periqia's `Lamia_Guard_Common.lua`) -- this is the actual fix for
    the soft-lock: a costumed player can never click-trigger a crate NPC at all (the same
    `m_Costume` block), so the old trigger-based removal could never fire in the first place. A
    server-initiated `delStatusEffect()` isn't gated by that check, only a player-initiated
    trigger packet is -- walking within range now auto-strips the costume, after which the crate
    can be triggered normally on a follow-up approach.
  - `!costume 0` confirmed as the manual test/removal tool -- routes through chat-command parsing,
    not the `0x01A` trigger packet, so it's unaffected by the block regardless of state.
  - `globals/effects/illusion.lua` is now fully unused by this mission (left inert).
  Still 🟡 pending: live confirmation everything above actually works end to end.
- 🟢 **Root cause of the door-prop bug finally found and fixed 2026-08-24**: the entire
  `_1u*`/`_ju*` door-prop family had a systematic one-letter identifier drift against the real
  client -- topaz's `_juh` was actually the real client's `_jug`, `_jug` was really `_juf`, etc.,
  same pattern across all 62 props in the zone (both letter and number ranges). Root-caused using
  a new tool find, `Xenonsmurf/FFXI-DATS`'s `Info/Door or Objects.json` (real, ground-truth client
  prop positions per zone, see `D:\Claude\FFXI-Tools\FFXI-DATS`) -- nearest-neighbor XZ matching
  against topaz's existing (pre-fix) coordinates showed the drift unambiguously (correct matches
  ~1-2 units, wrong ones 80+). Also confirmed the coordinate transform between this JSON and
  `npc_list.sql` is pure identity for X, Y, and Z -- no rotation/scale/flip; topaz's old crude
  whole-number positions were simply truncated-toward-zero copies of the real precise values.
  Fixed 48 of 53 active `_1u*`/`_ju*` rows (renamed to the correct real identifier + full-precision
  real X/Y/Z) via a one-to-one nearest-neighbor assignment script (backup saved at
  `D:\Claude\FFXI-Tools\ffxi\reference\npc_list.sql.bak-before-mamool-fix`). **5 rows intentionally
  left untouched** (`17047863` `_1u4`, `17047879` `_1uk`, `17047881` `_1um`, `17047891` `_1uw`,
  `17047917` `_jum`) -- their nearest real-prop match was already claimed by another row, meaning
  these are likely genuine leftover duplicate rows from an earlier fix pass rather than simple
  shifts; need manual review, not a forced guess. **Not yet SQL-reimported or live-tested** -- run
  `py -3 dbtool.py` from `C:\topaz\tools` and restart the map-server (name changes are affected by
  `LoadNPCList()`'s boot-time caching, same as the Quhaaja model fix earlier this session) before
  testing. See `ffxi_client_to_topaz_coord_transform` memory for the reusable methodology.
- ✅ **User confirmed live 2026-08-24: all doors in this mission now working.** Root cause and fix
  above validated in production.
- 🟢 **Follow-up collision cleanup, same day**: the original one-off fix script (above) didn't
  check for post-fix name collisions between a confidently-renamed row and one of the 5
  intentionally-untouched rows. A general-purpose successor script,
  `D:\Claude\FFXI-Tools\fix_zone_door_props.py`, built while extending this fix to Leujaoam
  Sanctum, added that check and caught **5 real collisions** in this zone's own already-applied
  fix: `17047863`/`17047864` (both `_1u4`), `17047881`/`17047882` (both `_1um`),
  `17047891`/`17047892` (both `_1uw`), and a `_jun`/`_juo` chain across `17047918`/`17047919`/
  `17047920` (`17047918` needed to keep its true original name `_jun` since a real name-dispatched
  trigger script, `_jun.lua`, depends on it -- confirmed by checking `IDs.lua` and the zone's
  `npcs/` folder before touching it). Fixed all 5 by renaming the row with no confident real-match
  (never a trustworthy identity to begin with) to a `_dup<npcid>` placeholder rather than letting
  it silently collide. Zone re-verified fully collision-free afterward. **Also not yet
  SQL-reimported or live-tested** -- same reimport/restart caveat as above applies to these 5
  additional rows.
- ✅ **2026-08-30, real csids found for both 2-option menus, replacing text-only workarounds.**
  Decoded directly from this mission's own real capture logs (raw `0x032`/`0x05B` packets +
  the capture tools' own `[ID View]` decode, cross-verified across 2 independent captures) --
  Viscous Liquid's "Take a sip?" prompt is real csid **103** (`option 1` = drink, directly
  observed), Quhaaja's "Do you want to give up?" is real csid **106** (`option 1` = confirm,
  inferred by elimination -- the capture never completed that path, only showed the decline
  side). Both now use a real `player:startEvent()` / `onEventFinish()` client-rendered menu
  instead of the earlier always-succeeds/two-trigger-confirm text workarounds. **User-confirmed
  live 2026-08-30: both popups work as intended.**
- ✅ **2026-08-30, Assault points fixed** -- `npcs/Rune_of_Release.lua`'s `BASE_ASSAULT_POINTS`
  table was simply missing an entry for id 14, so every real completion silently awarded 0
  points (user-reported live, screenshot showing "You gain 0 Assault points!" after a real
  2-lockbox completion). Replaced with the user's own compiled Assault Rewards reference
  worksheet, including its real per-mission modifier: base 1333, minus a `floor(66.6 × (8 -
  chests collected))` deduction, using the same `instance:getProgress()` counter Quhaaja's
  turn-in logic already increments. See the System-wide section for the same worksheet's
  cross-reference against all other zones.

### Evade and Escape (Lebros Cavern, mission 24)
**Overall status: ✅** -- Live-tested and confirmed passed by the user 2026-09-02.
- ✅ Entrance position fixed 2026-08-18.
- ✅ Kill-all-3-Dahak mechanic validated correct by real capture.
- ✅ **2026-08-19**: found and fixed the same `onMobDespawn`-instead-of-`onMobDeath` latent miscount
  bug as Coney/Black Baron -- `mobs/Dahak.lua` now counts progress on a real death, gated + hardened
  with `MOBMOD_NO_DESPAWN`.
- ✅ **2026-08-22, wiki rebuild**: the 3 "Switch" NPCs (previously left unwired, see original note
  below) are now live. FFXIclopedia describes a real switch-hunting/avoidance mechanic (3 switches
  among 7 possible rooms, each active 5 min once hit, all 3 active spawns Rune of Release; Dahaks
  are explicitly meant to be evaded, not farmed). User confirmed both mechanics are real and
  independently valid ("kill or hit all switches") -- not mutually exclusive, so `npcs/Switch.lua`
  (new) increments the same shared `instance:getProgress()` counter `Dahak.lua`'s kill path already
  uses; `onInstanceProgressUpdate`'s existing `progress >= 3` check needed no changes. Simplified
  from the wiki's exact 5-minute-expiry/simultaneity state machine to a flat cumulative counter
  (documented as a deliberate simplification in `Switch.lua`'s header, not a blind guess).
- 🔴 **2026-08-23, user-reported: instance completely unpopulated live** -- no mobs, no switches, no
  helper props. Found a real capture that was already sitting on disk (`Lebros Cavern LC - Evade
  and Escape`, Thris) with full `PathLog` data for every entity registered to this instance --
  used it to find and fix 3 distinct real bugs:
  1. All 3 Dahak `mob_spawn_points` rows were still `(0,0,0,0)` placeholders -- same "spawns at
     world origin" bug class as Shanarha's Coney. This alone explains the missing mobs.
  2. The 3 Switch positions (previous entry above, `222/470/350`-family) were hand-placed from a
     user-provided position-map image, not real capture data -- turned out to be off by 100+
     yalms in places. Replaced with real capture-confirmed positions.
  3. `17035561` (a helper prop, real name `_irk`) was registered to `instance_entities` since
     2026-08-21 with **no matching `npc_list` row at all** -- still a `NOT_CAPTURED` stub.
     `instance_entities`' load query is an `INNER JOIN` against `npc_list`
     (`instance_loader.cpp`), so this one entity was silently dropped, not fatal to the rest of
     the instance -- but still a real missing prop, now filled in from the same capture.
  Also found and fixed (lower-severity, cosmetic-only, didn't block spawning): a systematic
  off-by-one-too-low id bug in `IDs.lua`'s `_1r`/`_ir` helper-prop family, from the 2026-08-21
  cross-reference pass -- every entry this capture covers had its id set 1 lower than the real
  `PathLog` folder's id (e.g. `_irk` pointed at `17035560`, which is really `_irj` -- the real
  `_irk` is `17035561`, the missing row above). Corrected only the entries this capture actually
  confirms; entries outside this capture's coverage (`_1r5`/`_1ra`/`_1rf`/`_1rt`/`_1rv`/`_ir4`)
  left unverified rather than blindly extrapolated. Full audit confirms all 24 entities registered
  to `instance_entities` for this instance now have real, matching `npc_list`/`mob_spawn_points`
  rows -- nothing else missing.
- 🔴 **2026-08-25, user-reported (round 1): rock wall impassable** at
  `LOGPOS,,63,298.4463,-30.0392,181.9479`, user's own hypothesis "2 objects registered near this
  location and possibly overlapping." Initial fix (nearest-neighbor based, see history) removed
  `17035553`'s instance-24 registration -- **later found to be wrong, see round 2 below.**
- 🔴 **2026-08-25, user-reported (round 2): a different LOGPOS now missing a prop**, at
  `LOGPOS,,63,261.8069,-30.1285,101.5942` -- user correctly guessed "perhaps the one registered at
  the prior location was this missing item" and asked for a full pipeline rebuild of this mission.
  Found the real Evade and Escape PathLog capture (Thris) already sitting on disk and used it as
  ground truth for the whole `_1r*`/`_ir*` id range this instance uses (ids `17035518-17035561`),
  superseding the earlier FFXI-DATS-nearest-neighbor-based renames for this range. Real findings:
  - `17035552` (nearest-neighbor-renamed to `_jrc` earlier this session) is actually `_irb`, whose
    real position (260,-33.004,101) is exactly the round-2 reported LOGPOS -- it had been
    mis-positioned to sit duplicated on top of `17035553`, which is what caused round 1's "2
    overlapping objects" symptom in the first place. Restored to its real position/name.
  - `17035553` (`_ird`, removed from instance 24 in round 1) is actually `_irc`, the real prop at
    round 1's reported LOGPOS -- re-registered to instance 24.
  - `17035518`/`17035521`/`17035529`/`17035554` were all sitting at completely unrelated real
    positions (belonging to other missions or plain wrong) -- corrected to this capture's real
    `_1rd`/`_1rg`/`_1ro`/`_ird` positions.
  - `17035529` (`_1ro`) was *also* wrongly registered to instance 22 (Lebros Supplies) via a
    2026-08-25 nearest-neighbor guess for that mission's own unrelated rock-wall report -- that
    guess borrowed this id's position without knowing its real (440,-53.171,60) location was needed
    elsewhere. Removed from instance 22; Lebros Supplies' real door prop is still unidentified, see
    TODO.md. (Instance 27's registration of the same id was independently capture-confirmed on
    2026-08-21 and is unaffected/correct.)
  - `17035556`-`17035561` already had correct positions from the earlier drift fix; only their
    `_jr*` names were cosmetically wrong per this capture (`_ir*` is real) -- renamed for
    consistency, no functional change.
  All 8 real name+position corrections applied in `npc_list.sql`; `instance_entities.sql` updated
  to match (17035553 restored to instance 24, 17035529 removed from instance 22). Not yet
  SQL-reimported or live-tested.
- ✅ **2026-08-25 cleanup: phantom duplicate-object rows removed.** User theorized live-tonight
  that persistent blockers were more likely bad positioning/wrong objects than baked geometry, and
  noted the corollary -- a genuinely shared real object (same orientation/size/type) can validly be
  reused by id across multiple instances. Checked the theory directly against FFXI-DATS's real
  rotation/scale data (not just XZ position) and found a real instance of it: `17035517`/`17035518`
  (`_1rd`), `17035520`/`17035521` (`_1rg`), and `17035527`/`17035528` (`_1rn`) were each **2 different
  npcids mapped to the exact same single real client object** (FFXI-DATS confirms only 1 real
  object exists at each coordinate) -- artifacts of the earlier zone-wide drift fix minting "new"
  ids for props that already existed under an older id. Neither id in each pair was ever loaded by
  the same instance at once (517/520/527 -> instances 21+26, 518/521/528 -> instance 24 only), so
  this wasn't causing a live double-collision anywhere, just duplicate dead-weight data. Also found
  2 fully unregistered phantom rows from the same root cause, `17035565`/`17035566` (`_jrb`/`_jrd`,
  exact duplicates of `_irb`/`_ird`'s real position), registered nowhere at all.
  **Fix**: removed all 5 duplicate rows from `npc_list.sql`; consolidated onto the surviving ids
  (`17035517`/`17035520`/`17035527`), now registered to instance 24 as well as 21/26 in
  `instance_entities.sql`. No `IDs.lua` changes needed -- none of the removed ids were referenced by
  name in any Lua script. Confirmed `_1rp`/`17035530` (the still-open Lebros Supplies wall, see
  below) is NOT part of this pattern -- FFXI-DATS confirms it's a genuine lone object, no duplicate.
- Original note (superseded by the above, kept for context): the capture data found 2026-08-19 did
  have Switch text (MesNum 7451/7452/7454) but the timestamps didn't cleanly map 1-kill-to-1-switch,
  so it was left unwired at the time rather than guess a wrong mapping. The wiki's independent
  kill-or-switch mechanic resolves that ambiguity without needing that mapping.
- 🟢 **2026-09-02: real Dahak patrol/roam built**, backported from a user-supplied real
  LandSandBoat-format reference script -- 6 real endpoint positions (2 groups of 3), bitwise-gated
  per Dahak by numeric offset from 17035324 (17035325=top group only, 26=bottom group only,
  27=both). Resolves the earlier "Dahak roam is non-functional, no ROAM_DISTANCE row" concern --
  confirmed via `mob_controller.cpp` that `onMobRoam()` fires on its own tick independent of the
  native roam-distance-gated path, so this doesn't need that row at all. Also added Dahak's real
  sleep/gravity/bind immunity (`mob_pools` poolid 894's `immunity` column, 0 -> 7) -- Topaz has no
  Lua-side immunity setter, DB-only. Terror immunity was also requested by the source script but
  has no engine equivalent in this Topaz build (no `IMMUNITY_TERROR` bit exists at all) -- real gap,
  not portable. Lua-only for the roam logic; the immunity value needs `py -3 dbtool.py update full`.
  Not yet live-tested.
- 🟢 **2026-09-02 (later): 2 real switch bugs fixed + the real 7-room mechanic built,
  user-reported live "no switches."** (1) All 3 `SWITCH1-3` `npc_list` rows were still `(0,0,0)`.
  (2) `status=6` (CUTSCENE_ONLY) -- same never-renders-client-side bug already found and fixed for
  Periqia's Bridge Switch this session -- fixed to `0`. User then supplied real `!logpos`
  coordinates for all 7 real candidate rooms (a single capture can only ever show whichever 3 the
  game picked that run, which is why only 3 were ever found before). Real "3 randomly chosen of 7"
  mechanic now built in `instances/evade_and_escape.lua` (`CANDIDATE_ROOMS` + `placeSwitches()`,
  repositions the 3 real Switch NPCs onto a random non-repeating subset of 3 every instance) --
  same real-position-reuse pattern already proven for Saving Private Ryaaf's 5-pattern room
  selection. `npc_list.sql`'s 3 switch positions are now just a fallback default, always
  overridden at instance creation. Needs `py -3 dbtool.py update full` + restart.
- ✅ **2026-09-02 (later): Dahak HP corrected** -- `mob_groups` row for groupid 10 (zoneid 63) had
  `HP=0` (falls back to level-based scaling), user-directed real HP is 16500. Fixed in
  `mob_groups.sql`. Needs `py -3 dbtool.py update full` + restart.
- ✅ **2026-09-02 (later): Draw-In added** -- `mobs/Dahak.lua`'s header already claimed
  `MOBMOD_DRAW_IN` was "kept as-is" from the LSB backport, but the actual `setMobMod()` call was
  never written. Real, standard pattern for this dragon family (Wyrm/Black_Dragon/Dark_Dragon all
  set this on spawn) -- added to `onMobSpawn`. Lua-only.
- ✅ **2026-09-02 (later): switch messages moved off chat-print onto the real dialog engine**,
  user-reported live. `SWITCH_ACTIVATED`/`SWITCH_REFRESHED` (7436/7439) confirmed real via this
  mission's own CapLog (raw MesNum labels there are drifted +15 vs the real client text table --
  verified by exact text match against dat-extractor). `Switch.lua` now uses
  `player:messageText()`. `SWITCH_EXPIRING` (7437) also wired in at 60s-remaining from
  `evade_and_escape.lua`'s per-second tick (estimate, not a confirmed retail threshold -- the real
  text exists but no capture pins the exact trigger point). A 4th real string at text id 7438
  ("Nothing happens... The other switches appear to have shut down as well...") was confirmed
  real via dat-extractor but never observed firing in any capture -- user reviewed and found no
  evidence of a decoy-switch/sequence mechanic, left unbuilt/unused rather than guessed.
- ✅ **2026-09-02 (later): Rune of Release position and grid-ref dialog fixed**, both user-reported
  live. Position was falling back to the shared `npc_list` default ("I-8") instead of this
  mission's own room -- real coordinates (301,-29.978,-62 / 299,-30.01,-62, dir 192) confirmed via
  this mission's own PathLog capture, now set explicitly in `onInstanceCreated` (same pattern as
  Supplies Recovery). Grid-ref text was also wrong -- `RUNE_UNLOCKED_POS`'s letter param is
  0-indexed (H = 7th letter, not 8); real value per this mission's own CapLog line is H-8, now
  sent as `(7, 8)`. See `topaz_rune_unlocked_pos_letter_indexing` memory -- this exact mistake has
  now recurred across most missions in this project on first wiring.
- ✅ **2026-09-02, user-confirmed live: PASSED.** All of the above (Dahak HP/Draw-In/roam, switch
  dialog + 5-min timer + 60s warning, 3-of-7 room randomization, Rune of Release position + grid
  text) verified working in a real playthrough.
- ✅ **2026-09-12, user-reported live: switches rotating to face the player + despawning/blinking
  on activation, real lamp glow never appearing.** Three real bugs found and fixed in
  `npcs/Switch.lua`:
  1. A stray `npc:lookAt(player:getPos())` was rotating this static wall-mounted prop -- removed
     (Nyzul Isle's `Rune_of_Transfer.lua`, the real precedent for this model, has no such call).
  2. `forceRespawn()` (added 2026-09-02 as a workaround for "no visible change") does a literal
     hard despawn + a real respawn packet 1s later -- that IS the despawn/blink symptom, not a fix.
     Removed; replaced with the already-proven `Supplies_Crate.lua`/`caskets.lua` toggle pattern
     (set through the unlit value first) so a re-trigger still forces a real broadcast even when
     the stored value already matches (`setAnimationSub()` only sends a packet when the value
     changes -- `lua_baseentity.cpp:4381`).
  3. **Root cause of "never glows" even with a correct broadcast**: `animationsub` values were
     guessed as `0`(unlit)/`1`(lit), matching LSB's *source code* convention but never actually
     confirmed against a real client. Decoded the user's own retail packet captures
     (`mission_toolkit/ffxi_zone_database.db`, capture_id 90 "Lebros Cavern LC - Evade and
     Escape") byte-for-byte: every real `CEntityUpdatePacket` for these 3 npcs with the
     `UPDATE_HP` bit set shows `animationsub = 4` (unlit) / `5` (activated), and `namevis = 36`,
     never `0`/`1`/`32`. Independently cross-confirmed against a second, unrelated real capture
     for the identical model (1509) in a third zone (Nyzul Isle's `Rune_of_Transfer`/`Runic_Lamp`,
     capture_id 177) -- same exact values. `Switch.lua` and `npc_list.sql` (`17035481-3`) both
     corrected to the real values. User-confirmed fixed live.

### Shooting Down the Baron (Periqia, mission 34)
**Overall status: ✅** -- Live-tested and confirmed working, warp mechanic included.
- ✅ **2026-08-30, real Wide Scan gap fixed**: user-reported live -- Black Baron was always visible
  on widescan, and `mob_pools`' own `namevis=2` never actually addressed this despite an earlier
  tracker note claiming it was "already correct" (that note was wrong -- bit `0x002` isn't
  `FLAG_HIDE_NAME`/`FLAG_UNTARGETABLE`, so it never blocked `isWideScannable()`). Fixed with the
  same new `wideScanHidden` localVar mechanism built for Shanarha Grass Conservation's Coney
  (real, scoped C++ addition, `src/map/entities/baseentity.cpp`) -- name/target/attack all stay
  normal, only the widescan blip is hidden.
- ✅ Entrance position fixed 2026-08-18 (was noticeably off, ~90 units).
- ✅ Kill-1 mechanic (Black Baron) already correct. Lockbox rewards (LSB-ported, validated) and
  Assault points (1210, real) now both confirmed/fixed.
- ✅ **2026-08-19**: found and fixed the same `onMobDespawn`-instead-of-`onMobDeath` latent miscount
  bug as Coney/Dahak -- `mobs/Black_Baron.lua` now counts progress on a real death, gated + hardened
  with `MOBMOD_NO_DESPAWN` (this file's own header comment used to cite "progress-on-despawn" as
  the pattern to follow -- it was actually the bug).
- ✅ **2026-08-22, live-test bug**: Black Baron rendered green and could not be attacked at all.
  Traced to `mob_groups` row 13's malformed columns -- `minLevel=0, maxLevel=75, allegiance=78`
  instead of the clearly-intended `minLevel=75, maxLevel=78, allegiance=0` (trailing `allegiance`
  byte dropped/shifted, pre-existing data, not introduced this session).
  `CBattleEntity::ValidTarget` (battleentity.cpp:1255) requires `allegiance <= PLAYER` (<=1) for
  normal PvE targeting -- `78` failed every branch and fell through to `return false`,
  permanently untargetable regardless of anything else. Fixed the row.
- ✅ **2026-08-22, cross-referenced against FFXIclopedia's Solo Assault Guide by Korvana**: guide
  confirms "He does not show up on Wide Scan" -- not previously built. `CMobEntity` has no
  dedicated wide-scan flag (only NPCs do); `isWideScannable()` falls back to
  `!IsNameHidden() && IsTargetable()`, so `mob_pools` poolid 431's `namevis` FLAG_HIDE_NAME bit is
  the only lever available -- set it. Side effect: also hides his nameplate (not separately
  confirmed, but there's no way to have one without the other in this engine).
- ✅ **2026-08-23, built from user-provided wiki writeup + 3 independent real captures**: the warp
  mechanic ("does not aggro", "warps every ~15% HP, disappears/reappears unclaimed, doesn't regen")
  is now live in `mobs/Black_Baron.lua`'s `onMobFight`. First pass used the Thris Nov2025 capture
  (only 1 real playthrough at the time -- "Periqia LC" turned out to be a duplicate of the same
  session, not a second source) -- directly confirmed 2 real warps: sudden 52-116 yalm position
  jumps with no HP regen across them, timed loosely (not evenly) around the 15% mark, matching the
  wiki's own "or so" hedge -- `WARP_INTERVAL = 15` is a reasonable approximation, not a
  capture-exact value.
  **Cross-confirmed same day** by downloading 2 more genuinely independent captures from the
  Discord archive catalog (`discord_captures/mission_source_catalog.md` + a 2nd link found in the
  raw scraped chunks): **Giichi** -- real spawn position (-207.777,-16.162,-144.718), HP Track:
  "Killed 17006658 (Black Baron): 2180~16215HP, Est.HP: 13618" (single-round BST WS kill, too fast
  to observe a warp -- doesn't contradict the mechanic, just never triggered it); **Siknawz** --
  another real spawn position (-252.279,-5.964,17.985), a much tighter HP Track figure: "Killed
  17006658 (Black Baron): 14206~14341HP" (overlaps Giichi's looser range around ~14000-14300 --
  `mob_groups` now uses 14270, the midpoint of this tighter bound), plus real text confirmation of
  "spams amnesia" ("Black Baron Abrasive Tantara -> Siknawz (amnesia)"). Siknawz's fight ran ~3
  minutes (long enough a warp could plausibly have happened) but that capture format only logs a
  single position snapshot per NPC, not a delta history -- can't confirm or rule out a warp there.
  Warp destinations use a pool of 6 real, independently-observed positions (4 distinct capture
  spawn points + 2 real warp targets from within the Thris fight, plus `mob_spawn_points.sql`'s
  existing default spawn -- itself a separately-recorded real sample, left untouched rather than
  overwritten) rather than fabricated "anywhere on the map" coordinates, which risk landing
  off-navmesh -- 4 independent real samples landing in different parts of the map is itself
  supporting evidence for "spawns anywhere". Also fixed `mob_pools` poolid 431's `aggro` (1 -> 0)
  -- was set to aggro despite the wiki's explicit "does not aggro you" even when spawned at the pop
  point; `namevis` (Wide Scan exclusion) was already correct.
- ✅ **2026-08-24, live-tested and closed out.** `WARP_POINTS` pruned of 6 coordinates that had been
  improvised from Seagull Grounded/Excaliace's route data (different mission's territory, same
  zoneid 56) -- confirmed live as the cause of a real bug: Baron warped to
  (-419.9437,-15.8397,49.3929), right next to one of those borrowed points, landing outside this
  mission's own playable area. Now only the 6 real Baron-specific captured points + 10
  user-walked/`!checknav`-confirmed-in-this-instance points remain.
  Warp animation also improved same day, per user feedback that the original single `kesu` pulse
  into an ~1s instant teleport read as a jarring disappear, not a warp: now pulses `kesu` twice
  (800ms apart) for a real telegraphed buildup, then a 2.2s beat before the actual teleport +
  `deru`. Investigated pairing this with `setStatus(DISAPPEAR)/(NORMAL)` to actually hide the model
  (as `Armoury_Crate.lua`'s NPC door props do) -- root cause of the earlier live regression (Baron
  vanished permanently) now confirmed, not just avoided: `CBattleEntity::isDead()`
  (`battleentity.cpp:94-97`) treats `status==DISAPPEAR` as literally dead for anything with combat
  state (mobs included, unlike NPCs), and flipping status back to `NORMAL` afterward doesn't undo
  whatever the AI controller does in response. Confirmed no other mob script in this codebase pairs
  `kesu`/`deru` with a status toggle -- a real engine constraint, not fixable in Lua. `kesu`/`deru`
  without the status toggle is genuinely the best available option; the model stays visible through
  the actual teleport moment (brief window where he's still targetable/attackable) -- user
  evaluated a proper fix (a mob-self-callable `FLAG_UNTARGETABLE` toggle, would need a small C++
  binding + rebuild) and decided to leave it as a known, accepted minor edge case rather than pursue
  it now. User confirmed the animation now matches retail behavior.

### Demolition Duty (Ilrusi Atoll, mission 44)
**Overall status: ✅** -- 2026-09-01, **first confirmed clean completion**: user passed the
mission live, variable score-based AP payout confirmed correct (score 4 -> 400 AP, exactly
matching `DEMOLITION_AP_PER_SCORE = 100`/score point from `Rune_of_Release.lua`'s single-data-point
wiki fit -- not a coincidence, the formula is working as designed). Full mechanic built and
extensively live-tested 2026-08-30/31 through 09-01, with a long real bug-fix loop (below). Damage
tuning (mob-skill dmgmod) may still want further iteration for feel, but the mission itself is
completable end-to-end. The 🔴 scaffold-era summary this section used to open with is stale and
was replaced.
- 🟡 **Still open, non-blocking**: a real engine-level bug found 2026-09-01 -- the automaton can get
  stuck refusing to move for minutes after being Stunned by an Imp, even though `CInactiveState`
  (the AI state Stun forces entities into) is supposed to self-exit as soon as
  `HasPreventActionEffect()` clears, and that check runs every tick (`ai_container.cpp:351`). Not
  yet root-caused -- two live-diagnosable branches (Stun still actually active vs. a stuck AI
  state-stack) that need an in-game observation (does a status icon still show above the automaton
  when it's stuck?) to tell apart. This is a general engine mechanism, not Demolition-Duty-specific
  -- would affect any mob-type entity that gets crowd-controlled while ally-flagged and
  non-retaliating. Worth its own investigation pass outside this mission.
- ✅ **2026-08-31, real second live-test round -- 2 more real bugs found and fixed.**
  1. **Mob-skill damage far too low** (user-reported: Slapstick/Knockout/Magic Mortar ~10 dmg vs
     ~35 for a plain auto-attack, at high TP). Root cause: the 2026-08-30/31 `TP_NO_EFFECT` fix
     (below) switched to `TP_DMG_VARIES`, but that tpeffect's real damage-scaling branch
     (`monstertpmoves.lua`) multiplies by `MobTPMod(skill:getTP()/10)` -- a SEPARATE curve that only
     exceeds 1x above raw TP 2000/3000 (i.e. `skill:getTP()` >= 20000/30000, impossible, real max TP
     is 3000) -- so it was silently a flat 1x regardless of TP. The `1.5, 2.5, 3.5` args the scripts
     already passed were never even read in that branch -- they're consumed only by
     `tpeffect==TP_DMG_BONUS`, via `fTP(tp, mtp1, mtp2, mtp3)`, the real 100/200/300%-TP curve this
     was always meant to use. Fixed `slapstick.lua`/`knockout.lua` by switching to `TP_DMG_BONUS`
     (keeps the same 1.5/2.5/3.5 args, now actually applied). `magic_mortar.lua` had a related but
     distinct bug -- `TP_MAB_BONUS` boosts magic accuracy, not damage, so it never scaled with TP at
     all; switched to `TP_DMG_BONUS` with a new `tpvalue=15` (that formula is a different, linear-
     from-origin curve, not `fTP`'s 3-point table, so it can't hit the same exact endpoints -- 1.5x
     at 1000 TP, 4.5x at 3000 TP, same rough shape, needs live-tuning like the other two). Not yet
     re-tested live.
  2. **Automaton walks through Wreckage and ends up on the far side attacking, stranding the paired
     Carrion Crab out of the player's reach** (user-reported, called out as "becoming a major
     issue"). User asked whether `pathTo`'s wallhack flag was the cause -- checked against real
     source (`src/map/ai/helpers/pathfind.cpp:95`, header comment "run through walls if path is too
     long"): `PATHFLAG_WALLHACK` only changes which navmesh/static-terrain pathfinding function is
     used, nothing to do with entity-vs-entity blocking -- **confirmed this engine has no mob-vs-mob
     collision at all** (true to real FFXI too), so wallhack was never the cause and turning it off
     would not have fixed this. Real cause: `pathTo()` targeted Wreckage's exact center coordinate,
     not a stopping point short of it -- with a 3-second `AI_TICK_MS`, the automaton's continuous
     walk between script ticks had plenty of time to carry it straight through Wreckage's model
     before the next tick's distance check (`WRECKAGE_ENGAGE_RANGE = 8`) could switch it into
     `mob:engage()`. Fixed in `Demolition_Automaton.lua` with a new `approachPoint()` helper: pathTo
     now targets a point `WRECKAGE_APPROACH_STANDOFF` (4 yalms) short of Wreckage's center, back
     along the automaton-to-Wreckage line, so the destination itself never lands inside/through the
     model. Not yet re-tested live.
- 🟡 **2026-08-31, THIRD live-test round -- one more real bug found in the fix above, plus a known
  tuning gap.** User re-tested: Slapstick/Knockout now doing only ~30 dmg (fTP curve correctly
  wired but still weak), Magic Mortar doing ~4000 dmg (way overscaled).
  - **Magic Mortar was a real bug, not a tuning question**: `tpvalue=15` in the previous fix was a
    10x arithmetic error -- `MobMagicalMove`'s `TP_DMG_BONUS` formula is
    `damage * (TP/10 * tpvalue) / 100 = damage * TP * tpvalue / 1000`, so `tpvalue=15` gives a
    **15x-45x** multiplier (1000-3000 TP), not the intended 1.5x-4.5x. Corrected to `tpvalue=1.5`.
  - **Slapstick/Knockout's ~30 dmg is a genuine tuning gap, not a bug** -- the `fTP` curve is
    correctly wired now (see the entry above), but `mob:getWeaponDmg() + dstr` (the formula's base,
    `dstr` capped +-10) is inherently small for this automaton's stats, so even a maxed 3.5x stays
    low. Bumped `dmgmod` 1->2 in both scripts (the formula's own exposed tuning knob) as a starting
    adjustment. Not yet re-tested live -- expect further iteration.
- 🟢 **2026-08-31, same live-test round -- confirmed working, no action needed:** Wreckage
  targeting now works (the C++ `ValidTarget()` rebuild from the previous round is confirmed live);
  automaton fires a mob skill roughly every 10-15 hits (deemed acceptable by the user); all 5 Imps
  and their paired Carrion Crabs are spawning and associating correctly. **Still open:** AP-per-run
  when an automaton is lost to the leash mechanic has not been validated across a completed run.
- ✅ **2026-08-30/31, full real mechanic built** from the user-provided wiki walkthrough: Uzhahn
  issues one controllable "Demolition Automaton" per instance (`npcs/Uzhahn.lua`/
  `demolition_duty_common.lua`), which the player leads to 5 real Wreckage obstacles
  (`mobs/Demolition_Automaton.lua`/`mobs/Wreckage.lua`) and destroys via real native combat; a
  leash/countdown/replacement loop, a repair mechanic, and a real score-based completion
  (`UZHAHN_DEMOLITION_COMPLETE`/`UZHAHN_COMPLETE_OTHER`, real dat-extractor-confirmed dialogue,
  correcting an earlier wrong MesNum guess) are all real per the wiki and wired in.
- ✅ **Wreckage converted from an untargetable `npc_list` prop to a real `CMobEntity`** -- the
  original NPC-prop approach couldn't receive real native combat/mob-skill interaction at all
  (`useMobAbility()`/`mob:engage()` both require a real `CBattleEntity` target); this was the root
  cause the whole scripted-HP/scripted-Slapstick-chance workaround era was papering over. Real
  `mob_pools`/`mob_groups`/`mob_spawn_points` rows added, same ids reused.
- ✅ **Real "Slapstick" mob-skill system wired in** -- automaton's `skill_list_id` pointed at a real
  list (363, `Automaton_Harlequin`) containing its 3 real skills (1943 slapstick, 2067 knockout,
  2301 magic_mortar). **Real bug found and fixed**: none of the 3 had a
  `scripts/globals/mobskills/*.lua` file -- `luautils::OnMobSkillCheck` returns 1 (blocked) by
  default with no script registered, so all 3 were unconditionally blocked regardless of TP
  (confirmed live: automaton given 3000 TP via GM command still never fired). Created
  `slapstick.lua`/`knockout.lua`/`magic_mortar.lua` (plain `MobPhysicalMove`/`MobMagicalMove` hits --
  see `slapstick.lua`'s own header for why the real player/pet-automaton WSC/ftp weaponskill formula
  doesn't apply to a plain `CMobEntity`). A follow-up bug (`TP_NO_EFFECT` making a "weaponskill" hit
  weaker than a plain auto-attack) was also found and fixed (`TP_DMG_VARIES`).
- ✅ **Carrion Crab spawn-on-mob-skill mechanic implemented** -- documented in comments since
  2026-08-30 but never actually wired up. `entity.onMobWeaponSkill` in
  `mobs/Demolition_Automaton.lua` now spawns the real, distance-confirmed 1:1-paired
  `CRAB_FOR_WRECKAGE1-5` crab (fixed to fire on all 3 real skills, not just Slapstick, after an
  initial narrower pass). **Real bug found**: `CRAB_FOR_WRECKAGE1` (17002551) sat at `(0,0,0)` --
  `src/map/instance_loader.cpp:150`'s own population query unconditionally excludes any
  `mob_spawn_points` row at exactly `(0,0,0)`, so it could never be loaded into any instance at all
  ("SpawnMob: mob <17002551> not found" in the log) -- not a pairing/collision bug (targid
  collision was checked and ruled out). Fixed with a real non-zero placeholder (Wreckage1's own
  position).
- ✅ **Passive aggro is player-only in this engine -- fixed for both Imps and the crab.**
  `src/map/zone_entities.cpp`'s `CZoneEntities::SpawnMOBs` (the only passive aggro-scan in the
  codebase) is hard-typed to a real player, so hostile mobs never autonomously notice or hold hate
  on a `CMobEntity` ally like the automaton, regardless of allegiance -- same real root cause
  independently found for Chanoix (Leujaoam Sanctum SP, see that mission's own entry). Fixed with a
  real, amount-controlled `mob:addEnmity(target, CE, VE)` pulse (`pulseThreatHateLoop`, its own
  1.5s timer decoupled from the AI's 3s movement tick) covering both Imps and any spawned crab --
  tuned up twice after live-testing showed a player could pull a crab off with only a few hits.
- ✅ **Real, scoped C++ fix: players must not be able to attack Wreckage, only the automaton
  should.** The automaton's own `ALLEGIANCE_TYPE::PLAYER` (needed so it reads as a real ally) put it
  in the *exact same* allegiance relationship with Wreckage as any real player -- no existing SQL
  flag or allegiance value could separate the two (matching allegiances instead would have broken
  the automaton's own combat via `CMobController::TryDeaggro`'s same-allegiance auto-deaggro rule).
  Added a localVar-gated check to `CBattleEntity::ValidTarget()` (`entity:setLocalVar(
  "playerCannotAttack", 1)`), same low-risk pattern as this session's earlier `isWideScannable()`
  addition. **Needs an engine rebuild, not just a restart -- not yet confirmed built/deployed.**
- 🟡 **Damage/TP tuning still in progress as of this entry** -- Wreckage's DEF/MDEF, the automaton's
  ATTP and `cmbDmgMult`, its level (tried and reverted -- tanked hit rate instead of just damage),
  `MOBMOD_TP_USE_CHANCE`, and a Regain effect have all been adjusted across several live-test
  rounds chasing a ~30-40 dmg/hit target and more frequent mob-skill usage. Last known state: ~40-50
  dmg/hit, user asked for ~30-35, cmbDmgMult dropped 60->42 in response -- not yet re-tested.
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ Lockbox rewards (???_box + remedy) and Assault points (1100) now real.
- 🔴 **Still a scaffold, no objective content.** Real mechanic found via capture: Uzhahn hands the
  player a controllable "Demolition Automaton" pet that attacks "Wreckage" props; the automaton
  has a leash/self-destruct/replacement loop if the player strays too far; completion is a scored
  outcome ("score of 10 points on your work assessment"), not a simple kill-count. Needs a
  controllable-pet-AI mechanic this codebase doesn't have a ready pattern for yet. See
  `instances/demolition_duty.lua`'s header for full detail.
- 🟢 **12 zero-position ambient mobs fixed 2026-08-25** (`Carrion_Crab` ×4, `Imp` ×8, ids
  `17002552`-`17002563`), found via a zone-wide `mob_spawn_points.sql` sweep and fixed with real
  spawn positions from the `Ilrusi Atoll - Demolition Duty (Thris Nov2025)` capture's PathLog.
  Data-completeness fix only -- these aren't the real "Wreckage"/automaton objective content
  above, likely just ambient zone population. Not yet SQL-reimported or live-tested.
- 🟢 **2026-08-29**: the Automaton + 5 Wreckage props were still all at `(0,0,0)` despite the
  2026-08-19 entry below claiming they were staged -- real positions restored (2 independent
  NPCLogger observations each, same capture), Automaton registered to `instance_entities` (was
  missing entirely) and its one missing `SpawnMob()` call added. Entity-presence only -- the real
  controllable-pet-AI mechanic is still unbuilt. Not yet SQL-reimported or live-tested.
- ✅ **Data pass 2026-08-19 (no AI built, groundwork only)**: re-read the capture in full detail.
  Confirmed the automaton engaged exactly 5 distinct targets ("Target acquired." x5, one per real
  Wreckage prop) and has real model_id=40 (100 HP/100 speed/40 base speed at last widescan sample);
  confirmed exactly 2 full destroy-and-replace leash cycles plus 2 more that resolved as a
  near-miss ("Safety program has been shut down" instead of "Delete."); confirmed the completion
  line is spoken by Uzhahn (not the player), real MesNum 7561; confirmed the 30-minute time limit
  (`instance_list.sql` already had this right). The "score 10 for 5 Wreckage" 2-points-per-Wreckage
  read is a clean fit but only one data point -- flagged as a hypothesis, not fact. Staged the 5
  real Wreckage prop positions (PathLog-confirmed, corroborated by NPCLogger widescan) into
  `npc_list.sql`/`instance_entities.sql`/`IDs.lua` as hidden, unspawned groundwork -- **no behavior
  change, `demolition_duty.lua` is untouched** -- so a future pet-AI implementation pass doesn't
  have to re-derive this data. Also registered Uzhahn to instance 44 in `instance_entities.sql`,
  which had never been done despite his `npc_list` row being real and correct.

---

## C (Corporal)

### Counting Sheep (Leujaoam Sanctum, mission 5)
**Overall status: 🟡 -- Corrected 2026-09-02.** The 🔴 status and the 2026-08-24 note below (ice
wall/mine props "not yet wired to any mission logic") are **stale**: the mine-triggered
ice-cage-break mechanic this note called for was actually built on 2026-08-29 (see
`instances/counting_sheep.lua`'s header + `npcs/Qiqirn_Shepherd.lua`/`Karakul.lua` --
hire-a-Shepherd, lead him to a cage, he mines it open over several ticks, touch the freed Karakul
inside) but the tracker's Overall line was never updated to reflect it. Re-verified 2026-09-02:
`Qiqirn_Shepherd.lua`'s `tick()`/`mineStep()` and `Karakul.lua`'s `onTrigger` are both present,
correctly wired to `common.ROOM_PAIRS`/`common.ALL_CAGE_IDS`, and structurally sound. Downgraded to
🟡 (built, real gap remains) rather than ✅ or 🟢 because the mechanic is only genuinely completable
for 2 of the real 5 cage/Karakul rooms -- the other 3 real Karakul ids and 4 real QiqirnMine ids
were never captured by any of the 3 available playthroughs, a real data gap, not a build gap (see
bullets below). (Original 2026-08-24 "entirely empty"/blocker note kept below for history.)
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data, loss run).
- ✅ **Real mechanic + rewards confirmed 2026-08-19** from a second, complete capture: trade
  Imperial gold/silver/bronze pieces to Qiqirn Dealer's dice game to win big karakul sheep. Real
  Assault points (825) and lockbox rewards (??? Dagger + hi-potion_+2/tank) both confirmed and
  wired in.
- ✅ **2026-09-02 content-completeness sweep**: re-confirmed correct, no new fix needed. Rune of
  Release/Ancient Lockbox `setPos()` (already wired 2026-08-24) re-checked against the same real
  capture's PathLog -- Rune matches to within rounding, Lockbox off by ~1.2 yalms (within normal
  interaction range, not a bug). `instance_entities.sql`/`mob_spawn_points.sql` clean. See
  `Assault_Fix_Log.md`'s "Content-completeness sweep" entry for the full writeup. Overall stays
  🔴 -- the still-open gaps (3 of 5 Karakul/QiqirnMine ids never captured, Ice Cage break-state
  unconfirmed, dice-game/shepherd-follow needing new engine precedent) are unchanged.

### The Double Agent (Mamool Ja Training Grounds, mission 15)
**Overall status: ✅** -- User-confirmed complete 2026-09-02.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data).
- ✅ Real mechanic built 2026-08-18, then rebuilt 2026-08-24 from 2 independent captures + wiki +
  dat-extractor: 26 real Qiqirn Spy NPCs (17047628-17047653, `npcs/Qiqirn_Spy.lua`) each offer a
  real per-NPC-CSID menu (capture/question/cancel); one is randomly the double agent per instance
  (`instance:setProgress`, same pattern as Golden Salvage). Lockbox rewards (???_box -> hi-potion
  +3) and real Assault points (550) wired in. Decoy dialogue text ids are capture-derived with the
  zone's known client-version -1 offset applied, but not independently re-verified against a
  client dialog table dump -- worth an independent check if dialogue looks wrong live. Known gap:
  the wiki's directional hint component ("somewhere in east?") has no dat-extractor-confirmed
  message id yet -- distance-tier hints only.
- ✅ **9 zero-position `Puk` mobs fixed 2026-08-25** (ids `17047654`-`17047662`), found via a
  zone-wide sweep and fixed with real positions from `Mamool Ja Training Grounds - The Double
  Agent (Thris Nov2025)`'s PathLog. Re-confirmed 2026-09-02: `mob_spawn_points.sql` rows are
  correct real (non-zero) positions.
- ✅ **2026-09-02: `instance_entities.sql` registration re-verified entity-by-entity** against the
  Double Agent capture's NPCLogger, including for the `_1u*` door props whose captured live ids
  are +1-drifted vs their real `npc_list` id (known zone-wide capture-id-offset issue) -- every
  entity this instance needs (26 spies, 9 Puk, Rune of Release, Ancient Lockbox, and the door
  props near the spy cluster) is present and correctly registered to instance 15. No missing
  registrations found (unlike mission 11's earlier door-registration bug).
- 🟢 **2026-09-02 fix: Rune of Release/Ancient Lockbox staging position.**
  `instances/the_double_agent.lua` never called `setPos()` for this pair, so they defaulted to
  Imperial Treasure Retrieval's shared coordinates (`301, 2, -417` / `299, 2, -420`) -- ~165 yalms
  from this mission's own real spot. Fixed via `setPos()` using the real capture position from
  this mission's own NPCLogger: Rune of Release `(-222, 1, -384)`, Ancient Lockbox
  `(-220, 2, -385)`, both dir 192 (same pattern already used by every other Mamool Ja mission,
  e.g. `the_susanoo_shuffle.lua`). Not yet SQL/live-verified (Lua-only change, no reimport
  needed).
- 🟢 **2026-09-02, user-reported live: capture/question menu "not wired up to dialog options."**
  Root cause: `onTrigger` called `player:startEvent(csid)` with zero padding -- this project's own
  documented rule is that a bare/short `startEvent()` call can render a CS event's dialog/menu
  broken instead of a clean freeze, easily misdiagnosed as a wrong-text-id problem. The real event
  itself (decompiled via FFXI-EventsDump) was already correct: message 7597/7598 in that tool's own
  numbering (confirmed to be the same real 7576/7577 already wired here, per the known client/
  capture id offset) for the prompt and 3-option menu, options in the exact order this file already
  expected. Fixed by padding to the full 10-value signature (`csid, 0, 0, 0, 0, 0, 0, 0, 0, 0`,
  matching `Naja_Salaheem.lua`'s convention).
- 🟢 **Same pass: user provided a real full dialog-table dump (7547-7580) for this NPC's text
  block.** Used it to fix two real content gaps:
  - The real spy's hint was one fixed line (7568). The wiki's own walkthrough quotes 3 different
    real-spy hint lines seen across different real playthroughs ("Noooo Listen", "I know
    noooothing, yooo know?", "There nooo Qiqirn like that, yooo know?") -- these match 7568/7564/
    7567 verbatim, confirming the real spy's hint is a random pick from a pool, not one fixed line.
    Now picks randomly from `QIQIRN_SPY_REAL_HINT_POOL = {7568, 7564, 7565, 7566, 7567}`.
  - A numeric-yalm hint style (7547, "Just N yalm(s) over there, okay?") was confirmed to exist
    alongside the 4 distance-tier lines already wired, but was dead/unused. Since no capture pins
    down which decoys use which style, each decoy now stably picks by its own npc id parity
    (documented assumption, not a capture-confirmed formula) so both real message families
    actually see use.
  - **2026-09-02 (later): direction hints implemented too**, per user suggestion -- rather than
    independently computing a compass bearing from raw X/Z, the decoy actually turns to face the
    real spy via `npc:lookAt()` (the same engine call used for real NPC-facing behavior everywhere
    else) and its own resulting rotation byte is mapped to a compass octant using the engine's own
    real rotation-byte convention (0=N/64=E/128=S/192=W, atan2-based, user-confirmed earlier this
    session -- see the Saving Private Ryaaf writeup above). Exact 8-way direction (7548-7555) used
    when close, vague 4-way cardinal-only (7556-7559) when far, matching the wiki's described
    behavior. All 3 real hint styles (yalm distance, direction, tier) now cycle by npc id modulo 3
    (documented assumption on selection, not capture-confirmed).
- 🟢 **2026-09-02 (later): wrong-guess penalty rounding fixed.** User clarified the exact
  worksheet wording -- "66.67 point penalty, rounded down, for every false accusation" -- the
  rounding applies to the CUMULATIVE total (`floor(66.67 * n)`), not a pre-rounded 66-per-guess
  flat rate. `Rune_of_Release.lua` was computing `66 * wrongGuesses`, which only matches the real
  value at 1 wrong guess and undershoots the real penalty from 2 onward (e.g. 3 wrong guesses:
  real 200, was giving 198). Fixed to `math.floor(66.67 * wrongGuesses)`.
- ✅ **CORRECTION to the padding bullet above, 2026-09-02 (later still): the 10-value padding fix
  was itself wrong.** User-reported live: the menu stopped opening at all after that change went
  in. Real cause: this event genuinely expects a bare `player:startEvent(csid)` call, matching
  `Quhaaja.lua`'s own real, live-confirmed-working menu in the same zone -- the general
  "always pad startEvent" rule isn't universal (see `topaz_startevent_padding_required` memory).
  Reverted to bare. A second, related bug then surfaced from the same root confusion: `onEventUpdate`
  had been storing a stale ack value that made `onEventFinish` always land on the same branch
  regardless of the real selection (user-reported: "all Qiqirn Spy say the same line over and
  over") -- fixed by trusting `onEventFinish`'s own `option` parameter directly. Finally, a
  **real option-value shift** was found via user screenshot: the client sends raw values shifted
  +1 from the menu's visual order (displayed "Capture"=1st item sends raw 1, "Question"=2nd sends
  raw 2, "Nothing"=3rd sends raw 0) -- `onEventFinish`'s branches corrected to match.
- ✅ **2026-09-02 (later): 4 real rocks fixed, user-reported live.** `_1u1`/`_1ux`/`_1uy`/`_1uz`
  were registered to this instance but sitting at their `npc_list` default `animation=9`
  (CLOSED/impassable), same door-prop bug class fixed repeatedly elsewhere this session --
  explicitly opened in `onInstanceCreated` (`_1u1` also needed its `IDs.lua` alias added, the real
  row already existed but was never referenced by name).
- ✅ **2026-09-02, user-confirmed live: PASSED.** Menu options, hints, and capture/completion all
  verified working end-to-end in a real playthrough.

### Siegemaster Assassination (Lebros Cavern, mission 25)
**Overall status: ✅ -- User-confirmed complete 2026-09-01.**
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 1210 points.
- ✅ Kill-any-1-of-8 was wrong -- completion didn't fire until the 7th kill. Threshold raised to
  7 (exact observed completion point, single capture). Lockbox reward wired in.

### Building Bridges (Periqia, mission 35)
**Overall status: ✅** -- User-confirmed complete 2026-09-02.
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ Trigger-all-4-switches mechanic confirmed correct (4 distinct Bridge Switches each triggered
  once). Lockbox rewards (???_axe, newly wired) and Assault points (1320, real) now real.
- ✅ **User-provided 2026-08-19**: full lockbox data supersedes the single-item entry above -- 3
  qItems (??? Axe / ??? Polearm / ??? Box, equal-split, no odds given) and 4 regItems (Hi-Potion
  +3, Hi-Potion Tank, Hi-Ether Tank, Hi-Reraiser). Wired into `Periqia/npcs/Ancient_Lockbox.lua`.
- ✅ **2026-09-12: same rotation/despawn-blink/wrong-animsub bug class found and fixed on
  `Bridge_Switch.lua`** as Evade and Escape's `Switch.lua` (this codebase's own 2026-09-03 note on
  this row already flagged the same `animationsub` default-4 theory and reverted it as "no effect"
  -- that revert was premature, since the activated value tested against was still the wrong `1`).
  Applied the same real, packet-capture-confirmed fix: removed `lookAt()`/`forceRespawn()`,
  `animationsub` corrected to `4`(unlit)/`5`(activated), `namevis` corrected `32`->`36` in
  `npc_list.sql` (`17006814-17`). Not independently re-captured for this specific zone -- carried
  over from the cross-zone-confirmed real values (same model 1509, verified in both Lebros Cavern
  and Nyzul Isle captures), consistent with this file's own original note that no real Building
  Bridges capture ever caught a switch activation packet at all.

### Searat Salvation (Ilrusi Atoll, mission 45)
**Overall status: 🟢 -- CORRECTED 2026-09-02.** The bullet below describing "autonomous NPC-AI,
no precedent, unbuilt" was stale/wrong -- it's a prior session's own superseded read of the win
capture. `scripts/zones/Ilrusi_Atoll/instances/searat_salvation.lua`'s header already documents a
2026-08-24 FULL REBUILD that corrected this exact misreading to the real mechanic (a
player-guided escort, not autonomous AI) and built it end-to-end -- that build was simply never
reflected back into this tracker entry until now. Verified the code actually implements what its
own header claims: `npcs/QiqirnDiver_Common.lua` (talk to an idle diver to make it follow you,
`onTrigger`/`tick()`) and `npcs/GiantOrobon_Common.lua` (sight-range scare check, `DiverCommon.
scare()`) are both real, complete, non-stub scripts wired into the instance via `IDs.lua`'s
`QIQIRN_DIVER`/`GIANT_OROBON`/`QIQIRN_CHIEF_DIVER` tables. Kept at 🟢 rather than ✅ since none of
this has been live-tested yet.
- ✅ Entrance approximated 2026-08-18 (user-provided real-WIN capture, older format, no PathLog).
  Real WIN, 825 points.
- 🟢 **Real mechanic, built 2026-08-24, re-confirmed live-in-code 2026-09-02**: talk to an idle
  Qiqirn Diver to make it follow you (`SEARAT_DIVER_GREET`); a nearby Giant Orobon (sight-range
  threat, cannot be attacked/attack) scares a followed diver into fleeing
  (`SEARAT_DIVER_SCARED`/`FLEEING`), and you must re-locate and re-talk to resume
  (`SEARAT_DIVER_READY`); delivering a diver to the Qiqirn Chief Diver
  (`SEARAT_DIVER_ARRIVED`/`THANKS`) completes that diver -- 1 delivered completes the mission
  (matches the real capture's own completion despite the Chief Diver's "not everybody" line firing
  at win time), all 5 needed for max Assault points. STILL OPEN: exact points-per-diver-saved
  scaling (only the 1-diver/solo 825pt data point is confirmed); Giant Orobon are stationary
  sight-checkers, not actually roaming/wandering (the header's "roaming" language is aspirational
  -- no capture ever caught their movement pattern, so none was built, a deliberate
  simplification, not a bug).
- 🟢 **2026-09-02, real bug fixed**: both `QiqirnDiver_Common.lua` `pathTo()` calls (following the
  guide, fleeing an Orobon) used bare `RUN + SCRIPT` flags with no `WALLHACK` -- this codebase's
  own established default (per project history) is `RUN + WALLHACK + SCRIPT`; a strict
  no-wallhack path is known to fail outright on navmesh gaps elsewhere in this session. Added
  `WALLHACK` to both calls as a preventive fix (not yet observed failing live, but matches a known
  bug class exactly).
- 🟢 **Data-completeness re-audit 2026-09-02: fixed.** All 5 Qiqirn Diver, all 7 Giant Orobon, and
  the Chief Diver (13 ids, `17002564`-`17002576`) were sitting at `(0,0,0,0)` in `npc_list.sql`
  despite being fully registered to `instance_entities` -- fixed with real x/y/z/r from the
  Siknawz 2023.06.19 `[W]` win capture's own NPCLogger database (`Ilrusi Atoll C - Searat
  Salvation`). Rune of Release/Ancient Lockbox already had real per-instance `setPos()` from the
  2026-08-24 rebuild -- re-confirmed correct, no change needed. No unwired doors found near this
  mission's real entity cluster (checked against the zone's full real door-prop list; nearest is
  well outside interaction range).
- 🟢 **2026-09-02 (later), user-provided fresh wiki walkthrough + real capture -- 3 real fixes:**
  - **Widescan flags backwards.** The wiki explicitly says "Qiqirn Divers show up on Widescan.
    Giant Orobons do not." All 13 rows (`17002564`-`17002576`) had `widescan=1` in `npc_list.sql`
    -- fixed the 7 Giant Orobon to `0`, left the 5 Divers + Chief Diver correctly at `1`.
  - **Giant Orobon were stationary (previously documented as a deliberate simplification, since no
    capture had ever caught their movement).** User then provided a fresh real capture
    ("Searat_Salvation[W] - 4 Divers Rescued.zip") with a real PathLog for all 7 -- confirms they
    genuinely roam continuous closed loops. New file `Orobon_Roam_Routes.lua` holds the real
    routes (Douglas-Peucker simplified, 1613 raw points -> 250 waypoints, same method already
    proven for Periqia's Lamia guards); `GiantOrobon_Common.lua` now walks them one leg per tick
    via the same `advancePatrol()` pattern as `Lamia_Guard_Common.lua`.
  - **"Long and narrow Sight aggro" was a flat circular radius.** Replaced with a real
    forward-facing cone check (long distance, narrow half-angle) using this project's own
    `worldAngle()` rotation-byte convention (`src/common/utils.cpp`, same one confirmed this
    session for the Qiqirn Spy direction hints), so an Orobon can only "see" roughly what's in
    front of it -- matches the wiki's "possible to run behind them" / "slip through just to the
    side." Not capture-confirmed against exact real distance/angle values (none exist for this),
    documented as a reasonable estimate.
  - Re-confirmed the fresh capture's CapLog text matches this file's already-wired dialogue ids
    verbatim (`SEARAT_DIVER_GREET`/`SCARED` etc.) and confirms the existing multi-diver-scared-
    at-once behavior is correct (3 divers panicked at the identical capture timestamp from one
    Orobon).
  - Not yet live-tested. SQL change (`widescan`) needs `py -3 dbtool.py update full`; Lua changes
    need only a restart.
- 🟢 **2026-09-02 (later): real diver flee/hiding-spot data found.** The same capture zip included
  `pathlogs/Dukilles.log` -- not a per-entity PathLog but a human-annotated list of 18 real
  hiding-spot positions across the map (caves, wrecks, behind rocks), matching the wiki's own
  "hide in tunnels or in hiding spots on ships" almost verbatim. New file
  `Diver_Hiding_Spots.lua` holds them verbatim. `QiqirnDiver_Common.lua`'s `scare()` now paths the
  fleeing diver to its nearest real hiding spot instead of a synthetic random-direction point.
  Which specific spot a diver picks isn't capture-confirmed (no diver-side PathLog exists in this
  capture, only the 7 Orobon got one) -- nearest-spot is a documented approximation of the
  selection rule, but the spot positions themselves are real, not invented.

### Supplies Recovery (Leujaoam Sanctum, mission 6)
**Overall status: ✅** -- User-confirmed complete 2026-09-02.
2 real mechanic mismatches found and fixed early in this mission's rebuild, both
cross-checked against this project's own dat-extractor cache by TEXT (the capture's raw MesNums
for Kuihlud's lines were drifted -- see below):
1. **"No Imps appear until you talk to Kuihlud"** -- previously all 10 Imps spawned immediately at
   `onInstanceCreated`. Moved to a new `npcs/Kuihlud.lua`'s `onTrigger` (real message ids
   `KUIHLUD_INTRO`=7611/`KUIHLUD_REMINDER`=7612/`KUIHLUD_WIN`=7613 -- the capture reported
   7626/7627, which decode in our own dats to unrelated "You obtain &lt;item&gt;" template text,
   not Kuihlud's lines at all). Gasharyad/Salimuhl still spawn immediately (already traveling with
   the player per the wiki).
2. **"Mission ends when all Imps are dead, then compares supplies"** -- previously completion
   fired the instant a live 30s tick showed the player ahead, which could trigger mid-fight before
   every Imp was dead. Moved to `supplies_recovery_common.lua`'s new `onImpKilled()`, called once
   per real kill from `Imp.lua`, only evaluated once all 10 confirmed real Imps are down (wiki says
   11 total -- only 10 real positions have ever been found in any capture, honest gap, not
   fabricated up to 11).
Also wired the real `NO_SUPPLIES_OBTAINED` (7609, "You did not receive any supplies.") line for
the no-drop case (previously silent) and switched the Immortals' tick announcement to the real
dat-verified `IMMORTALS_SUPPLY_COUNT` (7610, numeric param) via `messageSpecial()` instead of a
manually-built string.
- 🟢 **2026-09-02 (later, again x2): real per-Imp-id drop table, corrected twice as more captures
  arrived.** First pass (3 more captures: 2x Grievor, 1x Tacocat) correlated real
  `[HP Track] Killed <npcid> (Imp)` lines against the immediately-following item/no-supplies line
  by timestamp for the first time, and concluded the drop was fully fixed per Imp id -- including 2
  ids read as "guaranteed no-drop." **3 MORE captures (Bemused 2019, Giichi 2021, Siknawz 2023)
  overturned that**: id `17059939`, previously 3/3 "confirmed no-drop," dropped "an Imperial wootz
  ingot" in all 3 of these later captures. Real reconciled model: each Imp id has ONE fixed item it
  CAN drop, but the drop itself is a real per-kill CHANCE (~50%, matching the observed hit/miss
  rate across all 6 captures combined) -- the earlier "no-drop" reads were just small-sample
  unlucky streaks, not the mechanic. Current state, 8 of 10 real ids with at least one clean
  same-timestamp confirmation, zero contradictions on WHICH item once one was seen:
  `17059936`=pickaxe, `17059939`=Imperial wootz ingot, `17059940`=gold ingot (lower confidence,
  single sample), `17059941`=karakul skin, `17059942`=chunk of rock salt,
  `17059943`=handful of armored arrowheads, `17059945`=bag of Imperial flour (all cross-checked
  against `item_basic.sql` by exact name match, not guessed). `17059944` has 4/4 samples with no
  drop observed -- could be a real non-dropper or still just an unlucky streak (~6% likely by
  chance alone).
- 🟢 **2026-09-02 (final pass, user-directed: "Some imps are coded to drop nothing").** Re-checked
  the MESSAGE pattern (not just drop presence) across all 6 captures, and it splits cleanly:
  `17059944` fires the real `NO_SUPPLIES_OBTAINED` message every time (4/4 samples) -- it
  participates in the roll, just hasn't won it yet in the samples available, so it stays on a
  normal `DROP_CHANCE` roll (falls back to the 2 remaining real-but-unassigned items: pinch of
  cluster ash, popoto). `17059937`/`17059938` NEVER produce any supply-related message at all in
  ANY of 7 combined kill observations (4 for 937, 3 for 938) -- every other id, including 944,
  always fires some message on every kill. That structural absence is the real signature of "coded
  to drop nothing" -- these 2 are now hard-coded no-drop with no roll and no message at all
  (`NO_DROP_IDS` in `supplies_recovery_common.lua`, `tryGrantSupplyPackage()`'s 2nd return value
  tells `Imp.lua` whether to show the no-supplies message or stay silent). Not yet SQL-reimported
  (N/A, pure Lua) or live-tested -- do not treat as signed off.
- ✅ **User-tested live 2026-08-24: no ice wall blockers present** -- this mission wasn't affected
  by the `_1x*`/`_jx*` door-prop drift bug (see Leujaoam Cleansing's entry) in the first place.
- ✅ Entrance already exactly right (real coordinates were already sourced from an inline SQL
  comment). Real WIN, 1100 points.
- 🟢 **2026-09-02, built**: Kill-all-12 was wrong -- real mechanic is a supply-package race against
  a rival NPC faction ("the Immortals"). Built in `Imp.lua` (`onMobDeath`, 50% drop chance -- real,
  4 of 8 kills dropped a package in the capture) and new
  `npcs/supplies_recovery_common.lua` (rotates the 4 real captured item flavors: gold ingot,
  handful of armored arrowheads, pinch of cluster ash, pickaxe -- via `addTempItem` +
  `messageSpecial(PLAYER_OBTAINS_TEMP_ITEM)`, the same real text-id pattern Counting Sheep's ore
  trade-in uses). The Immortals' rival counter and the 30s announcement cadence are driven from
  `instances/supplies_recovery.lua`'s `onInstanceTimeUpdate` (real: the capture's own CapLog ticks
  "The Immortals have recovered N supply package(s) thus far." every 30s exactly), completing the
  instance the first tick the player's own count exceeds the Immortals'. **Not capture-confirmed**
  (single non-exhaustive capture, documented rather than fabricated): the Immortals' own per-tick
  increment probability (approximated at a flat 20%/tick, tuned to roughly match the observed
  0,0,0,0,1,1,1,1,1,2,3,3,3,3,3,3 progression, not a real formula) and whether the real completion
  check truly happens exactly on the 30s tick (assumed, matches the observed ~58s gap between the
  capture's last "3" announcement and its actual win). Assault points and Lockbox reward already
  real from before.
- 🟢 **2026-09-02, real gap found and fixed**: `RUNE_OF_RELEASE`/`ANCIENT_LOCKBOX` never actually
  got a `setPos()` call -- both sat at this zone's shared `npc_list` default, which is actually
  **Bloody Rondo's own confirmed position** (`504/506, -302`), hundreds of yalms off. The real
  value had been correctly identified and written into this file's own header comment since
  2026-08-18 but never applied. Fixed via `setPos()` in `onInstanceCreated`, re-confirmed against
  real PathLog rows for both entities (`Rune_of_Release/17060015.csv`,
  `Ancient_Lockbox/17060014.csv`, both matching the header comment to 3 decimals). Not yet
  SQL-reimported or live-tested (this was a pure Lua change, no SQL edit needed).
- ✅ *(resolved, see the mechanic-correction bullets above)* `Kuihlud` (`17060101`) previously had
  zero Lua wiring at all -- now has a real `npcs/Kuihlud.lua` with dat-verified dialogue, and is
  the real gate for the whole Imp-spawn mechanic (not just cosmetic flavor as originally assessed).
- ✅ **2026-09-02 (later): full real hunting AI + drop-mechanic rebuild, user-reported live in
  several rounds.** Gasharyad/Salimuhl had zero combat AI (stub files, just stood/roamed) --
  built real hunting (`immortalAiTick()`, ally-engage pattern from Demolition Duty's Automaton),
  gated to start only after Kuihlud's trigger. Real per-Imp-id fixed drop items (7 confirmed,
  DROP_CHANCE 0.5) + 2 hard-coded no-drop ids (17059937/938, structurally confirmed via message
  pattern across 7 captures). The Immortals' own supply-chance mechanic rebuilt from a blind 30s
  timer to real combat-involvement gating (`immortalsAttacking()`) -- root cause of it always
  reading false found and fixed: `CMobEntity::Die()` clears the enmity list synchronously before
  the deferred `onMobDeath` ever runs, so the Imp's post-death enmity list was always empty
  regardless of who fought it; switched to marking the Imp directly at the moment an Immortal
  engages it, while still alive. Win-condition kill counter was also gated behind
  `isKiller and player`, silently skipping the completion check on any non-player kill -- now
  unconditional. A real loss (`playerCount <= immortalCount` once all 10 Imps are dead) previously
  went completely silent -- fixed to call `instance:fail()` immediately, using the same
  already-proven `MISSION_FAILED` flow. The periodic "Immortals recovered N supply packages"
  announcement always showed 0 despite the real backend count being correct -- root cause: the raw
  client text uses literal parameter slot 1 (`Numeric Parameter 1`), not slot 0; the Lua call only
  passed one argument (landing in slot 0), leaving the slot the text actually reads permanently at
  its default. Fixed by passing a dummy 0 then the real count. HP=0/`skill_list_id` mismatches for
  Gasharyad/Salimuhl also fixed (see mob_pools.sql's own comments on those rows) -- real Sword
  weaponskills (Gowam precedent) instead of Great Katana, real BLU spell list (299, includes
  Healing Breeze) instead of no spells at all, REGEN 50/tick. Gasharyad/Salimuhl's real
  terrain-independent cliff-climb (confirmed via a real retail note plus `!checknav`) was
  initially "fixed" with a forced hallway-waypoint detour, then that detour itself needed 2
  waypoint-position corrections and a leg-specific WALLHACK re-added (real local pathing failure,
  not the cliff) plus a route-progress-reset bug fix (was restarting the whole waypoint chain
  every tick a closer "bottom" Imp momentarily won the target check).
- ✅ **2026-09-02, user-confirmed live: PASSED.** Correct supply count now displays in chat, and a
  real loss now correctly exits the Assault instead of going silent.

### Imperial Treasure Retrieval (Mamool Ja Training Grounds, mission 16)
**Overall status: 🟡** -- Originally built 2026-08-29 from a real wiki walkthrough, then
**substantially rebuilt 2026-08-30** after live testing surfaced several real engine/data bugs and
a much better real design was ported in from a LandSandBoat implementation of this exact mission
(user-provided source). See `npcs/imperial_treasure_common.lua`'s header for the full ported
design writeup and `mamool_ja_carrier_common.lua` for the current (thin driver) carrier AI.
**Not yet a confirmed full clean live playthrough** -- keeping at 🟡.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 366 points.
- ✅ **2026-08-29, real root cause of "carriers/coffers invisible despite showing in `!navdebug`"**:
  `npc_list.status = 6` (`CUTSCENE_ONLY`) never renders client-side or shows on radar, even though
  the entity is correctly tracked server-side -- diagnosed by field-by-field diff against a
  confirmed-working NPC. Fixed for all 16 entities (6 carriers, 9 coffers, Governor) plus Zahakahm,
  plus a further systematic sweep across every Assault zone (82 more rows). Also fixed:
  `Rune_of_Release`/`Ancient_Lockbox` `widescan=0` (only these two, every sibling zone uses 1) and
  wrong positions (both were sitting at the same wrong coordinates, ~220,1.5,-505) -- corrected to
  real capture-confirmed spots near the entrance.
- ✅ **2026-08-30, real bug: carriers stored wander-waypoint/spawn-point floats in
  `npc:setLocalVar()`**, which is `uint32` (unsigned-integer-only) in this engine -- a negative
  float silently wraps around (confirmed live via the map-server log:
  `CNavMesh::findPath ... -> (..., 4294967040.000000)`, exactly `2^32-256`), producing garbage
  `pathTo()` targets that, combined with `WALLHACK`, walked carriers straight through walls until
  they despawned out of bounds. Fixed by keeping all persisted float positions in a plain Lua
  table (module memory) instead, keyed by npc id.
- ✅ **2026-08-30, real bug: the Governor-bound return leg used `WALLHACK` for the whole trip**,
  cutting straight through walls instead of the real bent route (confirmed against the user's own
  map + a GM-walked real `LOGPOS` route). Fixed: routed through 4 real GM-walked waypoints with NO
  `WALLHACK` on any leg, and no more silent fallback-to-wallhack-on-failure (a first attempt using
  capture-inferred waypoints with a wallhack fallback still clipped -- removed entirely; a stuck
  leg now just retries instead of ever cutting through geometry).
- ✅ **2026-08-30, PORTED a real LandSandBoat implementation of this mission** (user-provided
  source), replacing this session's own wiki-only wander/pursue state machine with a materially
  more accurate design: 3 of 6 carriers (Red/Blue/Yellow) are real ATTACKERS that claim coffers via
  a bitmask (prevents two carriers racing the same one) and return gems to a base point near the
  Governor; the other 3 (Green/White/Black) are real DEFENDERS that patrol fixed positions with an
  idle look-around pause and only react to a nearby gem-holding player; both roles use a real
  tick-based distance+facing check (not just proximity) to notice and intercept. Ported primitives
  that don't exist in this engine (`pointNear`, `despawn`, `utils.pickRandom`/`distanceWithin`)
  were substituted with engine-equivalent or inline logic. **Real user-provided defender routes**:
  Green Badge (8 points) and Black Badge (7 points) now have real coordinates; White Badge still
  uses a placeholder (own spawn point + small offsets) pending the user's level-mapping pass.
- ✅ **2026-08-30, real dialogue/messages wired in from a genuine capture + dat-extractor
  cross-check** (this zone's raw CapLog MesNum labels are known to drift -- re-verified against
  the real client dialog table): kill-tally-style item messages for coffer opens/steals
  (`PLAYER_OBTAINS_TREASURE_ITEM`/`ALLY_OBTAINED_TREASURE`/`ENEMY_STEALS_TREASURE`/etc, all real
  item-substitution messages using the confirmed real 9-gem set), the carrier's own
  `CARRIER_IDLE_TAUNT`/`CARRIER_STEAL_TAUNT` lines (moved to their real trigger conditions after
  an initial mix-up), and Zahakahm's real turn-in/completion dialogue -- the Rune of Release reveal
  was originally (wrongly) tied to the FIRST gem turn-in; real capture confirms it only reveals on
  the SECOND (empty-handed) trigger that completes the mission. Only the ruby/coffer `17047823`
  pairing is capture-confirmed; the other 8 coffers' specific gem is a fixed-but-arbitrary
  assignment across the same real 9-item set.
- ✅ **2026-08-30, navmesh swap validated live**: after the user replaced this zone's navmesh
  (sourced from another dev who'd already fixed similar pathing problems), carrier pathing that
  previously needed the wallhack-avoidance waypoint workarounds above now reportedly paths
  correctly without them -- not yet re-simplified in code (the workarounds are still harmless to
  leave in place), but worth revisiting if further navmesh-dependent issues surface.
- 🔴 **Not yet fixed**: `mob_spawn_points.sql`'s poolid for a wholly different mission's NMs
  (Bluethunder Kaqool Ja/Festive Firedrake, Blitzkrieg) was found to reference completely
  unrelated `mob_pools` rows during adjacent investigation -- see Blitzkrieg's own entry.
- 🟢 **5 of 6 named cast NPCs added 2026-08-25** via the npclogger cross-reference pass: Qultada,
  Joachim, Ulmia, Koru-Moru, Yoran-Oran (real canon FFXI characters -- real positions from the
  capture, real look bytes found by searching their other appearances elsewhere in `npc_list.sql`
  since this specific capture never recorded their model data). Role in this mission still not
  otherwise documented.

### Apkallu Breeding (Lebros Cavern, mission 26)
**Overall status: 🟢** -- **Corrected 2026-09-02 -- this header was stale, left at 🔴 from before
the same-day full rebuild** (real pairing minigame, morse-code word dialogue for all 16 real
Apkallu, Rhap Nelhah's real 2-trigger end-mission flow, real interpolated scoring formula -- see
this section's later bullets for the full build history). **Not yet live-tested by the user.**
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data, loss capture).
- 🟡 Real mechanic documented but not built: a pairing minigame (find matching male/female
  Apkallu couples by cry-code compatibility), 13 real NPC positions found. Needs a two-mob
  pairing system the engine doesn't have. **User-confirmed 2026-08-19**: Assault points scale
  with how many pairs are correctly matched (max 1300 for 8/8, +130 armband bonus), not a flat
  value -- 2 real packet-decoded completions this session (825, 550) are consistent with
  different pair counts. Deliberately left unset (falls through to 0) rather than wiring in a
  wrong flat number; real formula documented in `instances/apkallu_breeding.lua`'s header for
  whenever the minigame gets built.
- ✅ **User-provided 2026-08-19**: real lockbox reward data received (previously fully missing,
  flagged in the missing-rewards audit). qItems ??? Earring / ??? Sash / ??? Box (equal-split, no
  odds given); regItems Hi-Potion +2, Hi-Potion Tank, Reraiser. Wired into
  `Lebros_Cavern/npcs/Ancient_Lockbox.lua`. Independent of the still-unset Assault points formula
  above -- lockbox rewards apply regardless of pairs matched.
- 🟢 **5 of 6 zero-position `Vulcanian_Bomb` mobs fixed 2026-08-25** (`17035352`/`17035354`-
  `17035358`, 1 -- `17035356` -- has no data in the available capture), found via a zone-wide
  sweep and fixed with real positions from `Lebros Cavern S - Apkallu Breeding (Thris)`. Separate
  from the 13 pairing-minigame NPC positions already documented above -- these are ambient combat
  mobs. Also **corrects a stale `instance_entities.sql` comment** ("Apkallu Breeding -- SCAFFOLD
  ONLY, no mobs") -- real, capturable mobs do exist for this instance. Not yet SQL-reimported or
  live-tested.
- 🟢 **Rhap Nelhah added 2026-08-25** (`17035485`) via the npclogger cross-reference pass -- real
  NPC shared with Egg Conservation/Operation Black Pearl, real position + look byte (confirmed
  consistent across 2 independent captures). Not yet SQL-reimported or live-tested.
- 🔴 **2026-08-29 "fix" above was itself wrong, corrected 2026-09-02.** Re-checked directly
  against the real `Lebros Cavern S - Apkallu Breeding (Thris)` capture's own NPCLogger db
  (`Lebros Cavern.db`, table `entries`, `name='LebrosApkallu'`): this mission's real pairing NPCs
  are ids **17035337-17035351** (13 of 16 claimed ids resolve a real position; `17035336`/
  `17035339`/`17035341` have no capture data). The `LEBROS_APKALLU_MALE/FEMALE*` ids
  (`17035380`-`395`) that the 2026-08-29 pass moved here are a completely unrelated real id range
  -- they're Egg Conservation's (mission 28) actual mob family (`mob_groups.sql` groupid 23,
  poolid 197, built 2026-08-25) -- and moving them here meant Egg Conservation's own mobs were
  never registered to any instance at all (see Egg Conservation's own entry for that half of the
  fix). Fixed this pass:
  - `sql/npc_list.sql` (`17035337`-`17035351`): filled in real `pos_rot`/`pos_x`/`pos_y`/`pos_z`
    from the NPCLogger capture (were all `0,0,0` placeholder stubs despite the 2026-08-18 fix log
    entry claiming these positions were "found" -- they were documented but never actually
    written to SQL until now), and set `status`/`entityFlags` to the same real-spawned-NPC
    convention already used for `Rhap_Nelhah` in this same file (`status=0`, `entityFlags=27`).
    `17035336`/`17035339`/`17035341` left as unpositioned stubs (real open gap, not guessed).
  - `sql/instance_entities.sql`: registered the 13 real ids to instance 26 (previously not
    registered to any instance at all), moved the 16 `17035380`-`395` ids to instance 28 where
    they actually belong.
  - `scripts/zones/Lebros_Cavern/IDs.lua`: replaced the nested nonsense `[26]` sub-table (which
    held the wrong-mission `LEBROS_APKALLU_MALE/FEMALE*` ids) with a new `[26]` sub-table holding
    the real `APKALLU1`-`APKALLU13` = `17035337`...`17035351` mapping; flattened
    `LEBROS_APKALLU_MALE/FEMALE*` back to top-level `npc.*` keys, matching how
    `mobs/Lebros_Apkallu.lua`/`mobs/Qiqirn_Eggler.lua` actually read them (see Egg Conservation's
    entry -- those references were silently resolving to `nil` since 2026-08-29).
  Pairing/compatibility minigame logic itself is still not built -- 13 real NPCs now exist and
  spawn in the right instance with real positions, but nothing lets the player interact with them
  to form a pair yet; this is the reason Overall status stays 🔴. Not yet SQL-reimported or
  live-tested.
- 🔴 **Open gap, not fixed**: Rhap Nelhah (`17035485`, real position, confirmed spawned in this
  instance) has no `npcs/Rhap_Nelhah.lua` onTrigger script at all -- interacting with it currently
  falls through to the engine's default handler. The real quoted dialogue ("The slightly smaller
  ones are the girrrls...") comes from hand-decoded raw `0x2A` MessageSpecial packets in this
  capture (no plain-text CapLog exists for this mission), so there is no confirmed numeric text id
  to wire a script to without guessing -- left undone rather than fabricating one.
- ⚠️ **The above bullets predate this session's full 2026-09-02 rebuild** (real pairing minigame,
  Rhap Nelhah script, all 16 real morse-code word assignments, real scoring formula -- see
  `npcs/Lebros_Apkallu.lua`/`npcs/Rhap_Nelhah.lua`/`Apkallu_Breeding_Words.lua` and this section's
  bullets further up for the current, accurate state) -- kept for history, not current.
- 🟢 **2026-09-02, user-reported live: all 16 Apkallu invisible.** Root cause: `npc_list.sql`'s
  `look` blob for all 16 rows decoded to modelid `50` -- a never-verified placeholder stub, the
  same exact wrong value already found and fixed for the Lamia guards earlier this session (a
  "gal_" asset, not the right model). Fixed to the real modelid `1723`, taken from `mob_pools`
  poolid `197` ('Apkallu', familyid 27) -- the confirmed-working Egg Conservation mob family's own
  real look data. Needs `py -3 dbtool.py update full` + restart to test.

### Stop the Bloodshed (Periqia, mission 36)
**Overall status: ✅ -- User-confirmed complete 2026-09-02, full pass, no outstanding issues.**
The earlier kill-all-18 read (below) was wrong --
user provided the real wiki objective/walkthrough: "Kill all 35 Augmented Chigoes... not necessary
to kill [Chigoe Breeders] to win." The one confirmed capture's completion at 18 kills was actually
11 Augmented Chigoe + 7 Chigoe Breeder -- Breeder kills were being wrongly counted toward progress.
Real fixes applied (see bullets below): Breeders no longer count, threshold raised to 35 (exactly
matching this mission's own 35 real Augmented Chigoe spawn points already in this repo's SQL --
strong non-coincidental confirmation), progress moved to onMobDeath (was onMobDespawn, a known
false-complete bug class), and Rune of Release/Ancient Lockbox real position + grid ref fixed (see
below -- were never wired at all, silently defaulting to the shared placeholder position). Kept at
🟢 rather than ✅ since none of this has been live-tested yet.
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- 🟢 **2026-09-02: kill-all-18 corrected to the real kill-all-35 Augmented-Chigoe-only mechanic**
  (superseding the 2026-08-18 correction below, kept for history). `mobs/Chigoe_Breeder.lua` no
  longer contributes to progress at all; `mobs/Augmented_Chigoe.lua` moved from onMobDespawn to
  onMobDeath (same false-complete/false-count bug class already fixed elsewhere this session);
  `instances/stop_the_bloodshed.lua`'s threshold raised from 18 to 35.
- 🟢 **2026-09-02: Rune of Release/Ancient Lockbox real position + grid ref fixed.** Neither NPC
  ever had a `setPos()` call, so both silently defaulted to the shared placeholder position
  (`-495, -9.9/-9.695, -72/-75`). Fixed using real positions cross-confirmed identical across 2
  independent captures (Thris Nov2025 and "Periqia S", both NPCLogger): Rune of Release
  `(-222, -15, -60)`, Ancient Lockbox `(-218, -15, -60)`. Also fixed the completion message's grid
  ref: the wiki confirms real "H-8", but the code passed letter param `8` (which renders as the
  9th letter, "I" -- the exact same off-by-one bug class already found on Building Bridges).
  Corrected to `7` (0-indexed H).
- *(superseded above, 2026-08-18)* Kill-all-38 corrected to kill-all-18 (real capture completed at
  exactly 18 kills). Confirmed real mechanic: Chigoe Breeders genuinely breed/respawn more chigoes
  (7 breeder kills observed vs only 3 static spawn points) -- the exact completion formula (fixed
  count vs. population control) isn't fully disambiguated by one run. Lockbox rewards + Assault
  points (1100) now real.

### Apkallu Seizure (Ilrusi Atoll, mission 46)
**Overall status: 🟢** -- Built 2026-08-23 from a 2nd real capture (a WIN this time). **Not yet live-tested by the user.**
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ **2026-08-23, built**: Kill-all-8 (Kelp Pugil) was wrong, corrected to unhooked/no-op (Kelp
  Pugil are real but ambient, not the objective). Real mechanic is a stealth capture-net minigame
  against 5 real Fairy Apkallu -- a downloaded 2nd capture (Siknawz, a real WIN this time; the
  original Thris capture had ended before a successful catch) revealed the full mechanic: a
  3-tier trust ladder ("staring at you" -> emote -> "let down its guard"/"curious" -> emote ->
  "seems to like you"), auto-capture the instant max trust is reached (no separate player action
  -- confirmed, the real capture text fires "You give the hamsi..."/"You successfully capture..."
  the same second trust maxes, all 3 times), 3 captures = completion (confirmed exactly).
  Discovered along the way that `luautils::OnPlayerEmote` (engine's emote packet handler) already
  exists and is Lua-hookable -- the earlier "no engine precedent" assessment was based on an
  incomplete search. Built as `scripts/globals/apkallu_seizure.lua` (hooks
  `tpz.player.onPlayerEmote`, same pattern as Full Speed Ahead's `tpz.fsa`) since the engine
  passes no target-entity info through the emote packet, so "which NPC" has to be solved via
  proximity in Lua. Real item corrected: earlier header's "cage of Reef fireflies" guess was
  wrong, the real item is "hamsi" (5449), confirmed directly in the WIN capture's own text.
  Documented approximations (not capture-confirmed): no approach-from-behind facing check;
  trust-advancing emotes extended from the 2 directly observed (/bow, /welcome) to a small
  "calm gesture" whitelist; real wariness regression/"runs away" failure states not modeled
  (trust only ever increases -- a deliberate easier-not-harder simplification given ambiguous
  trigger data); hamsi grant cadence approximated as a flat 180s timer. See both files' headers
  for the full writeup.
- ✅ Real Assault points (1098) and lockbox rewards (??? axe + hi-potion_+3 + hi-reraiser)
  confirmed 2026-08-19 from a real Win capture.
- 🟢 **8 zero-position `Kelp_Pugil` mobs fixed 2026-08-25** (ids `17002577`-`17002584`), found via
  a zone-wide sweep and fixed with real positions from `Ilrusi Atoll - Apkallu Seizure (Thris
  Nov2025)`'s PathLog. These are the same "real but ambient, not the objective" Kelp Pugil noted
  above -- data-completeness fix only, doesn't touch the real capture-net mechanic. Not yet
  SQL-reimported or live-tested.
- 🟢 **Clavauert B Chanoix added 2026-08-25** (`17002659`) via the npclogger cross-reference pass
  -- real mission-giver NPC, real position + look byte both captured directly. Not yet
  SQL-reimported or live-tested.

---

## SM (Sergeant Major)

### Azure Experiments (Leujaoam Sanctum, mission 7)
**Overall status: 🟡 -- Corrected 2026-09-02.** The 2026-08-25 🔴 downgrade below ("NPC mapping and
mission logic still need to be built out") is **stale**: re-verified 2026-09-02 against the actual
files -- `instances/azure_experiments.lua` and `npcs/Nareema.lua` (the real 4-successive-graft
completion logic) are both present, complete, and structurally sound, and were already built on
2026-08-18, predating this note. `mob_spawn_points.sql`'s 10 real Lamia (Prosector/Bowyer/Sharper)
all carry real non-zero positions (confirmed 2026-08-25, re-checked 2026-09-02).
`instance_entities.sql` registration clean. Downgraded 🔴->🟡 (built from real data, real open
gaps remain -- see bullets) rather than back to 🟢/✅, since it's genuinely unclear whether the
2026-08-25 note referred to something real that regressed since, or was simply written in error --
flagging for a live playthrough to settle it either way.
- ✅ Entrance approximated 2026-08-18 from real capture Rune of Release position (older capture
  format, no PathLog). Real WIN, 1650 points (10 of 11 mined captures won).
- ✅ Kill-all-10 was completely wrong -- real objective is triggering Nareema (real NPC,
  previously a stub) 4 successive times for "grafts", confirmed exact across all 10 winning
  captures. Built and wired with an estimated ~90s recast cooldown (not precisely confirmed).
  Real Rune of Release/Lockbox staging positions set; Assault points and Lockbox reward
  (??? ring -> hi-potion +3) fixed.
- 🟢 **10 real mob positions pulled in 2026-08-25**, found via a `mob_spawn_points.sql`
  zero-position sweep: `LamiaProsector`/`LamiaBowyer`/`LamiaSharper` (`17059948`-`17059957`, 10
  total) were all sitting at `(0,0,0,0)` despite being real, present entities in this mission --
  initially misjudged as leftover dead weight from the superseded kill-all-10 mechanic, but
  checking all 11 winning captures' NPCLogger data directly showed they appear in every single
  one with exact positions, confirming they're real ambient/ancillary mobs, not unused artifacts.
  Pulled exact x/y/z/rotation from `experiments_1`'s capture (`azure_experiments/experiments_1/
  Grievor/npclogger/database/Leujaoam Sanctum.lua`). Positions only -- their actual role in the
  mission (if any beyond ambient population) is still unconfirmed. Not yet SQL-reimported or
  live-tested.
- ✅ **2026-09-02 content-completeness sweep**: re-confirmed correct, no new fix needed. Rune of
  Release/Ancient Lockbox `setPos()` (already wired 2026-08-18) and all 10 real Lamia mob
  positions re-checked -- all real, non-zero, no gaps. See `Assault_Fix_Log.md`'s
  "Content-completeness sweep" entry for the full writeup. Overall stays 🔴 -- the two already-
  flagged open items (Nareema's ~90s graft-recast estimate, the 10 ambient Lamia's exact role)
  are unchanged.

### Blitzkrieg (Mamool Ja Training Grounds, mission 17)
**Overall status: 🟡** -- **2026-08-30 REBUILT**: the 2026-08-25 position fix below was itself
wrong (a real, previously-unnoticed data-entry error, not a capture gap), and the mission mechanic
was rebuilt from a real user-provided wiki walkthrough cross-checked against a real capture.
**Not yet live-tested by the user** after this rebuild -- do not treat as signed off.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 880 points.
- ✅ **2026-08-30, real bug found: the 2026-08-25 "fix" below packed all 26 Molted mobs into a
  near-straight line at the WRONG location** (X -178 to -180.7, Z 107-134) -- this was the user's
  reported "giant clustered mass" symptom. Re-verified against two independent real captures of
  this exact mission (Thris Nov2025 regular + SM, agree exactly): real positions spread across a
  genuinely different area (X -148 to -155, Z 131-159) with real per-mob variation. All 26
  corrected.
- ✅ **2026-08-30, real false-complete bug**: `onMobDespawn` incremented kill progress on ANY
  despawn (leash included), not just a real kill -- same bug class already fixed elsewhere this
  session. Moved to `onMobDeath`, gated on a real player kill.
- ✅ **2026-08-30, real mechanic rebuild from a wiki walkthrough**: Bluethunder Kaqool Ja and
  Festive Firedrake were previously spawned immediately with everything else and wrongly counted
  toward the 200-kill total. Real mechanic: Bluethunder is a CONDITIONAL bonus NM (spawns if kills
  stay mostly Mamool-type within the first 125, tracked via a real rolling streak) that drops a
  real "Mamook Blackscale Key" (item 2226, confirmed via the capture's own packet data) used to
  free a prisoner (Lumaayu -- real name/dialogue confirmed via dat-extractor, but her real
  npc_list position is unmapped, see below); Festive Firedrake is wave-2-EXCLUSIVE bonus content,
  only spawned after the prisoner is escorted to the (now-revealed) Rune of Release. Neither
  contributes to the 200/300 kill counts. New shared module `mobs/blitzkrieg_common.lua` centralizes
  this. Real dat-extractor-confirmed messages wired in (kill tally every 5, wave 1/2
  advancing/decimated announcements, gate-locked text) -- raw CapLog MesNum labels for two of
  these were also found drifted, same class of bug as elsewhere in this zone.
- 🔴 **Not wired in (missing real data, not fabricated)**: Lumaayu's own npc_list position and id
  -- neither available capture reaches the NE-corner rescue. Full escort script
  (`npcs/Lumaayu.lua`) is built and ready (real dialogue: cage idle barks, greet, follow-nags,
  arrival) but not registered anywhere pending a real `LOGPOS` or fresh capture. Her
  combat-reaction dialogue (real, confirmed) also isn't wired -- unclear if she actually takes
  damage as a real entity.
- 🔴 **New finding, unrelated to this mission's own mechanic**: `mob_spawn_points.sql`'s `poolid`
  for both Bluethunder (27) and Firedrake (28) reference completely unrelated `mob_pools` rows
  (`Abyss_Sahagin`/`Abyss_Worm`) -- wrong family, wrong stats/level, explains a real
  "Impossible to gauge!" seen in the capture. Needs dedicated `mob_pools` rows (real: Lv.78,
  ~3500HP, blue magic skill list for Bluethunder) -- not attempted yet, flagged for a decision.

### Wamoura Farm Raid (Lebros Cavern, mission 27)
**Overall status: ✅** -- User-confirmed complete 2026-09-02.
- ✅ Fully validated 2026-08-18 by a real capture, real WIN. Kill-all-15 and entrance both
  confirmed exactly right. Assault points and Lockbox reward previously had no entry at all
  (silently gave 0/XP+gil only) -- both fixed with real values.
- ✅ **2026-08-25, user-confirmed live**: kill-all-15, Rune of Release, and Lockbox all work as
  intended. Does not block completion.
- 🟡 **2026-08-25, user-reported**: a pathway misregistration -- one location that should be open
  is blocked, one that should be blocked is open. Possible object misalignment/offset. Does not
  impact the ability to complete the mission. Not yet investigated -- need the 2 LOGPOS coordinates
  (the wrongly-blocked spot and the wrongly-open spot) to cross-check against real capture/
  FFXI-DATS data the way Evade and Escape's wall was diagnosed. The zone-wide door-prop audit run
  earlier the same day (see `door_props_only.md`) flagged 9 of this mission's 16 door props as
  NAME-DRIFT, but every one of those already matches FFXI-DATS exactly at its current SQL position
  (`d=0.0`) -- meaning the flagged captures' own id-attribution is what's shifted, not the SQL, so
  none of those should be "fixed" based on that audit alone. This live-reported issue may be a
  real, different bug (an animation/status default, not a name/position one) -- needs real
  coordinates to pin down properly.
- ✅ **2026-08-25, built**: real Ranch Wamoura -> Ranch Wamouracampa maturation mechanic. This
  mission's mob group (zoneid 63, groupid 13) was wired straight to poolid 3319
  (Ranch_Wamouracampa, already-evolved) -- all 15 mobs spawned as the finished moth from the very
  first tick, with no larva stage ever appearing, which is why the user couldn't confirm this was
  working (also confirmed the user has never seen this mechanic work on any other DSP/Topaz server
  either). Repointed to poolid 3318 (larva) in `mob_groups.sql`, renamed the 15 `mob_spawn_points`
  rows accordingly, and built `mobs/Ranch_Wamoura.lua`: an in-place model+name swap (via
  `setModelId`/`setName`, not a full pool respawn) after a timer, resetting on engage to mirror the
  real wild mechanic's "left alone" condition. Adapted from the wild Wamoura Prince -> Wamoura
  maturation (FFXIclopedia: ~1 Vana'diel day unengaged) -- per the user's explicit direction,
  shortened to 2/3 of this mission's 30-minute time limit (20 min) rather than the literal 1
  Vana'diel day, since that wouldn't fit the mission clock. Deliberately cosmetic/behavioral only
  (no HP/level change at maturation) -- no real source confirms Assault-specific larva-vs-moth
  difficulty, and the existing kill-all-15 mechanic already works correctly at the group's current
  stats, so this doesn't risk regressing that. Not yet SQL-reimported or live-tested. Also noted in
  passing: 2 more mob ids in this same group (`17035373`/`17035374`) exist in `mob_spawn_points`
  and are even registered to this instance in `instance_entities`, but aren't referenced anywhere
  in `IDs.lua`'s mob list, so they never actually spawn -- logged to TODO.md, not touched here.
- ✅ **2026-08-27, resolved -- the 2 unwired mob ids above are the real mechanic, not dead rows.**
  User identified them from the FFXI Atlas map: they're the map's cyan "share a spawn (only one
  will spawn)" markers, both at the mission's 2 northernmost branch points -- a deliberate gamble
  mechanic (only one of the two ever spawns per instance, forcing the player to guess which branch
  to check). Wired up: `WAMOURACAMPA_SHARED_SPAWN_27` added to `IDs.lua`, `onInstanceCreated` in
  `wamoura_farm_raid.lua` now randomly spawns exactly one via `math.random(#candidates)`.
  **17035373 (northeast branch) is commented out, not active** -- user confirmed it sits past the
  real pathway-misregistration blocker noted above, so only 17035374 (northwest) is live for now.
  Re-add 17035373 once that corridor blocker is resolved. TODO.md's entry for this removed.
- 🟢 **2026-09-02, user-reported: model/animation state out of sync after maturing.** Same bug
  class found and fixed repeatedly this session for Golden Salvage's Cursed Chest/Mimic --
  `tryMature()` only ever called `setModelId()`, never `setAnimationSub()`, so the moth model
  rendered with whatever pose the larva stage left it at. Real values, straight from this
  codebase's own SQL: `mob_pools` poolid 3318 (Ranch_Wamoura, larva) has `animationsub=0`; poolid
  3319 (Ranch_Wamouracampa, the real evolved-moth pool) has `animationsub=4`. Both now set
  explicitly (larva baseline at `onMobSpawn`, moth value alongside `setModelId()`/`renameEntity()`
  at maturation) in `mobs/Ranch_Wamoura.lua`.
- ✅ **2026-09-02 (later): larva/moth naming and modelid pairing corrected, user-reported live.**
  The real spawn identity is "Ranch_Wamouracampa" (larva), maturing into "Ranch_Wamoura" (moth) --
  backwards from the prior pass. All logic moved to `mobs/Ranch_Wamouracampa.lua` (now the real
  file, old `Ranch_Wamoura.lua` removed -- script resolution is name-keyed, and the real initial
  spawn name is "Ranch_Wamouracampa"). Real modelid/animsub pairing pinned down via live
  observation: larva = modelid 1802/animsub 4, moth = modelid 1808/animsub 0 (both now set
  explicitly at the correct stage). Mobskills also corrected -- `mob_groups` hardcoded a single
  poolid for the whole spawn group, so both stages shared one skill list; `tpz.mobMod.SKILL_LIST`
  now swapped live per stage (skill_list_id 254 larva / 253 moth), same pattern as Balgas Dais's
  Wyrm. Nameplate refresh issue (stale after maturing) fixed via the new `forceRespawn()` engine
  binding.
- ✅ **2026-09-02 (later): pathway misregistration resolved -- 7 real rocks fixed, user-reported
  live one at a time.** `_jr9`/`_jr2`-`_jr8` (Lua aliases `_ir2`-`_ir9`) were all real props
  registered to this instance but sitting at their `npc_list` default `animation=9`
  (CLOSED/impassable) -- same door-prop bug class as this mission's own `_1ro` fix. All now
  explicitly opened in `onInstanceCreated`. This resolves the 2026-08-25 "pathway
  misregistration" report above -- the real cause was several unopened rocks, not a position/name
  mismatch (the door-prop audit's NAME-DRIFT flags were a red herring, as already suspected).
- ✅ **2026-09-02 (later): 3rd northern shared-spawn candidate added, user-supplied real
  `!logpos`.** `17035375` (real id, `mob_groups` id 14 like its siblings, previously a genuine
  `(0,0,0,0)` unset stub) now has a real position and is registered/wired into
  `WAMOURACAMPA_SHARED_SPAWN_27` alongside `17035374` (`17035373` stays excluded, still blocked by
  a separate corridor issue -- unrelated to the rocks above). 2 more ids in the same stub family
  (`17035364`/`17035366`/`17035379`, positions still `(0,0,0,0)`, no real data) were briefly wired
  in as extra always-on larvae per an earlier request, then reverted same day -- user identified
  they're more likely additional real candidates for this same shared-spawn pool, and adding them
  as extras threw off the mission's kill-all-15 balance. Left unwired pending real position data.
- ✅ **2026-09-02 (later): maturation mechanic changed to random, user-directed.** Replaced the
  uniform "every larva matures on an identical timer" design with a random one -- exactly 3 of the
  18 real larvae mature per instance (the 15 always-on + whichever shared-spawn candidate got
  picked), each at a random point within a real 10-minute (600s) window, selected once in
  `onInstanceCreated` right after spawning. Non-chosen larvae never mature this instance by
  design. Combat-engagement delay preserved, rescoped to only the 3 chosen mobs.
- ✅ **2026-09-02, user-confirmed live: PASSED.** All of the above (kill-all-15/Rune/Lockbox,
  maturation naming+modelid+skill-list fix, all 7 rock fixes, 3rd shared-spawn candidate, random
  evolution mechanic) verified working in a real playthrough.

### Defuse the Threat (Periqia, mission 37)
**Overall status: 🟢** -- Built 2026-08-23 from the real capture + dat-extractor text verification. **Not yet live-tested by the user.**
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ **2026-08-23, built**: Kill-all-7 (Qiqirn Miner) confirmed wrong, corrected to unhooked/no-op
  (Miners are ambient guards). Real mechanic is a mine-detector proximity system against 15 real
  Qiqirn Mine entities -- all 15 now have real `npc_list` rows (invisible, `model_id=0`, matching
  the "detect, don't see" mechanic) and are registered to `instance_entities`. Real text confirmed
  via `dat-extractor` (`periqia_6476.json`), correcting a +15 MesNum drift in the raw capture (same
  bug class already found/fixed on Saving Private Ryaaf's dialogue).
  The single available capture only ever observed 10 explosions (irregularly spaced, ~1s to ~8min
  apart, across the full ~16 minute run, completion following immediately after the 10th) -- never
  a successful defuse, despite real client text existing for one ("You defuse the Qiqirn mine!").
  Modeled as an approximation, not a capture-exact reproduction: each mine arms with an
  independent random timer (30-900s, a reasonable fit to the observed spread, not a derived
  formula) and auto-explodes if left alone; a proximity-based defuse-before-it-explodes option
  (walk within 3 yalms of an armed mine) was added as a design fill-in so the real "defuse" text
  isn't dead/unreachable -- not confirmed by data. Either outcome counts toward the real
  capture-confirmed completion threshold of 10. Lockbox rewards + Assault points (952) now real
  regardless.
- 🟢 **7 zero-position `Qiqirn_Miner` mobs fixed 2026-08-25** (ids `17006732`-`17006738`), found
  via a zone-wide sweep and fixed with real positions from `Periqia - Defuse the Threat (Thris
  Nov2025)`'s PathLog. Same "ambient guards" Qiqirn Miner noted above -- data-completeness fix
  only, doesn't touch the real mine-detector mechanic. Not yet SQL-reimported or live-tested.

### Lost and Found (Ilrusi Atoll, mission 47)
**Overall status: 🟡** -- **Upgraded from 🔴 2026-09-02, then corrected same day**: a more
detailed real wiki walkthrough revealed the full mechanic is richer than first modeled (a real
staged Hint-count system, not a direct hot/cold-to-ring signal) -- the real hot/cold cycle itself
is now built, but the stage-1+ ability escalation genuinely can't be built without more real "???"
prop position data than currently exists. See the final bullet below. **Not yet live-tested by the
user.**
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- 🔴 Kill-all-8 (Kelp Kulshedra + Kelp Crab) was wrong -- corrected to unhooked/no-op pending real
  data. Real mechanic is a hot/cold search minigame guided by psychic NPC Tian Tian (proximity
  hints, no confirmed pickup trigger since the capture ended without a successful find).
- ✅ Real Assault points (1650) and lockbox rewards (??? gloves + hi-potion_+2/tank) confirmed
  2026-08-19 from a real Win capture.
- 🟢 **5 of 8 zero-position mobs fixed 2026-08-25** (`Kelp_Kulshedra`, ids `17002585`-`17002589`),
  found via a zone-wide sweep and fixed with real positions from `Ilrusi Atoll - Lost and Found
  (Thris Nov2025)`'s PathLog. 3 remaining (`17002590`-`17002592`, `Kelp_Crab`) have no data in
  either available capture. Same "ambient, not the real mechanic" Kelp Kulshedra/Crab noted above.
  Not yet SQL-reimported or live-tested.
- 🟢 **Tian Tian added 2026-08-25** (`17002671`) via the npclogger cross-reference pass -- the
  psychic hint-giver NPC referenced above, real position + look byte both captured directly.
  Data-completeness only -- the hot/cold hint mechanic itself is still unbuilt. Not yet
  SQL-reimported or live-tested.
- 🟢 **2026-09-02: real win-trigger for "find the ring" found and wired**, from a previously-
  unexplored capture ("Ilrusi Atoll SM - Lost and Found (2)", Giichi) that -- unlike the other 2
  captures for this mission -- covers a full search all the way to a real win. The pickup entity is
  npc_list's shared placeholder `'qm6'` (id `17002672`, real client-visible name "???"): triggering
  it at its real logged position (`-182.053, -4.959, -175.018`) fires "This is it! The Eye of
  Zahak!" and completes the mission immediately, confirmed both by the CapLog text and by
  `RUNE_UNLOCKED_POS`'s real grid ref (`I-9`, also fixed, was the generic `8,8`/H-8 placeholder).
  Registered to `instance_entities` (was never registered at all) and wired via new
  `npcs/qm6.lua` (`instance:complete()` on trigger) + `setPos()` in `lost_and_found.lua`. Rune of
  Release/Ancient Lockbox also given real per-instance positions for the first time (3 agreeing
  sources). Sibling placeholder `'qm7'` (`17002673`) also had a real logged position in the same
  capture but never triggered a win in that run -- left unregistered, role unconfirmed. `Kelp_Crab`
  `17002590`/`17002592` re-checked against all 3 available captures (including the
  newly-reviewed "(2)") -- still no data, remains a genuine open gap. Not yet SQL-reimported or
  live-tested.
- 🟡 **2026-09-02 (later, corrected): real hot/cold proximity-hint cycle built, but the mission's
  full real mechanic is richer than initially modeled.** A much more detailed user-provided wiki
  walkthrough revealed the real design: stage-0 hot/cold guides the player to the nearest of
  several real-world "???" props (which can turn out to be the ring, a Hint, Seaweed, or a Crab),
  NOT the ring directly; only after finding at least 1 real Hint prop does Tian Tian gain new real
  abilities (1 hint = names the nearest party member to the ring, 2 hints = a cardinal direction,
  3 hints = exact yalm distance). Only 2 real "???" prop positions exist in any available capture
  -- `qm6`/17002672 (the ring itself) and `qm7`/17002673 (real position confirmed, but never
  triggered in any capture, so its Hint/Seaweed/Crab outcome is genuinely unconfirmed) -- so the
  stage-1+ ability escalation is NOT built (no confirmed real entity could ever grant hintCount>=1
  with current data; building it now would be unreachable dead code). What IS built and real: the
  3-line WAIT/EXAMINING/TIER hot/cold cycle (5 escalating tiers, all message ids cross-verified
  against `IDs.lua` by TEXT across all 3 captures -- Giichi matches with zero drift, the 2 Thris
  captures share a consistent +14 offset, confirmed line-for-line with zero exceptions), now
  targeting the nearest of the 2 known real props rather than the ring alone. Distance-to-tier yalm
  thresholds remain estimated, not capture-confirmed (no capture has player position data).
  Downgraded back to 🟡 (from a premature 🟢) since the full mechanic isn't actually complete --
  more real "???" prop positions (with confirmed outcomes) would be needed to build stage 1+. Lua-only,
  no SQL reimport needed. Not yet live-tested.

---

## CS (Chief Sergeant)

### Imperial Code (Leujaoam Sanctum, mission 8)
**Overall status: ✅ (2026-08-29) -- user-confirmed complete, full pass, no outstanding issues.**
Real mechanic (from a user-provided wiki walkthrough, replacing the earlier wrong "single-target
Saizo only" model): 3 named NMs (Saizo, Oko, Danzo) must all die; each spawns a shared searchable
"???" body (`npcs/qm0.lua`, repositioned to wherever each one dies), and the OGMA (needed to
unlock the Rune of Release) is always at whichever body died LAST -- examining it completes the
mission. `mobs/Saizo.lua`/`Oko.lua`/`Danzo.lua`: `onMobDeath` gated on a real player kill (was
previously also firing on ANY despawn, a false-complete bug), increments progress, marks the body
with `hasOGMA` only on the 3rd death.
- ✅ Both real `_1x*` door props for this mission (`_1XX`/17060152, `_1XY`/17060153) needed the
  same 2-part fix: `_1XY` was a genuine missing-registration bug (real npc_list row + IDs.lua
  constant existed but was never added to `instance_entities`, so nothing ever spawned there at
  all); both then needed `animation` corrected from 9 to 8 (9 matches this codebase's established
  "open" convention for `_1x`-style props on paper, but empirically left these two specific props
  visually closed/impassable -- 8, grouped with 9 in the same real animation-code reference, is
  the value that actually works for this model).
- ✅ Examining an early (non-final) `???` body used to freeze the player (a bare `return` with no
  response left the client's local interaction lock waiting on an acknowledgment that never came).
  Fixed, and landed on the real confirmed line for it (MesNum 7659, "littered with junk... nothing
  of interest") via a user-provided real dialog table cross-referenced against the actual
  speaker-attributed capture (Thris "Leujaoam Sanctum CS - Imperial Code" CapLog).
- ✅ **Full real dialogue now wired for all 3 NMs**, speaker-attributed from that same capture (not
  guessed from theme): Danzo and Oko previously had zero unique dialogue at all ("none found in
  the real capture" turned out to be wrong) -- both now have a real engage line, a real death
  line, and a real repeated combat taunt; Saizo gained an engage line, a low-HP bark, and an
  ability shout on top of his already-correct death line. One line (7648, "Rinpyotosha!") stays
  explicitly unattributed -- it never actually appears anywhere in the real capture log, so no
  mob file references it.
- ✅ Real Mijin-Gakure-at-20%-HP mechanic (does not kill him, matching the wiki) added to Saizo --
  was genuinely missing (his mob_pools skill list is empty, shared by 114 other pools). Kudagitsune
  (the Bhoot-family member in this mission)'s Perdition move and stun-interruptibility were both
  already correctly present natively, no fix needed. Kusa's true-sight/true-hearing/linking were
  already correct; blind + dark-sleep immunity and bind resistance were missing and added
  (light-based Sleep deliberately left working, per the real mechanic).
- ✅ Combat taunt lines initially fired almost every tick (a flat per-tick probability roll doesn't
  work against however often `onMobFight` actually runs) -- fixed with a real 30s cooldown gate
  for all 3 NMs.
- ✅ Rune of Release/Ancient Lockbox were sitting at the generic Leujaoam Cleansing shared default
  position (this mission never called `setPos()`, unlike every sibling mission in this zone) --
  fixed using the real per-mission override coordinates already sitting as inline SQL comments.
  Completion message's map-grid reference corrected to the real G-8 (was the generic H-8 default).
- ✅ Entrance position fixed 2026-08-18 (real data matched a pre-existing SQL comment exactly).
- ✅ Assault points/lockbox rewards fixed (independent of the mechanic rebuild above).

### Marids in the Mist (Mamool Ja Training Grounds, mission 18)
**Overall status: 🟡** -- 2026-09-02 content-completeness sweep: all 26 real mobs (8 Marid, 3
Chigoe, 15 Breeder/Mahout/Farrier), Zimahd, and the door props near the mission area are correctly
present and registered to instance 18 -- the instance is not empty. The one real content gap fixed
this pass was the Rune of Release/Ancient Lockbox staging position. Core mechanic (temporary-item
capture, see bullet below) is still genuinely unbuilt -- needs an engine feature this codebase
doesn't have, out of scope for a content-completeness pass. **Not yet live-tested by the user.**
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 1466 points.
- 🟡 Kill-all-26 was wrong -- real objective is capturing all 8 Marid with a temporary
  tranquilizer dart item, not combat. Documented in full (real ids/positions/item id) but not
  built -- needs a temporary-item-use hook that doesn't exist in the engine yet. Wrong
  progress-on-death removed from all 5 mob scripts in this mission. Lockbox reward wired in.
  Zimahd (17047840, real mission-giver who hands the player the dart) exists in `npc_list.sql`
  and is registered to instance 18, but has no `npcs/Zimahd.lua` -- no interaction script exists
  yet, consistent with the mechanic being unbuilt.
- ✅ **2026-09-02: `instance_entities.sql` registration re-verified entity-by-entity** against the
  Marids in the Mist capture's NPCLogger, including for the `_1u*` door props near the mission's
  own area whose captured live ids are +1-drifted vs their real `npc_list` id (known zone-wide
  capture-id-offset issue). All 26 mobs, Zimahd, Rune of Release, Ancient Lockbox, and the nearby
  door props are present and correctly registered. `mob_spawn_points.sql` positions for the 8
  Marid are real (non-zero, individually distinct) but each differs from this capture's live
  snapshot by tens of yalms in places (e.g. id 17047724: sql `160.6, 2.25, 238.3` vs capture
  live `272, 14, 236`) -- plausibly normal combat/wander movement rather than a data bug (a single
  live snapshot isn't a reliable "spawn point" source the way a PathLog is), left unchanged rather
  than overwritten from one ambiguous data point. Worth a live check if Marid spawn locations look
  wrong.
- 🟢 **2026-09-02 fix: Rune of Release/Ancient Lockbox staging position.**
  `instances/marids_in_the_mist.lua` never called `setPos()` for this pair, so they defaulted to
  Imperial Treasure Retrieval's shared coordinates (`301, 2, -417` / `299, 2, -420`) -- 500+ yalms
  from this mission's own real spot (this mission's area is around x 150-340, z 140-350). Fixed
  via `setPos()` using the real capture position from this mission's own NPCLogger: Rune of
  Release `(340, 14, 142)`, Ancient Lockbox `(340, 14, 145)`, both dir 192 (same pattern as every
  other Mamool Ja mission). Not yet SQL/live-verified (Lua-only change, no reimport needed).

### Egg Conservation (Lebros Cavern, mission 28)
**Overall status: 🟡** -- Full rebuild 2026-08-25 from a real user-supplied FFXIclopedia
walkthrough. Real objective: kill 15 Qiqirn Eggler total while protecting 8 female Lebros
Apkallu (mission fails if all 8 die). **Not yet SQL-reimported or live-tested.**
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 1246 points.
- ✅ **2026-08-25 CORRECTED**: threshold fixed from the earlier 12-personal-kill estimate to the
  real 15-total-kill objective (user-confirmed exact number), still via continuous respawns from
  the 6 static spawn points (`mobs/Qiqirn_Eggler.lua`). Also fixed a real false-complete bug:
  progress was counted on `onMobDespawn` (fires on ANY despawn, including a leash/reset with no
  real kill), now counted on `onMobDeath`.
- 🟢 **6 zero-position `Qiqirn_Eggler` mobs fixed 2026-08-25 (earlier pass)** (ids
  `17035396`-`17035401`), found via a zone-wide sweep and fixed with real positions from
  `Lebros Cavern - Egg Conservation (Thris Nov2025)`'s PathLog. These already matched both
  captures exactly -- untouched in this rebuild.
- 🟢 **Rhap Nelhah added 2026-08-25** (`17035486`) via the npclogger cross-reference pass -- see
  Apkallu Breeding's entry for the full writeup (shared NPC across 3 missions).
- ✅ **2026-08-25, full rebuild: 16 real Lebros Apkallu added, previously entirely missing.** The
  SQL had an aspirational comment ("ids 17035380-17035395 (Lebros Apkallu) are NPCs") with zero
  backing rows for years of this session's work -- confirmed via 2 independent real captures'
  PathLog + NPCLogger data (positions real; no look/model data was ever captured for them, same
  as other quest-only actors this session). Reused real poolid 197 (`Apkallu`, genuine FFXI
  model/stats) rather than inventing one; level matched to Qiqirn Eggler's own group (77-78) for
  balanced 1:1 combat; `allegiance=1` marks them non-hostile/curable. New `mobs/Lebros_Apkallu.lua`:
  males auto-engage any Qiqirn within 12 yalms via the real `engage()`/`getShortID()` bindings;
  females don't fight, and `instance:fail()` fires if all of them die. Qiqirn now ignore the player
  and engage a live female on spawn, matching the real "ignore you and go straight for the
  Apkallu until attacked" mechanic -- standard hate mechanics should pull a Qiqirn onto the player
  once actually damaged, same as any other mob (unverified live).
  **Male/female split corrected 2026-08-25 (same day), from real data, not guessed**: no
  model/scale field exists in either capture, but NPCLogger's `Flags3` field splits all 16 ids
  into 2 stable groups, confirmed identically by 2 independent captures (CS + Nov2025 Thris):
  `17035380`/`17035387`/`17035388` (Flags3~67502080-112) vs the other 13 (Flags3~67371264-296).
  3-large/13-small fits "larger = male, fewer, aid the fight" vs "smaller = female, many, must be
  protected" far better than the original arbitrary 8/8 alternating placeholder -- replaced it.
  Still not a confirmed "gender" field per se (Flags3 could encode something else that happens to
  correlate), so worth a live sanity check, but this is real evidence, not a guess.
- 🟡 **User-reported 2026-08-25: pathway misregistration** -- one location wrongly blocked, one
  wrongly open. Does not block completion. Checked both real captures and FFXI-DATS for any
  door/wall prop near this room's coordinates (`x` roughly -220..-80, `z` roughly 400..465) and
  found none in either source -- unlike every other door-prop bug fixed this session, there's no
  known object here to register or reposition. Needs live `!checknav` coordinates (the exact
  wrongly-blocked spot and the wrongly-open spot) to diagnose further.
- 🟢 **Real bug found and fixed 2026-09-02, during Apkallu Breeding's content sweep**: the 16 real
  Lebros Apkallu (`17035380`-`395`) built 2026-08-25 above were never actually registered to
  instance 28 in `instance_entities.sql` at all -- the 2026-08-29 pass (see Apkallu Breeding's
  entry) had moved them to instance 26 by mistake instead, so they have never spawned in Egg
  Conservation. Also, `mobs/Lebros_Apkallu.lua` and `mobs/Qiqirn_Eggler.lua` read them as flat
  `ID.npc.LEBROS_APKALLU_*` keys, but that same 2026-08-29 pass nested the constants inside
  `IDs.lua`'s `npc[26]` sub-table -- every reference has been resolving to `nil` since, meaning
  `isMale()` always returned false and the female-protection/male-engage AI never actually ran
  even when the mobs did spawn. Fixed: moved the 16 ids back to instance 28 in
  `instance_entities.sql`, and flattened the `LEBROS_APKALLU_*` constants back to top-level in
  `IDs.lua` (matching how the consuming scripts read them). Not yet SQL-reimported or live-tested.

### Operation: Snake Eyes (Periqia, mission 38)
**Overall status: 🟢** -- Built and believed correct from real capture data. **Not yet live-tested by the user** -- do not treat as signed off.
- ✅ **2026-08-30, real Wide Scan fix**: user-directed -- `Merrow_No16` excluded from widescan while
  staying named/targetable, same new `wideScanHidden` localVar mechanism as Shanarha Grass
  Conservation's Coney and Shooting Down the Baron's Black Baron (real C++ addition,
  `src/map/entities/baseentity.cpp`). `mob_pools`' `namevis=0` already didn't hide the name, so no
  SQL change was needed here, only the Lua-side localVar.
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ Real Assault points (2198) and lockbox rewards (??? necklace + hi-potion_+3/tank) confirmed
  2026-08-19 from a real Win capture (previous loss-only capture couldn't confirm the kill-all-15
  mechanic or rewards). Kill-all-15 mechanic itself still not independently re-verified against
  named-mob kill counts in the winning capture.
- 🟢 **15 zero-position mobs fixed 2026-08-25** (`Qutrub`/`Merrow_Shadowdancer`/`Merrow_No16`/
  `Karazahm`/`Lamia_No14`/`Umarid`/`Lamia_No17`, ids `17006739`-`17006753`), found via a zone-wide
  sweep and fixed with real positions from `Periqia - Operation Snake Eyes (Thris Nov2025)`'s
  PathLog. Not yet SQL-reimported or live-tested.

### Deserter (Ilrusi Atoll, mission 48)
**Overall status: 🟡** -- Built, but a real open gap/uncertainty remains (see bullets below). **Not yet live-tested by the user.**
- ✅ Entrance position fixed 2026-08-18 (real data matched a pre-existing SQL comment exactly).
- ✅ Kill-all-22 corrected to kill-any-5-named-agents (the 10 generic Draugar don't count; the 12
  codenamed Lamia/Merrow "agents" do). Threshold of 5 is the cleanest read of one successful
  capture, not fully disambiguated from "1 each of 5 specific identities." Lockbox rewards +
  Assault points (952) now real.

---

## SL (Second Lieutenant)

### Red versus Blue (Leujaoam Sanctum, mission 9)
**Overall status: 🟡** -- Built, but a real open gap/uncertainty remains (see bullets below). **Not yet live-tested by the user.**
- 🔴 **User-reported 2026-08-25**: 2 ice wall blockers, `!navdebug`-confirmed no helper object at
  `-86.5412,-3.5000,100.2507`. Nearest real client props (`FFXI-DATS`): `_1xh` (dist 6.10, already
  present in `npc_list` at fixed full precision) and, for the 2nd blocker
  (`32.8687,-3.5406,20.2432`), `_1xj` (dist 6.21, also already present/fixed). Both are farther off
  than the sub-2-unit matches seen elsewhere in this zone -- likely just normal
  standing-near-the-wall offset rather than a data bug, but not confirmed either way. **Zone-wide
  context**: confirmed 10 of 56 real door/object props in all of Leujaoam Sanctum have zero
  matching `npc_list` row at all (`_1x2`/`_1x9`/`_1xf`/`_1xp`/`_1xs`/`_1xt`/`_1xx`/`_jx9`/`_jxc`/
  `_jxj`) -- a real, systematic gap across the zone, not isolated to Imperial Code's `_1xx` case.
  Needs a real investigation pass (likely adding missing rows), not another position-drift fix.
- ✅ Entrance position fixed 2026-08-18.
- ✅ Real Assault points (2198) and lockbox rewards (??? earring + hi-potion_+3) confirmed
  2026-08-19 from a real Win capture (previous loss-only capture couldn't confirm rewards).
- 🟡 Root cause found, not wired in: Raubahn is sleepable, ~12 other named mobs in this mission
  are confirmed Sleep-immune (real capture data). No `mob_pools` rows exist yet for any of these
  mobs to encode the immunity split.
- 🔴 Completion condition (kill-all-27 vs. single-target Raubahn) still not fully disambiguated --
  the winning capture didn't clearly resolve this either.

### Azure Ailments (Mamool Ja Training Grounds, mission 19)
**Overall status: 🟡** -- Built, but a real open gap/uncertainty remains (see bullets below). **Not yet live-tested by the user.**
- ✅ Entrance approximated 2026-08-18 from a real 2023 capture's Rune of Release position (no
  PathLog for exact player position in this older capture format).
- ✅ Kill-all-62 was completely wrong -- real objective is getting afflicted by 3 of 7 specific
  debuffs and reporting to Garjham (real mission-giver NPC, previously a stub). Built and wired:
  Garjham checks the player's current status effects on trigger, tracks distinct ailments seen,
  completes at 3. The 62 real mobs are ambient disease vectors, not kill targets.
- 🔴 **CORRECTION 2026-08-18**: an earlier "1200 real points" entry here was wrong -- misread a
  `RUNE_UNLOCKED_POS` packet as the points message while hand-decoding a raw capture. Reverted;
  Assault points remain genuinely unconfirmed (0) pending a real capture that actually reaches the
  points-award packet.
- ✅ **User-provided 2026-08-19**: real lockbox reward data received (previously fully missing,
  flagged in the missing-rewards audit). qItems ??? Box / ??? Earring / ??? Sash (equal-split, no
  odds given); regItems Hi-Ether Tank, Hi-Potion +3, Hi-Reraiser, Hi-Potion Tank. Wired into
  `Mamool_Ja_Training_Grounds/npcs/Ancient_Lockbox.lua`.
- 🟢 **53 of 62 zero-position "ambient disease vector" mobs fixed 2026-08-25** (`Mamool_Ja_Warder`/
  `Pit_Lindwurm`/`Bugard`/`Poroggo`/`Huge_Spider`/`Leech`/`Slavering_Lizard`/`Qiqirn_Huckster`,
  ids `17047744`-`17047805`), found via a zone-wide sweep and fixed with real positions pulled
  from both available captures (`Mamool Ja Training Grounds SL - Azure Ailments`, 37 mobs, and
  its `(Wiggo, Win, Duo)` variant, 16 more). **9 remaining with no data in either capture**:
  `17047766`/`17047767`/`17047770`-`17047773` (`Poroggo`), `17047782`/`17047783` (`Leech`), and
  `17047804` (`Qiqirn_Huckster`). Not yet SQL-reimported or live-tested.

### Operation: Black Pearl (Lebros Cavern, mission 29)
**Overall status: 🟢** -- Built and believed correct from real capture data. **Not yet live-tested by the user** -- do not treat as signed off.
- ✅ Entrance position fixed 2026-08-18.
- ✅ Real engine bug fixed: a duplicate `[29] = {}` table key in `IDs.lua` was silently zeroing
  the mission's entire mob list (Lua last-key-wins) -- was spawning ZERO mobs before this fix.
- ✅ Kill-all-25 corrected to single boss kill (Jorporbor the Hellraker). Lockbox rewards +
  Assault points fixed. 3 new NPCs (Kadjaya + 2 guards) added with real positions.
- ⚠️ **2026-08-30, flagged not applied**: a Wide Scan cleanup request named "Black Baron" as this
  mission's target for the new `wideScanHidden` mechanism -- no such mob exists anywhere in this
  zone or mission (its real boss is Jorporbor the Hellraker, above; Black Baron is Periqia's own
  separate NM from Shooting Down the Baron). Likely a cross-mission mix-up in the request -- not
  applied here pending clarification of which real mob was actually meant.
- 🔴 Kadjaya/Whyjham's post-fight dialogue lines aren't wired in (cosmetic, mission completes
  fine without them).
- 🟢 **All 65 zero-position mobs fixed 2026-08-25** (`Troll_Combatant`/`Wamouracampa`/
  `Poroggo`/`Huge_Spider`/`Leech`/`Slavering_Lizard`/`Qiqirn_Huckster`/`Vulcanian_Bomb`, ids
  `17035402`-`17035466`), found via a zone-wide sweep and fixed with real positions from `Lebros
  Cavern SL - Operation Black Pearl`'s PathLog. This is the largest single fix from this pass --
  worth noting alongside the duplicate-`IDs.lua`-key bug above, since a mission that was
  "spawning ZERO mobs" for one reason could easily have masked this position gap too; both are
  now resolved. Not yet SQL-reimported or live-tested.
- 🟢 **Rhap Nelhah added 2026-08-25** (`17035485`) via the npclogger cross-reference pass -- see
  Apkallu Breeding's entry for the full writeup (shared NPC across 3 missions).

### Wake the Puppet (Periqia, mission 39)
**Overall status: 🟢** -- Built 2026-08-23 from a user-provided walkthrough + 3 real captures, cross-confirmed against official client text. **Not yet live-tested by the user.**
- ✅ **2026-08-22, found while investigating a Saving Private Ryaaf user report**: one `Bridge_Switch`
  (17006817, real content for Building Bridges, instance 35) was also stray-registered here via
  the same 2026-08-21 cross-reference pipeline batch mistake. Zero references anywhere in
  `wake_the_puppet.lua`. Removed the stray registration.
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ Real Assault points (1650) and lockbox rewards (??? box + hi-potion_+3/tank) confirmed
  2026-08-19 from a real Win capture.
- ✅ **2026-08-23, built**: Kill-all-31 (Wight) confirmed wrong, corrected to unhooked/no-op. Real
  mechanic is a command/emote-response system: retrieve at least 4 of 6 "Mark-II" puppet
  automatons ("Maymun") by activating one (`/salute`), leading it back to Adeeha (`/clap` every
  few steps, no auto-follow), optionally engaging Wights with it (`/hurray`), and deactivating it
  near Adeeha (`/goodbye`). While active, a Maymun periodically performs 1 of 12 gestures and
  repeats it until answered with the matching emote. The full command list and all 12
  gesture->response pairs were independently cross-confirmed **word-for-word** against Adeeha's
  own in-game help dialogue via `dat-extractor` (`periqia_6476.json`, indices 7626-7642) -- the
  most solidly-confirmed data of any mission built this session, official client text rather than
  inferred from gameplay logs. Also found while researching this: `luautils::OnPlayerEmote`
  (discovered building Apkallu Seizure earlier this session) is the right hook again here --
  earlier session note "needs an emote-response state machine this codebase has no precedent for"
  is now resolved. Built as `scripts/globals/wake_the_puppet.lua` (same
  hook-`tpz.player.onPlayerEmote` pattern as Full Speed Ahead/Apkallu Seizure).
  Real data: 3 independent captures (Thris, Siknawz x2 including a real WIN) together cover real
  positions for all 6 Maymun (spanning 3 distinct room-cluster pairs -- "the four rooms at the
  edges of the map") and 28 of 31 Wight (3 unconfirmed placeholder estimates, interpolated near
  real neighbors) -- all were `(0,0,0,0)` placeholders before this pass. Wights are now hidden at
  spawn (`mobs/Wight.lua`), revealed 4-nearest-to-activated-Maymun on `/salute` (real mechanic:
  "they pop only in areas specific to where you activate an automaton").
  Documented approximations (not capture-confirmed): no penalty modeled for a wrong/unanswered
  gesture (deliberately easier, not harder, same approach as Apkallu Seizure); `/goodbye`
  progress-counting is gated on proximity to Adeeha (inferred from the WIN capture's pattern, not
  separately confirmed against a delivery-elsewhere case).

### Desperately Seeking Cephalopods (Ilrusi Atoll, mission 49)
**Overall status: 🔴** -- Core mechanic still wrong, unbuilt, or a known-broken scaffold (see bullets below). **Not yet live-tested by the user.**
- ✅ Entrance position fixed 2026-08-18 (real data matched a pre-existing SQL comment except a
  y-sign transcription error).
- 🔴 Kill-all-30 (Qiqirn Pecheur) confirmed wrong -- corrected to unhooked/no-op. Real mechanic
  is a fishing-encounter system (repeated random "fished" mob fights until hooking an Orobon
  containing the ahtapot) that this codebase has no Assault-instance fishing hooks for yet. The
  original build's judgment to leave the fished mobs unspawned was correct. Lockbox rewards +
  Assault points (1100) now real regardless.
- 🟢 **2026-09-02: data-completeness re-audit**, cross-checking a 2nd real WIN capture ("Ilrusi
  Atoll SL - Desperately Seeking Cephalopods", Thris) against the original -- re-confirms the same
  fishing-encounter mechanic (real MesNum 7661, "You find an ahtapot in the belly of the Orobon!",
  fires mid-fight; killing that Orobon completes the mission) and the same 1100 Assault points. All
  30 Qiqirn Pecheur, the 6 "fished" mob placeholders, and the door props are confirmed intact/
  correctly left unspawned where appropriate; the fishing-encounter engine gap itself is unchanged
  and stays out of scope this pass. Fixed real per-instance Rune of Release/Ancient Lockbox
  positions (were sitting at the shared zone-default, same gap already found in 4+ other Ilrusi
  Atoll missions this session) and the real grid ref (`G-9`, was the generic `8,8`/H-8 placeholder)
  via `setPos()`/`messageSpecial()` in `desperately_seeking_cephalopods.lua`. Also found 3 real
  named flavor NPCs sitting fully positioned in `npc_list.sql` and already registered to this
  instance but never referenced anywhere in the build: Ulbuun ("Captain Ulbuun of the 41st
  Fighting Beavers", mission-giver, real greeting text via CSID 55 in the CapLog, fires MesNum 7630
  "A fine specimen!" on a successful catch) and rival hunters Walagarim/Bhjaama (1-line
  fishing-luck barks, e.g. MesNum 7634 "Damn... Nothin'..." on a failed catch). Added to `IDs.lua`
  for whenever the fishing system gets built -- the CS-event flow itself wasn't decompiled this
  pass, so they're documented, not wired. Not yet SQL-reimported or live-tested.

---

## FL (First Lieutenant)

### Bloody Rondo (Leujaoam Sanctum, mission 10)
**Overall status: 🔴 -- Corrected again 2026-08-25 (later).** Door-prop and static-position gaps
below are genuinely resolved, but **the user then clarified the real mechanic** (via
[ffxiclopedia](https://ffxiclopedia.fandom.com/wiki/Count_Dracula)): Count Dracula has 7 real TP
moves, and `Cursed_Doppelganger` isn't a static spawn at all -- it's **dynamically summoned by his
"Nosferatu's Kiss" TP move as a live copy of whichever player currently has the most hate**,
inheriting their equipment, food, and buffs (shadows/Protect/Shell/etc.), and slightly boosted in
power. The `mob_spawn_points.sql` position fixed below is real capture data but **not the actual
fix** -- it's just wherever the doppelganger happened to be summoned during that one engagement
(near Dracula, since that's where the fight was), not a meaningful "spawn point." Checked and
confirmed **zero TP moves are implemented anywhere**: `Count_Dracula.lua` is a bare kill-counter
stub, and `mob_skill_lists` has no rows at all for his skill list (id `252`). No precedent exists
anywhere in this codebase for a mob that clones a player's live equipment/buffs -- this may need
new engine-level Lua API support, not just a script, and is a real, substantial build, not a quick
fix. **2026-09-02: confirmed and scoped further, deferred by user direction -- full writeup at
`documentation/research/Cursed_Doppelganger_Mechanic_Research.md`** (real mechanic re-confirmed
directly from the wiki, plus a real check of Topaz's own C++ confirming `setModelId()`'s per-slot
gear logic is hard-gated to `TYPE_PC` only -- mobs can't currently receive a composite
race+gear look via Lua at all, a genuine engine gap, not just an unwritten script). Real 7-move
list (from the wiki, for whoever builds this):
- **Nocturnal Servitude** -- conal Charm + turns targets into bats; sleepable/bindable
  (Repose/Lullaby/Sheep Song/Yawn)
- **Wings of Gehenna** -- AoE damage, removes shadows, knockback + stun
- **Decollation** -- physical damage
- **Bloodrake** -- single-target large HP drain, absorbable by shadows
- **Heliovoid** -- AoE status-effect drain (removes 1 buff from all affected)
- **Eternal Damnation** -- gaze Doom (no effect if target's back is turned); Cursna/Holy Water cures
- **Nosferatu's Kiss** -- AoE drain (~300) + TP drain + summons `Cursed_Doppelganger` as described
  above; stunnable
- 🟢 **Full zone door-prop data completed 2026-08-25**: confirmed and added the last 10 missing
  real props for the whole zone (3 reactivated from pre-existing `NOT_CAPTURED` reserved slots --
  `17060121`→`_1x2`, `17060147`→`_1xs`, `17060148`→`_1xt` -- and 7 new rows added at
  `17060177`-`17060183` for `_1x9`/`_1xf`/`_1xp`/`_1xx`/`_jx9`/`_jxc`/`_jxj`, using real positions
  from `FFXI-DATS`). **Zone 69 now has all 56 real door/object props represented in `npc_list.sql`
  -- 100% coverage**, up from 46/56 before this session. See `npc_list.sql` around these ids for
  the added rows.
- ✅ **Door-prop registration resolved with real data, 2026-08-25**: initially registered the full
  56-prop set to instance 10 as a safety net (no capture had been checked yet). Then cross-checked
  against the real `Leujaoam Sanctum FL - Bloody Rondo` capture's player PathLog (49-point path,
  entrance `424,-341` straight to Dracula `~499,-298`) -- nearest door prop was 186 units away, an
  order of magnitude farther than any real match seen elsewhere in this zone. Independently
  confirmed with the 2 new user-supplied captures: zero of the 56 door prop ids appear anywhere in
  the Wiggo capture's full packet log either. **Two independent real data sources agree this
  mission's actual path needs none of the shared zone doors** -- removed the blanket registration
  entirely rather than leave 56 unnecessary rows in place.
- ✅ **`Cursed_Doppelganger` (17060012) real position found and fixed, 2026-08-25** -- user
  supplied 2 new captures (`Assault - LS - FL - Bloody Rondo [W]` and `Wiggo Captures FFXI -
  Assault - Bloody Rondo(Win)`). The `[W]` capture, like the original one, shows zero
  Doppelganger appearance across its full CapLog. But the **Wiggo capture's raw packet log
  (`PacketViewer/incoming/0x00E.log`) directly confirms npc id `17060012` spawning, engaged,
  `Status: 1`** -- real, if conditional/rare (2 of 3 available captures show no appearance at
  all). Position: `X=495.734, Y=4.554, Z=-300.302, rot=150` -- decoded by cross-checking against
  `Count_Dracula`'s already-confirmed-real position (`499, 4.563, -298`): they're right next to
  each other, which resolved a packet-field-labeling ambiguity (the raw packet's own "Y"/"Z"
  labels don't match this SQL's X/Y/Z convention -- the packet's large horizontal value is SQL's
  `Z`, its small vertical value is SQL's `Y`). Fixed in `mob_spawn_points.sql`. This also upgrades
  the earlier "possibly a decoy/illusion that only appears under some condition, unconfirmed"
  theory from speculation to confirmed -- the trigger condition itself is still unknown. Not yet
  SQL-reimported or live-tested.
- ✅ Entrance position fixed 2026-08-18 (real data matched a pre-existing SQL comment exactly) --
  not re-verified this pass, may also need a fresh look given how wrong other "believed correct"
  claims in this zone turned out to be.
- ✅ Kill-all-2 corrected to kill-all-1 (Count Dracula only) -- same caveat as above.
- **Not yet SQL-reimported or live-tested.** Run `py -3 dbtool.py` from `C:\topaz\tools` and
  restart the map-server before testing.

### The Susanoo Shuffle (Mamool Ja Training Grounds, mission 20)
**Overall status: 🟢** -- Built and believed correct from real capture data. **Not yet live-tested by the user** -- do not treat as signed off.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 1650 points.
- ✅ Kill-1 (Orochi) already correct, validated by capture. Lockbox reward wired in.

### Better Than One (Lebros Cavern, mission 30)
**Overall status: 🟢** -- Built and believed correct from real capture data. **Not yet live-tested by the user** -- do not treat as signed off.
- ✅ Entrance position fixed 2026-08-18 (real capture PathLog data). Real WIN, 1650 points.
- ✅ Kill-1 (Black Shuck) already correct, validated by capture. Lockbox reward wired in.
- 🟢 **6 zero-position `Nocuous_Inferno` mobs fixed 2026-08-25** (ids `17035471`-`17035476`),
  found via a zone-wide sweep and fixed with real positions from `Lebros Cavern FL - Better Than
  One (Thris)`'s PathLog. Not yet SQL-reimported or live-tested.

### The Price is Right (Periqia, mission 40)
**Overall status: 🟢** -- Built and believed correct from real capture data. **Not yet live-tested by the user** -- do not treat as signed off.
- ✅ Entrance position fixed 2026-08-18 (was on the shared placeholder).
- ✅ Kill-1 mechanic (King Goldemar) already correct. Lockbox rewards + Assault points (1650) now
  real.
- ✅ **1 zero-position mob resolved 2026-09-01** (`17006802`, `Bloody_Daggers`) -- originally
  found via a zone-wide sweep with no PathLog data in the one combined multi-mission capture
  checked at the time. A later sweep found 2 real dedicated single-mission captures that had been
  overlooked; fixed in `mob_spawn_points.sql` to `(371.000, -2.000, 83.000, 236)`. Not yet
  live-tested by the user.

### Bellerophon's Bliss (Ilrusi Atoll, mission 50)
**Overall status: 🟢** -- Built and believed correct from real capture data. **Not yet live-tested by the user** -- do not treat as signed off.
- ✅ Entrance position fixed 2026-08-18 (real data matched a pre-existing SQL comment except its
  y value).
- ✅ Kill-1 mechanic (Khimaira 14X) already correct. Lockbox rewards + Assault points (1650) now
  real.

---

## Cross-cutting notes (not mission-specific)

**🟢 FIXED 2026-08-20: 26 of 50 missions were calling `RUNE_UNLOCKED` (no params) with
`RUNE_UNLOCKED_POS`'s param shape, silently dropping the grid position from the rune-unlock
message.** User-reported on Sagelord Elimination ("rune of release text does not include the POS")
-- checked the whole codebase rather than fixing just that one mission, and found the identical
bug in 25 others across all 5 zones. `RUNE_UNLOCKED` (no bracket placeholder, takes 0 params) and
`RUNE_UNLOCKED_POS` (takes a 0-based letter index + number) are separate message ids in every
zone's `IDs.lua` -- these 26 missions were calling the wrong one with the right one's params,
same class of bug already caught and fixed individually on Excavation Duty and Lebros Supplies
earlier this session. Fixed by swapping the constant (params left as-is) in all 26:
`apkallu_seizure`/`bellerophons_bliss`/`demolition_duty`/`deserter`/
`desperately_seeking_cephalopods`/`lost_and_found`/`searat_salvation` (Ilrusi Atoll),
`troll_fugitives`/`wamoura_farm_raid` (Lebros Cavern), `escort_professor_chanoix`/
`shanarha_grass_conservation` (Leujaoam Sanctum), `azure_ailments`/`blitzkrieg`/
`breaking_morale`/`imperial_treasure_retrieval`/`marids_in_the_mist`/`sagelord_elimination`/
`the_double_agent`/`the_susanoo_shuffle` (Mamool Ja Training Grounds), `building_bridges`/
`defuse_the_threat`/`operation_snake_eyes`/`saving_private_ryaaf`/`shooting_down_the_baron`/
`stop_the_bloodshed`/`the_price_is_right`/`wake_the_puppet` (Periqia). Only Preemptive Strike and
Imperial Agent Rescue (both Mamool Ja) already used the right constant.

**Caveat, not yet resolved**: the actual grid letter/number params passed (mostly `8, 8`, a few
`7, 8`) were **not independently re-verified against real capture data per mission** -- they were
carried over as-is from whatever was already there, which itself looks like a copy-pasted
placeholder value repeated across missions rather than confirmed per-mission real data (no fix-log
entry exists documenting a real capture-verified grid for any of these). So the rune-unlock message
will now show *some* grid position on all 26, but the exact letter/number shown may not be
retail-accurate for most of them -- confirming that needs a real capture or wiki source per
mission, not done here. This fix only addresses the reported symptom (position missing entirely).

**🟢 RESOLVED 2026-08-20: the day-long door/gate/wall "impassable when it shouldn't be" bug across
4 missions (Lamia No.13, Imperial Agent Rescue's Dilapidated Gates, Orichalcum Survey's `_1XO`,
Excavation Duty's Brittle Rock walls) was a client-side addon, not a server bug.** The user found
it directly: **Gateway**, an Ashita launcher addon, forces *all* door/wall/animation states to
render as open on the tester's own client regardless of what the server sends. This explains why
an entire day of server-side investigation -- navmesh queries, dup-entity theories,
animation-field testing, `SpawnNPCList` staleness, packet-type checks -- never produced a single
visible change during live testing: the client was overriding the render either way. **The fix is
client-side: disable/configure Gateway so it stops forcing animation states open.** No further
server-side action is needed for this symptom.

An earlier same-day theory (`!warpassault`'s `setInstance()` leaving `SpawnNPCList` etc. stale
after a same-zone instance transition) was a real, well-reasoned mechanism and was fixed
(`SpawnNPCList.clear()` etc. added to `setInstance()`), but the user's live retesting disproved it
as the cause of *this* symptom -- the bug persisted after that fix, clean recompile, and fresh
`!warpassault` session. The fix was kept (it's a real, valid improvement to a genuine but unrelated
staleness case) but should not be cited as the door-bug fix; see the correction entry in
`Assault_Fix_Log.md` (search "CORRECTION: the actual root cause was client-side").

Following this, Excavation Duty's Brittle Rock 4/5 were restored to the simple pattern matching
rocks 1-3 (commit `478eb89f65`) -- see that mission's section below.

**Capture-mining coverage**: all 50 Assault missions across all 5 zones have now had at least one
real capture mined as of 2026-08-18/19. Every zone reached "fully audited" status at some point
during this session (see `Assault_Fix_Log.md`'s milestone entries for exact dates per zone).
Missions still missing real Assault points/lockbox data are called out individually in their own
entry above (search this file for "still 0" / "unconfirmed" / "falls through").

**Engine dependency -- `object:takeDamage()` Lua hook**: Imperial Agent Rescue (PSC, Mamool Ja
Training Grounds, mission 11) and Excavation Duty (PSC, Lebros Cavern, mission 21) both rely on
this hook for splash damage and instant-kill mechanics respectively. See
[`Dependency_takeDamage_LuaHook.md`](Dependency_takeDamage_LuaHook.md) for what it does, where it
lives in this codebase, and what porting it to another DSP-lineage fork would take (raised
2026-08-19 after a DSP-fork dev reported not having it exposed).

**Systemic gap -- Ancient Lockbox "???" items were never probabilistic, anywhere**: user provided
real mechanics confirming the "???" item from any Ancient Lockbox is not guaranteed (a fixed
per-mission drop rate, real value **50%**) and requires the recommended-level gate -- every
lockbox script in this codebase has given its "???" item at a guaranteed 100% this whole session,
with the level-gate missing entirely outside Leujaoam Sanctum's mission-1 branch (now fixed
there). Both `scripts/zones/Leujaoam_Sanctum/npcs/Ancient_Lockbox.lua` and the shared
`scripts/globals/assault_lockbox.lua` (covers Lebros Cavern/Mamool Ja Training Grounds/Periqia/
Ilrusi Atoll, since all of those delegate to it) now have an identical
`QITEM_DROP_CHANCE_PCT = 100` constant with a comment noting the real value is 50 -- **currently
left at 100 (guaranteed) at the user's explicit request**, for easier live testing while other
mechanics are still being verified. Change both to 50 (one line each) whenever real probabilistic
drops are wanted -- this deliberately avoids silently changing already-signed-off missions'
(Preemptive Strike, Requiem) loot behavior without being asked. See `Assault_Fix_Log.md` for the
full writeup.

---

## How to use this file

When a new capture gets mined or a user report comes in:
1. Find (or add) the rank section, then the mission subsection (missions are listed in mission-id
   order within each rank, following the zone order: Leujaoam Sanctum, Mamool Ja Training Grounds,
   Lebros Cavern, Periqia, Ilrusi Atoll).
2. Add/update the bullet with today's date and a 🔴/🟡/🟢/✅ status marker.
3. Cross-link to `Assault_Fix_Log.md` for anything with a real investigation writeup -- this file
   stays terse (what's wrong, one-line root cause if known), the fix log carries the full story.
4. When something gets fixed, flip its marker (don't delete the line -- keep the history of what
   was wrong so a regression is easy to recognize).
