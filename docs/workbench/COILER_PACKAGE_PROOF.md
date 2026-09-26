# Coiler Package Dependency Proof

## Goal

Use the Puppetmaster attachment **Coiler** as a second dependency-closure proof case.

Unlike Medusa, Coiler is not primarily a zone/mob problem. It crosses:

- obtainable item identity;
- internal automaton attachment identity;
- SQL puppet equipment metadata;
- attachment Lua lifecycle;
- shared automaton Lua behavior;
- modifier enums;
- C++ item classes;
- C++ attachment unlock/equip/persistence logic;
- dynamic C++→Lua dispatch;
- automaton weapon-skill consumers;
- conditional Optic Fiber / Overdrive interactions;
- shop/drop acquisition paths.

The machine-readable baseline is:

`test_fixtures/fixtures/coiler_attachment_dependency_truth.json`

Source baseline:

`LandSandBoat/server@3747feee0e38ab5c0283c4fe8deea7f0a9022351`

## Identity is not one row

Coiler immediately demonstrates why package closure cannot equate "item" with one numeric ID.

### Obtainable item

The Lua item enum declares:

`xi.item.COILER = 2413`

This identity is used by acquisition content such as Rararoon's Nashmau shop.

### Internal puppet-equipment record

`sql/item_puppet.sql` contains:

```text
itemid = 8583
name = coiler
equip slot = 3
element slots = 131072
```

Slot 3 is `ITEM_PUPPET_ATTACHMENT`.

The low byte of 8583 is 135, which is the internal attachment index used by automaton equipment state.

The element-slot mask is `0x20000`, representing Thunder capacity cost 2 in the nibble-encoded element-slot scheme.

So closure needs a semantic mapping between:

```text
inventory item 2413
      ↓ unlock/trade/sub-ID mapping
internal puppet item 8583 / attachment index 135
      ↓
attachment name "coiler"
      ↓
Lua behavior
```

A package that migrates only the inventory item or only `item_puppet` is incomplete.

## Dynamic Lua dispatch

C++ does not hard-code `coiler.lua`.

`luautils::OnAttachmentEquip` and the related maneuver/update functions get the puppet item's **name** and dynamically dispatch to:

```text
xi.actions.abilities.pets.attachments[name]
```

For Coiler, that resolves to:

`scripts/actions/abilities/pets/attachments/coiler.lua`

This is an important dependency type because ordinary static import/require analysis will not find it.

## Attachment lifecycle

`coiler.lua` delegates its lifecycle to shared automaton functions:

- `xi.automaton.onAttachmentEquip`
- `xi.automaton.onAttachmentUnequip`
- `xi.automaton.onManeuverGain`
- `xi.automaton.onManeuverLose`
- `xi.automaton.updateAttachmentModifier`

These live in:

`scripts/globals/automaton.lua`

## Actual Coiler behavior

The shared attachment modifier table defines Coiler as:

```text
modifier: xi.mod.DOUBLE_ATTACK
0 maneuvers: 3
1 maneuver: 10
2 maneuvers: 20
3 maneuvers: 30
opticFiber: true
```

That makes the global automaton implementation part of the feature.

It also creates dependencies on:

- `xi.mod.DOUBLE_ATTACK`;
- modifier add/remove APIs;
- maneuver-count semantics;
- local variable APIs used to track applied modifier values;
- Optic Fiber performance-boost logic.

## Weapon-skill fan-out

Coiler is not only an equip-time modifier.

`xi.automaton.getExtraHits()` reads the automaton's DOUBLE_ATTACK modifier and rolls extra hits for automaton weapon skills.

Current direct consumers include at least:

- `knockout.lua`
- `slapstick.lua`
- `bone_crusher.lua`
- `string_clipper.lua`
- `chimera_ripper.lua`
- `string_shredder.lua`
- `shield_bash.lua`

This means the dependency can travel in the opposite direction from what a naïve package builder expects:

```text
Coiler
 → DOUBLE_ATTACK
 → getExtraHits
 → several automaton weapon-skill implementations
```

Whether every consumer must be physically included depends on the target comparison. But every consumer must at least be **evaluated** so the package can prove target compatibility.

## C++ puppet runtime

Coiler depends on the generic puppet item/runtime model.

Relevant source includes:

- `src/map/items/item_puppet.h/.cpp`
- `src/map/utils/puppetutils.cpp`
- `src/map/lua/luautils.cpp`
- `src/map/lua/lua_item_puppet.cpp`

Key behavior includes:

- identifying item type `ITEM_PUPPET`;
- distinguishing head/frame/attachment slots;
- validating element-capacity limits;
- resolving attachments through `0x2100 + attachment`;
- storing unlocked attachments as bits;
- persisting `unlocked_attachments`;
- persisting `equipped_attachments`;
- equipping up to 12 attachment slots;
- calling Lua attachment hooks on equip/unequip/maneuver/update.

If a target lacks equivalent puppet runtime behavior, Coiler cannot be called complete merely because its SQL/Lua files exist.

## Conditional dependencies

Coiler exposes a dependency relation different from hard `REQUIRES`.

### Optic Fiber

Its modifier is marked:

`opticFiber = true`

Optic Fiber can therefore amplify Coiler's modifier.

But Coiler does not require Optic Fiber to function.

This should be modeled conceptually as:

`CONDITIONALLY_MODIFIES`

rather than forcing Optic Fiber into every Coiler package.

### Overdrive / maneuver semantics

`getManeuverCount()` treats an active maneuver under Overdrive as three maneuvers for attachment scaling.

Again, this changes Coiler behavior conditionally but is not a hard prerequisite for basic Coiler operation.

The reviewer should be able to see:

- hard dependency;
- conditional interaction;
- acquisition-only relation;
- target-equivalent implementation.

## Acquisition scope

Coiler is obtainable from multiple content paths.

Verified examples include:

### Rararoon shop

`scripts/zones/Nashmau/npcs/Rararoon.lua`

- item: `xi.item.COILER`
- price: 185,250
- requirement: PUP level 80

### Ob loot

`data/zones/alzadaal_undersea_ruins/mobs.yaml`

Ob has Coiler as an uncommon drop.

These acquisition paths are not necessarily required when the migration goal is only "backport Coiler behavior."

Therefore the Package Scope UI should surface them as:

`QUESTIONABLE_USER_SCOPE`

The user can choose:

- include behavior only;
- include shop availability;
- include drop source;
- include all acquisition paths.

That is a strong example of why user agency belongs **before** package assembly.

## Expected dependency graph

```text
Coiler inventory item 2413
├─ shop/drop acquisition paths                  [user scope]
└─ internal puppet identity mapping
   └─ item_puppet 8583 / attachment index 135
      ├─ equip slot: attachment
      ├─ Thunder capacity: 2
      ├─ CItemPuppet
      ├─ puppetutils unlock/equip/persistence
      │  ├─ char_pet.unlocked_attachments
      │  └─ char_pet.equipped_attachments
      ├─ dynamic C++→Lua dispatch by name
      │  └─ attachments/coiler.lua
      │     └─ globals/automaton.lua
      │        ├─ attachmentModifiers["coiler"]
      │        │  └─ xi.mod.DOUBLE_ATTACK
      │        ├─ updateAttachmentModifier
      │        ├─ getManeuverCount
      │        ├─ Optic Fiber interaction        [conditional]
      │        └─ getExtraHits
      │           ├─ knockout
      │           ├─ slapstick
      │           ├─ bone_crusher
      │           ├─ string_clipper
      │           ├─ chimera_ripper
      │           ├─ string_shredder
      │           └─ shield_bash
      └─ target engine/runtime equivalence checks
```

## Current toolkit result

Coiler performs poorly under the current generic discovery model, which is exactly why it is a useful test.

| Dependency area | Current state |
| --- | --- |
| item_basic generic item records | Partial |
| item_puppet | **Gap** |
| inventory→internal puppet identity | **Gap** |
| attachment-name dynamic dispatch | **Gap** |
| attachment Lua artifact | Discoverable only if separately seeded |
| automaton.lua shared behavior | **Gap/Partial** |
| DOUBLE_ATTACK enum/mod semantics | Partial graph infrastructure, not proven for Coiler |
| getExtraHits→weapon skills fan-out | **Gap** |
| CItemPuppet / puppetutils runtime | C++ indexable, but semantic closure not modeled |
| char_pet persistence fields | **Gap** |
| Optic Fiber conditional interaction | **Gap relationship type** |
| shop/drop acquisition paths | **Gap/user-scope relationship** |

So if today's package system were asked to migrate "Coiler," it would not be safe to say the automatically discovered closure was complete.

## Design lessons from Coiler

### 1. Logical identity mapping is required

We need a generic concept such as:

`REPRESENTS_SAME_LOGICAL_ENTITY`

or a typed mapping edge between:

- inventory item;
- puppet internal item;
- attachment index;
- Lua attachment name.

Numeric IDs alone cannot be treated as universal identities.

### 2. Dynamic dispatch needs evidence extraction

C++ patterns like:

```text
attachment->getName()
lua["..."]["attachments"][name]
```

should produce a dynamic-dispatch relationship from the item record/name to its Lua script.

### 3. Shared-file dependency must be symbol-aware

`automaton.lua` contains definitions for many attachments.

If Coiler requires one table row and several functions in that file, the graph should record those symbols/regions as evidence without concluding that every other attachment defined in the same file is a Coiler dependency.

Physical packaging may still copy the whole file, but semantic scope and package explanation should remain narrower.

### 4. Reverse consumers matter

A feature can affect downstream consumers.

Coiler changes DOUBLE_ATTACK behavior consumed by multiple automaton weapon-skill scripts.

Dependency closure therefore needs both:

- "what Coiler calls/requires";
- "what must understand Coiler's behavior to remain correct."

### 5. Acquisition is separate from behavior

Shop/drop availability should be selectable independently from the core feature implementation.

This is a good candidate for the user-agency workflow:

```text
Core behavior                    INCLUDE
Rararoon shop availability       INCLUDE / EXCLUDE / QUESTIONABLE
Ob drop source                   INCLUDE / EXCLUDE / QUESTIONABLE
Optic Fiber interaction          TARGET_EQUIVALENT / INCLUDE / QUESTIONABLE
```

## Acceptance target

Coiler should be considered a successful dependency proof when starting from the logical feature "Coiler attachment" automatically produces:

1. inventory item identity;
2. internal puppet-equipment identity;
3. the mapping between them;
4. attachment Lua;
5. shared automaton behavior symbols;
6. DOUBLE_ATTACK modifier semantics;
7. C++ puppet item/runtime support;
8. persistence schema;
9. weapon-skill consumers of Coiler's extra-hit behavior;
10. conditional Optic Fiber/Overdrive interactions;
11. acquisition paths presented as optional user scope;
12. no silent ID conflation or silent omission.

This proof should be retained alongside Medusa because the two cases stress almost opposite ends of the dependency model:

- **Medusa:** cross-zone/system state + mobs + SQL/YAML + Lua + event lifecycle.
- **Coiler:** logical item identity + dynamic dispatch + shared Lua framework + C++ runtime + persistence + downstream consumers.
