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

The Server sidebar now links to `/server/gm`, a searchable, copy-only GM command browser. `/server/gm/commands` lists metadata read from the active local server checkout. No game command submission endpoint exists. If the server root is missing or lacks `scripts/commands`, the page reports the catalog error. This first UI pass is standalone HTML; shared-shell visual integration may be refined later.
