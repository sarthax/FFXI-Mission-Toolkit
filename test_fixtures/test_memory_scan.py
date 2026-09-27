#!/usr/bin/env python3
"""Memory scan finds a date-shaped version string planted in a live process (self-scan), ignores non-date
noise like 34092344_0, and ranks versions by count."""
import ctypes, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workbench.client import memory_scan as ms


def main():
    if sys.platform != "win32":
        print("memory scan self-test: SKIP (not Windows)")
        return
    Z = b"\x00"
    planted = ctypes.create_string_buffer(Z * 64 + b"30191204_1" + Z * 64)  # keeps bytes resident
    noise = ctypes.create_string_buffer(Z * 16 + b"34092344_0" + Z * 16)
    r = ms.scan_pid(os.getpid())
    assert r["versions"].get("30191204_1", 0) >= 1, r["versions"]
    assert any(h["value"] == "30191204_1" for h in r["hits"]), r["hits"]
    assert r["bytes_scanned"] > 0 and r["regions"] > 0
    assert "34092344_0" not in r["versions"], "non-date noise must not match"
    counts = list(r["versions"].values())
    assert counts == sorted(counts, reverse=True), "ranked by count"
    assert isinstance(ms.find_client_processes(), list)
    del planted, noise
    print("memory scan self-test: PASS")


if __name__ == "__main__":
    main()
