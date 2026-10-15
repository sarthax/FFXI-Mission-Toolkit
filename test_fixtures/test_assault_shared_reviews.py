"""Shared Assault infrastructure evidence and explicit cross-mission scope."""
import pytest
from workbench.domains.assault_shared_reviews import update, link, read


def test_shared_review_and_mission_links(tmp_path):
    path=tmp_path/"reviews.db"
    topics={"Whitegate infrastructure", "System-wide"}
    update("System-wide","topaz","fixed","historical repair","fix log §5",topics=topics,path=path)
    update("System-wide","dsp_port","blocked","needs port",topics=topics,path=path)
    link("System-wide",42,topics=topics,path=path)
    link("System-wide",42,topics=topics,path=path)
    result=read(path)
    assert len(result["reviews"])==2
    assert len(result["history"])==2
    assert result["links"]==[{"topic":"System-wide","mission":42}]
    link("System-wide",42,topics=topics,path=path,unlink=True)
    assert read(path)["links"]==[]


def test_shared_fix_requires_evidence_and_valid_scope(tmp_path):
    path=tmp_path/"reviews.db"
    topics={"Whitegate"}
    with pytest.raises(ValueError,match="evidence"):
        update("Whitegate","dsp_validation","fixed",topics=topics,path=path)
    with pytest.raises(ValueError,match="Unknown"):
        link("Other",42,topics=topics,path=path)
    with pytest.raises(ValueError,match="mission"):
        link("Whitegate",51,topics=topics,path=path)
    assert read(path)["history"]==[]


def test_shared_review_ui_contract():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    html=(root/"gui/templates/domain_assault.html").read_text(encoding="utf-8")
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert 'id="assault-shared"' in html
    assert '/domains/assault/shared/review' in html
    assert '/domains/assault/shared/link' in html
    assert 'section.history' in html
    assert '@app.post("/domains/assault/shared/review")' in host
