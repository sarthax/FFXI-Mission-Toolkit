"""Static smoke contracts; compilation requires the user's installed Windows x86 Ashita SDK."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "native/ashita_workbench_probe"


def test_native_probe_is_an_explicit_read_only_sdk_smoke_test():
    source = (BASE / "workbench_native_probe.cpp").read_text()
    assert '#include "Ashita.h"' in source
    assert "class WorkbenchNativeProbe final : public IPlugin" in source
    assert "ASHITA_INTERFACE_VERSION" in source
    assert "Ashita::PluginFlags::UseCommands" in source
    assert '"/wbprobe"' in source
    assert 'GetMemberServerId(0)' in source
    assert 'entities->GetServerId(i) == server_id' in source  # entity-map scan: the SDK has no GetEntityIndexById
    assert 'if (index == 0) {' in source  # unresolved -> diagnostic line, never reads XYZ
    assert 'GetMemberIsActive(0)' in source
    assert 'GetLocalPositionX(index)' in source
    assert 'GetLocalPositionY(index)' in source
    assert 'GetLocalPositionZ(index)' in source
    assert 'std::isfinite(x)' in source
    assert "XYZ write=disabled; packet injection=disabled" in source
    for forbidden in ("WriteProcessMemory", "VirtualProtect", "AddOutgoingPacket(",
                      "GetWarpPointer(", "SetPosition(", "CreateRemoteThread"):
        assert forbidden not in source


def test_native_plugin_requires_x86_sdk_and_exports():
    cmake = (BASE / "CMakeLists.txt").read_text()
    exports = (BASE / "exports.def").read_text()
    assert "CMAKE_SIZEOF_VOID_P EQUAL 4" in cmake
    assert "ASHITA4_SDK_PATH" in cmake
    assert "Ashita.h" in cmake
    for symbol in ("expCreatePlugin", "expDestroyPlugin", "expGetInterfaceVersion"):
        assert symbol in exports
    assert "add_library(workbench_native_probe MODULE" in cmake
