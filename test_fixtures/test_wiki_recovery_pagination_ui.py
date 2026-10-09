"""Smoke contract for paged Wiki recovery browsing (read-only navigation)."""
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    host = (root / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    page = (root / "gui/templates/wiki.html").read_text(encoding="utf-8")
    audit = (root / "src/workbench/devtools/reference/wiki_import_audit.py").read_text(encoding="utf-8")
    assert 'recovery_page: int = 1' in host
    assert 'recovery_offset = (recovery_page - 1) * 12' in host
    assert 'preview_local_recovery(con, sample_limit=12, recovery_offset=recovery_offset)' in host
    assert '"recovery_has_more": recovery_has_more' in host
    assert 'recovery_page={{ recovery_page + 1 }}' in page
    assert 'recovery_page={{ recovery_page - 1 }}' in page
    assert 'recovery_total' in page
    assert '--recovery-offset' in audit


if __name__ == "__main__":
    main()
