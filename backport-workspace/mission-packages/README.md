# mission-packages/

One subfolder per Topaz→DSP backport package. Each package folder holds:

- **`lua/`** — the original Topaz Lua source, copied verbatim (untouched — never hand-edited here,
  only ever re-copied from the real Topaz checkout if it changes upstream).
- **`lua-dsp/`** — the converted-for-DSP output, mirroring `lua/`'s relative paths file-for-file.
  Produced by `backport_lua_convert.py` (the same engine behind the GUI's Lua Converter page) --
  either pasted through the GUI one file at a time, or via `py -3 backport_package.py
  mission-packages/<name>` for the whole package at once (also runs the binding audit/sanity
  check/SQL collision check and writes `BACKPORT_REPORT.md` -- see the workspace's own README).
- **`sql/`** (optional) — Topaz SQL rows this package's content depends on, if any.
- **`cpp-engine-reference/`** (optional) — reference copies of any C++ source this package's
  content ended up depending on, for context.
- **`navmesh/`** (optional) — any zone `.nav` files the package specifically needs, if not already
  covered by the target DSP checkout's own.

`configs/` holds `<mission>.config.json` files if you use a package-building script (this
project's own `package_mission.py` is not bundled here — it's a project-specific one-off driver,
not general toolkit code).

`_example_godmode/` is a real, working, already-verified example of this shape (Topaz's real
`scripts/commands/godmode.lua` and its converted DSP output, confirmed byte-for-byte equivalent
to old-dsp-reference's own native `godmode.lua`) — run
`py -3 backport_binding_audit.py --all-packages` from the toolkit root to see it audit clean.
