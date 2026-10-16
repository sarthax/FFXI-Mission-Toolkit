# Server → GM Command Center — implementation roadmap

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

## Next slices

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

## Slice 2: Browser (implemented)

The Server sidebar now links to `/server/gm`, a searchable, copy-only GM command browser. `/server/gm/commands` lists metadata read from the active local server checkout. No game command submission endpoint exists. If the server root is missing or lacks `scripts/commands`, the page reports the catalog error. The page extends the shared `workbench_page.html` shell (top navigation) via `gui/templates/server_gm_commands.html`.

## Categories, usage and ID lookup (2026-10-15)

- Each command carries `category`, `usage` (parsed from the command's own `!name <req> {opt}` help line) and `params`
  (`label`, `required`, `type` from the `parameters` string, `lookup` kind). Categories come from an explicit name map in
  `catalog.py`; unmapped commands land in "Other".
- `GET /server/gm/lookup?kind=&q=&limit=` searches the active server's own tables (item, keyitem, title, effect, spell,
  zone, mob, npc) by name or id prefix. IDs are read, never invented. Key item IDs come from the active server's
  `keyitems.lua` because they drift between LSB and Topaz/DSP.
- The page has category tabs, a left command list, and a right entry pane with per-parameter inputs, ID pickers, a live
  preview and Copy. "Send to game" stays disabled: no command transport exists (the native plugin only does warp/speed).

## Send to game

The page can type a built command into the game chat through the native Ashita plugin (`POST /live-client/native/chat`). It is double opt-in and off by default:

1. The plugin must be online (`allow_file_commands=1`).
2. `config/workbench_native/settings.ini` must contain `allow_chat_commands=1`. A stock Ashita/server install has no such file or line; add both. The installer writes a commented template but never overwrites an existing file.
3. The character must have GM permission on the server. Replies appear in game chat.

Only single-line `!` commands (ASCII, no `;`, max 128 chars) are accepted; the plugin re-validates every line. The browser asks for confirmation before sending.
