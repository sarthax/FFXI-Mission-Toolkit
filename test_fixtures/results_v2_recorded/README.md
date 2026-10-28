# Recorded MOG-09 reports (test fixtures)

Two real MOG-09 reports from the disposable test characters, copied **unchanged** from the sanitized samples in
PR #1420 (account names and local paths were replaced there; character names and ids are test characters and were
kept, which the owner confirmed is not personal data). They are the importer's input format (`schema_version 1`).

| File | Run | Recorded verdict |
|---|---|---|
| `mog09_fail_obs-20261021T025326Z.report.json` | `obs-20261021T025326Z` | FAIL: client bag 8 rows and Safe 1 row, persisted rows 0 on four polls |
| `mog09_pass_obs-20261021T040036Z.report.json` | `obs-20261021T040036Z` | PASS: same scenario, persisted rows 9 |

These are runner-reported, unauthenticated receipts: a PASS here is a recorded verdict, never independent gameplay
proof, and nothing in the tests re-runs anything. Do not edit the values; tests assert what the page shows for them.
Their sanitized copies deliberately hash differently from the originals held on the operator machine.
