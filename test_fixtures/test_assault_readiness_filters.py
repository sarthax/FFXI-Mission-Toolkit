import pytest
from workbench.domains.assault_readiness_filters import filter_missions

def test_ready_to_test_requires_confirmed_implementation_and_port():
    def mission(number, i, p, v, readiness="needs_evidence"):
        return {"number":number,"zone":"Periqia","readiness":{"status":readiness},
                "reviews":{"implementation":{"state":i},"port":{"state":p},"validation":{"state":v}}}
    entries=[mission(1,"validated","validated","pending"),
             mission(2,"unverified","validated","pending"),
             mission(3,"validated","unverified","pending"),
             mission(4,"validated","validated","pending","blocked"),
             mission(5,"validated","validated","validated","validated")]
    assert [m["number"] for m in filter_missions(entries,status="ready_for_live_test")]==[1]
    assert [m["number"] for m in filter_missions(entries,status="port_pending")]==[3]
    assert [m["number"] for m in filter_missions(entries,status="blocked")]==[4]
    assert filter_missions(entries,zone="Ilrusi Atoll")==[]
    with pytest.raises(ValueError):
        filter_missions(entries,status="other")

def test_readiness_filter_ui_is_separate_from_issue_backlog():
    from pathlib import Path
    page=(Path(__file__).resolve().parents[1]/"gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert 'name="readiness_zone"' in page
    assert 'name="readiness_status"' in page
    assert 'name="backlog_status"' in page
    assert 'id="readiness-results"' in page

def test_live_test_queue_requires_independent_issue_and_shared_port_evidence():
    mission={"number":12,"zone":"Periqia",
             "readiness":{"status":"needs_evidence"},
             "reviews":{"implementation":{"state":"validated"},"port":{"state":"validated"},
                        "validation":{"state":"pending"}},
             "issue_crossrefs":[{"id":1,"reviews":{"dsp_port":{"state":"unreviewed"}}}],
             "shared_dependencies":[{"title":"Portal","port":"fixed"}]}
    assert filter_missions([mission],status="ready_for_live_test")==[]
    mission["issue_crossrefs"][0]["reviews"]["dsp_port"]["state"]="fixed"
    assert [m["number"] for m in filter_missions([mission],status="ready_for_live_test")]==[12]
    mission["shared_dependencies"][0]["port"]="unreviewed"
    assert filter_missions([mission],status="ready_for_live_test")==[]
    mission["shared_dependencies"][0]["port"]="not_applicable"
    assert [m["number"] for m in filter_missions([mission],status="ready_for_live_test")]==[12]
