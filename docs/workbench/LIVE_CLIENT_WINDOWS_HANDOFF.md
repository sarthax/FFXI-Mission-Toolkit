# Windows test handoff and Codex access

Development continues in GitHub/cloud. A Windows FFXI/Ashita session supplies
runtime evidence that Linux CI cannot produce.

## Codex access on the Windows test machine

This cloud chat has no attached Windows shell, SSH or RDP tool. Enabling RDP or
SSH on Windows alone does not give this session a callable remote connection.
There is no remote-access switch for the existing chat.

The supported immediate option is a separate Codex CLI or IDE session running on
the Windows test machine. See the [official CLI quickstart](https://github.com/openai/codex#quickstart)
and [Windows documentation](https://developers.openai.com/codex/windows).
With Node.js/npm installed, open PowerShell and run:

```powershell
npm install -g @openai/codex
git clone https://github.com/sarthax/FFXI-Mission-Toolkit.git
cd FFXI-Mission-Toolkit
codex
```

If the checkout already exists, use that directory and update it to `main`
without discarding local changes. In Codex, choose **Sign in with ChatGPT**.
This creates a local session, rather than attaching it to this cloud conversation.
Keep its task scoped to collecting read-only test evidence and reports; cloud
branches and CI remain authoritative for implementation.

Suggested local-session task:

> Read addons/workbench_live/README.md and this Windows handoff. Inspect the
> installed framework metadata and help collect read-only recording acceptance
> evidence. Do not change game position/speed, client memory or server data.
> Let the operator perform game movement and login/logout. Produce JSONL and a
> runtime report with exact commands, errors and expected/observed behavior.

Return the resulting artifacts to the cloud session for analysis. Local CLI
installation itself does not establish FFXI adapter compatibility.

## Produce an offline runtime report

Python 3.11+ can generate a report on either Windows or the cloud host. The report
validates an immutable recording snapshot, hashes those same bytes, summarizes
cadence/zone/instance transitions, targets and raw axis ranges, and optionally
parses PE version resources and SHA-256 hashes. It never executes or loads DLLs
into a process, sends network requests or verifies a running game image.

In the repository checkout:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e . pefile
.\.venv\Scripts\python -m workbench.runtime.live_client.runtime_report `
  "C:\path\to\telemetry.jsonl" --game-version "30191204_1" `
  --binary "C:\path\to\Ashita.dll" --binary "C:\path\to\Ashita-cli.exe" `
  --output "runtime-report.json"
```

Substitute actual paths. `--binary` is optional and repeatable; without it, pefile
is unnecessary. `--game-version` is operator-reported evidence. Output defaults
to stdout; `--output` creates a new file and rejects existing files. Recording
input is limited to 16 MiB/10,000 frames; each optional binary is limited to 64 MiB.

The report never turns a version string, matching hash, successful decode or
observed zone transition into a supported-build or lifecycle-verification claim.
Share the JSONL, report and relevant command/error notes; reports do not contain
the binary files or their full local paths.

## Remaining runtime acceptance

1. Start with a distinct explicit exporter ID. Record movement and a zone change.
   Note whether export continues or safely stops on unavailable observations;
   if it stops, preserve the message and restart after loading completes.
2. Log out and back in. Record any stop message, then explicitly start a fresh
   export. Confirm the player/zone/target belong to the intended character.
3. Unload while exporting and verify the file stops growing and remains decodable.
4. If two authorized instances are available, use different exporter IDs and
   verify separate output files and independent characters/targets.
5. Upload recordings into cloud replay; check seeking, target details, selected
   trace planes and waypoint/path downloads. Same-host live polling and verified
   map/heading transforms remain additional tests.

## Supplied-file identity evidence

The user supplied Ashita-cli.exe and Ashita.dll after a successful recording with
reported game version `30191204_1`. Both PE resources report file/product version
`4.0.0.2`, machine `0x014c` (x86). Exact metadata is retained in
[`ashita_supplied_binary_metadata.json`](../../tests/fixtures/live_client/ashita_supplied_binary_metadata.json).
The binaries are not stored in the repository. These are supplied-file identities;
they do not prove that those exact images were loaded during the recording.

## Inventory report coverage

The same report command accepts selected-target, inventory and legacy recordings.
`recording.entity_observation_summary` lists frame counts by declared scope,
truncated-frame count, entity-count distribution, total observations and optional
nonzero server-ID coverage. Legacy frames remain `unspecified`; their contents do
not establish target roles or complete inventory. Zero/absent IDs both remain unknown.

`distinct_entity_observations` now counts observed adapter/version, zone/instance,
client index, optional reported server ID and name combinations. It separates
same-slot/name observations with different reported IDs without claiming distinct
verified game entities. Missing instance identity stays unknown. Summary flags for
target roles, complete inventory and server identity remain false. A recording with
no truncation is not proof of complete world coverage or verified runtime support.

## Entity diagnostics acceptance (addon 0.2.0-experimental)

Use the existing read-only `/wblive start <unique-id> inventory` command with the
latest addon. Capture known NPC/mob/player targets, ordinary targeting and an
active subtarget, then switching/deselecting. Compare observed slots/names/reported
server IDs and target roles with independent runtime evidence. Record raw type,
status and spawn flags without assigning meanings from names or numeric guesses.

Missing optional getters should yield unknown fields/roles. A present getter with
invalid output or a source/context change must stop safely without appending the
rejected frame. Test logout, zone loading, unload and explicit restart with a new
file; if available, test two sources independently. Record source revision and
actual loaded Ashita/game version. The older supplied zone-50 capture verifies
neither these new fields nor their target-role semantics. No packet capture or
native game-write test is enabled by this slice.

## Passive packet acceptance (addon 0.3.0-experimental)

Copy the new workbench_packets.lua helper as described in the addon README. Start
telemetry, then separately run `/wblive packets start event_emote`. Perform a known
emote and an NPC event; stop packets and telemetry before returning both JSONL
files. Record actual loaded versions/source revision, commands, performance and
exact errors. Compare direction, byte length, e.data original bytes and hook-time
flags with an independent capture; do not assume final wire delivery or blocking.
Verify excluded chat/opcodes, bounded-rate/drop reporting, source stop/unload,
restart into a new file, and two-client isolation when available. Existing Capture
import and decoder are the cloud analysis path; packet writes are not enabled.

### Zoning recovery test package — 0.4.0 experimental

Replace all four Ashita Lua files together after `/wblive stop` and
`/addon unload workbench_live`; use the Ashita entry point as `workbench_live.lua`.
Reload `/addon load workbench_live` and start only after the player is fully available:

```text
/wblive start test-d inventory-zoning
/wblive status
```

Walk through one ordinary zone boundary. Preserve messages and the JSONL. Expected
successful evidence is both zones in one file. A player/entity name mismatch pauses
rather than records; at most one retry/second, a 30-second deadline and two coherent
original-identity samples in the same zone gate resumption. Gaps remain explicit.
Default/`inventory` modes do not enable recovery. Inactive party, changed identity,
invalid/unsupported API data, backwards clock, storage errors or deadline stop safely.
If Not exporting after loading, preserve the error and explicitly start a new file.
Do not restart while Paused or relax checks for slow zoning.

Then log out normally; observed inactivity must stop export. Relogin does not restart
stopped exports; start `test-e inventory-zoning` only after stable login. Return all
files, exact pause/resume/stop messages, zone/action sequence and loading duration.
Include installed addon and loaded framework/game versions. Packet streams stop on
pause and do not auto-resume; packet tests require a fresh telemetry recording.
Cloud tests pass, but zoning/relogin behavior and unobserved lifecycle boundaries
remain Windows verification requirements. No game commands or writes are added.

### Offline packet/telemetry evidence candidates

After stopping both exports, add `--packet-observations "C:\path\to\packets-telemetry-....jsonl"`
to the runtime report command. Preserve the telemetry filename: packet `source_recording`
refers to its filename stem. Renaming or anonymizing either source can prevent matches.
The existing Capture source validator checks the complete packet file (4 MiB/10,000
records maximum). No Capture database is created or changed, and no competing decoder
is introduced; upload that same packet file to Capture for canonical packet inspection.

Candidates require an exact declared recording label, client ID, adapter, reported
version, zone and timestamp, with exactly one eligible telemetry frame. Gaps and
ambiguous frames are left unmatched; there is no interpolation. The report retains
packet line/byte offsets and telemetry frame numbers, hashes both supplied byte
snapshots, counts unmatched observations, and limits candidate details to 1,000 entries.
These are temporal research candidates only. Filename labels do not prove recording
identity, packet timestamps have one-second resolution, packet instance identity is
absent, and clocks, server IDs, wire contents, opcode meanings and causal relationships
remain unverified. The original player recording has no accompanying packet export;
this report path is cloud-tested synthetically and still needs paired Windows evidence.

For packets already imported into an existing Toolkit Capture, add both
`--capture-database "C:\path\to\toolkit.sqlite" --capture-id 123` (use the actual
Capture database and ID). This opens the explicitly selected database read-only;
it never creates a database, imports packets, migrates schemas or changes rows.
Only the report's retained temporal candidates are checked (maximum 1,000).
An exact source SHA-256 plus line/byte span must identify one locator, and its
stored raw packet bytes, hook metadata and producer provenance must match the
same immutable supplied packet snapshot. Matching candidates include a relative
`/captures/<id>/packets/<seq>` link to the existing Toolkit packet view. Duplicate
imports remain ambiguous; absent or changed evidence has no link. Missing databases,
unsupported schemas and bounded lookup timeouts fail before report output.
An imported-packet link proves stored source correspondence only; it does not
verify runtime client identity, packet semantics, clocks, instances or causality.

Successful Test D now establishes four recovered zone transitions in one recording,
with five-second gaps matching supplied pause/resume messages. The first failed run
remains unresolved. Next Windows acceptance: observed logout/relogin must stop and
require explicit restart; record long-zone timeout behavior and populated normal
 target/subtarget roles. Preserve exact stop messages and version evidence. Passive
packet fidelity is a separate paired telemetry/packet test. A runtime report now shows
bounded gap details and raw diagnostic-field coverage; neither metrics nor successful
zone transitions establish a supported build or complete lifecycle compatibility.
