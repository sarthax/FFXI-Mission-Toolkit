# ffxi
ffxi dat reverse engineering

## Setup (verified working, 2026-08-24)

1. **Clone and open the real solution**: `mapViewer/mapViewer.sln`, not the repo root.
2. **NuGet**: `mapViewer` uses the NuGet package `nupengl.core` (bundles OpenGL/GLFW/GLEW).
   Install it via **Tools → NuGet Package Manager → Package Manager Console**, with
   `mapViewer.sln` already open and the project loaded (the console's "Default project"
   dropdown must show `mapViewer`, not be empty):
   ```
   Install-Package nupengl.core -Version 0.1.0.1
   ```
   Do **not** use `dotnet add package` — this is a native C++ project (`.vcxproj`), not a .NET
   SDK-style project; the `dotnet` CLI doesn't apply here at all.
3. **Toolset retarget**: this project targets the VS2015 (`v140`) toolset. If you're on a newer
   Visual Studio, it'll prompt "Retarget Projects" on first open — accept it (upgrade to
   whatever toolset you have, e.g. `v142`). This only changes which compiler is used, not any
   source code.
4. **GLFW3 crash on `glfwInit()`**: if you hit this, go to **Project Properties → C/C++ → Code
   Generation → Runtime Library** and change `/MDd` to `/MD`.
5. **Missing `glm/glm.hpp`**: the project's `.vcxproj` ships with zero
   `AdditionalIncludeDirectories` set — it never pointed at GLM's bundled location in this repo.
   Add this to **Project Properties (All Configurations) → C/C++ → General → Additional Include
   Directories**:
   ```
   <repo root>\opengl\glmath\glm-9.4.3
   ```
6. **GLM type errors** (`fvec3`/`u8`/`u16`/`u32` "is not a member of glm"): already fixed in this
   repo's own copy of `glm.hpp` (added `#include "./gtc/type_precision.hpp"`, the extension
   header that actually declares these short type aliases — the base `glm.hpp` alone doesn't).
   No action needed unless you're working from a different GLM copy.
7. **`std::string` not found** in a few headers (`SceneManager.h`, `FFXIMesh.h`,
   `FFXILandscapeMesh.h`): already fixed by adding explicit `#include <string>` to each — these
   relied on it leaking in transitively via `<vector>`/`<map>` on whatever older compiler this
   was originally built with; modern MSVC's STL doesn't guarantee that.

At this point the project should build clean (warnings only, no errors).

## Configuration (`mapViewer.ini`)

As of 2026-08-24, **all previously hardcoded settings are externalized** into a plain-text
`mapViewer.ini` written next to the exe on first run (seeded from whatever was compiled in) — no
rebuild needed to change any of them after that:

```ini
; mapViewer configuration -- edit these values directly, no rebuild needed.
; ffxidir must point at a real FFXI client install (the folder containing ROM/ROM2/etc).
ffxidir=C:\ValhallaXI\SquareEnix\FINAL FANTASY XI\
; mapid is the default zone/map dat to load if no command-line argument is given.
; Decoded as dir=mapid/1000000, then ROM<dir>\<(mapid%1000000)/1000>\<(mapid%1000000)%1000>.dat
mapid=4000010
screenwidth=768
screenheight=576
```

- **`ffxidir`**: your FFXI client's root install folder (must contain `ROM`, `ROM2`, etc.).
- **`mapid`**: which zone/map dat loads by default. A command-line argument still overrides this
  for one-off testing without editing the file.
- **`screenwidth`/`screenheight`**: window size.

The previous behavior (hardcoding `ffxidir` directly in `FFXILandscapeMesh.cpp`'s source and
recompiling for every change) still works as the seed value for a fresh `mapViewer.ini`, but is
no longer required for normal use.

## Running it

The window title reads "Tutorial 08 - Basic Shading" (a leftover from the OpenGL tutorial this
was built on top of) — this is expected, not a bug.

**All feedback is text-only, printed to a console window, not drawn on screen.** Since the
project defines `main()` (not `WinMain()`), MSVC auto-links it as a console app — a separate
terminal window exists alongside the render window and shows every load result and toggle state.
If you only see a blank/white render window, check for that second window (it may be behind or
minimized) before assuming something's broken.

### Controls (verified against source, 2026-08-24 — most of these were never documented before)

| Input | Action |
|---|---|
| Mouse | Look around (standard FPS-style camera) |
| `↑` `↓` `←` `→` | Move forward/back, strafe left/right |
| Numpad `+` / `-` | Camera speed up/down |
| `N` / `B` | Next / previous MMB (model piece) |
| `J` | Jump MMB index +10 |
| `V` | Cycle model variant within the current MMB (the only key the old README ever mentioned) |
| `X` | Toggle "model inclusive/exclusive" mode |
| `M` | Toggle MZB (zone/landscape) vs MMB (model) draw mode |
| `O` | Toggle octree (spatial culling) |
| `T` | Toggle MMB transform |
| `W` | Toggle wireframe |
| `C` | Toggle draw cube |
| `G` | Toggle dual-camera mode |
| `E` | Toggle active eye/camera (only meaningful with `G` on) |
| `S` | Toggle Potential Visible Set (PVS) draw |
| `D` / `F` | Previous / next PVS (only meaningful with `S` on) |
| `L` | Toggle draw normals |
| `Page Up` | Load the next map id (current + 1) live, replacing the current scene |

If nothing renders after moving/looking around, try `Page Up` a few times — the default
`mapid=4000010` may land on a landscape piece with no interesting geometry in view from the
default camera start position.

### Real zone-name → dat-id mapping

`reference/AltanaViewer_zones.csv` (pulled from [voliathon/AltanaViewer](https://github.com/voliathon/AltanaViewer)'s
`List/Zones/zones.csv`) is a real, community-maintained mapping of every zone name to its 3D
geometry dat, in `dir/sub/file` form (e.g. `4/0/19,Mamool Ja Training Grounds`). Convert a row to
this tool's numeric mapid with `mapid = dir*1000000 + sub*1000 + file` (dir 0 rows, e.g. `284/63`,
become `sub*1000+file` = `284063`). **Don't confuse this with `xurion/ffxi-map-dats`** — that repo
catalogs the small 2D navigation/overview map *images*, not 3D zone geometry; the two use
unrelated numbering and pulling a zone id from the wrong one silently loads nothing useful. The
correct default here (`mapid=4000019`, confirmed 2026-08-24) is Mamool Ja Training Grounds's real
geometry dat, `ROM4\0\19.dat` — the repo's original placeholder default (`4000010`) was actually
Talacca Cove, never a verified value.

Topaz's own server-side `zone_settings.sql` doesn't carry this mapping at all — the server just
tells the client "go to zone X"; the client resolves that internally via its own `FTABLE.DAT`,
whose binary format isn't decoded/documented here. The AltanaViewer CSV is the reliable source
for known zones; for anything not in it (or to double-check a row), `mapViewer` can scan a range
of ids itself and report which ones are real, using the exact same `loadMeshLandscape()` call
`Page Up` already exercises live:

```
mapViewer.exe --scan <startId> <endId>
```

This runs headless (no interactive render loop) and writes `scan_results.txt` next to the exe —
one confirmed-valid id per line, flushed as it goes so you can tail the file mid-scan. Progress
also prints to the console every 100 ids. Example: `mapViewer.exe --scan 4000000 4000999` scans
every id in the `ROM4\0\*` — `ROM4\<0-999>\*` id block that map ids like the default `4000010`
live in.

A "valid" id here means the file exists at the decoded path *and* parses successfully as a
landscape dat — the same bar the normal viewer and `Page Up` use, so results are directly
trustworthy for picking a default `mapid` in `mapViewer.ini`. It does not tell you the zone's
*name* (that mapping isn't recovered by this scan), only that the id is real.

---

## Historical changelog (original)

**19 May 2016**
1) fix a bug that cause premature stop in extracting dat.  Main reason why some dat have missing MMB & img.
2) add a default VAO creation, to fix no Model/Map display for window 10.  User need to update latest glm/glfw3 as well, else it will generate compile error.
3) fix DXT3 convert error, should be using BCD2Decode.

**7 June 2016**
1) fix transparency for mapViewer
2) add func 'v' to view individual Model within each MMB.

Note: mapViewer uses VisualStudio NuGet Manager for opengl, glfw2, glew.  The packages is 'nupengl.core' access thru 'Tools -> NuGet Package Manager -> Manage NuGet Packages for Solution'

Remember to change --- char ffxidir[512]="E:\\Program Files (x86)\\PlayOnline2\\SquareEnix\\FINAL FANTASY XI\\"; to your folder. *(Superseded 2026-08-24 — see Configuration section above; this is now only the seed value for a fresh `mapViewer.ini`, not something you need to edit and recompile.)*
