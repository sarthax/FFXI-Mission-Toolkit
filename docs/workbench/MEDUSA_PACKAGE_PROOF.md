# Medusa Package Dependency Proof

## Goal

Use the Arrapago Reef Medusa notorious monster as the first real proof case for the Packages dependency-closure workflow.

Medusa is intentionally useful because a correct backport is more than one mob row or one Lua file. Her implementation spans:

- zone entity/template data;
- helper mobs;
- skill-list membership;
- mob-skill definitions and scripts;
- a job-special mixin;
- enum/constants;
- zone text and title data;
- loot and item records;
- Lua runtime/API calls;
- related same-name variants in other zones that must **not** be pulled into this feature accidentally.

The machine-readable baseline is:

`test_fixtures/fixtures/medusa_arrapago_dependency_truth.json`

The source baseline is LandSandBoat revision:

`3747feee0e38ab5c0283c4fe8deea7f0a9022351`

## Selected feature boundary

This proof case is specifically:

**Arrapago Reef Medusa, entity 16998862, zone 54**

It is not "every object named Medusa."

The Al Zahbi and Bhaflau Thickets Besieged variants are related semantic variants and should be visible to research, but they are **out of package scope unless explicitly selected**.

This distinction is essential. Name matching is evidence for research, not sufficient evidence for migration membership.

## Manual source truth

### Root entity and template

Arrapago Reef zone data declares:

- entity: `16998862`
- template: `Medusa`
- template ID: `2606`
- species: `medusa`
- type: notorious
- level: 85
- skill list: `725`
- RNG/RNG jobs
- 55,000 HP
- 259,200-second respawn
- katana combat skill
- model 1865
- custom resistance/status configuration
- special drops

This entire template configuration is part of feature behavior. A dependency system that migrates only the spawn row or only the Lua file is incomplete.

### Four helper mobs

The Medusa script references:

`ID.mob.MEDUSA + 1` through `ID.mob.MEDUSA + 4`

Those are real adjacent zone entities:

- 16998863 — Lamia Exon
- 16998864 — Lamia Exon
- 16998865 — Lamia Exon
- 16998866 — Lamia Exon

Behavioral dependency:

- all four are spawned and added to Medusa's target on engage;
- the fight loop keeps helpers engaged;
- missing helpers may be respawned near Medusa during battle;
- helpers are despawned when Medusa disengages or dies.

This is a useful hard case because the dependency is expressed through arithmetic over an ID anchor rather than four literal entity IDs.

### Lamia Exon helper template

The helper template itself introduces further dependencies:

- template ID 2331
- species `lamiae`
- spell list 28
- skill list 171
- BLM/COR jobs
- scripted spawn

Therefore discovering the four helper IDs is not closure. Their template dependencies must also be traversed.

### Medusa skill list

`mob_skill_lists` list 725 contains:

- 1808 — petrifaction
- 1809 — shadow_thrust
- 1810 — tail_slap
- 1812 — pinning_shot
- 1813 — calcifying_deluge
- 1814 — gorgon_dance

The corresponding script implementations include at least:

- `scripts/actions/mobskills/shadow_thrust.lua`
- `scripts/actions/mobskills/pinning_shot.lua`
- `scripts/actions/mobskills/calcifying_deluge.lua`
- `scripts/actions/mobskills/gorgon_dance.lua`

Those scripts themselves use shared mob-skill helpers, effects, attack/damage enums, and Lua entity methods.

For example, the specialized scripts rely on operations such as:

- `xi.mobskills.mobPhysicalMove`
- `xi.mobskills.mobRangedMove`
- `xi.mobskills.processDamage`
- `xi.mobskills.mobStatusEffectMove`
- `xi.mobskills.mobGazeMove`
- entity damage/status APIs

These are downstream Lua/global/binding/engine dependencies and must be classified rather than silently assumed.

### Job special / Eagle Eye Shot

Medusa explicitly loads:

`scripts/mixins/job_special.lua`

and configures:

`xi.mobSkill.EES_LAMIA`

with a configured 75% chance and a random HPP trigger between 5 and 99.

The enum maps EES_LAMIA to mob skill 1931 (`eagle_eye_shot`).

A package that contains Medusa.lua but omits the required mixin/enum/skill/runtime support is not behaviorally complete.

### Loot

The Arrapago template declares:

- `medusas_armlet` — very common
- `mercenarys_dastanas` — common

Modern LSB stores these directly in zone YAML rather than relying on a Medusa `mob_droplist.sql` row.

Therefore package closure must traverse:

`mob template → loot entry → item identity → item records`

and must account for source-family representation differences.

### Title and text

Medusa's death/engage behavior also depends on:

- `xi.title.GORGONSTONE_SUNDERER` — title ID 475
- `ID.text.MEDUSA_ENGAGE`
- `ID.text.MEDUSA_DEATH`

These are small dependencies, but excluding them silently causes incomplete behavior.

### Related Besieged variants

Separate Medusa implementations exist in:

- Al Zahbi
- Bhaflau Thickets

Those scripts delegate lifecycle behavior to `xi.besieged`.

They share Medusa species/skill infrastructure but represent a different encounter/system.

For the Arrapago proof:

- research should reveal them as related variants;
- dependency closure should **not** include them by same-name matching;
- a user may explicitly expand scope to Besieged if desired.

## Expected dependency shape

A useful simplified graph is:

```text
Arrapago entity 16998862
└─ Medusa template 2606
   ├─ species: medusa
   ├─ skill list 725
   │  ├─ skill 1808 petrifaction
   │  ├─ skill 1809 shadow_thrust
   │  │  └─ shadow_thrust.lua
   │  ├─ skill 1810 tail_slap
   │  ├─ skill 1812 pinning_shot
   │  │  └─ pinning_shot.lua
   │  ├─ skill 1813 calcifying_deluge
   │  │  └─ calcifying_deluge.lua
   │  └─ skill 1814 gorgon_dance
   │     └─ gorgon_dance.lua
   ├─ loot
   │  ├─ medusas_armlet
   │  │  └─ item records
   │  └─ mercenarys_dastanas
   │     └─ item records
   ├─ Medusa.lua
   │  ├─ zone IDs/text
   │  ├─ title 475
   │  ├─ job_special.lua
   │  │  └─ EES_LAMIA / skill 1931
   │  └─ helper ID range
   │     ├─ 16998863 Lamia Exon
   │     ├─ 16998864 Lamia Exon
   │     ├─ 16998865 Lamia Exon
   │     └─ 16998866 Lamia Exon
   │        └─ Lamia Exon template 2331
   │           ├─ species: lamiae
   │           ├─ spell list 28
   │           │  └─ spell definitions
   │           └─ skill list 171
   │              └─ Lamiae mob skills/scripts
   └─ Lua API / bindings / engine support

Related but not automatically included:
   ├─ Al Zahbi Medusa_Besieged
   └─ Bhaflau Thickets Medusa_Besieged
```

## Current toolkit coverage audit

This is the important part of the proof.

| Dependency area | Current state | Why |
| --- | --- | --- |
| Migration action roots | Covered | Scope Review starts from canonical MigrationAction artifact IDs. |
| Generic transitive graph traversal | Covered | Package Scope can traverse supported relationship edges with evidence/path visibility. |
| User include/exclude/question/tag workflow | Covered | Scope decisions and reasons are persisted separately from evidence. |
| Stale-scope detection | Covered | Reviewed scope fingerprint invalidates when graph closure changes. |
| Legacy SQL mob spawn/group/pool/drop chain | Partial | Existing adapters and instance slice cover a subset of this chain. |
| Modern LSB zone mob YAML | **Gap** | Current logical extraction is SQL-oriented and does not normalize zone YAML mob templates/entities as equivalent logical records. |
| Medusa helper ID arithmetic | **Gap** | `MEDUSA + 1 .. +4` requires Lua constant/range reasoning or a specialized static reference resolver. |
| Helper-template traversal | **Gap** | There is no generic entity→template→species/skill/spell dependency closure yet. |
| Mob skill-list membership | **Gap** | `mob_skill_lists` is not currently a first-class logical dependency type in the server adapter profile. |
| Mob skill definitions | **Gap** | `mob_skills` is not currently a first-class logical dependency type for package closure. |
| Mob spell-list membership | **Gap** | `mob_spell_lists` is not currently a first-class logical dependency type. |
| Species/family dependencies | **Gap** | LSB species and legacy family concepts are intentionally distinct, but closure does not yet model either deeply enough. |
| Mob-skill Lua script linkage | **Gap/Partial** | Scripts are indexable artifacts, but list/member→script linkage is not guaranteed. |
| Lua `require()` / mixin dependency | **Gap** | Current package analyzer deliberately does not infer require chains. |
| Lua API → binding → C++ | Partial | Workbench has Lua/binding/C++ graph infrastructure, but Medusa-specific closure is not yet proven end to end. |
| Lua enum/constants | Partial | Enum graph infrastructure exists, but Medusa script references are not yet proven to resolve automatically. |
| YAML loot → item records | **Gap** | Current item logical records exist, but the YAML loot-symbol edge is not created. |
| Zone text/title dependencies | **Gap/Partial** | Source data exists, but Medusa-specific Lua references are not yet guaranteed to become package dependencies. |
| Same-name alternate variants | Needs semantic rule | Must be surfaced as related research evidence without becoming package members automatically. |

## Result of the first proof

The Package Scope workflow itself is behaving as intended: if these edges existed in the graph, it could expose them, require decisions, preserve reasons, and block stale/unresolved scope.

The discovery layer is **not yet sufficient to claim a complete Medusa package**.

That is a successful proof result, because it identifies concrete missing generic analyzers before any target-apply functionality is added.

## Implementation priorities exposed by Medusa

### P0 — server logical dependency model

Add source-neutral logical concepts for:

- mob template/entity membership;
- species/family reference;
- mob skill list;
- mob skill;
- mob spell list;
- spell-list member;
- loot entry;
- item reference.

Adapters should map Topaz/DSP/LSB physical representation to those concepts rather than assuming identical tables.

Modern LSB zone YAML needs its own adapter/extractor path.

### P0 — Lua dependency extraction

Add explicit graph edges for:

- `require()` / mixins;
- zone ID symbol references;
- entity ID anchors/ranges where statically resolvable;
- enum/constants;
- referenced global functions/modules.

For an expression such as:

`ID.mob.MEDUSA + 1 .. ID.mob.MEDUSA + 4`

the analyzer should resolve the base ID from the zone IDs source and emit the four concrete entity dependencies with evidence showing the arithmetic expression.

If resolution is not safe, emit an explicit unresolved/analyzer-gap node rather than omitting the dependency.

### P0 — mob skill/spell closure

Model:

```text
mob template
→ skill list
→ skill-list members
→ mob skill definition
→ Lua skill implementation

mob template
→ spell list
→ spell-list members
→ spell definition
```

Then continue Lua/binding/C++ traversal from those implementations.

### P0 — loot/item closure

Model:

```text
mob template
→ loot entry
→ item identity
→ item_basic
→ equipment/weapon/usable/etc representations as applicable
```

An item already present and equivalent in the target can then become a reviewed `TARGET_EQUIVALENT`, with evidence, instead of disappearing.

### P1 — related-variant semantics

Add a relationship such as:

`RELATED_VARIANT`

for same conceptual entities across different zones/systems.

This relationship should be visible in research/trace views but excluded from default package closure unless the package explicitly opts into related variants.

## Acceptance target

Before Medusa is considered a trustworthy dependency proof:

1. Start from the Arrapago Medusa entity/script only.
2. Automatically discover every REQUIRED class in the JSON truth set.
3. Show Al Zahbi/Bhaflau variants as related but not included.
4. Resolve helper mobs without manually entering four IDs.
5. Traverse helper spell/skill lists.
6. Reach mob skill Lua implementations.
7. Traverse Lua/mixin/binding/C++ dependencies or produce explicit unresolved nodes.
8. Traverse loot to item records.
9. Preserve every exclusion/equivalence decision and reason.
10. Produce zero silent omissions.

Only after that should we use the same mechanism on an Assault/mission package and then consider approval/apply UI.
