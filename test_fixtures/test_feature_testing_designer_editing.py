"""Guided designer regression: multi-row edit controls and persisted draft loading."""
from pathlib import Path


def test_guided_designer_has_editable_assertion_rows_and_saved_drafts():
    html=(Path(__file__).resolve().parents[1]/"gui/templates/feature_testing.html").read_text(encoding="utf-8")
    for token in ("ft-design-assertion-list","ft-design-update","ft-design-remove",
                  "ft-design-load-saved","ft-design-refresh-saved",
                  "ft-design-saved","ft-draft-revision","readAssertion()","loadSpec(s)"):
        assert token in html


def test_saved_draft_still_requires_operator_token():
    from workbench.server_admin.feature_testing.router import draft_list
    from fastapi import HTTPException
    from starlette.requests import Request
    import pytest
    scope={"type":"http","method":"GET","path":"/feature-testing/builder/drafts",
           "headers":[],"scheme":"http","server":("127.0.0.1",8420),"client":("127.0.0.1",12345)}
    with pytest.raises(HTTPException) as exc:
        draft_list(Request(scope),x_test_operator_token=None)
    assert exc.value.status_code==403
