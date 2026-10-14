"""Assault backlog filtering uses only recorded review decisions."""
import pytest
from workbench.domains.assault_backlog import backlog


def test_actionable_filters_do_not_infer_topaz_completion():
    missions = [{"number": 42, "name": "Lamia No.13", "zone": "Ilrusi Atoll",
                 "issue_crossrefs": [
                     {"id": 1, "text": "Lamia charm animation", "candidates": [{}],
                      "reviews": {"topaz": {"state": "fixed"}, "dsp_port": None, "dsp_validation": None}},
                     {"id": 2, "text": "Lockbox rewards", "candidates": [],
                      "reviews": {"topaz": {"state": "fixed"}, "dsp_port": {"state": "fixed"},
                                  "dsp_validation": None}},
                     {"id": 3, "text": "Spawn blocker", "candidates": [],
                      "reviews": {"topaz": None, "dsp_port": {"state": "blocked"},
                                  "dsp_validation": None}}]}]
    assert [x["issue"] for x in backlog(missions, status="topaz_fixed_unported")] == [1]
    assert [x["issue"] for x in backlog(missions, status="ported_awaiting_test")] == [2]
    assert [x["issue"] for x in backlog(missions, status="blocked")] == [3]
    assert [x["issue"] for x in backlog(missions, search="charm")] == [1]
    assert backlog(missions, zone="Periqia") == []
    assert backlog(missions, status="open") == []
    with pytest.raises(ValueError):
        backlog(missions, status="unsupported")


def test_backlog_ui_anchors():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    ui=(root/"gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert 'id="assault-backlog"' in ui
    assert 'href="#assault-{{ row.mission }}-issue-{{ row.issue }}"' in ui
    assert 'name="backlog_status"' in ui
