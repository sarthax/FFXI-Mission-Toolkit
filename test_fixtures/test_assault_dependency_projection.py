from workbench.domains.assault_dependency_projection import project


def test_dependencies_deduplicated_and_scoped():
    missions=[{"number":42,"zone":"Ilrusi Atoll"},{"number":41,"zone":"Ilrusi Atoll"},{"number":32,"zone":"Periqia"}]
    shared=[{"title":"Zone timeout", "missions":[42],
             "zones":[{"zone":"Ilrusi Atoll","evidence":"Zone.lua CSID 102"}],
             "reviews":{"topaz":{"state":"fixed"},"dsp_port":None,"dsp_validation":None}},
            {"title":"Appraisal", "missions":[32],"zones":[],"reviews":{}}]
    project(missions,shared)
    assert len(missions[0]["shared_dependencies"])==1
    assert missions[0]["shared_dependencies"][0]["scope"]=="direct + zone"
    assert missions[1]["shared_dependencies"][0]["scope"]=="zone"
    assert missions[2]["shared_dependencies"][0]["scope"]=="direct"
    assert missions[0]["shared_dependencies"][0]["validation"]=="unreviewed"
    assert missions[0]["shared_dependencies"][0]["evidence"]==["Zone.lua CSID 102"]


def test_shared_dependency_ui():
    from pathlib import Path
    page=(Path(__file__).resolve().parents[1]/"gui/templates/domain_assault.html").read_text(encoding="utf-8")
    assert "mission.shared_dependencies" in page
    assert "#assault-shared-{{ dep.section_id }}" in page
