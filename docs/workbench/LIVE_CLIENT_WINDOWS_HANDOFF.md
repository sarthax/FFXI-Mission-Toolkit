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
