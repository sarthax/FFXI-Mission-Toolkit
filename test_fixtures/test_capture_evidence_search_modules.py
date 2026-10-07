#!/usr/bin/env python3
"""Static regression contracts for modular cross-capture Evidence Search."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_SRC = ROOT / "src" / "workbench"


def main():
    server = (WORKBENCH_SRC / "app" / "_host_impl.py").read_text(encoding="utf-8")
    related_service = (WORKBENCH_SRC / "captures" / "_related_evidence_impl.py").read_text(encoding="utf-8")
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

    # CapLog chat projection is a distinct deterministic family. The service enforces the typed
    # native observation contract; the GUI surfaces the exact shared parser line and suppresses
    # the duplicate generic-provenance card. Text/timestamp similarity and PacketDB row ids remain
    # explicitly excluded as identity keys.
    assert "def chat_native_source_matches(" in related_service
    assert "same CapLog parser observation sequence with typed native source id" in related_service
    assert "Chat native source" in related_template
    normalized_related = " ".join(related_template.split())
    assert "exact same CapLog parser observation" in normalized_related
    assert "PacketDB row-number collisions" in related_template
    assert "is_chat_projection" in related_template
    assert "r.relation == 'same source line span'" in related_template

    # Presentation summaries and handoffs must add context without introducing a new match rule.
    assert "related-summary" in related_template
    assert "source locator" in related_template
    assert "provenance relation" in related_template
    assert "packet match" in related_template
    assert "entity match" in related_template
    assert "item match" in related_template
    assert "dataset_labels" in related_template
    assert "item_family_labels" in related_template
    assert "r.record_type" in related_template
    assert "/captures/search?module=entities&q={{ r.entity_id }}" in related_template
    assert "/captures/search?module=vendors&q={{ r.item_id }}" in related_template
    assert "/captures/search?module=crafting&q={{ r.item_id }}" in related_template
    assert "/captures/search?module=items&q={{ r.item_id }}" in related_template
    assert "/captures/search?module=chat" in related_template

    print("Capture Evidence Search module regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
