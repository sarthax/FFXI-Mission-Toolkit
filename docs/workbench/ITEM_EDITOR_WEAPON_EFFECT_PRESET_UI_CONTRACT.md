# Item Editor weapon-effect preset UI contract

The browser-facing Weapon Effects panel should be a thin renderer over `weapon_effect_ui_contract.py` rather than duplicating proc numbering in JavaScript.

## Behavior

- Show the source-backed preset catalog for the active lineage.
- Include all eight elemental-damage variants plus drain, Dispel, absorb-status, self-buff, death, and NM/scripted behavior presets.
- Show only fields relevant to the selected proc type.
- Auto-stage rows only when `rowsSafeToApply=true` / capability is `row-only`.
- Route `verify-lineage` and `server-code-required` cases to the server handoff instead of adding SQL rows.
- Support always-on `mods` or conditional `latents` using the existing staging collections.
- Do not create another save endpoint. Staged rows must still pass `/itemedit/validate` and `/itemedit/save-atomic` so current backup, journal, validation, and undo behavior remains authoritative.

## UI actions

A preset card should expose:

1. preset selector;
2. active-lineage capability badge;
3. chance / damage / element / status / power / duration controls as applicable;
4. optional latent condition + parameter;
5. generated-row preview;
6. **Stage rows** only for row-safe plans;
7. **Server handoff** for all other plans.

The UI contract deliberately keeps self-buff fail-closed even on LSB. A specific self-buff status must be verified in the active server handler before direct row application is enabled.
