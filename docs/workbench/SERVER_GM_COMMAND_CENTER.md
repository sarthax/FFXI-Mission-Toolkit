# Server → GM Command Center — operator and implementation guide

> **Current status (2026-10-18):** Searchable command catalog, parameter/ID lookup, favorites, history, presets, targeted player selection, native Ashita **opt-in Send to game**, and high-privilege confirmations are implemented on Toolkit `main`. Sending requires configured local native plugin controls and actual server GM authorization. The original slices below are preserved as historical development notes; earlier “no command transport” descriptions are superseded by **Send to game** and **Workflow features**.

For current global status and remaining acceptance gaps, consult [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md). The legacy no-transport statements below are dated milestones, not current limitations.

## Current operator workflow

1. Select the intended local server profile; open **Server → GM Command Center** and verify the command catalog is from that checkout.
2. Choose a category/command, set optional Target player, and fill fields with supported lookup results and Lua-derived hints.
3. Review the generated command and use **Copy** by default. Favorites, History and Presets are stored in this browser, not the server.
4. Only on an authorized test client, enable the documented native/plugin options and check GM privileges before using **Send to game**. High-privilege commands require an additional confirmation.
5. Verify game/server response independently; a client-side typed command is not proof that the operation succeeded. Maintain records for state-changing commands.


## Slice 1: Local command catalog (implemented)

`workbench.server_admin.gm_commands.catalog` reads the Lua command metadata
from the selected **local** DSP-Valhalla checkout at `scripts/commands/*.lua`.
It does not import or execute Lua. It extracts command names, descriptions,
permission values and parameter signatures; it marks all commands as
`execution_enabled=false`. Only `getmobaction` and `checklocalvar` receive
`diagnostic_candidate` labels, which are **not** permission grants or proof of
read-only behavior on every server revision.

Verified reference repository: `sarthax/darkstar-to-valhalla`, branch `main`,
`scripts/commands` (134 entries at initial inspection). This catalog is
read from a local checkout, not directly from GitHub at runtime. Future UI must
show which configured checkout and branch/version the catalog represents.

## Historical proposed next slices (superseded in part)

1. Server module page with searchable catalog, source links, selected server
   profile and copy-only command preview (no execution).
2. Opt-in Toolkit→Ashita command transport with explicit user confirmation,
   bounded allowlist and controls tied to active client/session identity.
3. Validate server-side GM authorization, command response mode and exact
   transcript correlation on a test server; show parsed responses as
   *observations*, not authoritative spawn-state verdicts.
4. Separate and explicitly review state-changing commands (warps, spawn,
   inventory, mission progression); provide previews, audit history and
   risk-specific confirmation, never silently execute them.

The existing Ashita addon's GM response capture remains separate. No server
source modification is required for the planned GM path.

## Slice 2: Browser (historical implementation milestone)

The Server sidebar now links to `/server/gm`, a searchable, copy-only GM command browser. `/server/gm/commands` lists metadata read from the active local server checkout. At this historical stage, no game command submission endpoint existed; see current Send to game section. If the server root is missing or lacks `scripts/commands`, the page reports the catalog error. The page extends the shared `workbench_page.html` shell (top navigation) via `gui/templates/server_gm_commands.html`.

## Categories, usage and ID lookup (2026-10-15)

- Each command carries `category`, `usage` (parsed from the command's own `!name <req> {opt}` help line) and `params`
  (`label`, `required`, `type` from the `parameters` string, `lookup` kind). Categories come from an explicit name map in
  `catalog.py`; unmapped commands land in "Other".
- `GET /server/gm/lookup?kind=&q=&limit=` searches the active server's own tables (item, keyitem, title, effect, spell,
  zone, mob, npc) by name or id prefix. IDs are read, never invented. Key item IDs come from the active server's
  `keyitems.lua` because they drift between LSB and Topaz/DSP.
- The page has category tabs, a left command list, and a right entry pane with per-parameter inputs, ID pickers, a live
  preview and Copy. At the time of this milestone, "Send to game" was disabled; native command transport has since been implemented (see below).

## Send to game

The page can type a built command into the game chat through the native Ashita plugin (`POST /live-client/native/chat`). It is double opt-in and off by default:

1. The plugin must be online (`allow_file_commands=1`).
2. `config/workbench_native/settings.ini` must contain `allow_chat_commands=1`. A stock Ashita/server install has no such file or line; add both. The installer writes a commented template but never overwrites an existing file.
3. The character must have GM permission on the server. Replies appear in game chat.

Only single-line `!` commands (ASCII, no `;`, max 128 chars) are accepted; the plugin re-validates every line. The browser asks for confirmation before sending.

## Workflow features (2026-10-15/16)

All of this state is per-browser (localStorage); nothing is stored on the server.

- **Target player** (`gmc.tgt`): one field at the top fills every `player` parameter. A blank leading optional `{player}`
  is omitted so the command's own argument shift applies (`!setplayerlevel 75`, not `!setplayerlevel 0 75`). Other
  blank middle arguments are still sent as `0` with a warning.
- **Enumerable dropdowns**: currency (from `char_points` columns) and quest/mission log ids (from `log_ids.lua`) via
  `/server/gm/lookup` kinds `currency`, `questlog`, `missionlog`. Per-log quest/mission ids are not covered yet.
- **Favorites and history** (`gmc.fav`, `gmc.hist`): star a command; the last 40 sent/copied lines are kept with their
  field values.
- **Presets** (`gmc.pre`): named, ordered lists of command lines ("Add to preset"), with Send all for instant
  character builds.
- **Pull from 3D viewer**: clicking an entity in the zone viewer publishes `wb.viewer.selection`; position/mob/NPC
  fields can fill from it.
- **Hints and ranges**: parsed from each command's own Lua validation (`level < 1 or level > 99`, `must be between`
  error text), never guessed. Out-of-range values show a warning.
- **Permission badge**: commands with permission 3+ (for example `!exec`, `!reloadglobal`) show "high-privilege" and
  require an extra confirmation before Send.
- **Feature Trace** button on each command opens `/features/trace?q=<command>`.
- Theme: the page uses the app's `--surface/--border/--accent` tokens, so it follows light/dark mode.
