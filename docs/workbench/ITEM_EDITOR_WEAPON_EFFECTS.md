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

## What this does not mean

These rows configure behavior that the selected server lineage already implements. They do **not** create arbitrary new combat semantics. If a proc type is absent from the target DSP/Topaz/LSB combat scripts/core, a local server-code change is still required.

The helper therefore treats the mature portable legacy cases (damage, debuff, HP/MP/TP drains, dispel) as row-configurable and flags newer/special handlers such as self-buff or NM-specific behavior for lineage verification / server-code handoff.

## Client DAT boundary

The combat proc itself is server driven and is not a charge/enchantment DAT feature. Existing battle subeffects can be displayed by the stock client. DAT editing is only needed when changing client-owned item identity/presentation such as item name, description, icon, equip metadata, or a custom textual description of the effect.

## Intended GUI pass

The Item Editor should render this as a dedicated **Weapon Effects** panel rather than mixing it into the normal MOD/augment list:

- proc type
- proc chance
- subeffect / battle presentation
- base damage or amount
- element
- status id / power / duration when applicable
- always-on (`item_mods`) vs conditional (`item_latents`)
- latent condition and parameter
- explicit warning when the selected effect requires lineage-specific server code

The implementation helper lives at `src/workbench/editors/items/weapon_effects.py`. It builds and recognizes the row bundles but intentionally leaves live writes to the Item Editor's existing backup/journal/validation path.