from __future__ import annotations

from pathlib import Path

from workbench.validation.packages import coverage


def test_coverage_uses_package_safe_settings_bridge(monkeypatch, tmp_path):
    seen = {}

    monkeypatch.setattr(coverage, "get_topaz_root", lambda: tmp_path)
    monkeypatch.setattr(coverage, "run", lambda root, zones: seen.update(root=root, zones=zones) or {
        "files_processed": 0,
        "files_with_flags": 0,
        "files_with_unflagged": 0,
        "flag_reason_counts": {},
        "unflagged_token_counts": {},
        "unflagged_detail": [],
        "errors": [],
    })
    monkeypatch.setattr(coverage, "print_summary", lambda result: None)
    monkeypatch.setattr("sys.argv", ["coverage.py"])

    coverage.main()

    assert seen["root"] == tmp_path
    assert seen["zones"] is None


def test_coverage_source_has_no_root_settings_import():
    source = Path(coverage.__file__).read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime.legacy_settings import get_topaz_root" in source
