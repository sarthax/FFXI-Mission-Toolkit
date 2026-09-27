"""Read-only runtime scan of a running FFXI client for its version string (e.g. 30191204_1).

FFXiMain.dll is packed on disk, so the on-disk probes cannot see the version the client reports via /ver
and sends in lobby packet 0x26. Once running, the unpacked string lives in process memory. This opens the
process with PROCESS_QUERY_INFORMATION|PROCESS_VM_READ only and never writes. Windows-only (ctypes).
A miss is UNKNOWN, never absent.
"""
from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x2
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
# Client processes: pol.exe hosts FFXiMain.dll for retail/Ashita/xiloader launches; ffxi.exe is a fallback.
CLIENT_EXES = ("pol.exe", "ffxi.exe", "ffxi-boot.exe", "polboot.exe")
# 30 + YY (18-26) + MM (01-12) + DD (01-31) + _N: real FFXI patch versions are dates; this rejects the
# resource/ROM-id noise (e.g. 34092344_0) that a bare 3\d{7}_\d also matches.
VERSION_RE = re.compile(rb"(?<![0-9])(30(?:1[89]|2[0-6])(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])_\d)(?![0-9])")
CHUNK = 1 << 20


class _PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


class _MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_size_t), ("AllocationBase", ctypes.c_size_t),
                ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]


def _k32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k.Process32First.argtypes = k.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32)]
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
    k.VirtualQueryEx.restype = ctypes.c_size_t
    k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_size_t)]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


def find_client_processes() -> list[dict]:
    """[{pid, exe}] for running FFXI client processes."""
    if sys.platform != "win32":
        return []
    k = _k32()
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out = []
    try:
        e = _PROCESSENTRY32()
        e.dwSize = ctypes.sizeof(e)
        ok = k.Process32First(snap, ctypes.byref(e))
        while ok:
            name = e.szExeFile.decode("mbcs", "replace")
            if name.lower() in CLIENT_EXES:
                out.append({"pid": e.th32ProcessID, "exe": name})
            ok = k.Process32Next(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)
    return out


def scan_pid(pid: int, pattern: re.Pattern = VERSION_RE, max_hits: int = 50) -> dict:
    """Scan committed readable memory of `pid` for `pattern` (bytes regex, group 1 = value).
    Returns {pid, versions: {value: count}, hits: [{address, value}], regions, bytes_scanned, unreadable}."""
    if sys.platform != "win32":
        raise OSError("memory scan is Windows-only")
    k = _k32()
    h = k.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise PermissionError(f"OpenProcess({pid}) failed (winerror {ctypes.get_last_error()}); "
                              "run the toolkit at the same or higher privilege as the client")
    versions: dict[str, int] = {}
    hits: list[dict] = []
    regions = scanned = unreadable = 0
    try:
        addr, mbi = 0, _MBI()
        while k.VirtualQueryEx(h, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
            base, size = mbi.BaseAddress, mbi.RegionSize
            if mbi.State == MEM_COMMIT and not (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) and mbi.Protect:
                regions += 1
                off = 0
                tail = b""
                while off < size:
                    n = min(CHUNK, size - off)
                    buf = ctypes.create_string_buffer(n)
                    got = ctypes.c_size_t(0)
                    if not k.ReadProcessMemory(h, base + off, buf, n, ctypes.byref(got)) and got.value == 0:
                        unreadable += 1
                        break
                    data = tail + buf.raw[:got.value]
                    scanned += got.value
                    for m in pattern.finditer(data):
                        v = m.group(1).decode("ascii")
                        versions[v] = versions.get(v, 0) + 1
                        if len(hits) < max_hits:
                            hits.append({"address": hex(base + off - len(tail) + m.start(1)), "value": v})
                    tail = data[-16:]  # a hit can straddle a chunk edge; 10 chars max
                    off += n
            nxt = base + size
            if nxt <= addr:
                break
            addr = nxt
    finally:
        k.CloseHandle(h)
    versions = dict(sorted(versions.items(), key=lambda kv: (-kv[1], kv[0])))  # most frequent first
    return {"pid": pid, "versions": versions, "hits": hits, "regions": regions,
            "bytes_scanned": scanned, "unreadable": unreadable}


def scan_client_version() -> dict:
    """Find running client(s) and report the version string(s) found in memory."""
    procs = find_client_processes()
    results = []
    for p in procs:
        try:
            r = scan_pid(p["pid"])
            r["exe"] = p["exe"]
            # Patch history strings (patch.cfg-style) can also be resident; the client's own version is
            # normally the most frequent/last-loaded, so report all and let the operator judge.
            results.append(r)
        except (OSError, PermissionError) as ex:
            results.append({"pid": p["pid"], "exe": p["exe"], "error": str(ex), "versions": {}, "hits": []})
    return {"running": bool(procs), "processes": results}
