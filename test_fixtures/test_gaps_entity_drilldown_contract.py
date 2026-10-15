"""Guard Data Gaps entity deep-link and source-evidence export contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gaps_entity_filter_and_csv_contract():
    host = (ROOT / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    gaps = (ROOT / "gui/templates/gaps.html").read_text(encoding="utf-8")
    viewer = (ROOT / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")
    browse = host.split('@app.get("/gaps",', 1)[1].split('@app.get("/gaps/report")', 1)[0]
    export = host.split('@app.get("/gaps/report")', 1)[1].split("SQL_TABLES = {", 1)[0]
    assert "entity_id: int | None = None" in browse
    assert "entity_id: int | None = None" in export
    assert 'row["entity_id"] == entity_id' in browse
    assert 'row["entity_id"] == entity_id' in export
    assert '"values", "field_flags"' in export
    assert 'json.dumps(row[nested]' in export
    assert 'name="entity_id"' in gaps
    assert 'entity_id={{ entity_id if entity_id is not none else' in gaps
    assert "'&mode=compare&source=dsp&entity_id='" in viewer
    assert "entity.live_observation &&" in viewer
