"""Route/template contract for the zone-first entity reconciliation browser."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_data_gaps_comparison_wiring():
    host = (ROOT / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    page = (ROOT / "gui/templates/gaps.html").read_text(encoding="utf-8")
    assert 'def gaps_browse(' in host
    assert 'mode: str = "compare"' in host
    assert 'build_report(DB_PATH, zoneid' in host
    assert '@app.get("/gaps/report")' in host
    assert 'format not in ("json", "csv")' in host
    assert 'gap-conflict' in page
    assert "row.values[origin]" in page
    assert "['client', 'dsp', 'lsb']" in page
    assert 'Legacy: zero position' in page
    assert 'Legacy: unregistered' in page
