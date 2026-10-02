"""Locate and, when necessary, build the vendored DAT extractor executable."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from workbench.runtime.paths import VENDOR_ROOT

PROJECT_DIR = VENDOR_ROOT / "dat-extractor"
EXE = PROJECT_DIR / "bin" / "Debug" / "net9.0" / "dat-extractor.exe"


def ensure_dat_extractor() -> Path:
    if EXE.exists():
        return EXE
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError(
            f"{EXE} is missing and the .NET 9 SDK (`dotnet`) is not on PATH; "
            f"install it, or run `dotnet build` in {PROJECT_DIR}"
        )
    print(f"  dat-extractor.exe not built yet -- running dotnet build in {PROJECT_DIR}")
    result = subprocess.run(
        [dotnet, "build", "-v", "q"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not EXE.exists():
        raise RuntimeError(
            f"dotnet build of dat-extractor failed:\n"
            f"{result.stdout[-1500:]}{result.stderr[-500:]}"
        )
    return EXE
