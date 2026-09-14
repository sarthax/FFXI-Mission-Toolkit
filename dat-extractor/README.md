# dat-extractor

Standalone tool for reading FFXI client `.DAT` files directly — no GUI, no manual XML export.
Built by porting the relevant parsing algorithms out of [POLUtils](https://github.com/Windower/POLUtils)
(the same tool behind every dialog-table XML export used in this project) into a small,
scriptable console app.

Requires the .NET 9 SDK (`dotnet --version` to check). Build once with `dotnet build`, then run
via `dotnet exec bin\Debug\net9.0\dat-extractor.dll <args>` (faster than `dotnet run`, which
re-checks the build every time).

## Commands

### Extract one file
```
dat-extractor <path-to-dat-file> [output.json]
```
Prints (or saves) every `{index, text}` entry in a dialog-table `.dat` file as JSON.

### Scan a whole ROM tree for matching text
```
dat-extractor --scan <romRootDir> [--min N] [--contains "text"]
```
Recursively checks every `.DAT` under `romRootDir` (e.g. the client's `ROM` folder) and reports
every one that parses as a valid dialog table. `--min N` (default 5) filters out tiny incidental
matches. `--contains "text"` only reports files containing that text (case-insensitive), printing
the matching lines inline. Scanning the entire `ROM` folder (~47,000 files) takes about 2.5
minutes. **This is the most reliable way to find something you know exists but don't have an
indexed ID for** — see the caveat on `--find-zone` below.

### Resolve a rom-file id to a physical path
```
dat-extractor --resolve <clientRootDir> <fileNumber> [fileNumber2 ...]
```
FFXI's DAT files are indexed by a "file number" via `VTABLE(n).DAT`/`FTABLE(n).DAT` files in each
`ROM(n)` folder — the same lookup POLUtils' own dropdown UI uses internally. Given one or more file
numbers, resolves each to its real `ROM<n>\<dir>\<file>.DAT` path and reports whether it parses as
a dialog table.

### Dump a string table (area names, region names, etc.)
```
dat-extractor --strings <path.dat> [--contains "text"]
dat-extractor --strings <clientRootDir> <fileNumber> [--contains "text"]
```
Reads FFXI's "offset string table" format (used for area names, job names, region names — file
numbers 55465/55467/55654 respectively) and prints every `{id, text}` entry. Useful for looking up
what a numeric area/region ID actually means.

### Find which dialog-table file(s) belong to a named zone
```
dat-extractor --find-zone <clientRootDir> <mappingsXmlPath> <zone name substring>
```
`mappingsXmlPath` is POLUtils' own `ROMFileMappings.xml` (in this repo checkout at
`PlayOnline.FFXI.Utils.DataBrowser\ROMFileMappings.xml`) — the same index its language/expansion/
zone dropdowns are built from. Resolves the XML's numeric area-name references via the AreaName
string table, matches against your search text, and resolves each hit's `rom-file id` to a
physical path.

**Caveat, found while testing**: `ROMFileMappings.xml`'s DialogTables category doesn't appear to
list every dialog-table file for a given zone — testing "Whitegate" found 8 real, correctly-tagged
files (multiple languages/expansions), but none of them were the specific Drahbah/Chochoroon/
appraiser file that `--scan --contains "appraise"` found directly. The index seems to cover a
*subset* of each zone's dialog content, not the exhaustive set. Treat `--find-zone` as a fast
first pass to narrow things down, but fall back to `--scan --contains "<known phrase>"` when you
need to be sure you've found everything, or need a specific file you can't locate via the index.

### Browse/search the full category tree (like the GUI's dropdown menus)
```
dat-extractor --tree [--client <clientRootDir>] <search text>
```
Loads POLUtils' `ROMFileMappings.xml` and `Messages.resx` — both embedded directly in this tool,
no external file paths needed — and resolves the *entire* category tree the GUI's menus are built
from (Dialog Tables, Images, Item Data, MobLists, String Tables, all languages/expansions), not
just the DialogTables area-name subset `--find-zone` covers. Search text matches against any
resolved label at any level (a category name or a leaf's name); matching a category prints every
file under it. `--client` additionally resolves `area-name`/`region-name` references in the
DialogTables category (needed for zone labels) — omit it to browse everything else (all the
String Tables / Item Data / MobLists category labels resolve from the embedded XML alone, no
client needed).

Example: `dat-extractor --tree "Area Names"` reproduces exactly what the screenshot's `String
Tables > English > Area Names` menu path shows, plus the French/German/Japanese/Alternate/Search
variants the GUI's submenus also have.

### Extract by rom-file id, auto-detecting the format
```
dat-extractor --extract-id <clientRootDir> <romFileId> [output.json]
```
Resolves the id, then tries each supported parser (DialogTable, DmsgStringTable,
OffsetStringTable, MobList, ItemData, in that order) until one succeeds. This is the natural
pairing with `--tree` — search for a label, take its `rom-file id`, extract it, without needing to
know ahead of time which format that particular entry uses.

**MobList** (`Menu:MobLists` category) gives `{id, name}` for every monster/NPC in a zone — verified
against Ilrusi Atoll's list: id `17002497` → "Percipient Fish", matching the mob ID already wired
into this project's own `Ilrusi_Atoll/IDs.lua`.

**ItemData** (`Menu:ItemData` category) gives `{id, name}` for items — only id + name are extracted,
not the full stat block (level/jobs/races/damage/etc. — the format encodes those too, per item
type, just not parsed here). Verified against several IDs already used in this project's Lua:
`605` → "Pickaxe", `739` → "Orichalcum Ore", `2278` → "??? Ring", `2286` → "??? Box" — all exact
matches.

**DmsgStringTable** (`Menu:Missions` / `Menu:Quests` categories, magic header `"d_msg"`) gives
`{index, text}` for mission/quest log entries — e.g. the "Aht Urhgan" missions table decodes real
titles like "Land of Sacred Serpents", "Immortal Sentries", "President Salaheem". POLUtils
actually has three distinct `d_msg` sub-formats (`DMSGStringTable`/`2`/`3` in its source, differing
header layouts); only variant 3 is ported here, identified by manually walking a real file's bytes
against all three candidate headers until one matched end-to-end. If a `d_msg` file fails to parse,
it may be using variant 1 or 2 instead — not ported, would need the same treatment.

**XiStringTable** (magic header `"XISTRING"`) covers "Time-Related Terms + Pronouns", "In-Game
Messages (2)", and "POL Messages" — the last remaining unrecognized formats after a full sweep of
every category under the GUI's "String Tables" menu.

### String Tables category coverage

Ran every category under `String Tables > English` (26 total, per the GUI's own menu) through
`--extract-id` to check real-world coverage, not just assume format similarity within the menu:

| Format | Categories |
|---|---|
| `OffsetStringTable` | Area Names (+Alternate), Region Names, Job Names, Race Names, Character Selection, Chat Filter Types, Day Names, Directions, Equipment Locations, Error Messages, In-Game Messages (1), Menu Item Descriptions, Menu Item Text, Moon Phases, Status Names, Various (1)/(2), Weather Types |
| `DmsgStringTable` | Missions, Quests, Ability Names, Ability Descriptions, Spell Names, Spell Descriptions, Key Items, Titles |
| `XiStringTable` | Time-Related Terms + Pronouns, In-Game Messages (2), POL Messages |
| Not text (icon graphics) | Statuses — out of scope, see below |

25 of 26 categories now extract correctly. The 26th, "Statuses," turned out to be a ~3.75MB file
with a header that doesn't match any text format — almost certainly status-effect *icon* graphics
(distinct from "Status Names", the text labels, which already works fine) — out of scope since
image/texture formats aren't ported here.

## What's not built yet

Image/texture formats (`Menu:Images`, and whatever "Statuses" turns out to be) and audio are both
out of scope for now. Also not ported: the full ItemData stat fields beyond id/name (level, jobs,
races, damage, etc. — the byte layout is known, just not parsed into fields yet).

## Source files

- `Program.cs` — all commands and parsers (`DialogTableParser`, `OffsetStringTableParser`, the
  VTABLE/FTABLE resolver).
- `src/FFXIEncoding.cs` — FFXI's custom text encoding, copied unmodified from POLUtils (it's
  already GUI-free).
- `src/Element.cs` — small enum FFXIEncoding needs for decoding elemental-symbol markers.
- `ConversionTables/*.dat` — binary lookup tables FFXIEncoding needs, copied unmodified from
  POLUtils, embedded as resources at build time.

`<CETCompat>false</CETCompat>` is set in the `.csproj` to work around a .NET 9 / Windows CET
(hardware shadow stack) compatibility crash (`AreShadowStacksEnabled()` assert) — without it the
tool crashes immediately on every run on this machine.
