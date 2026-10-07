"""Canonical Capture video/OCR service.

The mature YouTube OCR implementation remains staged losslessly in ``_ocr_impl`` while Phase C
moves its package ownership. Repository-owned run state, layout profiles, timing logs, and vendor
tools are rebound through the canonical runtime path service. The module alias preserves the
historical mutable module globals used by existing capture regressions and operator workflows.
"""
from __future__ import annotations

import sys

from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT

from . import _ocr_impl as _impl

_impl.ROOT = REPO_ROOT
_impl.RUNS_ROOT = REPO_ROOT / "mission_reports_v2" / "youtube_ocr_runs"
_impl.OCR_TIMING_PATH = REPO_ROOT / "mission_reports_v2" / "ocr_timing.jsonl"
_impl.LAYOUT_PROFILE_PATH = REPO_ROOT / "mission_reports_v2" / "youtube_chat_layout_profiles.json"
_impl.VENDOR_FFMPEG_BIN = VENDOR_ROOT / "ffmpeg" / "bin"
_impl.VENDOR_TESSERACT_DIR = VENDOR_ROOT / "tesseract"

if __name__ == "__main__":
    raise SystemExit(_impl.main())

sys.modules[__name__] = _impl
