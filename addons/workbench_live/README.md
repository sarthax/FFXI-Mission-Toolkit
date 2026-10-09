# Experimental read-only client observation export

This addon source is **not a verified native FFXI adapter**. Cloud tests execute
its Lua 5.1 code against synthetic SDK/API data and exercise the toolkit's real
JSONL decoder. No actual game build is approved by those tests.

The exporter uses public observation interfaces, has no memory offsets, and
has no game write functions. It starts only after an explicit command, samples
at most once per second, and writes a new bounded JSONL file in its addon folder.
It stops on invalid fields, identity changes, unavailable interfaces, backwards
clock changes or the 16 MiB limit. Existing export files are retained. Player
and selected-target observations remain distinct from inferred server identities.

## Ashita v4 test installation

1. In the authorized Windows/Ashita test environment, create an Ashita addon
   folder named `workbench_live`.
2. Copy `workbench_observation.lua`, `workbench_export.lua` and
   `workbench_packets.lua` into that folder.
3. Copy **`workbench_live_ashita.lua` as `workbench_live.lua`** in that folder.
   The repository's `workbench_live.lua` is the alternative Windower entry point;
   do not use it in Ashita.
4. Load using `/addon load workbench_live`.
5. Once logged in, start with `/wblive start ashita-test-a`. Each launcher instance
   must have its own distinct ID. `/wblive status` shows whether export is active;
   `/wblive stop` closes the export.

The addon prints the new `telemetry-<id>-<time>-<suffix>.jsonl` path. The source
labels its client version `unverified-ashita-v4-api`. Coordinates and heading
are the SDK's raw local-position/heading values; units and map transforms require
real verification. Selected target observations are exported with kind `unknown`; when the published
subtarget-state getter is available, both target and subtarget are distinguished.
Missing targets produce an empty entity list in selected-target mode.
There is no OS process discovery, memory-layout validation or write adapter.
Ashita v3 compatibility has not been established.

The zone comes from the local player's party slot (`GetMemberZone(0)`), checked
again after sampling. Ashita's SDK documents entity `ZoneId` as only populated
for the local player under certain conditions; it is not required for player or
selected-target observations. If an older copy reports "entity zone does not
match player zone", replace `workbench_observation.lua`, unload the addon with
`/addon unload workbench_live`, and load it again before starting a fresh export.

## Windows acceptance run

Record the actual Ashita version, FFXI game/module version and module SHA-256
metadata in the test report; do not upload game binaries or credentials.

- Confirm loading alone creates no export. Start explicitly, move normally, turn,
  and select/deselect a known NPC or player. Check coordinates, heading and target
  identity against independent runtime observations.
- Record at least a minute, then stop. Upload the JSONL through the cloud
  Workbench's **Client → Live Client → Open recording** controls. Check playback,
  seeking, last-frame behavior and the relative trace. Ashita recordings initially
  use X/Y; select X/Z or Y/Z to inspect the other raw axes. Uploading the same
  recording twice should create independent sessions.
- Verify a normal zone transition, loading/logout, source unload and missing
  observations. A transient invalid SDK observation intentionally stops export;
  explicitly start a fresh export after logging in/loading finishes. No invalid
  frame should overwrite the last-good observation.
- If two authorized client instances are available, use distinct exporter IDs
  and verify character, target, zone and export-file isolation.
- Report exact commands, source revision, framework/game versions, expected and
  observed behavior, JSONL parsing results and any printed stop errors. A successful
  source test does not prove calibrated maps or memory-write compatibility.

For real-time file-feed testing, the Workbench must run on a host able to read
that file. Its optional local file-feed Settings use the printed file path and
instance ID; **Poll file feed** reads appended frames. A cloud Workbench cannot
implicitly read a remote Windows filesystem. Offline JSONL upload is the cloud
validation path until an explicit network transport is implemented.

## Windower alternative

Use the repository's `workbench_live.lua` plus both helper modules in a Windower
addon folder named `workbench_live`. Explicit commands are `//wblive start <id>`,
`//wblive status` and `//wblive stop`. The source reads player and t/st/pet
observations through Windower APIs and reports an unverified build. This alternative
has only synthetic cloud coverage and is not the selected Ashita validation target.

## Cloud regression

Install test dependency `lupa`, then run:

```sh
.venv/bin/python -m pytest -q tests/test_live_client_ashita_source.py tests/test_live_client_windower_source.py
```

Dedicated Live Client Regression CI installs Lua 5.1 bindings and executes these
source-to-file-feed tests alongside the replay and Chromium UI regressions.
All addon implementation here is original MIT-licensed toolkit code. The reference
SDK/API sources and their distinct licenses are documented in
`docs/workbench/LIVE_CLIENT_NATIVE_RESEARCH.md`; their implementation is not bundled.

## Runtime evidence received

An authorized user confirmed that recording succeeded after the PR #698 zone-field
fix and supplied 121 observations spanning 120 seconds in zone 50. Both the strict
recording loader and file-feed decoder accepted every frame. The capture includes
movement, changing raw heading and eight distinct selected targets. An anonymized
copy now exercises replay and the Chromium viewer in cloud regression.

The user reported game version `30191204_1` and walking up/down stairs without
changing zones. Later supplied Ashita-cli.exe/Ashita.dll both report PE version
`4.0.0.2`; their exact hashes are recorded as supplied-file evidence. This does
not verify the images loaded during capture. This is partial runtime evidence,
not a supported-build declaration. Zone transitions, logout,
multiple clients, coordinate calibration and same-host live polling still need
acceptance evidence. The source remains read-only and explicitly unverified.

In the replay console, enter a name and download the observed player or target
position as a waypoint. **Download path to current frame** exports all consumed
recorded observations, rather than the downsampled trace. These JSON downloads
preserve raw coordinates and unverified source provenance; they do not warp the
client or place entities in a zone database.

Use **Save player to library** or an entity row's **Save to library** to keep a
named raw observation on the toolkit host. The Waypoint library section supports
name/zone filtering, rename/delete and portable JSON import/export. Saved points
remain after recordings are unloaded and the host restarts. Import appends
independent entries and preserves the existing library if validation fails.

See the [Windows/Codex test handoff](../../docs/workbench/LIVE_CLIENT_WINDOWS_HANDOFF.md)
for local test-agent setup and the offline runtime-report command. The report
collects recording summaries and optional binary metadata without executing
client binaries or declaring a supported running build.

### Selected-target identity

Ashita observations optionally retain the published `IEntity:GetServerId` value
as `server_entity_id`, separate from `client_index`. Missing getter or zero keeps
identity unknown; invalid values or target changes during sampling stop export.
The getter mapping is cloud-tested with synthetic Lua interfaces and requires
Windows validation. It does not establish server/database correlation or entity
kind. Existing recordings remain compatible; no client writes are enabled.

### Experimental bounded Ashita inventory

Use `/wblive start <unique-instance-id> inventory` to opt into additional named
entity-slot observations. `/wblive start <unique-instance-id>` retains selected-
target mode. Stop before changing modes. Inventory is Ashita-only and read-only.

The range 0–2303 follows the pinned Ashita v4 `petinfo`/`chamcham` addon examples,
not guessed offsets. Each sample queries that bounded range and retains at most
32 entities, including the selected target first. The player, duplicate target,
nil slots and blank names are excluded. `entities_truncated` marks when another
named slot exists beyond the cap. This is a subset, not a complete world census.
Kinds remain unknown; no instance, packet, or server-database identity is inferred.
Existing one-second sampling, file/line limits and explicit stop/restart remain.

New frames retain `observation_scope` and `entities_truncated`; the Toolkit console
shows the bounded scope and truncation. Old recordings retain unspecified scope.
Getter failures, invalid data, changed observed identities or player/zone changes
stop export without appending the rejected frame. Cloud Lua/decoder/browser tests
passed; actual enumeration bounds and behavior on your Windows client remain
unverified. When testing later, collect an inventory recording with a selected
NPC/mob/player and note displayed names/counts, target switching, zoning and any
stop messages. You can perform this directly in Ashita without local Codex.

### Raw entity diagnostics and target roles

The existing start commands now collect optional published `IEntity:GetType`,
`GetSpawnFlags` and `GetStatus` values as `raw_entity_type` (uint8),
`raw_spawn_flags` and `raw_status` (uint32). Missing getters retain unknown values;
present getters returning invalid values stop the export before the rejected frame
is appended. Raw codes are not translated into NPC/mob/player kinds, liveness,
death or verified spawn/despawn events. They are shown in the existing entity table.

When `ITarget:GetIsSubTargetActive` is available, slot 0 is the ordinary target
while inactive; while active it is the subtarget and slot 1 supplies the original
target. `target_roles` retains one or both source-reported roles; overlapping
slots produce one entity with both roles. Without that getter, the existing slot-0
observation remains available with unknown role. Target mode/index, entity/name/
reported-ID and player/zone checks reject mixed samples. Instance identity stays
unknown. Target/subtarget observations precede inventory slots and share the same
32-entity cap. No extra exporter or competing schema was introduced.

These mappings are source-backed and cloud-tested, not validated on the user's
Windows installation. The pinned APIs and reconciliation matrix are in the
[reference audit](../../docs/workbench/LIVE_CLIENT_REFERENCE_AUDIT.md#reconciliation-with-ashita-capability-research--2026-10-09).
For the next Windows run, record normal targeting, a subtarget selection, target
switches and inventory near known NPCs/mobs/players; report raw values and exact
stop messages. Keep addon revision, actual loaded framework/game build and server
context in the test notes. Older recordings replay with unknown raw fields/roles.

### Optional passive packet observations (Ashita only)

After explicitly starting telemetry, separately enable the narrow packet profile:

```text
/wblive start ashita-test-a inventory
/wblive packets start event_emote
/wblive packets status
/wblive packets stop
/wblive stop
```

This profile observes incoming `0x034` (existing Toolkit event evidence) and
`0x05A`, and outgoing `0x05D` (the pinned Ashita example's emote packets). Other
IDs are filtered before reading payloads; there is no all-packet/chat/login profile.
This is not comprehensive packet/event capture. Packet enablement is independent
of ordinary telemetry enablement, but requires its active recording identity.

The addon reads only `e.data`, not modified buffers, raw pointers or chunk bytes;
it never modifies packet events, injects or blocks packets. Direction, original
hook bytes, hook-reported opcode/length, UTC-second timestamp, sequence, zone,
source recording/client identity, cumulative rate drops and hook-time injected/
blocked flags are retained. Flags and original hook bytes do not prove final wire
traffic or final blocking; builds and opcode semantics remain unverified.

Limits: 10 accepted observations per second across directions, 1024 bytes per
packet, 4096 bytes per line, 4 MiB and 10,000 observations per packet file. Rate
excess is dropped/count-reported; malformed observations, identity/context changes,
backwards clocks, storage errors and file/count limits stop packet export. Telemetry
stop/failure and addon unload also stop it. Stopping packets leaves telemetry active.
A stopped packet file is preserved; starting another requires a fresh telemetry
recording, preventing overwrite and stale source identity reuse.

Stop capture, then upload the printed `packets-telemetry-…jsonl` file through the
existing Capture **Add Files** workflow, or include packet files in a normal Capture
source folder/archive. Upload `telemetry-…jsonl` separately to Live Client replay.
Capture recognizes packet content, validates the whole bounded source, and writes
canonical raw-packet rows with SHA-256/line/byte-offset locators. Existing Packet
Viewer/decoder/correlation services remain authoritative. Unknown opcodes remain
unknown, and hook-reported/header opcode or size disagreements are retained in
source details rather than silently corrected. Normal source rebuild is supported
when the original file remains available under existing Capture policies.

Cloud Lua/Capture tests do not verify these hooks on Windows. The next runtime
trial should use a known emote and NPC event, compare original hook bytes/direction/
length against an independent Capture source, and record framework/game/addon
revision, source stop messages and performance. No local Codex is required.

### Inventory runtime evidence and zoning stops

Supplied tests A/B validate 30 frames in Bastok Markets (zone 235) and 24 in North
Gustaberg (107), with 1,035 nonzero reported entity IDs and no reported truncation.
One client performed additional zoning, combat, logout and relogin, but neither file
contains those transitions or explicit target roles. Runtime export coverage improves;
loaded-build compatibility, complete inventory, diagnostic/role fields, catalog ID
agreement, packet fidelity and lifecycle continuity remain unverified.

The current exporter stops at the first invalid/transitional sample rather than
writing mixed or stale data. After zoning or relogin, check `/wblive status`; if it
is not exporting, capture the exact Workbench Live stop message and explicitly run
`/wblive start <unique-id> inventory` again once the player is fully available.
Keep each preserved file and the messages before/after the transition. This is
manual recovery guidance, not validated automatic resume or uninterrupted zoning.

The test-B screenshot confirms the addon was already loaded, export started, and
`workbench_observation.lua:85: player identity mismatch` stopped further samples
before later-zone messages. “Addon is already loaded” reflects a duplicate load
attempt, not failure of the active exporter. The identity guard must remain intact;
the underlying cause needs a stable post-zone retry and observed identity evidence.
