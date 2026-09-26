# Domain Plugin & Content Framework Architecture

Status: FOUNDATION IMPLEMENTED  
Scope: optional FFXI domain layer above the universal Workbench graph/migration model.

## Goal

Different FFXI content takes materially different shapes. The Workbench must understand those shapes without teaching the universal core about BCNM, Assault, Nyzul, quest variables, minigames, ranks, or other game-specific concepts.

The plugin layer therefore has two levels:

1. **Reusable content frameworks/archetypes** — generic shapes such as battlefields, simple turn-ins, multi-zone progression, state-machine missions, minigames, and repeatable system containers.
2. **Named system packages** — Assault, Nyzul Isle, Abyssea systems, battlefield families, and future systems. These compose reusable frameworks and add only the rules unique to that system.

The GUI separately groups these packages and future tools into high-level **Domains** for navigation. Domain categories are organizational and may contain multiple system packages; they are not new universal-core concepts.

## Why this matters

Modern LSB often centralizes behavior behind reusable Lua classes/globals/modules and data files. Legacy DSP commonly spreads equivalent behavior across zone Lua, SQL, IDs, globals, and engine code.

The Workbench must compare **semantic roles and behavior**, not repository layout.

For example, a battlefield feature may have these semantic roles:

- registry
- entry policy
- battlefield script
- battlefield membership/groups
- mob scripts
- reward logic
- mission/quest hook
- exit policy

LSB may implement several roles in a reusable BattlefieldMission framework plus YAML. DSP may implement the same roles through `bcnm_info.sql`, `bcnm_battlefield.sql`, zone/bcnm Lua, and mob scripts. Different paths do not imply missing behavior.

## Content archetypes

### Simple NPC / Turn-in
Small-scope NPC/event/item/key-item/reward content.

### Multi-zone Progression / Hunt
Multiple zones, NPC gates, monster kills, variables/key items, and staged progression.

### Battlefield Instance
Reusable arena content suitable for BCNM/KSNM/ISNM/ENM/mission battlefields and compatible variants.

### Multi-stage Mission / Quest
State machine spanning multiple stages, zones, NPCs, events, and optional embedded frameworks.

### Minigame / Puzzle
Timers, temporary state, interactables, scoring, resets, and win/loss conditions.

### Repeatable / System Container
Points/rank/currency/entry-resource systems containing many child features.

A single Feature may compose multiple archetypes.

## Plugin contract

`DomainPlugin` exposes bounded extension points:

- `identify()`
- `classify_archetypes()`
- `discover_surfaces()`
- `discover_dependencies()`
- `compare()`
- `generate_migration_rules()`
- `validate()`
- `report()`

Plugins may add semantic interpretation and validation policy, but canonical persistence remains through Evidence, Finding, Feature, Artifact, Relationship, Capability, MigrationAction, ValidationRun, and ValidationResult.

## Built-in foundation

Current declarative plugins:

- `framework.battlefield`
- `framework.quest_mission`
- `framework.multizone_progression`
- `framework.minigame`
- `system.assault`

`system.assault` composes the battlefield and quest/mission frameworks and then adds Assault-specific semantic roles such as AP, tags, ranks, appraisal, lockboxes, and objective conventions.

## Representation profiles

Two common implementation profiles must be supported explicitly:

### Modular framework
Typical of modern LSB:
- reusable framework classes/globals/modules
- central content registration
- structured YAML/data
- individual feature scripts plugging into shared services

### Legacy distributed
Typical of DSP:
- zone-local Lua
- BCNM/instance Lua
- SQL registries and memberships
- IDs.lua
- global helpers
- engine bindings/C++ where needed

Neither profile is globally authoritative. Feature completeness is determined from evidence-backed semantic coverage.

## GUI domain taxonomy

The shared GUI shell exposes a first-class **Domains** workspace. Its current high-level categories are:

- Abyssea
- Battlefields
- Battle Systems
- Conflict / Battle
- Combat
- Dynamis
- Escha
- Hobbies
- HELM
- Events
- Missions
- Quests
- Records of Eminence
- Trust
- Other

Current populated groupings include:

- **Battle Systems**: Assault, Nyzul Isle
- **Battlefields**: AMAN-Trove, Ambuscade, ANNM, BCNM, ENM, HKCNM, ISNM, KCNM, KSNM, Login, Master Trials, SCNM, SKCNM, Walk of Echoes
- **Conflict / Battle**: Ballista, Besieged, Brenner, Campaign, Colonization, Expeditionary Force, Garrison
- **Records of Eminence**: General, Unity, Tutorial, Quests, Vanabout
- **Trust**: Misc, Combat, Quest
- **Abyssea**: Altepa, Attohwa, Grauberg, Konschtat, La Theine, Misareaux, Tahrongi, Uleguerand, Vunkerl, Bastion

These entries may be placeholders. A visible category or subsection does not imply that a plugin, analyzer, migration backend, validator, or write-capable admin workflow exists. Existing generic tools such as Zone Editor remain generic and may be linked from a domain rather than duplicated.

## Navigation model

Plugins should eventually expose user-facing feature structure such as:

- stages
- zones
- NPCs
- mobs
- battlefields/instances
- state variables/key items
- entry requirements
- rewards
- system currencies/ranks
- unresolved dependencies

This navigation model should be derived from canonical evidence and remain traceable into Feature Trace.

## Validation strategy

Framework plugins should contribute validators appropriate to their archetype.

Battlefield examples:
- registry identity
- entry conditions
- party/level/time policy
- entity/group coverage
- mob behavior surfaces
- win/loss handling
- reward/completion handling
- exit behavior

Mission/state-machine examples:
- stage transitions
- required variables/key items
- zone/event coverage
- completion/reward paths
- embedded framework coverage

Minigame examples:
- timer lifecycle
- reset behavior
- interaction coverage
- win/loss state
- scoring/reward behavior

## Initial proof case

The pinned Ancient Vows LSB→DSP E2E is the first reusable battlefield + quest/mission composition fixture. It is not a special Ancient Vows plugin: the test activates reusable frameworks from feature metadata and compares semantic FeatureSurface roles across the two representations.

Assault remains a separate system package and a drift/reverse-pipeline fixture even though the GUI groups it under Battle Systems alongside Nyzul Isle. The user's local Assault backports will later test functionality that can exceed public LSB coverage.
