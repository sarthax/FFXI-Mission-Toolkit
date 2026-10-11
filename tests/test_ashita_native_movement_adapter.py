"""Native movement adapter: host-side policy tests + static safety contracts (no game access)."""
import glob
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1] / "native/ashita_workbench_probe"


def _vcvars():
    for pattern in ("C:/Program Files/Microsoft Visual Studio/*/*/VC/Auxiliary/Build/vcvars64.bat",
                    "C:/Program Files (x86)/Microsoft Visual Studio/*/*/VC/Auxiliary/Build/vcvars64.bat"):
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


def test_adapter_policy_passes_host_compiled_tests():
    vc = _vcvars()
    if shutil.which("cmd") is None or vc is None:
        pytest.skip("MSVC not available")
    with tempfile.TemporaryDirectory() as tmp:
        bat = Path(tmp) / "b.bat"
        bat.write_text(
            f'@echo off\ncall "{vc}" >nul\n'
            f'cl /nologo /std:c++20 /EHsc /W4 /WX /Fe:"{tmp}\hostexe.exe" /Fo"{tmp}\\\\" '
            f'"{BASE / "movement_adapter_test.cpp"}" || exit /b 1\n"{tmp}\hostexe.exe"\n')
        r = subprocess.run(["cmd", "/c", str(bat)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ALL PASSED" in r.stdout


def test_movement_is_disabled_by_default_and_consent_gated():
    plugin = (BASE / "workbench_native_probe.cpp").read_text()
    adapter = (BASE / "movement_adapter.h").read_text()
    assert "bool enabled_ = false" in adapter
    assert "DEV-SERVER-ONLY" in plugin
    assert "movement DISABLED by default" in plugin
    assert "server_confirmed = false" in adapter
    assert "server_confirmed=NO" in plugin
    # No raw memory/packet primitives; writes only through the approved port methods.
    for forbidden in ("WriteProcessMemory", "VirtualProtect", "AddOutgoingPacket(",
                      "CreateRemoteThread", "GetWarpPointer("):
        assert forbidden not in plugin and forbidden not in adapter
    assert plugin.count("SetLocalPositionX(index, p.x)") == 1
    assert "Stop(\"unload\")" in plugin
