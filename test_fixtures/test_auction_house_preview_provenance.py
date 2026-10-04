from datetime import datetime, timedelta, timezone

from src.workbench.server_admin.auction_house.preview_provenance import (
    DEFAULT_PREVIEW_TTL_SECONDS,
    MAX_PREVIEW_TTL_SECONDS,
    MIN_PREVIEW_TTL_SECONDS,
    PREVIEW_TTL_ENV,
    make_preview_provenance,
    preview_ttl_seconds,
    validate_preview_provenance,
)


def _environment():
    return {"profile_id": 7, "name": "AH Test", "environment": "TEST", "family": "lsb", "is_active": True}


def _policy():
    return {
        "family": "lsb",
        "source_kind": "lsb-map-settings",
        "source_path": "/server/settings/default/map.lua",
        "policy_fingerprint": "abc123",
        "policy_ready": True,
    }


def _preview(now=None, ttl_seconds=300):
    preview = {"action": "list_item", "adapter": "lsb-compatible"}
    preview["preview_provenance"] = make_preview_provenance(
        environment=_environment(),
        schema_family_hint="lsb-compatible",
        policy_binding=_policy(),
        action=preview["action"],
        adapter=preview["adapter"],
        now=now,
        ttl_seconds=ttl_seconds,
    )
    return preview


def _validate(preview, now):
    return validate_preview_provenance(
        preview,
        environment=_environment(),
        schema_family_hint="lsb-compatible",
        active_policy_binding=_policy(),
        now=now,
    )


def test_preview_provenance_has_expiry_audit_and_replay_ids():
    created = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)
    preview = _preview(created, 300)
    provenance = preview["preview_provenance"]
    assert provenance["preview_id"]
    assert provenance["audit_id"]
    assert provenance["replay_id"]
    assert len({provenance["preview_id"], provenance["audit_id"], provenance["replay_id"]}) == 3
    assert provenance["replay_protection"] == "consume-on-execute"
    assert provenance["ttl_seconds"] == 300
    assert provenance["created_at_utc"] == "2026-10-04T19:00:00Z"
    assert provenance["expires_at_utc"] == "2026-10-04T19:05:00Z"
    assert _validate(preview, created + timedelta(seconds=299)).binding_ready is True


def test_expired_preview_fails_closed():
    created = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)
    preview = _preview(created, 300)
    check = _validate(preview, created + timedelta(seconds=300))
    assert check.binding_ready is False
    assert "preview_expired" in {issue.code for issue in check.issues}


def test_missing_audit_or_replay_id_fails_closed():
    now = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)
    for key, expected in (("audit_id", "preview_audit_id_missing"), ("replay_id", "preview_replay_id_missing")):
        preview = _preview(now, 300)
        preview["preview_provenance"].pop(key)
        check = _validate(preview, now + timedelta(seconds=1))
        assert check.binding_ready is False
        assert expected in {issue.code for issue in check.issues}


def test_invalid_replay_contract_fails_closed():
    now = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)
    preview = _preview(now, 300)
    preview["preview_provenance"]["replay_protection"] = "reusable"
    check = _validate(preview, now + timedelta(seconds=1))
    assert "preview_replay_contract_invalid" in {issue.code for issue in check.issues}


def test_declared_ttl_must_match_expiry_window():
    now = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)
    preview = _preview(now, 300)
    preview["preview_provenance"]["ttl_seconds"] = 600
    check = _validate(preview, now + timedelta(seconds=1))
    assert "preview_ttl_mismatch" in {issue.code for issue in check.issues}


def test_ttl_configuration_is_bounded_and_invalid_values_fall_back(monkeypatch):
    monkeypatch.delenv(PREVIEW_TTL_ENV, raising=False)
    assert preview_ttl_seconds() == DEFAULT_PREVIEW_TTL_SECONDS
    monkeypatch.setenv(PREVIEW_TTL_ENV, "5")
    assert preview_ttl_seconds() == MIN_PREVIEW_TTL_SECONDS
    monkeypatch.setenv(PREVIEW_TTL_ENV, "999999")
    assert preview_ttl_seconds() == MAX_PREVIEW_TTL_SECONDS
    monkeypatch.setenv(PREVIEW_TTL_ENV, "not-a-number")
    assert preview_ttl_seconds() == DEFAULT_PREVIEW_TTL_SECONDS


def test_malformed_expiry_fails_closed():
    now = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)
    preview = _preview(now, 300)
    preview["preview_provenance"]["expires_at_utc"] = "not-a-date"
    check = _validate(preview, now + timedelta(seconds=1))
    assert check.binding_ready is False
    assert "preview_expiry_invalid" in {issue.code for issue in check.issues}
