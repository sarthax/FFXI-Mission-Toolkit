# Item Editor: weapon additional effects

The Equipment/Item Editor has a structured model for server weapon additional effects instead of treating them as ordinary stat augments.

Always-on effects use `item_mods`; conditional effects use the same bundle in `item_latents` with `latentId` / `latentParam`.

| Field | Mod id | Purpose |
| --- | ---: | --- |
| additional-effect type | 431 | server proc handler |
| subeffect | 499 | battle visual/message |
| damage/amount | 500 | base amount |
| chance | 501 | proc chance % |
| element | 950 | resist/damage element |
| status | 951 | status-effect id |
| power | 952 | status power |
| duration | 953 | status duration |

Example: 20% Fire damage for base 25 becomes `431=1`, `499=1`, `500=25`, `501=20`, `950=1` on modern LSB-style handling.

## Presets and safety

Presets cover Fire/Ice damage, HP/MP/TP drain, Dispel, self-buff, absorb-status, instant-death, and NM-specific behavior. They expand to explicit modifier rows.

Capability badges are fail-closed:

- `row-only`: safe for direct editor application on that lineage;
- `verify-lineage`: verify the target fork first;
- `server-code-required`: model/export only until Lua/C++ support exists;
- `unsupported`: unknown effect type.

Only `row-only` is automatically writable.

## Self-buff framework

Self-buffs produce a structured local-agent handoff containing proc chance, battle subeffect, status id, power, duration, attacker/self target semantics, stacking/overwrite requirements, server references, and implementation tasks.

Current LandSandBoat reference:
`https://github.com/LandSandBoat/server/blob/base/scripts/globals/additional_effects.lua`

Relevant points are `xi.additionalEffect.attack`, `xi.additionalEffect.procFunctions`, and the `SELF_BUFF` handler. Current LSB explicitly handles Blink and Haste. New statuses require extending/verifying that handler and defining stacking behavior.

Archived DSP reference:
`https://github.com/DarkstarProject/darkstar/blob/master/scripts/globals/status.lua`

DSP documents the older `ITEM_ADDEFFECT_TYPE` mapping as `1=status/damage/HP drain`, `2=MP drain`, `3=TP drain`, `4=dispel`, `5=self-buff`, `6=instant death`. Modern LSB uses `SELF_BUFF=12`, so modern type ids must not be written into DSP/Topaz without mapping the active fork.

The local server agent should verify lineage/proc numbering, extend the self-buff handler, define stacking, apply the effect to the attacker, return the correct battle message/subeffect, and add tests for chance/power/duration/stacking.

`build_self_buff_blueprint()` creates this handoff.

## Editor integration

The existing Effects tab remains the authoritative staged-write path. Weapon-effect presets should add explicit rows into the existing `stagedEffects.mods` / `stagedEffects.latents` collections so save, validation, backup, journal, undo, and restore continue to use one path.

The UI must not write a generated bundle when the selected lineage capability is `verify-lineage`, `server-code-required`, or `unsupported`; those states are preview/handoff only. This prevents modern LSB proc ids from being written into older DSP/Topaz servers without mapping the active fork.

The combat proc itself is server driven, not a charge/enchantment DAT mechanic. DAT editing is only needed for client-owned identity/presentation such as name, description, icon, equip metadata, or custom descriptive text.
