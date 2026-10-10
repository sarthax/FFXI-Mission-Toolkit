# Key Items — operator guide and implementation status

Updated: 2026-10-10. Source of truth: merged `main` code and `docs/workbench/ROADMAP_CURRENT.md`.

## Where to start

Open **Server → Key Items** (`/keyitems`). The catalog displays client key-item IDs, names and descriptions alongside server-enum readiness. Use the search and readiness filter to find a specific item or inspect missing/drifted mappings. Select **Inspect** on an item for details and Lua references.

## Source identity and status

When the active server profile is **DSP**, the primary mapping is resolved against exactly one configured checkout enum source at `scripts/globals/keyitems.lua` or `scripts/globals/key_items.lua`. DSP constants are shown **without** a `tpz` namespace; `ZERUHN_REPORT` is an example of a bare source constant. LSB and Topaz are **reference lineages**, not proof of active DSP values.

- **Clean**: a unique normalized DSP constant matches the client name **and** numeric ID.
- **Drifted**: the normalized name resolves uniquely, but the numeric ID differs. Do not substitute the client ID in DSP scripts.
- **Missing**: no exact normalized source-name match. A similar spelling is not automatically treated as an alias.
- **Source unavailable / ambiguous**: a source file is missing/unreadable, multiple source paths are found, or duplicate definitions/reused numeric IDs prevent reliable identity. These are **not** clean matches.

DSP catalog health reports the enum source path, definition and unique-name counts, ambiguous names and reused IDs. Select the appropriate server profile in Settings if the DSP health panel indicates the wrong checkout. A clean mapping proves an enum correspondence, **not** that a script path runs successfully in-game.

## Lua source inspector

Select a key item, then the **Lua references** inspector. Choose a lineage: **DSP (active)** for the configured DSP checkout, or reference LSB/Topaz where available. Static discovery recognizes literal `hasKeyItem`, `addKeyItem`, `delKeyItem` and `npcUtil.giveKeyItem` calls in supported namespaces, including bare DSP constants. The results distinguish **require**, **grant** and **remove** operations.

Filter by operation; results are grouped by Lua file with counts, exact source paths, line numbers and excerpts. Expand a script for individual evidence. **Copy location** copies a `path:line`; **Copy script evidence** copies the operations, citations and Lua statements in that script group. **Find in Feature Trace** searches by filename: it is a research handoff, **not** a guaranteed direct jump to a canonical implementation or execution trace. Mission/quest/NPC/zone labels are inferred from source paths and do not establish runtime execution.

The DSP inspector uses a **persistent, incremental SQLite Lua-reference index** stored in the toolkit data area, not the DSP checkout. Unchanged files are reused; edited files are refreshed; deleted-file references are pruned following a complete scan. Root isolation prevents mixing different checkouts. The first scan may take longer. Results are bounded/truncated when scan or reference limits are reached. The scanner omits commented-out literal calls, but may miss dynamic, numeric, multiline or helper-generated behavior; verify important claims in source and with runtime/capture evidence.

## Read-only safeguards and validation

This module inspects client catalog entries, server enums, code and recorded evidence. It does **not** grant/revoke key items or edit character ownership. Avoid treating a successful CI run as proof of local DSP compatibility.

**Local smoke test**: (1) select the DSP server profile and confirm the catalog-health source path; (2) search for a known DSP key item; (3) compare its displayed constant and ID with the checked-out enum; (4) open Lua references, filter grant/require/remove and copy a source citation; (5) alter a *test checkout* Lua file and verify that the incremental index reflects changed/deleted calls; (6) switch profiles to confirm the references are not mixed. Leave production scripts unchanged.

## Implementation ledger

Merged main PRs: **#868** (DSP identity), **#875** (bare DSP Lua references), **#880** (catalog health), **#881** (collision protection), **#883** (Lua block comments), **#889** (DSP constant labels), **#891** (per-item evidence reasons), **#896** (incremental persistent index), **#899** (source/Feature Trace handoff), **#900** (path-derived research scope), **#902** (per-file groups), **#905** (operation summaries), **#910** (source-line summaries), **#911** (copy grouped evidence). Other earlier Key Items foundations predate this list.

### Remaining work

- [ ] **Local DSP acceptance**: compare current client and active DSP checkout data, exercise edge cases and track mismatches with reproducible evidence.
- [~] **Exact identity aliases**: investigate missing names and introduce explicit, reviewed aliases only if sourced and unambiguous (no fuzzy auto-match).
- [~] **Lua coverage**: identify additional verified DSP helper/call patterns; avoid asserting runtime relationships from static mentions.
- [~] **Deep navigation**: link source citations to exact Feature Trace, NPC, quest and mission entities only when the destination can be resolved unambiguously.
- [ ] **Performance and index health**: measure large-checkout indexing, surface freshness/truncation diagnostics and recovery controls where useful.

Keep this guide, the in-tool Help, and the current roadmap updated together when Key Items capabilities change.
