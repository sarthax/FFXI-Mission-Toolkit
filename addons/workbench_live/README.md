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
2. Copy `workbench_observation.lua` and `workbench_export.lua` into that folder.
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
real verification. Only the player's current selected target is exported as an
entity, with kind `unknown`. Missing targets produce an empty entity list.
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
