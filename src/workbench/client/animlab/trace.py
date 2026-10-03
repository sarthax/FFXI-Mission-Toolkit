"""Filtered ProcMon capture around an Anim Lab sweep (wraps FFXI-Tools run_anim_capture.ps1).

Refuses to run without the saved filter config (an unfiltered capture exhausts RAM).
Needs an elevated shell. The addon's markers.log tags each opened DAT with the anim playing.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

TOOLS = Path("D:/Claude/FFXI-Tools")
SCRIPT = TOOLS / "run_anim_capture.ps1"
CONFIG = TOOLS / "tools" / "procmon" / "ffxi_dat.pmc"
MARKERS = Path("C:/ValhallaXI/Ashitav4-Beta/addons/animprobe/markers.log")


def _run(*args: str) -> subprocess.CompletedProcess:
    if not CONFIG.exists():
        raise FileNotFoundError(f"missing ProcMon filter config: {CONFIG}")
    return subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def start() -> str:
    r = _run("start")
    return r.stdout + r.stderr


def stop(markers: Path | str = MARKERS) -> str:
    r = _run("stop", "-Markers", str(markers))
    return r.stdout + r.stderr


def main(argv=None) -> int:
    import sys
    a = (argv if argv is not None else sys.argv[1:]) or [""]
    if a[0] not in ("start", "stop"):
        print("usage: python -m workbench.client.animlab.trace start|stop")
        return 2
    print(start() if a[0] == "start" else stop())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
