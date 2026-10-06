#!/usr/bin/env python3
"""Regression contract for Dialog Browser research-workbench QOL."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "dialog.html").read_text(encoding="utf-8")
    explore = (ROOT / "src" / "workbench" / "devtools" / "server" / "_explore_event_impl.py").read_text(encoding="utf-8")

    assert "def _parse_dialog_id_query(" in server
    assert "value.lower().startswith(\"0x\")" in server
    assert "def _dialog_event_refs(" in server
    assert "def _enrich_dialog_rows(" in server
    assert "dialog_drift_report" in server
    assert "capture_events" in server
    assert "LIKE ?" in server
    assert 'results = _enrich_dialog_rows(' in server
    assert "SELECT COUNT(*) FROM dialog_text WHERE zoneid = ?" in server
    assert "ORDER BY idx LIMIT ? OFFSET ?" in server
    assert "SELECT COUNT(*) FROM dialog_text WHERE zoneid = ? AND idx < ?" in server

    assert '"message_ids": decompile_summary["message_ids"]' in explore
    assert '"message_refs": message_refs' in explore
    assert '"schema_version": 2' in explore

    assert "Dialog Browser" in template
    assert "decimal ID (7465), or hex ID (0x1D29)" in template
    assert "Zone browse mode" in template
    assert "No search filter is active" in template
    assert "Jump to ID" in template
    assert "page {{ page }} of {{ total_pages }}" in template
    assert "prev" in template and "next" in template
    assert "Research context / implementation links" in template
    assert "IDs.lua mapping" in template
    assert "Events / CSID references" in template
    assert "Runtime capture evidence" in template
    assert "Nearby dialog IDs" in template
    assert "Copy / implementation helpers" in template
    assert "text.{{ d.constant_name }}" in template
    assert "Dialog Drift Overview" in template
    assert "/events/view?zone=" in template
    assert "/entity/{{ c.entity_id }}" in template
    assert "Feature Trace" in template

    print("Dialog Browser research-workbench regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
