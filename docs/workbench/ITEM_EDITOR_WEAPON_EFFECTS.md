# Item Editor: weapon additional effects

The Equipment/Item Editor now has a structured model for the server's existing weapon additional-effect fields instead of treating them as ordinary stat augments.

## Existing server-data path

Always-on effects are represented by `item_mods`; conditional effects use the same modifier bundle in `item_latents` with `latentId` / `latentParam`.

Common DSP/Topaz/LSB modifier ids used by the helper:

| Field | Mod id | Purpose |
| --- | ---: | --- |
| additional-effect type | 431 | selects the server proc handler |
| subeffect | 499 | battle visual/message subeffect |
| damage/amount | 500 | base damage or amount |
| chance | 501 | proc chance percent |
| element | 950 | elemental resist/damage element |
| status | 951 | status-effect enum id |
| power | 952 | status power |
| duration | 953 | status duration |

Example: an always-on 20% Fire-damage proc for 25 base damage is the bundle `431=1`, `499=1`, `500=25`, `501=20`, `950=1`. A latent version stores the same bundle in `item_latents` with one shared condition.

## Presets and lineage safety

The framework includes presets for Fire/Ice damage, HP/MP/TP drain, Dispel, self-buff, absorb-status, instant-death, and NM-specific behavior. Presets expand to explicit modifier rows rather than hiding the underlying data.

Each effect receives a capability badge:

- `row-only` — safe for direct editor application on that lineage;
- `verify-lineage` — the model exists, but the target fork must be verified first;
- `server-code-required` — the editor can model/export the desired behavior, but server Lua/C++ must be added or extended;
- `unsupported` — unknown to the framework.

Only `row-only` effects are considered safe to apply automatically. This is intentionally fail-closed.

## Self-buff framework

Self-buffs are represented as a structured server handoff. A blueprint carries chance, battle subeffect, status id, power, duration, attacker/self target semantics, stacking/overwrite requirements, lineage-specific code references, and a local-agent checklist.

Current LandSandBoat reference:

`https://github.com/LandSandBoat/server/blob/base/scripts/globals/additional_effects.lua`

Relevant implementation points are `xi.additionalEffect.attack`, `xi.additionalEffect.procFunctions`, and the `SELF_BUFF` handler. Current LSB explicitly handles **Blink** and **Haste**. Blink checks existing Blink/Copy Image shadows; Haste applies with `attacker:addStatusEffect(...)`, with an upstream TODO around power/duration/tier/overwrite semantics. Arbitrary self-buff statuses therefore remain `server-code-required` until implemented and tested.

Archived DSP reference:

`https://github.com/DarkstarProject/darkstar/blob/master/scripts/globals/status.lua`

DSP documents the older `ITEM_ADDEFFECT_TYPE` mapping as `1=status/damage/HP drain`, `2=MP drain`, `3=TP drain`, `4=dispel`, `5=self-buff`, `6=instant death`. Modern LSB uses a larger enum where `SELF_BUFF=12`. Modern LSB type ids must not be written into DSP/Topaz solely because the logical effect name matches.

A local server agent implementing a new self-buff should:

1. identify the active lineage and exact additional-effect dispatcher;
2. verify proc-type numbering;
3. add/verify the desired status branch;
4. define stacking/replacement behavior;
5. apply the status to the attacker/self with the lineage API;
6. return the correct battle subeffect/message tuple;
7. add focused server tests for chance, power, duration, and stacking.

`build_self_buff_blueprint()` produces this handoff data directly.

## Editor-facing output

The helper also provides:

- preset expansion into exact rows;
- recognition of existing raw effect rows;
- compact summaries such as `20% damage · fire · amount 25`;
- lineage capability checks;
- explicit `rows_safe_to_apply()` gating;
- generic server-handoff export for effects needing verification or code.

This allows the GUI to eventually show three layers together: human-readable behavior, exact SQL rows, and server-code requirements.

## Client DAT boundary

The combat proc is server driven and is not a charge/enchantment DAT feature. Existing battle subeffects can be displayed by the stock client. DAT editing is only needed for client-owned item identity/presentation such as name, description, icon, equip metadata, or custom descriptive text.

## Intended GUI pass

The Item Editor should render a dedicated **Weapon Effects** panel with preset/custom mode, proc chance/type, subeffect, damage/amount, element, status/power/duration, always-on vs latent storage, latent condition, lineage capability badge, and generated server handoff when needed.

The implementation helper lives at `src/workbench/editors/items/weapon_effects.py`. It intentionally leaves live writes to the Item Editor's existing backup/journal/validation path.