#!/usr/bin/env python3
"""Static regression contracts for modular cross-capture Evidence Search."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = (ROOT / "gui_server.py").read_text(encoding="utf-8")
    related_service = (ROOT / "workbench" / "core" / "services" / "capture_related_evidence.py").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "capture_search.html").read_text(encoding="utf-8")

    for module in (
        '"events": {',
        '"packets": {',
        '"entities": {',
        '"battle": {',
        '"items": {',
        '"vendors": {',
        '"crafting": {',
        '"chat": {',
        '"spatial": {',
        '"environment": {',
    ):
        assert module in server, module

    # Spatial search must not emit every path point as an individual result.
    assert "COUNT(*) AS" not in server or "ENTITY_PATH" in server
    assert "GROUP BY p.capture_id,p.zone_db,p.entity_id,c.capture_label" in server
    assert "COUNT(DISTINCT p.leg)" in server
    assert "s.family IN ('poitrack_db','spawntrack_csv')" in server

    # Environment search stays on explicit normalized families.
    assert "s.family IN ('weathertrack_db','conquesttrack_csv')" in server
    assert "CASE WHEN s.family='weathertrack_db' THEN 'WEATHER' ELSE 'WORLD_STATE' END" in server

    assert "Spatial & Movement" in template or "module_meta.label" in template
    assert "Evidence Search" in template
    assert "Data Explorer" in template

    # Related Evidence must be provenance-driven rather than timestamp-neighbor guessing.
    related_template = (ROOT / "gui" / "templates" / "capture_related_evidence.html").read_text(
        encoding="utf-8"
    )
    assert "def _capture_related_locators(" in server
    assert "same source byte span" in server
    assert "same source line span" in server
    assert "same SQLite source row" in server
    assert "source_sha256" in server
    assert "timestamp proximity" not in server.lower()
    assert "/related-evidence" in server
    assert "Related Evidence" in template
    assert "Timestamp proximity" in related_template
    assert "same hashed physical source" in related_template
    assert "list_non_temporal_matches" in server
    assert "Explicit packet correlation" in related_template
    assert "Timestamp/alignment" in related_template
    assert "ambiguous candidates" in related_template

    # Cross-module entity expansion must use numeric identity, never names or timestamp proximity.
    assert "def _capture_entity_identity_matches(" in server
    assert "same captured numeric entity id" in related_service
    assert "len(npc_rows) != 1" in related_service
    assert "Entity identity" in related_template
    assert "same zone" in " ".join(related_template.lower().split())
    assert "Names and timestamp proximity are not identity keys" in related_template
    assert "def _capture_item_identity_matches(" in server
    assert "same captured ordinary item id" in related_service
    assert "Key-item IDs are a separate namespace" in related_template
    assert "Item identity" in related_template

    print("Capture Evidence Search module regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
