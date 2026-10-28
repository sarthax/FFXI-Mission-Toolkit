# #1409 — Typed action library (implementation)

`workbench.server_admin.feature_testing.typed_action_library` is the machine-readable registry behind the
phase-1 crosswalk ([SCENARIO_SUITE_TYPED_LIBRARY_1409.md](SCENARIO_SUITE_TYPED_LIBRARY_1409.md)) and the
phase-2 guard ([SCENARIO_TYPED_LIBRARY_CONTRACT_1409.md](SCENARIO_TYPED_LIBRARY_CONTRACT_1409.md)). It is data
plus validation: it **never** dispatches an action, calls a server or GM command, emits a packet, reads a
database or promotes a verdict.

## What is in it
Twelve reviewed templates (the crosswalk's rows, in the same order): ten Headless `action + expectation` pairs
(`navigate_near`, `talk_to_npc`, `inspect_npc`, `advance_event`, `finish_event`, `wait_for_state`, `recover_hp`,
`invite_party`, `accept_party_invite`, `engage_target`) and two Toolkit readbacks (`read_inventory`,
`read_progression`). Each has a human label, structured parameter specs (name, type, range), the native
Headless `do` / `expect` keys, the crosswalk's source reference and stated limits, and a support tier.

| API | Purpose |
|---|---|
| `list_templates()` / `get_template(id)` | Stable-order copies of the templates |
| `export_registry()` | Versioned (`toolkit-typed-action-library/1`), deterministic, JSON-serializable |
| `check_param(spec, value)` | `None` if the value fits the spec, else a short reason |
| `build_step(id, action_value, expectation_value)` | A native `{"do": {...}, "expect": {...}}` **draft** after validating both values; `ValueError` names the template and parameter |

## What it does not establish
- `HEADLESS_SCHEMA_ONLY` means the native key and parameter shape match the pinned XIHeadless schemas
  (`NATIVE_SCHEMA_HEAD`). It does **not** mean the runner dispatches it or that it proves anything in game.
- A built step has `oracle_status: UNAPPROVED`, `verdict: UNKNOWN`, `execution_enabled: false`. An action, a
  state readback and an oracle remain three different things; packet opcodes are never used to infer behavior.
- `TOOLKIT_READBACK_ONLY` templates point at real, authenticated, SELECT-only supervisor routes
  (`/api/supervisor/test-character-inventory-v2`, `/api/supervisor/test-character-progression`). They have no
  native Headless pair and `build_step` refuses them.
- Parameter values are shape-checked, not looked up: an NPC or entity ID is not verified for any zone.

## Drift protection
`test_fixtures/test_typed_action_library_1409.py` checks the registry against the merged crosswalk fixture
row for row (ids, labels, tiers, native keys, source references, limitations) and against the reviewed guard on
200+ valid and invalid values (the library accepts exactly what the guard recognizes, including single-precision
overflow, NaN, booleans-as-integers and malformed walk targets).

## Not included
Editor pickers and the Given/When/Then preview (#1411, shared editor paths), importing native scenarios (#1410),
and any runner or preflight work (#1412, #1255).
