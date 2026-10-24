# Local acceptance tooling (synthetic only)

Reusable harnesses from the 2026-10 acceptance sprints (#1348). Nothing here touches a real
DSP/Valhalla/production database, XIHeadless or gameplay. Run from a throwaway worktree of the
candidate under test; never from a live checkout.

| File | Purpose |
|---|---|
| `make_b20_fixtures.py` | Generates 20 synthetic B20 paired-reviewer cases (+ `MANIFEST.json`) and checks each against the real `inspect_paired_readiness()`. |
| `b20_browser_driver.js` | Console driver: selects a fixture pair in the real viewer, inspects, records POSTs and result text. |
| `selected_jobs_setup_db.py` | Builds a synthetic schema and a SELECT-only user in an isolated MariaDB. |
| `selected_jobs_accept.py` | 31 checks of the selected-jobs route against that DB (errors, `DB_PORT`, cleanup, read-only audit via `general_log`). |

## Isolated database recipe (Windows)
1. `mariadb-install-db.exe --datadir=<scratch>\dbdata --password=` (never the live datadir).
2. `mariadbd.exe --no-defaults --datadir=<scratch>\dbdata --port=3398 --bind-address=127.0.0.1 --skip-name-resolve --console`
   Confirm the live service port (3306) is not the one you start.
3. Write a random password to `.synth_pw` (never print it), then run `selected_jobs_setup_db.py`.
4. From the candidate checkout: `TOOLKIT_CHECKOUT=. PYTHONUTF8=1 python selected_jobs_accept.py`.
5. Stop the instance (`Get-NetTCPConnection -LocalPort 3398 -State Listen | Stop-Process`) and delete the datadir and `.synth_pw`.

## Browser technique notes
- Sandbox mode: set `MISSION_TOOLKIT_TEST_DATA_DIR`; strip `MISSION_TOOLKIT_SUPERVISOR_*` for scratch servers.
- Serve fixtures from an untracked `gui/static/<dir>` in the throwaway worktree.
- Hook `window.fetch` to hold or record POSTs; capture the original before any reload.
- Attach files with `DataTransfer` plus a `change` event. The B20 viewer sits in `<details id="sd-readiness-handoff">`.

## Windows cleanup
- Use `core.autocrlf=false` in worktrees; remove them with PowerShell `cmd /c "rmdir /s /q <path>"`, then `git worktree prune`.
- Delete temporary PR refs with `git update-ref -d refs/tmp/pN`.
- Run tests with `PYTHONUTF8=1 PYTHONPATH=src:.:test_fixtures`.
