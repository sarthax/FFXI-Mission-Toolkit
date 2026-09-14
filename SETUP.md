# Getting Started

This is a toolkit for looking up FFXI zone data (NPCs, dialog, mission info) for Topaz server
development. You do not need to know Python to use it.

## First time setup

1. Install Python 3.11 or newer from https://www.python.org/downloads/ -- during install, check
   the box that says **"Add python.exe to PATH"**.
2. Double-click **setup.bat**.
3. It will ask for two folder paths:
   - Your **FFXI client install folder** (contains `FFXiMain.dll`)
   - Your **Topaz server folder** (contains `conf\map.conf`)
4. It installs everything it needs and builds the zone database, your Topaz server's own SQL
   index, the LandSandBoat cross-reference data, and syncs the BG Wiki page dump. This can take
   a while the first time (the LandSandBoat and FFXI-DATS downloads alone are a few hundred MB) --
   it's reading real data out of your FFXI client, your Topaz server, and a couple of GitHub
   repos for every zone.
5. When it's done, it starts the toolkit automatically and tells you to open
   **http://127.0.0.1:8420** in your web browser. Everything on the homepage should already show
   real data -- if any row instead shows an "Install" button, that one piece couldn't be
   downloaded automatically (usually a network hiccup during setup) and just needs one click.

## Using it after the first time

Just double-click **start.bat**. No need to rebuild anything unless you want to (see below).

## About xi_tinkerer

The toolkit **will not start at all** without a piece called `xi_tinkerer`. setup.bat downloads
and installs the real, current version of it automatically from its GitHub release -- you don't
need to do anything for this normally.

If setup.bat reports it couldn't install it automatically (e.g. no internet access, or a
firewall blocking it), do it by hand instead:

1. Go to https://github.com/sruon/xi-tinkerer-py/releases
2. Download the `.whl` file matching your Python version and Windows
3. Open a command prompt in this folder and run:
   `python -m pip install path\to\the\downloaded\file.whl`
4. Run setup.bat again.

## Changing your saved paths

Your FFXI/Topaz paths are saved in `toolkit_config.txt`. Delete that file and run setup.bat
again if you ever move either install, or just edit the file directly.

## Rebuilding data later

You never need a command prompt for this. Every data source has its own **Rebuild** button
right on the homepage (http://127.0.0.1:8420) -- Dialog text, NPC/mob names, your Topaz server's
SQL, the LandSandBoat cross-reference, BG Wiki, and more. Click Rebuild on whichever row changed
(e.g. you edited your Topaz server's scripts, or LandSandBoat/BG Wiki updated upstream) and it
re-indexes just that piece. A row showing an "Install" button instead means that piece isn't
downloaded yet -- one click fetches it from its real source (LandSandBoat/GitHub, FFXI-DATS/
GitHub, xi-tinkerer-cli/GitHub).

The only thing with no button: **`/events?zone=<name>`** generates itself automatically the
first time you view a zone you haven't looked at before (takes a few seconds), and is cached
after that -- or use the homepage's "Per-zone event data" Rebuild button to pre-generate every
zone at once (slower, several minutes, but then nothing needs on-demand generation later).

## Something more technical?

See `TOOLING_OVERVIEW.md` for the full tool inventory and how everything fits together.
