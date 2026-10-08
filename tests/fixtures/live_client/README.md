# Ashita v4 runtime regression capture

`ashita_v4_runtime_anonymized.jsonl` derives from an authorized user-provided
recording after the conditional entity-zone fix (PR #698). The user reported
successful capture in FFXI with Ashita v4. It contains 121 consecutive observations
one second apart, spanning 120 seconds in zone 50, including eight distinct
selected-target identities across 35 frames; 86 frames have no selected target.

Player/client names and target names are replaced; target indices are consistently
remapped and timestamps shifted to start at 1000. All coordinates, headings,
zone values, frame order and target-presence transitions are retained. The
original uploaded file is not committed.

This evidence establishes successful observation export and cloud decoding for
one reported runtime. It does not establish exact client-build compatibility,
zone transitions, logout/disconnect, concurrent clients, coordinate calibration,
entity/server-ID matching, process detection or write support. In follow-up the
user reported FFXI client version `30191204_1`, confirmed walking up/down stairs
and no zone change, and identified the AshitaXI/Ashita-v4beta project. The exact
installed Ashita files were subsequently supplied for offline metadata inspection:
both report file/product version `4.0.0.2`. Their SHA-256 hashes and x86 PE machine
are recorded in `ashita_supplied_binary_metadata.json`; binaries are not committed.
The game version is user-reported evidence and supplied-file identity is not a
verified running-build identity or allowlist entry.

Raw X/Y spans are approximately 118/109, while Z spans 6. The replay viewer
initially selects X/Y for the experimental Ashita source and permits X/Z and
Y/Z without modifying recorded coordinates or assuming a calibrated map.
