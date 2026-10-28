"""Guard: code, scripts, tests, templates and data must not hard-code a personal checkout path.

History/reference material is exempt (docs/archive, data/assault logs, vendor, backport-workspace).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"D:[\\/]+Claude|dsp-branches|dsp-master|dsp-wt-")
EXEMPT_PREFIXES = ("docs/archive/", "data/assault/", "vendor/", "backport-workspace/", "test_fixtures/test_no_hardcoded_local_paths.py")
TEXT_SUFFIXES = {".py", ".js", ".cjs", ".html", ".json", ".md", ".yml", ".yaml", ".txt", ".toml", ".bat", ".ps1"}


def scan(files, root=REPO):
    hits = []
    for rel in files:
        if rel.startswith(EXEMPT_PREFIXES) or Path(rel).suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                hits.append(f"{rel}:{n}")
    return hits


def test_scan_detects_pattern(tmp_path):
    bad = "P = 'D:" + chr(92) + "Claude" + chr(92) + "thing'" + chr(10)
    (tmp_path / "x.py").write_text(bad, encoding="utf-8")
    (tmp_path / "ok.py").write_text("P = '<local>/thing'" + chr(10), encoding="utf-8")
    assert scan(["x.py", "ok.py"], tmp_path) == ["x.py:1"]


def test_tracked_files_have_no_personal_checkout_paths():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    assert scan(out.splitlines()) == []
