# WotG Mission 25 Branching Dependency Proof

## Scope

This proof case covers Wings of the Goddess Mission 25, **The Will of the World**, and the nation-quest gate required before Mission 26, **Fate in Haze**.

Primary reference pages:

- FFXIclopedia: The Will of the World
- FFXIclopedia: Beneath the Mask
- FFXIclopedia: What Price Loyalty
- branch references for Songbirds in a Snowstorm, Blood of Heroes, Sins of the Mothers, and Howl from the Heavens

Machine-readable truth set:

`test_fixtures/fixtures/wotg25_branching_mission_truth.json`

Source baseline:

`LandSandBoat/server@3747feee0e38ab5c0283c4fe8deea7f0a9022351`

## Why this is a different stress test

The earlier Medusa/Coiler/Heat Seeker cases are dominated by entity, runtime, item, and acquisition closure.

This mission is primarily a **state-machine and content-routing problem**.

Correct behavior depends on:

- current mission;
- completed prerequisite quests;
- campaign allegiance/nation;
- quest state variables;
- zone transitions;
- exact NPC/entity presence;
- zone-scoped events/CSIDs;
- event parameters;
- onEventUpdate branches;
- onEventFinish state changes;
- key-item grant/use/removal/reissue;
- item trades;
- dialogue/default-event fallbacks;
- waits/timers;
- battlefield/instance availability;
- alternate nation quest chains.

A package containing only the top-level mission Lua would be essentially useless.

## Top-level mission

`25_The_Will_of_the_World.lua` is deceptively small:

```text
Southern San d'Oria (S)
  Raustigne
    event 149
      parameters include campaign allegiance
        ↓
      mission complete
        ↓
      Fate in Haze
```

If dependency discovery stopped there, it would conclude this is nearly trivial.

It is not.

Mission 26 loads `scripts/missions/wotg/helpers.lua`, and its section is gated by:

`xi.wotg.helpers.meetsMission26Reqs(player)`

That helper accepts completion of any one of:

- What Price Loyalty — Bastok
- Blood of Heroes — San d'Oria
- Howl from the Heavens — Windurst

This is an **OR branch**, not three simultaneous prerequisites.

## Bastok branch

### Beneath the Mask

Prerequisites:

- Honor Under Fire completed;
- current WotG mission at least Fate in Haze.

The quest uses at least these actor/event surfaces:

```text
Bastok Markets (S)
  Gentle Tiger
    345, 351, 346, 352, 347, 353

Beadeaux (S)
  zone-in event 1

The Eldieme Necropolis (S)
  Red Axe
    42, 44, 43, 45

Vunkerl Inlet (S)
  Leadavox
    event 2

Beaucedine Glacier (S)
  Hoarfang
    event 7
```

It also requires:

- Beeswax trade;
- Red Textile Dye trade;
- Wax Seal key item;
- Wax Seal grant;
- Wax Seal requirement;
- Wax Seal removal;
- quest variable `Prog` transitions 0→6;
- Super Reraiser reward.

This demonstrates why a key item cannot be modeled as simply "referenced."

Its role is temporal:

```text
Leadavox
  gives Wax Seal
      ↓
quest Prog 4 requires Wax Seal
      ↓
Red Axe consumes/removes Wax Seal
```

Those are three distinct relationship types.

### What Price Loyalty

Prerequisite:

- Beneath the Mask completed;
- current WotG mission at least Fate in Haze.

Actor/event surface:

```text
Bastok Markets (S)
  Gentle Tiger
    348, 354, 349, 355, 357, 350, 356

North Gustaberg (S)
  Roderich
    10, 11

Xarcabard (S)
  zone-in
    8, 10

Xarcabard (S)
  Forbidding Portal
    9

Everbloom Hollow
  instance event 10000
```

Key-item lifecycle:

```text
Sack of Victuals
  given by Gentle Tiger
  required for Roderich step
  removed after Roderich event

Commander's Endorsement
  granted on Xarcabard zone-in
  required for portal/battle progress
  can be reissued by Gentle Tiger
```

The quest also carries an explicit implementation warning:

> the What Price Loyalty instance is not implemented currently.

The existing script uses event 10000 as a placeholder to advance `Prog` to 5 and return the player to Xarcabard.

That must become:

`IMPLEMENTATION_GAP`

not:

`COMPLETE`

## San d'Oria branch

The branch exists in current source:

- `WOTG_SAN_9_Songbirds_in_a_Snowstorm.lua`
- `WOTG_SAN_10_Blood_of_Heroes.lua`

This branch immediately shows different dependency types from Bastok.

Songbirds includes:

- a day/timer gate;
- two NPCs in Southern San d'Oria (S);
- Beaucedine zone-in event;
- three key items acquired by **fishing**;
- Goliath Worm item grant;
- Flint Stone trade;
- zone text/messages;
- Orcish Bloodletter spawned by an event;
- mob death advancing quest state.

So even though Mission 26 only asks "was Blood of Heroes completed?", the branch dependency chain reaches fishing, item acquisition, spawned mobs, text, and combat.

This is exactly why package closure cannot simply link:

`Fate in Haze → Blood of Heroes.lua`

and stop.

## Windurst branch

The reference content expects:

- Sins of the Mothers;
- Howl from the Heavens.

Global quest IDs 53 and 54 exist in current LSB's quest enum, and `meetsMission26Reqs()` explicitly checks `HOWL_FROM_THE_HEAVENS`.

However, source search did not find the corresponding Windurst quest scripts.

The wiki/reference path for Howl from the Heavens contains substantial behavior:

- one-day wait;
- three Magicite-location key items;
- present-day beastman stronghold traversal/access requirements;
- Windurst NPC/zone cutscenes;
- Windurstian Bulwark;
- open-area confrontation;
- multiple timed enemy waves;
- Protective Wards;
- Romaa Mihgo helper NPC;
- quest completion/reward.

This is therefore an excellent example of:

`EXPECTED_CONTENT_MISSING`

The mission graph knows the branch is supposed to exist, while the implementation graph is incomplete.

The package/review system must preserve both facts.

## New dependency semantics required

Mission analysis needs more than the generic artifact relationships already present.

Useful logical relationships include:

```text
PROGRESSES_TO
REQUIRES_MISSION
REQUIRES_QUEST
REQUIRES_ANY_OF
TRIGGERED_BY
ZONE_IN_TRIGGERS
USES_EVENT
EVENT_UPDATES
EVENT_COMPLETES
SETS_QUEST_VAR
REQUIRES_QUEST_VAR
GRANTS_KEY_ITEM
REQUIRES_KEY_ITEM
CONSUMES_KEY_ITEM
REISSUES_KEY_ITEM
REQUIRES_TRADE
GRANTS_ITEM
REQUIRES_TIMER
REQUIRES_ZONE
REQUIRES_ENTITY
SPAWNS_ENTITY
COMPLETES_ON_MOB_DEATH
USES_DIALOG_TEXT
USES_CLIENT_EVENT
HAS_IMPLEMENTATION_GAP
EXPECTED_FROM_REFERENCE
```

Not all of these need to become universal relationship names verbatim, but the information must be representable.

## CSID/event identity

A critical rule exposed by this proof:

**CSID/event number is not a globally sufficient identity.**

Examples such as event `10` appear in different zones/content contexts.

A canonical event identity needs context such as:

```text
zone
entity or zone-in source
event/csid
content owner
trigger condition
event parameters
event update behavior
event finish behavior
```

For example:

```text
event:
  zone: North Gustaberg (S)
  actor: Roderich
  csid: 10
  content: What Price Loyalty
```

is semantically different from another zone's event 10.

This eventually needs to connect to client event resources when client-side CS/event data is available.

## DefaultActions conflict surface

Mission-specific event handling is layered over zone-level default actions.

Examples found during the proof include:

- Gentle Tiger has a default Bastok Markets (S) event;
- Roderich has a default North Gustaberg (S) event;
- Forbidding Portal has a default Xarcabard (S) response;
- Raustigne has a default Southern San d'Oria (S) event.

The package validator should check whether the target's default entity behavior conflicts with, masks, or differs from the migrated quest/mission event override.

This is not necessarily something that gets copied into the package, but it is part of readiness evidence.

## State-machine closure

The graph needs to preserve transitions, not just references.

A useful representation for one step is:

```text
State:
  quest = Beneath the Mask
  status = ACCEPTED
  Prog = 3

Trigger:
  Leadavox trade
  Beeswax + Red Textile Dye

Event:
  Vunkerl Inlet (S), CSID 2

Finish effects:
  confirm trade
  grant Wax Seal
  Prog = 4
```

A backport can fail even when all files/NPCs/items exist if one of those transition effects is wrong.

## Viability vs completeness

This proof reinforces the distinction established by the acquisition work.

Example:

```text
The Will of the World / Fate in Haze bridge

Bastok branch:
  scripts/state/events present
  What Price Loyalty battlefield missing
  VIABLE_WITH_ACCEPTED_GAP (if reviewer accepts placeholder)

San d'Oria branch:
  scripts present
  additional fishing/combat closure required
  UNKNOWN until validated

Windurst branch:
  expected by mission helper/wiki
  quest scripts missing
  INCOMPLETE
```

A developer may intentionally decide:

```text
Ship Bastok branch first.
Accept missing Windurst branch.
Track San d'Oria validation separately.
```

That can be a legitimate development choice.

But the package must report:

```text
Mission viability: PARTIAL / reviewed
Mission completeness: INCOMPLETE
Accepted gaps:
  - What Price Loyalty battlefield
  - Windurst nation branch
```

It must never convert those accepted gaps into "complete."

## Current toolkit gaps

The current dependency graph does not yet automatically reconstruct this mission truth set.

Major missing analyzers are:

1. Mission/Quest Lua state-machine extraction.
2. Section/check condition normalization.
3. Quest/mission var transitions.
4. Zone/entity-scoped CSID extraction.
5. Event argument/update/finish relationships.
6. NPC actor → canonical zone/entity resolution.
7. Key-item lifecycle modeling.
8. Trade dependencies.
9. Timer/day gating.
10. OR branch modeling.
11. Expected-reference versus implementation comparison.
12. DefaultActions conflict checks.
13. Client event/dialog resource linkage.
14. Placeholder/TODO implementation-gap findings.

## Acceptance target

This proof is successful when starting from:

`The Will of the World`

automatically exposes:

1. Raustigne/event 149 and Mission 25 completion.
2. Fate in Haze.
3. `meetsMission26Reqs`.
4. All three nation branch choices.
5. Each branch's prerequisite quest chain.
6. NPCs/zones/events for the selected branch.
7. Quest/mission state variables.
8. Key-item lifecycle.
9. Item trades/rewards.
10. zone-in triggers.
11. event update/finish effects.
12. timers/day waits.
13. combat/instance/fishing/etc. dependencies reached by the branch.
14. missing Windurst branch as expected content rather than silently absent.
15. What Price Loyalty battlefield as an explicit implementation gap.
16. client CSID/dialog/event dependencies when client evidence is available.
17. reviewer ability to accept individual branch/implementation gaps without erasing them.

Only after this works should we consider mission packages trustworthy.
