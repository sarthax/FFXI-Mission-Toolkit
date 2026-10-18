from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_duplicate_ids_are_never_classified_as_unique():
    assert "if (map.length > 1 || live.length > 1) kind = 'ambiguous';" in SOURCE
    assert "else if (!map.length) kind = 'live_only';" in SOURCE
    assert "else if (!live.length) kind = 'server_only';" in SOURCE
    assert "map.length <= 1) kind = 'last_seen';" in SOURCE

def test_ambiguity_count_is_visible():
    assert "row.kind === 'ambiguous' ? ' (' + row.map + ' map / ' + row.live + ' live)'" in SOURCE
