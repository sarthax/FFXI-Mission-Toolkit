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

## Presets the editor can expose

The framework includes named presets that expand to explicit modifier rows instead of hiding the underlying data:

- Fire damage
- Ice damage
- HP drain
- MP drain
- TP drain
- Dispel
- Self buff
- Absorb status
- Instant death
- NM-specific scripted behavior

Each effect also receives a lineage capability badge:

- `row-only` — the selected lineage has the modern row-driven handler for this proc type;
- `verify-lineage` — the data model exists, but the target DSP/Topaz/fork implementation must be checked before writing type ids;
- `server-code-required` — the editor can model the desired behavior and generate a handoff, but server Lua/C++ must be added or extended;
- `unsupported` — the proc type is unknown to the framework.

This is intentionally fail-closed. Modern LSB proc-type numbers must not be written into DSP/Topaz merely because the logical effect name is the same.

## Self-buff framework

Self-buffs are represented as a structured handoff rather than pretending SQL alone is sufficient. A blueprint carries:

- proc chance
- client battle subeffect
- status-effect id
- power
- duration
- target = attacker/self
- stacking/overwrite behavior requirement
- lineage-specific server reference
- local-agent implementation checklist

For current LandSandBoat, the relevant upstream path is:

`https://github.com/LandSandBoat/server/blob/base/scripts/globals/additional_effects.lua`

The useful implementation points are `xi.additionalEffect.attack`, `xi.additionalEffect.procFunctions`, and the `SELF_BUFF` handler. Current LSB explicitly handles **Blink** and **Haste** in that handler. Blink first checks for existing Blink/Copy Image shadows before applying; Haste currently applies through `attacker:addStatusEffect(...)` with a TODO upstream to verify power/duration/tier/overwrite details. That is exactly why the Toolkit requires the server implementation to declare stacking behavior rather than assuming it.

For LSB the blueprint can safely emit the modern row bundle (`SELF_BUFF=12`) as reference/configuration data, but it still marks the effect `server-code-required` when the requested status is not implemented by the handler.

DSP must be treated differently. Its archived enum/reference file is:

`https://github.com/DarkstarProject/darkstar/blob/master/scripts/globals/status.lua`

That file documents the legacy `ITEM_ADDEFFECT_TYPE` mapping as `1=status/damage/HP drain`, `2=MP drain`, `3=TP drain`, `4=dispel`, `5=self-buff`, `6=instant death`. Modern LSB uses a larger proc-type enum where `SELF_BUFF=12`. A DSP self-buff blueprint therefore carries modern rows only as a reference shape and marks them **not safe to apply** until the local agent maps the logical effect to the target server's actual numbering.

The local server agent should perform this sequence for a new self-buff:

1. identify the active server lineage and exact additional-effect dispatcher;
2. verify that lineage's proc-type numbering;
3. add or verify the desired status branch in the self-buff handler;
4. define stacking/replacement behavior explicitly;
5. call the lineage's status-effect API on the attacker/self;
6. return the correct additional-effect subeffect/message tuple;
7. add a focused server regression covering chance, power, duration and stacking.

The Toolkit helper `build_self_buff_blueprint()` produces this handoff data directly so the Equipment Editor can show both the SQL-side configuration and the server work still required.

## Additional enhancement opportunities

The same framework can support several useful editor capabilities without touching core server code:

- preset picker that expands to visible modifier rows;
- raw/structured toggle so expert users can inspect exact mod ids;
- always-on vs latent/conditional storage toggle;
- lineage capability badge (`row-only`, `verify-lineage`, `server-code-required`);
- effect summary such as `20% chance: Fire +25` or `25% chance: self Haste, 45s`;
- existing-effect recognizer that converts raw `item_mods` rows back into structured fields;
- validation that blocks unsupported proc ids rather than silently writing them;
- local-agent handoff export for self-buffs and other scripted effects;
- future server-code references for absorb-status, instant-death, and NM-specific proc handlers.

## What this does not mean

These rows configure behavior that the selected server lineage already implements. They do **not** create arbitrary new combat semantics. If a proc type is absent from the target DSP/Topaz/LSB combat scripts/core, a local server-code change is still required.

## Client DAT boundary

The combat proc itself is server driven and is not a charge/enchantment DAT feature. Existing battle subeffects can be displayed by the stock client. DAT editing is only needed when changing client-owned item identity/presentation such as item name, description, icon, equip metadata, or a custom textual description of the effect.

## Intended GUI pass

The Item Editor should render this as a dedicated **Weapon Effects** panel rather than mixing it into the normal MOD/augment list:

- preset / custom mode
- proc type
- proc chance
- subeffect / battle presentation
- base damage or amount
- element
- status id / power / duration when applicable
- always-on (`item_mods`) vs conditional (`item_latents`)
- latent condition and parameter
- lineage capability badge
- explicit warning when the selected effect requires lineage-specific server code
- generated local-agent implementation handoff for scripted effects

The implementation helper lives at `src/workbench/editors/items/weapon_effects.py`. It builds and recognizes the row bundles but intentionally leaves live writes to the Item Editor's existing backup/journal/validation path.