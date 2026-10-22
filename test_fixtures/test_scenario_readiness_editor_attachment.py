"""Synthetic #1313 editor attachment: route segregation, origin and pairing guards."""
from copy import deepcopy
import json
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from test_capture_readiness_viewer import pair
from workbench.server_admin.scenario_authoring.editor_router import (
    EvidenceReviewRequest, PairedReadinessRequest,
    inspect_evidence_handoff, inspect_readiness_handoff,
)


def request(headers=None, host="127.0.0.1"):
    all_headers = {"content-type": "application/json", "x-requested-with": "toolkit-ui",
                   "origin": "http://127.0.0.1:8000"}
    all_headers.update(headers or {})
    scope = {"type": "http", "method": "POST", "scheme": "http",
             "server": ("127.0.0.1", 8000), "client": (host, 8001),
             "path": "/scenario-developer/handoff/readiness/inspect",
             "headers": [(k.encode(), v.encode()) for k, v in all_headers.items()]}
    return Request(scope)


def test_paired_route_returns_unapproved_display_and_leaves_canonical_inspector_separate():
    review, sidecar = pair()
    untouched = json.dumps([review, sidecar], sort_keys=True)
    result = inspect_readiness_handoff(request(), PairedReadinessRequest(review=review, sidecar=sidecar))
    assert result["canonical_step_associations"] == "UNASSIGNED"
    assert result["scenario_specification"] is None
    assert result["execution_enabled"] is False
    assert result["approved_for_execution"] is False
    assert result["verdict"] == "UNKNOWN"
    assert json.dumps([review, sidecar], sort_keys=True) == untouched
    with pytest.raises(HTTPException) as err:
        inspect_evidence_handoff(request(), EvidenceReviewRequest(review=sidecar))
    assert err.value.status_code == 422


@pytest.mark.parametrize("headers,host,code", [
    ({}, "192.0.2.1", 403),
    ({"origin": "https://attacker.invalid"}, "127.0.0.1", 403),
    ({"x-requested-with": "other"}, "127.0.0.1", 403),
    ({"content-type": "text/plain"}, "127.0.0.1", 415),
    ({"content-length": "bad"}, "127.0.0.1", 400),
    ({"content-length": "9100001"}, "127.0.0.1", 413),
])
def test_route_rejects_untrusted_envelopes(headers, host, code):
    review, sidecar = pair()
    with pytest.raises(HTTPException) as err:
        inspect_readiness_handoff(request(headers, host), PairedReadinessRequest(review=review, sidecar=sidecar))
    assert err.value.status_code == code


def test_route_refuses_cross_capture_tampered_digest_and_forged_approval():
    review, sidecar = pair()
    for field, value in (("capture_id", sidecar["capture_id"] + 1),
                         ("original_handoff_projection_sha256", "0" * 64),
                         ("approved_for_execution", True)):
        changed = deepcopy(sidecar)
        changed[field] = value
        with pytest.raises(HTTPException) as err:
            inspect_readiness_handoff(request(), PairedReadinessRequest(review=review, sidecar=changed))
        assert err.value.status_code == 422
