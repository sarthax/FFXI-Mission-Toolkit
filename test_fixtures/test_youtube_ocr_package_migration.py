#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.captures.video import ocr as canonical
from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT


def main() -> None:
    assert not (REPO_ROOT / "youtube_chat_ocr.py").exists()
    assert canonical.ROOT == REPO_ROOT
    assert canonical.RUNS_ROOT == REPO_ROOT / "mission_reports_v2" / "youtube_ocr_runs"
    assert canonical.OCR_TIMING_PATH == REPO_ROOT / "mission_reports_v2" / "ocr_timing.jsonl"
    assert canonical.LAYOUT_PROFILE_PATH == REPO_ROOT / "mission_reports_v2" / "youtube_chat_layout_profiles.json"
    assert canonical.VENDOR_FFMPEG_BIN == VENDOR_ROOT / "ffmpeg" / "bin"
    assert canonical.VENDOR_TESSERACT_DIR == VENDOR_ROOT / "tesseract"
    assert callable(canonical.frame_index)
    assert callable(canonical.capture_observations)
    assert callable(canonical.main)

    original_runs = canonical.RUNS_ROOT
    sentinel = REPO_ROOT / "__youtube_ocr_migration_sentinel__"
    canonical.RUNS_ROOT = sentinel
    try:
        assert canonical.RUNS_ROOT == sentinel
    finally:
        canonical.RUNS_ROOT = original_runs

    code = (
        "from workbench.captures.video import ocr; "
        "from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT; "
        "assert ocr.ROOT == REPO_ROOT; "
        "assert ocr.RUNS_ROOT == REPO_ROOT / 'mission_reports_v2' / 'youtube_ocr_runs'; "
        "assert ocr.OCR_TIMING_PATH == REPO_ROOT / 'mission_reports_v2' / 'ocr_timing.jsonl'; "
        "assert ocr.LAYOUT_PROFILE_PATH == REPO_ROOT / 'mission_reports_v2' / 'youtube_chat_layout_profiles.json'; "
        "assert ocr.VENDOR_FFMPEG_BIN == VENDOR_ROOT / 'ffmpeg' / 'bin'; "
        "assert ocr.VENDOR_TESSERACT_DIR == VENDOR_ROOT / 'tesseract'; "
        "assert callable(ocr.frame_index); assert callable(ocr.capture_observations); assert callable(ocr.main)"
    )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=Path(tmp), check=True)
        subprocess.run(
            [sys.executable, "-m", "workbench.captures.video.ocr", "--help"],
            cwd=Path(tmp),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    main()
