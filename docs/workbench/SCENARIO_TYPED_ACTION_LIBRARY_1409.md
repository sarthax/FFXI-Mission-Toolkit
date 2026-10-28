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

## Picker hints
Parameters that are IDs in the DSP catalog carry an optional `picker` hint (`npc` on `talk_to_npc` and
`inspect_npc` `npc_id`; `zone` on the `wait_for_state` `zone` check). The Scenario Developer's typed step builder uses it
to offer a search over the existing local DSP catalog (`/scenario-developer/catalog/search`). Picks are
*unreconciled source candidates*: they fill an ID field that stays editable, the step records where the value came
from, and it is never presented as verified for a particular zone or client. A hint never changes which values are
valid.

## Independent actions and checks (#1411)
The library also lists its **10 actions** and **8 checks** separately (`list_actions()`, `list_checks()`); each was
reviewed on its own, and the 12 templates only fix which were reviewed *as pairs*. A native step may therefore be an
action only (`do`), a check only (`expect`), or both, each holding exactly one reviewed key. All 80 action/check
combinations pass review; only the 10 reviewed pairs carry a `template_id`. Whether the XIHeadless runner accepts a
single-sided step is not verified here.

## Saved with a draft: `native_steps`
A draft may carry one optional top-level field, `native_steps`: `{"library_version": 1, "steps": [...]}` with 1 to
50 steps. `validate_native_steps()` (called from `validate_spec`) requires every stored step to be reviewed-supported,
names to be unique with no surrounding whitespace, and allows an optional `note` (1 to 300 characters of plain text,
for provenance). No other field is allowed, and nothing is trimmed or ignored. The field is excluded from
`base_spec_sha256` (like `contract_v2`), so editing steps never invalidates recorded v2 fingerprints, and drafts without
it hash exactly as before. Drafts must still be `design_only` with an unassigned runner: the field never makes a draft
executable or published. Fifty maximum-size steps use about 28 KB of the 32 KiB draft cap; the existing cap still
applies. A draft that uses the field cannot be opened by an older checkout.

### Add Action Step / Add Check Step (#1411)

The builder's step-type list has three groups: the reviewed action+check pairs, every reviewed action on its own
(10) and every reviewed check on its own (8). Choosing one side shows only that side's inputs. One-sided values are
validated by the server's native-JSON review (`/scenario-developer/typed-import`) rather than a second validator,
and the saved step contains only the side that was filled in (no empty `do`/`expect`). A one-sided step verifies
nothing by itself, and runner handling of one-sided steps is still unconfirmed (see the limits line shown in the UI).

### Export form and observed execution paths (#1457, #1459)

**Export.** XiHeadless `CheckStructure` requires `expect` to be an object, so the builder's exported JSON (Copy,
Download, the JSON panel) writes `"expect": {}` for an action-only step. The saved draft keeps the step one-sided,
and `validate_native_steps` still refuses a stored empty `expect`. Import reads `"expect": {}` next to a `do` back as
action-only; an empty `expect` with no action is refused, as the runner loader refuses it. A check-only step is
exported as is. The export's shape was checked against the rules recorded in the local verification
(`docs/workbench/SCENARIO_1411_LOCAL_VERIFICATION.md`, PR #1456) by a mirror in the node test, not by the real validator.

**Observed paths.** Each registry action and check carries `observed_paths`: whether the XiHeadless file loader and the
MCP `task_scenario_start` path accepted that key when the local verification fed it to them (at XiHeadless
`e5e8035071`), with the MCP rejection reason where there was one. At that commit the loader accepted all 18 keys (action-only only as
exported), and MCP accepted only `wait_ms`: other actions are rejected as `scenario_resource_actions_not_yet_supported`,
`invite`/`accept_invite` as `scenario_legacy_actions_not_supported`, and every check as
`scenario_expectations_not_yet_supported`. The builder shows this beside the chosen step type and on each step. It
is acceptance only: `execution_tested` is always false, and nothing here says the runner dispatches a key. The table is
a snapshot and goes stale if XiHeadless changes; a test pins the keys against the library so a new key cannot be added
without a decision about its row.

### Given / When / Then preview (#1411)

Under the step list the builder shows the steps as a reading: an action is a `When`, a check is a `Then`, and a
second action (or check) in a row is an `And`; an action after a check starts a new `When`. The wording is the
native key with underscores as spaces plus the value, so it adds no meaning of its own. `Given` is not derived from
the steps (it comes from the editor's Preconditions field), so the preview does not invent it. It is a rendering of
the draft: no result, oracle or verdict is implied, and step names are shown as text only.

### Editor wiring (#1411)

The Scenario Developer editor treats the builder as a view of `spec.native_steps` (stored as
`{library_version, steps}`). Opening, forking, cloning, creating or switching back from Advanced JSON loads the
draft's steps into the builder through the same server review used for pasted JSON; builder edits write
`native_steps` back and count as unsaved work. If the builder cannot show a draft's steps (library unavailable,
a step with an extra field such as `note`, a shape it does not recognise) it says so, disables adding, and the
saved steps are left exactly as they were. In Advanced mode the JSON text is the document and the builder is
read-only: the builder's own handlers refuse edits (not only the browser's `inert`) and a note says why. The lock follows the
mode on every document replacement, so opening, forking or creating a draft while Advanced is open returns to an editable builder. Builder provenance notes (which catalog row filled a value) are not saved with the draft.

## Reviewing native scenario JSON (#1411)
`review_native_steps(steps)` checks pasted native scenario steps (for example from an agent or a scenario file)
against the library without trusting them. Each step comes back as `SUPPORTED` (matches a reviewed action/check pair
and passes its parameter checks), `UNSUPPORTED` (well formed but outside what the library models: an unknown action
or check, neither `do` nor `expect`, more than one action or check, or any extra field such as `timeout_ms`), or
`INVALID` (malformed, or a value the template rejects), with reasons. A step with extra fields is **never trimmed
down** to fit; it is reported and not imported. The result is marked `UNREVIEWED_EXTERNAL_INPUT`: a passing step has
had its shape checked and nothing else, and nothing is accepted automatically. In the Scenario Developer's builder a
person ticks the supported steps to accept, and each accepted step records where it came from.

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
