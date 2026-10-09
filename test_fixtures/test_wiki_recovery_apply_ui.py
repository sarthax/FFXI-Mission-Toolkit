"""Guarded recovery form and route preserve paginated preview workflow."""
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    host = (root / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    ui = (root / "gui/templates/wiki.html").read_text(encoding="utf-8")
    assert '@app.post("/wiki/recovery/apply")' in host
    assert 'expected_raw_hash=expected, confirm=True' in host
    assert 'recovery_page={page}' in host
    assert 'recovery_result if recovery_result in ("applied", "failed")' in host
    assert 'action="/wiki/recovery/apply"' in ui
    assert 'name="source_hash" value="{{ entry.source_hash }}"' in ui
    assert 'name="recovery_page" value="{{ recovery_page }}"' in ui
    assert 'name="confirm" value="yes" required' in ui
    assert 'recovery_page={{ recovery_page + 1 }}' in ui


if __name__ == "__main__":
    main()
