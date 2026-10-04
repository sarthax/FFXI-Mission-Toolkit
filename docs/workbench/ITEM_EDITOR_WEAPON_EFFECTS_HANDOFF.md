# Local server-agent handoff: weapon additional effects

Use this only when the Item Editor marks a requested effect `verify-lineage` or `server-code-required`.

1. Confirm active server lineage and its `ITEM_ADDEFFECT_TYPE` numbering.
2. Trace the melee additional-effect dispatcher used by the target fork.
3. For self-buffs, identify the self-buff proc handler and status-effect API.
4. Add only the requested status/effect semantics, including stacking, overwrite, immunity, duration, power, and battle-message/subeffect behavior.
5. Add a focused server regression for proc chance and effect semantics.
6. Once verified, update the Toolkit lineage capability table so the editor can safely move that effect from handoff-only to row-only where appropriate.

Reference points:

- LSB: `scripts/globals/additional_effects.lua`, `xi.additionalEffect.attack`, `xi.additionalEffect.procFunctions`, and the `SELF_BUFF` handler.
- DSP: archived `scripts/globals/status.lua` documents legacy additional-effect numbering; verify the actual target fork dispatcher before changing SQL.
- Topaz: treat DSP-era semantics as a starting point only; verify the active fork/version before enabling row-only writes.
