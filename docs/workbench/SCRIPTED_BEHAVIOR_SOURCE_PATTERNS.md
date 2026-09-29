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
