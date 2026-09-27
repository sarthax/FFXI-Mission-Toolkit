"""Locates vendor/dat-extractor's built exe, building it with `dotnet build` on first use.

bin/ and obj/ are gitignored, so a fresh clone or worktree has the source but not the exe; every
dat-driven rebuild (dialog, NPC names, mission/key-item text, per-zone events) then failed with
[WinError 2] or silently indexed nothing. Raises a clear error instead if it can't be built."""
import shutil
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent / "vendor" / "dat-extractor"
EXE = PROJECT_DIR / "bin" / "Debug" / "net9.0" / "dat-extractor.exe"


def ensure_dat_extractor() -> Path:
    if EXE.exists():
        return EXE
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError(f"{EXE} is missing and the .NET 9 SDK (`dotnet`) is not on PATH; "
                           f"install it, or run `dotnet build` in {PROJECT_DIR}")
    print(f"  dat-extractor.exe not built yet -- running dotnet build in {PROJECT_DIR}")
    r = subprocess.run([dotnet, "build", "-v", "q"], cwd=PROJECT_DIR, capture_output=True, text=True)
    if r.returncode != 0 or not EXE.exists():
        raise RuntimeError(f"dotnet build of dat-extractor failed:\n{r.stdout[-1500:]}{r.stderr[-500:]}")
    return EXE
