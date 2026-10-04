# Weapon Effects feature status

Implemented in this slice:

- structured additional-effect fields and row generation;
- always-on and latent/conditional row bundles;
- elemental damage, drain, Dispel, self-buff, absorb-status, death, and scripted/NM-specific presets;
- lineage capability classification and fail-closed write gating;
- existing-row recognition and summaries;
- local server-agent handoff exports and self-buff implementation contract;
- regression coverage proving generated rows fit the Item Editor's existing staged effect payload shape.

Not part of this slice:

- changes to DSP/Topaz/LSB server code;
- a new save/write endpoint;
- direct staging UI buttons for presets.

The related preset UI is intentionally a follow-on adapter to the existing Effects tab. It should stage rows into the existing atomic save path rather than duplicate it.
