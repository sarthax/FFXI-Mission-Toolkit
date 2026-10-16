# GM diagnostics on an unmodified server

**Default Stage 3 path: no DSP source changes or native exporter required.**

Verified against `sarthax/Topaz-to-Valhalla` `release`:
`scripts/commands/getmobaction.lua` registers `!getmobaction {mobID}`
with `permission=1`; it uses `GetMobByID(mobId)` and reports the
mob's current action ID to the GM. When no ID is passed it uses the
cursor target. The command is observational; it does **not** establish
that a mob has or has not spawned in a particular instance.

`entity_gm_diagnostics.gm_entity_diagnostic_plan` builds conservative,
copyable manual commands for verified DSP mob IDs only. It deliberately
does not send commands via Ashita, issue chat text automatically, grant GM
rights, or present unverified LSB/Topaz commands as supported. The server
build and permission must be checked before use.

## Manual workflow

1. Inspect a live entity in the 3D Viewer and obtain its **global server ID**, not an Ashita client slot.
2. For a mob on a confirmed compatible DSP/Topaz server, copy
   `!getmobaction <global-id>` into in-game chat as a GM.
3. Record the printed action ID (or failure), zone, observed time and
   the instance context, if known.
4. Correlate with the Toolkit's server spawn configuration, Lua spawn
   conditions, Ashita observations and Feature Trace evidence.
5. Keep server runtime classification **unknown** unless independently
   supported by an authoritative source. In particular a failed command
   may mean an invalid ID, command permissions or missing instance context.

## Architectural decision

The earlier native snapshot reader, writer and provider are optional
experimental infrastructure, not dependencies for the core diagnostics.
Future work should expose copyable GM actions in the 3D inspector and
a structured GM response capture/evidence dossier; avoid any server binary
modifications. Existing GM command inventory must be checked against the
*actual* deployed build rather than assumed from a source branch.
