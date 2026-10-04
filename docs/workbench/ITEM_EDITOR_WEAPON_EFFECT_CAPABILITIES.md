# Item Editor: server effect capability registry

The Weapon Effects model now has a read-only lineage capability registry for configured DSP, Topaz, and LandSandBoat server trees.

## Purpose

The registry answers two separate questions before the UI stages weapon-effect rows:

1. Can this effect be represented with the existing `item_mods` / `item_latents` row bundle?
2. Does the selected server lineage actually have a known handler family for that behavior?

The result remains fail-closed:

- `row-only` — the existing row bundle is considered safe to stage through the Item Editor's existing `stagedEffects` collections and `/itemedit/validate` → `/itemedit/save-atomic` path.
- `verify-lineage` — rows can be previewed/exported, but must not be auto-staged until the selected fork is verified.
- `server-code-required` — generate a local-agent/server handoff instead of pretending SQL alone implements the behavior.
- `unsupported` — block the effect.

## Source probing

`weapon_effect_capabilities.probe_server_tree()` inspects expected source files and known dispatcher markers without modifying the checkout.

For LSB it looks for the modern additional-effect dispatcher in:

- `scripts/globals/additional_effects.lua`
- `xi.additionalEffect.attack`
- `xi.additionalEffect.procFunctions`
- the `SELF_BUFF` handler family

DSP/Topaz probes use the legacy `ITEM_ADDEFFECT_*` definitions and treat proc-numbering compatibility as unverified until the active fork is inspected.

A textual match is evidence only. `self_buff_support()` deliberately returns `handlerVerified=false` even when a requested status name is present, because the editor still cannot infer stacking, overwrite rules, target semantics, duration/power interpretation, or battle-message behavior from a name match.

## Preset staging contract

`preset_plan()` produces:

- target lineage;
- proc type and label;
- capability state;
- exact modifier rows;
- `mods` vs `latents` target collection;
- readable summary;
- server handoff metadata;
- explicit `rowsSafeToApply` decision.

This keeps a future Weapon Effects preset panel thin: it should consume the plan and append only `row-only` rows to the existing staged effect payload. It must not add a second save endpoint or bypass current backup/journal/validation behavior.
