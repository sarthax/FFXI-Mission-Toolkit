# Related proposal: Item Editor Weapon Effects preset UX

The structured weapon-effect model is intentionally separate from the current Item Editor Effects tab write path. The next UI slice should remain a convenience layer only.

## Proposed panel

Add a **Weapon Effects** card inside the existing Effects tab with:

- preset selector: elemental damage, HP/MP/TP drain, Dispel, debuff, self-buff, death, scripted/NM-specific;
- editable chance, amount, element, status id, power, and duration;
- always-on vs latent/conditional storage;
- active-lineage capability badge: `row-only`, `verify-lineage`, `server-code-required`, `unsupported`;
- generated-row preview before staging;
- **Stage rows** enabled only for `row-only` capabilities;
- **Copy server handoff** for everything requiring server verification/code.

The panel should insert generated rows into the existing `stagedEffects.mods` / `stagedEffects.latents` collections and then call the existing `rerenderEffects()` path. It must not add a second save endpoint or bypass `/itemedit/validate` and `/itemedit/save-atomic`.

## Why separate

`gui/static/itemedit_ux.js` is a shared, actively evolving Item Editor surface. Keeping this UI adapter in a small follow-on PR minimizes collision risk while the backend model can merge independently. No Auction House files are involved.
