# Scripted Entity Behavior — LSB Source Pattern Inventory

## Purpose

This inventory records recurring behavioral structures observed directly in LandSandBoat zone Lua.
The goal is a generic behavior/dependency vocabulary that applies to mobs, NPCs, doors/objects,
escorts, mission actors, and other scripted entities without hard-coding one game system.

The scripted-behavior layer records what source does and what other actors/state it depends on.
Mission/quest/acquisition/domain adapters may add stronger semantics when the evidence supports them.

## Representative source samples

The initial mixed inspection covered:

- `PsoXja/mobs/Gargoyle.lua` — mob death opens a corresponding stone door.
- `Temple_of_Uggalepih/mobs/Temple_Guardian.lua` — mob death opens a named door for a fixed duration.
- `Grand_Palace_of_HuXzoi/mobs/DE_Quasilumin.lua` — escort state machine, local vars, paths,
  timers, door animation/state, completion door, pause/resume trigger behavior and cleanup.
- `Halvung/npcs/qm8.lua` — trade predicate, trade completion and key-item grant.
- `Uleguerand_Range/npcs/Eternal_Ice.lua` — trigger-gated key-item grant.
- `Norg/npcs/Repat.lua` — NPC-local state, player char vars, event start/update/finish,
  randomized state, gil cost/reward and item reward.
- `Nyzul_Isle/mobs/Gem_Heister_Roorooroon.lua` — helper-driven path selection, local runtime
  state, companion entity positioning/status, timers and instance-aware spawn behavior.
- `Bhaflau_Remnants/npcs/_23c.lua` — event-gated door opening, shared `xi.salvage` helpers,
  sealing/unsealing other doors, group spawn and conditional world-object state.
- `Arrapago_Remnants/npcs/_220.lua` — event finish changes door animation/targetability and
  activates/spawns a range of related entities.
- `Kuftal_Tunnel/npcs/qm1.lua` — repeating timer helper, random position/status cycle and
  trade-triggered mob pop.
- `RuLude_Gardens/npcs/Maat.lua`, `Port_Bastok/npcs/Ensetsu.lua`,
  `Southern_San_dOria/npcs/qm3.lua`, `Castle_Oztroja/npcs/_47d.lua` — persistent player-state
  gates, event routing, char-var progression, door state and key-item rewards.

## Generic behavior grammar observed

### Entity hooks

Common entry points are not mob-only:

- `onSpawn`, `onMobInitialize`, `onMobSpawn`, `onMobRoam`, `onMobEngage`,
  `onMobFight`, `onMobWeaponSkill`, `onMobDeath`, `onMobDespawn`;
- `onTrigger`, `onTrade`, `onEventUpdate`, `onEventFinish`, `onPath`;
- combat-response hooks such as `onPlayerAbilityUse`, `onSpellPrecast`, `onMagicHit`.

The behavior model therefore treats hooks generically and records the source hook name rather than
using a mob-specific state machine.

### Player/progression state

Recurring source primitives:

- read/write player char vars;
- quest/mission/status checks;
- key-item possession/grant/removal;
- item and gil grant/removal;
- trade predicates and trade completion;
- start/update/finish event routing.

The scripted-behavior layer records these as generic player-state/progression effects. Dedicated
mission/quest/acquisition analyzers may later map them to stronger domain identities.

### World/entity state

Recurring operations:

- open/close doors;
- set animation;
- set status/visibility/targetability;
- set position/spawn position;
- spawn/despawn related entities;
- modify combat/runtime parameters;
- move/path actors.

These are first-class behavioral effects because they frequently form package dependencies even
when no mission-state transition is involved.

### Cross-entity orchestration

Source commonly locates other actors through `GetMobByID` / `GetNPCByID`, then reads state or
changes the target actor. Examples include:

- a mob death opening a door;
- a boss reading another boss's local vars;
- a door spawning mobs and activating objects;
- an escort opening/closing nearby doors;
- an NPC trade spawning a target mob;
- one entity transferring target/enmity/claim to another.

These relationships must surface in dependency review rather than remaining hidden inside Lua.

### Runtime state machines

Many scripts implement lightweight state machines with:

- entity local vars;
- player char vars;
- timers/system time;
- path-point indexes;
- status/animation changes;
- random ranges/probability guards;
- repeated callbacks.

This is broader than mission progression. Escort movement, boss phases, minigames, rotating QMs and
instance mechanisms all use the same structural pattern.

### Helper indirection

A substantial fraction of behavior is hidden in:

- `local function foo(...)`;
- `local foo = function(...)`;
- `entity.foo = function(...)`;
- shared `xi.<system>.<helper>(...)` calls.

Direct-hook extraction alone is therefore incomplete. The extractor now follows statically named
local/entity helper calls with a bounded, cycle-safe traversal and keeps the helper source span and
call chain in rule metadata.

Shared `xi.<system>` calls remain explicit system-helper effects rather than being inlined or
assumed equivalent.

## Current extractor coverage

Covered conservatively:

- balanced `entity.on*` hook discovery;
- reachable local/entity helper discovery with bounded cycle-safe call traversal;
- HPP guards;
- random timing ranges and simple percent guards;
- direct timers;
- direct named mob spawn references;
- despawn/cleanup presence;
- cross-entity local-state reads;
- enmity/claim transfer when tied to a direct named spawn;
- combat modifiers;
- spell override calls;
- loot/drop-ID override;
- key-item grant/removal;
- player char-var reads/writes;
- event start/update calls;
- trade predicate/completion;
- item/gil rewards;
- door open, animation, status, targetability and position changes;
- path/pathThrough control;
- explicit `xi.<system>.<helper>` calls;
- exact source spans for direct and helper-derived rules.

## Still open

Important patterns intentionally remain unclaimed:

- arbitrary expression evaluation and alias/data-flow resolution;
- dynamically computed entity IDs/ranges outside the existing specialized dependency analyzers;
- table-driven reward mappings where the concrete value depends on runtime lookup;
- semantic interpretation of every `csid`/option branch;
- callback body expansion for anonymous timer/queue closures as independent provenance spans;
- loops over ID tables/ranges as fully resolved actor sets;
- instance-local/global state identity beyond observed source expressions;
- helper calls imported from other Lua modules;
- full quest/mission meaning when only generic char vars/events are visible;
- retail behavior that is absent/stubbed in the source snapshot.

These remain explicit future analyzer work rather than inferred behavior.

## Architectural conclusion

Mobs, NPCs, doors, escorts and other scripted entities should share one generic scripted-behavior
representation. The distinction between them is source/entity identity and the hooks/effects they
use, not a separate core behavioral framework.

Domain plugins should interpret this evidence when appropriate:

```text
Lua source
  -> generic scripted behavior
     -> generic dependencies/effects
        -> mission/quest interpretation (when proven)
        -> acquisition interpretation (when proven)
        -> instance/system interpretation (when proven)
        -> Package Scope / Feature Trace
```

This prevents mission-specific assumptions from leaking into the universal dependency framework
while still allowing higher-level feature analyzers to derive stronger semantics.


## Larger LSB behavior sweep — 2026-09-29

A broader repository search across zone/entity/instance Lua found recurring behavior outside the first mob/NPC sample:

- global/server state through `GetServerVariable` / `SetServerVariable`;
- respawn scheduling and spawn eligibility through `setRespawnTime`, `DisallowRespawn`, and related calls;
- time/day/weather gated logic through `VanadielHour`, day-element/weather lookups, and weather-change listeners;
- party/alliance-sensitive behavior through `getParty` / `getAlliance`;
- instance orchestration through instance local vars, stage/progress, character/mob lists, registry/entry callbacks, and completion/failure callbacks;
- zone-level trigger areas, weather callbacks, conquest callbacks, and zone-in positioning;
- AI/combat-mode mutation such as auto-attack/magic/mob-ability enablement, behavior modes, roam flags, spell lists, skill selection, immunities, and status effects;
- packet/animation/message surfaces such as action packet injection, entity animation packets, messageSpecial/messageName/messageBasic, cutscenes, and event updates;
- mission/quest progression APIs such as add/complete mission/quest;
- currencies, titles, temp items, treasure injection, drop overrides, and other reward systems;
- teleport/position/zone transfer and instance-exit movement;
- listeners/callbacks and anonymous timer/queue closures that carry additional behavior;
- table/switch-driven phases and weighted action selection;
- shared-system modules such as `xi.nyzul`, `xi.salvage`, `xi.instance`, `xi.combat`, `xi.treasure`, and others.

### Open-ended behavior requirement

This sweep confirms that the semantic effect list must **not** be treated as exhaustive. Lua can invoke any bound engine API or shared Lua module, and new bindings may appear over time.

The extractor therefore has two layers:

1. **Semantic effects** for patterns the Workbench understands well enough to normalize, such as key-item grants, door opens, state changes, spawn/despawn, pathing, rewards, and shared-system dependencies.
2. **Generic API-call evidence** for every statically visible call shape the extractor can identify. These records preserve call style, receiver/namespace, function name, original source line, line number, hook/helper owner, and provenance without claiming semantic interpretation.

This means an unfamiliar call such as `mob:setSomeFutureEngineFlag(...)` is still visible in Feature Trace and evidence review immediately. A later analyzer can promote it to a stronger semantic class without losing the original source observation.

### Broadened hook ownership

Behavior entry points are no longer limited to `entity.on*`. The generic hook scanner now recognizes owner objects such as:

- `entity.on*`;
- `zoneObject.on*`;
- `instanceObject.on*`;
- registry/entry callbacks such as `registryRequirements`, `entryRequirements`, and `afterInstanceRegister`.

Additional owner conventions can be added without changing the behavior graph model.

### Still unresolved after the broad sweep

The raw API-call layer preserves these cases, but stronger semantic extraction still needs dedicated work for:

- nested anonymous timer/queue/listener callback bodies;
- table-driven/switch-driven phase machines;
- dynamically computed entity IDs and ranges;
- alias/data-flow propagation across locals/tables/helpers;
- imported helper/module body expansion;
- party/alliance predicates and per-member effects;
- weather/time/day predicates as structured conditions;
- instance stage/progress/state semantics;
- server/global variable identities and lifecycle;
- mission/quest API calls mapped to canonical progression identities;
- packet/message/event APIs mapped to protocol/client evidence;
- AI/spell/skill/status/immunity APIs mapped to normalized engine/binding identities;
- zone transfer/teleport semantics with destination identity;
- reward/treasure/currency calls mapped into the unified acquisition graph.

Those are now explicit enrichment targets rather than blind spots: the generic call layer ensures the source evidence is retained even before semantic promotion exists.


## Callback closure enrichment — 2026-09-29

Timer, queue, and named listener closures are now represented as first-class behavior branches rather than only as raw calls inside their parent hook. The extractor preserves:

- callback kind (`timer`, `queue`, `addListener`);
- delay source expression where present;
- listener event name where statically visible;
- callback receiver and arguments;
- callback call line and balanced function-body source span;
- nested API-call observations;
- nested named state reads/writes.

The Behavior Inspector renders a callback node between the parent hook and the callback's rules/effects so delayed/event-driven behavior is visually distinct from synchronous hook behavior. This is still source-static: callback execution timing/order at runtime remains a validation concern.


## Literal phase-machine enrichment — 2026-09-29

The extractor now recognizes a conservative table/switch state-machine pattern used by bosses such as Ultima:

```lua
local phase = mob:getLocalVar('phase')
switch (phase): caseof
{
    [1] = function()
        mob:setLocalVar('phase', 2)
    end,
}
```

A transition is promoted only when:

- the switch selector is a local alias directly assigned from a named state read;
- the case key is statically visible;
- the case writes back to that exact same canonical state identity.

This produces a verified `STATE_EQUALS(from) -> WRITE_STATE(to)` transition with source span, selector alias, hook and confidence. Writes to other state variables inside the same case are deliberately not treated as transitions of the selector state.

The Behavior Inspector displays these in a dedicated State Transitions table and links the state node to the transition guard in the causal graph. Dynamic dispatch, computed case keys, indirect state aliases and arbitrary control-flow inference remain open enrichment work.
