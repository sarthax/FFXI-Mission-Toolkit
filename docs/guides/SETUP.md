# Getting Started

The Mission Toolkit / Workbench is a local browser-based toolkit for FFXI private-server research, capture analysis, client DAT inspection, editing, validation, and guarded server administration. You do not need to know Python to use the normal GUI workflows.

## First-time setup

1. Install **Python 3.11 or newer** from python.org. During Windows installation, enable **Add python.exe to PATH**.
2. Double-click `setup.bat`.
3. Configure your **FFXI client install folder** when prompted. A normal retail installation contains `FFXiMain.dll` and the ROM trees used by the DAT/client tools.
4. Configure at least one server/source checkout. The Workbench supports:
   - LandSandBoat,
   - Topaz / Topaz-Next style repositories,
   - DSP / Darkstar-style repositories,
   - compatible custom forks where the relevant schema/source adapters match.
5. Allow setup to install the required Python dependencies and any bundled/vendor tooling needed by the configured workflows.
6. When setup completes, start the toolkit and open:

```text
http://127.0.0.1:8420
```

## Starting the Workbench later

Double-click:

```text
start.bat
```

You do not need to rebuild all indexes on every launch. Individual data sources can be rebuilt when their underlying client/server/reference source changes.

## Named server environments

The current Workbench no longer assumes one permanent Topaz/DSP server path.

After first launch, open **Settings → Server Environments** and create the environments you actually use. Typical examples are:

- `Live` — production/private server
- `Test` — test database/source checkout
- `Dev` — development checkout
- `Backup` — offline/reference copy

Each profile records its server family and root. The active profile becomes the default context for generic/server-admin tools such as Character Editor, Zone Editor, Item Editor, Entity Profile, and model/server correlation.

Multiple profiles from the same family are supported; for example, `LSB Live` and `LSB Test` remain separate environments.

### Server-root inputs

For DSP/Topaz-style installs, environment setup can accept the checkout root, its `conf` directory, or a native `map*.conf` file and normalize it back to the canonical server root.

For LandSandBoat, the root or recognized settings path can be normalized similarly.

The Workbench does **not** copy database passwords into the environment profile. Native server configuration remains authoritative for connection credentials.

### LIVE environment safety

Editor/admin workflows identify LIVE profiles and require explicit confirmation where a write can affect the live server. Research/indexing tools remain read-only unless the workflow explicitly exposes an apply/edit action.

## FFXI client path and client assets

A legally owned FFXI installation is required for client DAT/resource analysis. No Square Enix game data is distributed with this repository.

Client-derived working data is generated locally and ignored by Git.

### Item DAT cache

Character inventory and related item views can use a persistent client item cache.

Default behavior is **lazy**: when an item/icon is first requested, the Workbench parses the local DAT record, stores parsed metadata in SQLite, extracts the icon to a PNG file, and reuses it on later requests.

If you prefer to pay that extraction cost once up front, open Settings and use:

**Build all item DAT cache**

The cache is scoped to the configured client installation/snapshot and detects source DAT changes by file metadata before reusing entries. Clearing the cache is safe; the Workbench simply returns to lazy extraction.

## About xi-tinkerer

`xi-tinkerer` / `xi-tinkerer-py` is used by supported DAT/zone/model parsing paths. `setup.bat` normally installs the supported build automatically.

If automatic installation fails because of networking/firewall restrictions, install the appropriate wheel manually from the xi-tinkerer-py release source used by the project, then rerun setup.

Example:

```bat
python -m pip install path\to\xi_tinkerer_whl_file.whl
```

## Rebuilding indexes and source data

The Workbench contains rebuild/install controls for the data families that are safe to refresh independently. Rebuild only the source that changed where possible—for example:

- server SQL/source index after changing server code,
- client snapshot/index after switching client builds,
- wiki/reference source after updating an offline dump,
- capture index after adding or repairing capture sources.

Some client/event resources are generated on demand and cached after first use.

## Character Editor prerequisites

Character Editor uses the **active Server Environment**. The connected server/database must be identifiable as a supported lineage/schema before write capabilities are enabled.

Writes are intentionally guarded. Supported mutations require the character to be verifiably offline and normally use preview/approval, stale-state rechecks, transactions, and audit logging. If a field/category is read-only, that may be an intentional runtime-ownership boundary rather than a missing implementation.

See `docs/workbench/CHARACTER_EDITOR_CLOSEOUT.md` for the current write/read-only contract.

## Item Editor and Zone Editor

Item Editor and Zone Editor also consume the active named environment. When multiple same-family environments exist, use the named profile rather than relying on the legacy Topaz/DSP family selectors.

Legacy/reference paths are retained for compatibility and cross-lineage comparison tools, but they are no longer the primary admin target.

## Capture setup

Capture ingestion supports multiple current and historical logger formats, including PacketLogger/PacketViewer-style logs, Ashita Packeteer, PacketDB, NPCLogger variants, EventView/ActionView families, structured mission/shop/weather/crafting loggers, PCAP/PCAPNG, and chat/OCR-derived evidence.

Use the Captures Help/support matrix in the GUI and `docs/workbench/CAPTURE_FORMAT_AUDIT.md` when determining which parser should ingest a source.

## Troubleshooting

If a GUI tool says a server route/profile is unavailable:

1. confirm an enabled Server Environment exists,
2. confirm the correct profile is active,
3. use the profile connection test in Settings,
4. verify the server root/config file points at the intended Live/Test/Dev environment,
5. restart the Workbench after changing bootstrap-level configuration if the affected adapter does not reload dynamically.

If client-derived item icons/data are slow on first access, either let the lazy cache warm naturally or run the one-time full item DAT cache build.

## More technical documentation

- `README.md` — product overview
- `docs/workbench/ROADMAP_CURRENT.md` — authoritative current capability/status roadmap
- `docs/workbench/RECENT_CHANGES_2026-10-03.md` — recent merged-change reconciliation
- `docs/guides/TOOLING_OVERVIEW.md` — tooling/component inventory
- `docs/workbench/CHARACTER_EDITOR_CLOSEOUT.md` — Character Editor safety/capability contract
- `docs/workbench/CAPTURE_FORMAT_AUDIT.md` — capture format/parser support
