from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from workbench.client.dat import extractor_bin as canonical
from workbench.runtime.paths import VENDOR_ROOT

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    assert not (REPO_ROOT / "dat_extractor_bin.py").exists()
    assert canonical.PROJECT_DIR == VENDOR_ROOT / "dat-extractor"
    assert canonical.EXE == canonical.PROJECT_DIR / "bin" / "Debug" / "net9.0" / "dat-extractor.exe"

    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "dat-extractor"
        exe = project / "bin" / "Debug" / "net9.0" / "dat-extractor.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"stub")
        with patch.object(canonical, "PROJECT_DIR", project), patch.object(canonical, "EXE", exe):
            assert canonical.ensure_dat_extractor() == exe

        exe.unlink()
        with patch.object(canonical, "PROJECT_DIR", project), patch.object(canonical, "EXE", exe), patch(
            "workbench.client.dat.extractor_bin.shutil.which", return_value=None
        ):
            try:
                canonical.ensure_dat_extractor()
            except RuntimeError as exc:
                assert ".NET 9 SDK" in str(exc)
            else:
                raise AssertionError("missing dotnet should fail clearly")

        def fake_run(*_args, **_kwargs):
            exe.parent.mkdir(parents=True, exist_ok=True)
            exe.write_bytes(b"built")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(canonical, "PROJECT_DIR", project), patch.object(canonical, "EXE", exe), patch(
            "workbench.client.dat.extractor_bin.shutil.which", return_value="dotnet"
        ), patch("workbench.client.dat.extractor_bin.subprocess.run", side_effect=fake_run):
            assert canonical.ensure_dat_extractor() == exe

    code = (
        "from workbench.client.dat import extractor_bin as e; "
        "assert e.PROJECT_DIR.name == 'dat-extractor'; "
        "print('outside-repo DAT extractor import: PASS')"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("DAT extractor package migration: PASS")


if __name__ == "__main__":
    main()
