# Project Tako analysis and the native `warp` mode

Status: static analysis only (2026-10-11). Nothing here has been live-tested on the server yet.
Keep in sync with `LIVE_CLIENT_DELIVERY_ROADMAP.md` and `LIVE_CLIENT_THIRD_PARTY_CONTROL_RESEARCH.md`.

## Scope and method
- Subject: `C:\ValhallaXI\Project-Tako` (.NET WPF, standalone). Authorized local analysis for a private DSP/Topaz dev server.
- Method: `ilspycmd 8.2.0.7535` (installed into the session scratchpad; run under the .NET 8.0.11 runtime
  with `dotnet exec --fx-version 8.0.11`, because it asserts under the 9.0 runtime on this machine).
  Decompiled `ProjectTako.exe`, `.Core`, `.Memory`, `.Hooking`. Nothing of Tako was copied or modified.
- Explicitly NOT adopted: GM/wallhack/player-flag writes, `LoadLibrary` injection, external
  `WriteProcessMemory`, packet injection.

## How Tako works
- External process; reads/writes FFXI memory via `OpenProcess/ReadProcessMemory/WriteProcessMemory` (`WindowsAPI`).
- Finds client structures by signature scan from `Config/tako.pointers.json` (`ownpos`, `entityarray`,
  `autofollow`, `player`, `zoneinfo`, `party`, `mapbase`, ...).
- Not dependent on Windower; its Windower link is an optional shared-memory command/keyboard bridge.
  Struct names match Windower/Ashita because they describe the same client memory.
- Hooking DLL imports only `LoadLibraryA`/`FreeLibrary` (loader only).
- Navigation: `NavMeshManager` (`TryFindPath`, `Raycast`, `IsValidPosition`).

## Position override (the key finding)
`Player.SetPosition` builds a position struct (keeps current yaw/pitch/roll, replaces X/Y/Z) and writes it twice:

| Call | Address |
|---|---|
| `EntityManager.SetEditableMovement` | `entity.WarpPtr + 52` |
| `EntityManager.SetEditableMovement2` | `entity.WarpPtr + 1476` |

- It does NOT write `LocalPosition` (what our `local` mode writes). `WarpPtr` points at the entity model /
  "editable movement" object (Ashita `ffxi/entity.h:100` says the same), which the client movement code
  reads when reporting position to the server. Hypothesis: that is why Tako's moves are server-visible.
- Struct layout (memory order): `X, Height, Horiz, 1.0, Roll, Yaw, Pitch` floats (Ashita `position_t`: X, Z, Y).
- Tako commands: `setpos x y z` (passes args as x, z, y), `warp <entity name|<t>|player>` copies that
  entity's `LocalPosition` into the same struct, plus saved points and `MoveTo` (navmesh path).
- Speed: `SetMovementSpeed2` on the entity (`Player.cs` ~643; resets to 5.0 at ~653). Also `SetMovementSpeed`,
  `SetAnimationSpeed`, `SetHeading`.
- Autorun: `AutoFollowManager` / `AutoFollow{FollowDeltas, IsAutoRunning}` = the mechanism our adapter already uses.

## Ashita SDK mapping
| Tako | SDK |
|---|---|
| autofollow deltas / IsAutoRunning | `IAutoFollow` (used, live-tested) |
| LocalPosition (not Tako's route) | `SetLocalPosition*` (`local` mode, untested) |
| WarpPtr | `IEntity::GetWarpPointer(index)` (`Ashita.h:712`) |
| editable movement +52/+1476 | not wrapped; raw float writes by us (`warp` mode) |
| MovementSpeed2 | `IEntity::SetMovementSpeed2` (`Ashita.h:848`) - not yet exposed in our plugin |

SDK axes (zone 98 observation): SDK X = server x, SDK Y = server z (horizontal), SDK Z = server y (height).

## `warp` mode (implemented, untested)
- `/wbprobe movement enable warp DEV-SERVER-ONLY`, then `/wbprobe move <id> dx dy dz` (vertical allowed).
- Same safeguards as other modes: off by default, consent token, 2-min TTL, <=3 yalm per command,
  1 s rate limit, unique ids, character/zone binding, zoning/stale-state rejection, Stop, audit ring.
- Extra fail-closed checks in `SdkMovementPort::WriteWarpPosition`: warp pointer non-null, both structs
  readable (SEH-guarded), both within 2.0 yalm of `LocalPosition`, otherwise reasons
  `warp_pointer_null | warp_unreadable | warp_struct_mismatch | warp_write_failed` and nothing is written.
- `/wbprobe warpinfo` is a read-only dump of the pointer and both structs for discovery.
- Reports are always `scope=client_local server_confirmed=NO`; confirmation = `!logpos` / Toolkit telemetry.

## Open questions (answer only from live evidence)
1. Does `warpinfo` show both structs matching LocalPosition? If not, offsets differ on this client build.
2. After a 1-yalm warp does `!logpos` change, and does it persist after walking / zoning? (server-confirmed vs revert)
3. Are both structs required, or only +52?
4. Does speed override (`SetMovementSpeed2`) work and is it server-tolerated?

## Live result 2026-10-11 (zone 98, dev server, user screenshot)
- `warpinfo`: ptr=0x2C0F7D50; both +52 and +1476 readable and equal to LocalPosition (memory order x, height, horiz). Offsets valid on this client.
- `!logpos` before: (184.591, 33.162, 255.142). `move w1 1 0 0` -> `warp_written`; `!logpos` right after: (185.591, 33.162, 255.142).
  **Server-confirmed** +1 x. No snap-back after walking (later logpos 193.549, 33.999, 261.029).
- `move w2 0 0 1` (SDK Z +1) -> `warp_written`; character visibly sank ~1 yalm into terrain: server/!logpos Y is INVERTED (+Y = down),
  matching the CLAUDE.md rule. SDK Z delta must be negated for "up". Not yet followed by a `!logpos` on w2.
- Not yet tested: zoning after warp, large jumps (>3 yalm limit), speed override, `!checknav`-gated targets.


## Toolkit-driven warp, speed hold and enablement (built 2026-10-11, live test pending)

Status: host-tested only (adapter, control router, Python channel/API). **Not yet live-tested**: large-distance warps,
warps after zoning, speed value mapping, the file channel, and click-to-warp in the viewer.

### Enablement (default OFF, admin opt-in)
- Nothing is armed at load. The in-game `/wbprobe movement enable warp DEV-SERVER-ONLY` path still works.
- Persistent opt-in lives in `<Ashita>/config/workbench_native/settings.ini` (re-read every 2 s, except TTL/base speed which are load-time):
  ```
  allow_file_commands=1      ; lets the Toolkit arm/stop/warp/speed through command.txt
  auto_arm=warp              ; optional: arm at load and re-bind after every zone change (""/warp/autorun/local)
  enable_ttl_seconds=0       ; 0 = never expires (default 120)
  speed_percent=120          ; optional: hold this speed once armed (25..400)
  base_speed=5.0             ; MovementSpeed2 at 100% (verify with /wbprobe speed status)
  ```
- The `DEV-SERVER-ONLY` token is a consent literal only. **There is no server-identity check**: the plugin cannot tell
  a private dev server from any other. An allow-list (zone/server name or host) is the natural next step for other admins.

### Control channel (Toolkit -> plugin)
`config/workbench_native/{settings.ini, command.txt, status.txt}`; flat key=value. The plugin publishes a per-load `nonce`
in `status.txt` (~2 Hz); each command carries `seq` (epoch ms, strictly increasing), `nonce`, `ts_ms` (must be within 15 s),
and, for `enable`, `consent=DEV-SERVER-ONLY`. Commands: `enable`, `disable`, `stop`, `warp_to`, `speed`, `speed_off`.
Every command goes through the same MovementAdapter/SpeedOverride checks as the chat commands (binding, zoning, bounds, audit).
Result fields stay `scope=client_local`, `server_confirmed=NO`.

### Coordinates
Toolkit/viewer/commands use **server order** (what `!logpos` prints: x, y = height, z). The plugin converts once
(`ServerToSdk`: SDK = (x, z, y)). Viewer scene = (x, -y, -z), so server = (sx, -sy, -sz). Server Y is inverted: to raise
the character use a smaller Y (the viewer map-point pick applies a default 0.5 yd lift). Arbitrary map points are not
navmesh-checked: run `!checknav x y z` before treating one as valid.

### Speed override
`MovementSpeed2 = base(5.0) * percent / 100` (mapping unverified; compare with `!speed 120` via `/wbprobe speed status`).
Held at about 4 Hz while armed, so it survives zone changes; restored once on disarm/unload. Whether the server tolerates it is untested.
In game: `/wbprobe speed <25..400>|off|status`, `/wbprobe warp <id> <x> <y> <z>`.

### Live test steps
1. Unload the plugin, copy the new DLL (SHA-256 starts `033d5c3d7bc4c3e9`) over `plugins\workbench_native_probe.dll`, load it.
2. Create `config\workbench_native\settings.ini` with `allow_file_commands=1`.
3. `/wbprobe movement enable warp DEV-SERVER-ONLY`; `!speed 120`; `/wbprobe speed status` -> expect MovementSpeed2 about 6.0.
4. `/wbprobe warp t1 <x> <y> <z>` to a far point (copy from a mob spawn); verify with `!logpos`; walk and confirm no snap-back.
5. Zone and confirm the speed hold re-applies and (with `auto_arm=warp`) the plugin re-arms.
6. Toolkit 3D viewer: open the zone, "Native warp" panel, Arm, tick Pick target, click a spawn, "Warp to target", compare `!logpos`.
7. STOP / Disarm buttons; `/wbprobe movement audit` lists everything.

### Warp tab: compass nudges and navmesh pick (2026-10-11, not live-tested)
- Nudge buttons are N/E/S/W (+Up/Down): N = server +Z, E = +X, S = -Z, W = -X, per the viewer's documented compass (zone_plot2: rot 0 = East, 192 = North, world +Z north). Not yet verified against live `!logpos`.
- "Snap to navmesh" (default on) raycasts the loaded navmesh even when hidden, so a warp target can be picked with no entity present. Still run `!checknav x y z` before using a point in SQL.
