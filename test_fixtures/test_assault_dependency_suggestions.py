from workbench.domains.assault_dependency_suggestions import suggest

def test_suggest_exact_name_with_evidence_no_automatic_links():
    sections=[{"title":"System-wide", "comments":"Lamia No.13 and Requiem suffer timeout. Lamia No.13 was fixed.", "missions":[32]}]
    missions=[{"number":42,"name":"Lamia No.13"},{"number":32,"name":"Requiem"},{"number":1,"name":"Lamia"}]
    suggest(sections,missions)
    assert [x["mission"] for x in sections[0]["suggested_missions"]]==[42]
    assert sections[0]["missions"]==[32]
    assert sections[0]["suggested_missions"][0]["mentions"]==2
    assert "Lamia No.13" in sections[0]["suggested_missions"][0]["evidence"]


def test_no_guess_without_explicit_mission_name():
    sections=[{"title":"Navmesh", "comments":"Every zone needs denser pathing", "missions":[]}]
    suggest(sections,[{"number":3,"name":"Escort Professor Chanoix"}])
    assert sections[0]["suggested_missions"]==[]
