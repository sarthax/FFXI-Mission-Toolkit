#!/usr/bin/env python3
"""Offset detection for dialog drift: a uniform shift is found, scattered ids are not."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dialog_drift_overview as d


def main():
    real = {i: d.normalize(f"≺Special Code: 1F≻ Line number {i} of the dialog") for i in range(100)}
    shifted = [(i + 1, f"Line number {i} of the dialog") for i in range(10, 20)]  # wired id is real id + 1
    r = d.detect_offset(shifted, real)
    assert r["offset"] == -1 and r["explained"] == 10, r
    scattered = [(i, f"Line number {(i * 7) % 100} of the dialog") for i in range(10, 20)]
    assert d.detect_offset(scattered, real)["offset"] is None
    print("Dialog drift overview self-test: PASS")


if __name__ == "__main__":
    main()
