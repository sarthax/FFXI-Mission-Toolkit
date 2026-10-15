from workbench.domains.assault_readiness import assess,assess_all


def test_unknown_is_not_a_pass():
    m={"reviews":{},"issue_crossrefs":[],"shared_dependencies":[]}
    result=assess(m)
    assert result["status"]=="needs_evidence"
    assert len(result["unknown"])==3


def test_issue_and_shared_blockers_override_unknown():
    m={"reviews":{},"issue_crossrefs":[{"id":1,"reviews":{"dsp_port":{"state":"blocked"}}}],
       "shared_dependencies":[{"title":"Navmesh","topaz":"fixed","port":"open","validation":"unreviewed"}]}
    result=assess(m)
    assert result["status"]=="blocked"
    assert len(result["blockers"])==2


def test_all_stages_validated():
    m={"reviews":{s:{"state":"validated"} for s in ("implementation","port","validation")},
       "issue_crossrefs":[{"id":1,"reviews":{s:{"state":"fixed"} for s in ("topaz","dsp_port","dsp_validation")}}],
       "shared_dependencies":[{"title":"Portals","topaz":"fixed","port":"fixed","validation":"fixed"}]}
    assert assess(m)["status"]=="validated"
    assert assess_all([m])=={"validated":1}
