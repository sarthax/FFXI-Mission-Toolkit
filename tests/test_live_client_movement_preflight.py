"""Nudge preflight must never silently authorize writes."""
from workbench.runtime.live_client.models import ClientSnapshot, Position
from workbench.runtime.live_client.movement_preflight import evaluate_nudge


def params():
    return dict(snapshot=ClientSnapshot("ashita-a","verified-build","Hero",Position(235,1,2,3),10,"ashita"),
                target=Position(235,1.25,2,3),selected_client="ashita-a",
                selected_character="Hero",expected_zone=235,now=10.25,
                receiver_connected=True,authorized_dev_session=True,
                adapter_supports_writes=True,version_verified=True,
                independent_alignment_verified=True)


def test_eligible_proposal_does_not_execute():
    result=evaluate_nudge(**params())
    assert result.allowed and not result.executed and result.distance==0.25


def test_default_denies_writes_and_alignment():
    p=params()
    p["authorized_dev_session"]=False
    p["independent_alignment_verified"]=False
    r=evaluate_nudge(**p)
    assert not r.allowed
    assert "alignment_unverified" in r.reasons
    assert "write_authorization_unavailable" in r.reasons


def test_rejects_stale_wrong_zone_wrong_character_or_oversized_step():
    for change, reason in [
        (dict(now=20),"stale_snapshot"),
        (dict(expected_zone=236),"zone_mismatch"),
        (dict(selected_character="Other"),"identity_mismatch"),
        (dict(target=Position(235,7,2,3)),"step_out_of_bounds"),
        (dict(receiver_connected=False),"receiver_not_connected"),
    ]:
        p=params();p.update(change)
        assert reason in evaluate_nudge(**p).reasons
