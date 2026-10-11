# Ashita v4 native plugin smoke test (read-only)

This original C++ plugin tests whether the installed Ashita v4 SDK can build and load a
native x86 plugin. It deliberately has **no XYZ write, pointer scan, movement opcode,
outgoing packet injection, IPC or independent process hook**. It does not change the
existing `workbench_live` Lua addon or its settings.

## Build on Windows

Install Visual Studio 2022 with **Desktop development with C++**, CMake 3.22+,
and use the **x86/Win32** toolchain (Ashita v4 is 32-bit). The Ashita SDK is normally
under `<Ashita install>\\plugins\\sdk`. In PowerShell from the repository root:

```powershell
$env:ASHITA4_SDK_PATH = "C:\\Ashita\\plugins\\sdk"
cmake -S native/ashita_workbench_probe -B build/ashita-native-probe -G "Visual Studio 17 2022" -A Win32
cmake --build build/ashita-native-probe --config Release
```

Find `workbench_native_probe.dll` under the configured build output directory.
Copy **only** that DLL to your Ashita installation's `plugins` directory, **not**
`plugins/sdk`. This native plugin is intentionally excluded from the Lua addon
installer because the DLL must be built for the exact installed SDK/runtime.

## Load test

Use a disposable authorized DSP/Topaz test client. With Ashita running:

```text
/plugin load workbench_native_probe
/wbprobe
/wbprobe position
/plugin unload workbench_native_probe
```

Expected: a message that the native probe loaded; then an explicit
`SDK loaded; read-only; XYZ write=disabled; packet injection=disabled`
response. The `/wbprobe position` command shows read-only zone, entity index and native XYZ via `IParty::GetMemberServerId(0)`, `IResourceManager::GetEntityIndexById` and `IEntity::GetLocalPositionX/Y/Z`. Compare against the Toolkit live telemetry while stationary, then after walking a short distance. The results should agree to within normal telemetry timing and rounding; capture both readings and the Ashita SDK version for investigation. No position writes occur. Confirm unload, relog and reload succeed; test alongside the Lua live
telemetry addon. If loading fails, retain the console/error output and inspect the
actual export names and architecture with `dumpbin /exports` and
`dumpbin /headers`. Do not rename an x64 DLL or force-load incompatible builds.

Record: Ashita version, SDK header revision/date, FFXI module build, MSVC toolset,
the DLL SHA-256, load/unload results, and any crash/stack trace. Keep credentials,
private process memory and binaries out of GitHub issues.

The SDK's official reference project is
https://github.com/AshitaXI/exampleplugin . It requires CMake 3.22+, x86, and
`ASHITA4_SDK_PATH`. This project's source is original and does not vendor the
SDK or copy the template implementation. Review SDK LGPLv3 obligations before
distributing built plugin DLLs.

## Next gate

Successful loading only proves native plugin compatibility. Then inspect the
actual installed SDK and verify a supported position-access/write path before
adding a **separate explicitly armed** development-only movement capability.
Do not mistake a client-local coordinate change for server-accepted movement.

If `Index unresolved` appears, record the reported party slot, server ID, mapped index and map size. The party `GetMemberIndex(0)` value is not the same as the entity-map index; native lookup now uses the server ID and confirms the mapped entity before reading coordinates.
