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
response. The `/wbprobe position` command shows read-only zone, entity index and native XYZ via `IParty::GetMemberServerId(0)`, a bounded scan of `IEntity::GetServerId(i)` and `IEntity::GetLocalPositionX/Y/Z`. Compare against the Toolkit live telemetry while stationary, then after walking a short distance. The results should agree to within normal telemetry timing and rounding; capture both readings and the Ashita SDK version for investigation. No position writes occur. Confirm unload, relog and reload succeed; test alongside the Lua live
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

If `Index unresolved` appears, record the reported party slot, server ID, mapped index and map size. The party `GetMemberIndex(0)` value is not a full entity-map index. The Valhalla Ashita v4-Beta SDK lacks `IResourceManager::GetEntityIndexById`, so the tested plugin scans the entity map for a matching server ID before reading coordinates. The SDK also requires C++20 because its `Commands.h` uses `std::ranges`.

## Confirmed Windows validation (2026-10-11)

On the ValhallaXI Ashita v4.05 Beta environment, the user confirmed successful native XYZ readback in zone 98 at entity index 1024, with multiple changing coordinate samples after movement. The plugin was compiled with VS 18 x86 and C++20 against the local Beta SDK. This validates *read-only* native entity position access, not movement writes or server correction behavior. An unrelated Ashita plugin load attempt also produced an Error 126 message in the screenshot; it does not invalidate the successful `/wbprobe position` readings.

## Native versus Lua live-telemetry comparison

The repository now includes `workbench.runtime.live_client.native_position_compare`
with `PositionSample` and `compare_native_live`. Capture the native
`/wbprobe position` result and the Toolkit live dashboard snapshot from
the **same zone**, as close together in time as possible. The comparison
rejects mismatched zones and samples over two seconds apart, then reports
the three-dimensional distance (default tolerance 1.5 units). Compare while
stationary first, then after a short normal walk and stopping. This measures
agreement of two local client readings; it does **not** prove server acceptance
or permit game state writes.

### Native XYZ setter signature gate (2026-10-11)

Ashita v4-Beta public SDK `IEntity` declares `SetLocalPositionX/Y/Z(uint32_t, float) const`. The native plugin now performs compile-time signature checks and provides `/wbprobe capabilities` to report setter declaration availability. **This does not invoke a setter, establish runtime permission, or demonstrate server-accepted movement.** Confirm compilation against the installed `C:\\ValhallaXI\\Ashitav4-Beta\\plugins\\sdk` headers, then test the diagnostic on the authorized DSP test client. The existing XYZ reader and Lua telemetry comparison remain read-only.

## Movement adapter (development-only, disabled by default)

`movement_adapter.h` is an SDK-independent policy/state machine; `SdkMovementPort`
in the plugin is the only code that touches the game. The earlier "no XYZ write"
statement above describes the original probe; writes now exist but are gated:

* **Disabled after load.** Enabling needs the literal consent token and binds the session
  to the current character server-id and zone:
  `/wbprobe movement enable <autorun|local> DEV-SERVER-ONLY` (authorized private DSP/Topaz test server only).
* Auto-disables after 120 s; `/wbprobe movement disable`, `/wbprobe stop` (unconditional, needs no telemetry) and plugin unload all cancel.
* `/wbprobe move <id> <dx> <dy> <dz>` — relative; rejected for: disabled, bad/duplicate id, nonfinite,
  < 0.05 or > 3.0 yalms, < 1 s since last command, busy, unverified state, zoning, wrong character, wrong zone.
* Modes: `autorun` (experimental) sets `IAutoFollow` delta + `IsAutoRunning` so the client's own movement code runs
  and emits ordinary packets for the server to judge; the per-frame tick stops on arrival (0.35), overshoot, 4 s timeout, or lost state.
  `local` calls `IEntity::SetLocalPosition*` once (client-local; the server is not told).
* `/wbprobe movement status|audit` print the outcome/audit ring. Every outcome is reported
  `scope=client_local server_confirmed=NO`: native code cannot observe server acceptance, so verify against
  server-observed coordinates (Toolkit capture/GM `!pos`) separately.
* Axis semantics of `IAutoFollow` deltas and SDK Y/Z are **unverified** until the live smoke test below.

Host policy tests (no game): `cl /std:c++20 /EHsc movement_adapter_test.cpp`, or `pytest tests/test_ashita_native_movement_adapter.py`.

### Manual smoke test (not yet run)

1. Disposable character on the private DSP server, open flat area, Toolkit Live Client connected. `/plugin load workbench_native_probe`.
2. `/wbprobe movement` (expect DISABLED); `/wbprobe move t0 1 0 0` (expect REJECTED: disabled); `/wbprobe position` (record, plus server `!pos`).
3. `/wbprobe movement enable autorun DEV-SERVER-ONLY`, then `/wbprobe move t1 1 0 0`; `/wbprobe movement status`; `/wbprobe position`; compare with server `!pos` and Lua bridge. Press `/wbprobe stop` if anything looks wrong.
4. Repeat t2 with `0 1 0`, `0 0 1` to learn axis meaning. Only then, optionally, `enable local` and one 1-yalm `move`; note rubber-banding.
5. `/wbprobe movement audit`, then unload/reload and confirm DISABLED again. Report client-local vs server-observed positions separately.
