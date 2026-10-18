# Live Client and 3D Zone Viewer — operator workflow

Current merged Toolkit includes Ashita Lua observation, optional native plugin control, multi-entity telemetry, live-client activity and a 3D Zone Viewer. It is intended for authorized development servers only. Use [delivery/acceptance ledger](LIVE_CLIENT_DELIVERY_ROADMAP.md) for status and [bridge architecture](LIVE_CLIENT_BRIDGE.md) for details.

## Observe before acting
1. Confirm the active server profile and which Windows FFXI client, native plugin and Ashita addon are actually running.
2. Open the Live Client bridge console and check client identity, heartbeat freshness, zone/instance and position. Stale or headless file-feed presence alone is not proof that each field is fresh.
3. Open 3D Zone Viewer; selecting a live client can load its current zone and center on the player. Confirm the geometry DAT set, instance, terrain placement and player coordinate orientation before interpreting other dots.
4. Compare server entities/spawns and streamed live entities as **different evidence sources**. A targeted entity versus nearby broadcast entities, conflicting names or duplicate IDs may require identity reconciliation.
5. Use the combat/dialog activity panel as a telemetry summary, not a guaranteed complete packet or event capture.

## Native control (optional and gated)
- Observe in read-only mode first. Native movement supports arming, explicit STOP/disarm, bounded compass/diagonal nudge, position/warp targets, speed and bookmarks in supported client builds. Commands are opt-in and version-dependent.
- Confirm the exact client, zone and intended test destination, the authorization and native channel state, and a route back before issuing a movement action.
- Check plugin acknowledgments **and independent server-side position** (for example authorized GM `!logpos` before/after), with no snapback. A client-local success does not prove server acceptance; `server_confirmed=false` must remain visible.
- Repeat STOP/disarm, zoning, logout, reconnect, two-client isolation and multi-zone axis/landmark trials before marking a setup accepted. Never treat 2D autonomous routing as complete merely because 3D direct movement works.
- The experimental native warp mode and file-channel convenience settings must not silently weaken default-off behavior. Never use on an unauthorized public server.

## Report a reproducible issue
Record Toolkit and addon/native versions, client build, server revision, zone and instance IDs, client identity, timestamps, coordinates in each coordinate system, action and acknowledgment, independent server observation and relevant capture IDs. Do not publish secrets or raw private captures.

Related: `addons/workbench_live/README.md`, `docs/workbench/LIVE_CLIENT_WINDOWS_HANDOFF.md`, `docs/workbench/LIVE_ENTITY_RECONCILIATION.md`.
