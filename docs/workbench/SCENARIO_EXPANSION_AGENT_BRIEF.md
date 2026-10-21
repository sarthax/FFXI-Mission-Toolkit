# Scenario expansion: git-agent brief

Goal: grow `data/testing/feature_test_readiness.json` and `data/testing/test_specifications.json` from 2 runnable cases (MOG-09, INV-OBS-01) to a ranked, source-backed set across every domain, WITHOUT running anything live.

## Ground rules
- Work only from committed repo files and the DSP source on the `valhalla` remote. No live DB, no bots, no GM commands.
- Never invent IDs (key items, items, csids, mob ids, char_var names). Cite file:line in the DSP Lua/SQL for every ID and every expected value. If the source does not show it, write `UNKNOWN` and list it under blocking_gaps.
- Expected values must come from an oracle (SQL/Lua you cite), never from memory or a wiki alone.
- Do not edit runner code, supervisor code, or the GUI. Spec/data/docs only.
- One PR per domain, branch `spec/<domain>`, never merge; the owner merges.

## Per-case record (extend the existing schema, do not fork it)
id, kind (positive|negative|persistence|observation), title, setup (fixture needs), action (read-only or the exact GM/command), oracle (source citation + computed expectation), readback (which table/endpoint proves it: `char_inventory`, `chars.keyitems`, `char_vars:<name>`, GM info text), mutation (none|gm|client), run_mode, blocking_gaps, estimated_effort.

## Classify every case into one lane
1. **observe-now**: read-only, readable by existing supervisor endpoints (`test-character-inventory`, `-keyitems`, `-vars`). Highest priority.
2. **needs-readback**: needs a new fixed-query supervisor endpoint (name the table and columns).
3. **needs-mutation**: needs GM/client actions; owner approval per case.
4. **needs-deploy**: feature branch not on the live server.

## Domains and starting points
- gardening (GARD-01..09), voidwalker (VWK-01..07), assault_nyzul (ASLT/NYZ), missions_quests (MQ-01..05), moghancement (MOG-01..14, only MOG-09 done): existing planned cases; add oracle + readback + lane to each.
- Not yet in the readiness file: voidwatch (`data/voidwatch/*`, `docs/voidwatch/`), salvage (`data/salvage`), campaign (`data/campaign`, parked), chocobo raising (issue #1129), run/geo unlock quests (`data/run_geo`). Propose cases, same rules.

## Deliverables
1. Updated readiness/spec JSON per domain.
2. `docs/workbench/SCENARIO_COVERAGE_<domain>.md`: lane table, oracle citations, UNKNOWN list.
3. A ranked list of the first 10 observe-now cases across all domains (value x effort).
Run `PYTHONPATH=".;src" py -3.11 -m pytest -p no:cacheprovider test_fixtures -q -k "readiness or specification"` before each PR.
