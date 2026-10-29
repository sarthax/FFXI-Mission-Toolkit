import copy
import pytest
from workbench.server_admin.feature_testing.draft_preview import preview_draft
from workbench.server_admin.feature_testing.test_specifications import specification

def draft():
    doc=copy.deepcopy(specification("inventory_observation","INV-OBS-01"))
    doc["case_id"]="INV-DRAFT-02"
    return doc

def test_draft_preview_is_nonexecuting():
    r=preview_draft(draft(),{"client_bag":[],"db_bag":[],"client_safe":[],"db_safe":[]})
    assert r["verdict"]=="PASS"
    assert r["preview_only"] is True and r["persisted"] is False
    assert r["evidence_authenticated"] is False
    assert r["execution_enabled"] is False

def test_draft_preview_missing_is_blocked():
    r=preview_draft(draft(),{"client_bag":[],"db_bag":[]})
    assert r["verdict"]=="BLOCKED"

def test_draft_preview_denies_runner_binding():
    doc=draft()
    doc["runner"]="xiheadless_observation_v1"
    with pytest.raises(ValueError):
        preview_draft(doc,{})

def test_designer_shows_form_and_advanced_json():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/"gui/templates/feature_testing.html").read_text(encoding="utf-8")
    for key in ("ft-guided-designer","ft-design-add","ft-design-generate","ft-design-preview","ft-draft-json"):
        assert key in source
