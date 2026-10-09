"""Auction House final hardening: no game DB or Windows client required."""
from datetime import datetime, timedelta, timezone

import pytest

from workbench.server_admin.auction_house.reward_templates import RewardTemplateError
from workbench.server_admin.auction_house.reward_schedules import (
    create_schedule, cancel_schedule, get_schedule, list_schedules, _connect,
)
from workbench.server_admin.auction_house.reward_schedule_worker import _claim, _identity_matches
from workbench.server_admin.auction_house.reward_attempt_journal import (
    begin_attempt, mark_recipient, finish_attempt, get_attempt, list_attempts,
)
from workbench.server_admin.auction_house.recovery_journal import (
    begin_case, set_case_status, list_cases,
)
from workbench.server_admin.auction_house.augmented_rewards import (
    inspect_augmented_reward, reject_unverified_augmented_bundle,
)
from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked


ENV = {"name": "DSP Test", "family": "dsp", "environment": "test"}
ITEMS = [{"item_id": 123, "quantity": 1}]


def test_one_time_schedule_approval_cancel_and_no_duplicate_claim(tmp_path):
    path = tmp_path / "schedule.db"
    due = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    schedule = create_schedule(
        due_utc=due, environment=ENV, recipient_mode="selected",
        character_ids=[11, 12], items=ITEMS, confirmation=ENV["name"], path=path,
    )
    assert schedule["status"] == "pending"
    assert schedule["character_ids"] == [11, 12]
    assert len(list_schedules(path=path)) == 1
    assert not _claim(schedule["schedule_id"], path=path)  # not due
    assert cancel_schedule(schedule["schedule_id"], path=path)["status"] == "cancelled"
    assert not _claim(schedule["schedule_id"], path=path)


def test_due_schedule_claims_at_most_once(tmp_path):
    path = tmp_path / "schedule.db"
    due = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    schedule = create_schedule(
        due_utc=due, environment=ENV, recipient_mode="selected",
        character_ids=[1], items=ITEMS, confirmation=ENV["name"], path=path,
    )
    with _connect(path) as db:
        db.execute("UPDATE ah_reward_schedules SET due_utc=? WHERE schedule_id=?",
                   ((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(), schedule["schedule_id"]))
    assert _claim(schedule["schedule_id"], path=path)
    assert not _claim(schedule["schedule_id"], path=path)
    assert get_schedule(schedule["schedule_id"], path=path)["status"] == "running"


def test_schedules_reject_unknown_or_unapproved_profiles(tmp_path):
    due = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    base = dict(due_utc=due, recipient_mode="selected", character_ids=[1],
                items=ITEMS, path=tmp_path / "schedule.db")
    with pytest.raises(RewardTemplateError, match="confirmation"):
        create_schedule(**base, environment=ENV, confirmation="wrong name")
    with pytest.raises(RewardTemplateError, match="named DSP/Topaz"):
        create_schedule(**base, environment={**ENV, "environment": "live"}, confirmation=ENV["name"])
    with pytest.raises(RewardTemplateError, match="frozen"):
        create_schedule(**{**base, "recipient_mode": "all"},
                        environment=ENV, confirmation=ENV["name"])


def test_environment_binding_rejects_other_server():
    assert _identity_matches(ENV, dict(ENV))
    assert not _identity_matches(ENV, {**ENV, "name": "Other-Test"})
    assert not _identity_matches(ENV, {**ENV, "environment": "live"})


def test_reward_attempt_journal_preserves_unknown_then_completed(tmp_path):
    path = tmp_path / "attempt.db"
    begin_attempt(replay_id="r1", preview_id="p1", environment=ENV, items=ITEMS,
                  recipients=[{"char_id": 1, "char_name": "Alpha"},
                              {"char_id": 2, "char_name": "Beta"}], path=path)
    mark_recipient("r1", 1, "in_flight", path=path)
    report = get_attempt("r1", path=path)
    assert report["unknown_recipients"] == 2
    assert report["reconciliation_required"]
    mark_recipient("r1", 1, "committed", path=path)
    mark_recipient("r1", 2, "in_flight", path=path)
    mark_recipient("r1", 2, "failed", "Delivery was rolled back", path=path)
    assert finish_attempt("r1", path=path)["status"] == "partial"
    summary = list_attempts(path=path)[0]
    assert summary["committed"] == 1 and summary["failed"] == 1
    assert summary["unknown"] == 0
    with pytest.raises(ValueError):
        mark_recipient("r1", 1, "in_flight", path=path)


def test_recovery_cases_are_persistent_and_do_not_autofix(tmp_path):
    path = tmp_path / "cases.db"
    cid = begin_case(operation="player_purchase", environment=ENV,
                     evidence={"buyer_id": 123, "gil_before": 1000}, path=path)
    cases = list_cases(path=path)
    assert len(cases) == 1 and cases[0]["automatic_recovery_safe"] is False
    assert cases[0]["status"] == "possibly_interrupted"
    set_case_status(cid, "recovery_required", details={"rollback": "uncertain"}, path=path)
    assert list_cases(path=path)[0]["evidence"]["outcome"]["rollback"] == "uncertain"


def test_augment_codec_preview_is_not_an_unverified_mail_write(monkeypatch):
    from workbench.editors.character import equipment_augments
    monkeypatch.setattr(equipment_augments, "augment_catalog",
                        lambda root: {"rows": [{"id": 7, "effects": [{"mod": 1}]}]})
    result = inspect_augmented_reward(
        family="dsp", item_id=123, augments=[{"id": 7, "value": 2}],
        server_root="/verified/dsp",
    )
    assert result["encoded_bytes"] == 24
    assert result["delivery_enabled"] is False
    assert result["requested_augments"][0]["id"] == 7
    with pytest.raises(LegacyTestExecutionBlocked):
        reject_unverified_augmented_bundle([
            {"item_id": 123, "quantity": 1, "augments": [{"id": 7, "value": 2}]},
        ])



def test_augmented_write_flag_is_off_by_default(monkeypatch):
    from workbench.server_admin.auction_house.augmented_delivery import (
        augmented_test_writes_enabled, _verify_dsp_mail_source,
    )
    monkeypatch.delenv("FFXI_MISSION_TOOLKIT_AH_AUGMENTED_REWARD_TEST_WRITES", raising=False)
    assert not augmented_test_writes_enabled()


def test_augmented_dsp_mail_source_requires_extra_readback(tmp_path):
    from workbench.server_admin.auction_house.augmented_delivery import _verify_dsp_mail_source
    from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked
    src = tmp_path / "src" / "map"
    src.mkdir(parents=True)
    code = src / "packet_system.cpp"
    code.write_text("FROM delivery_box WHERE charid\nmemcpy(PItem->m_extra, extra\n")
    with pytest.raises(LegacyTestExecutionBlocked, match="not source verified"):
        _verify_dsp_mail_source(tmp_path)
    code.write_text(
        "FROM delivery_box WHERE charid\nmemcpy(PItem->m_extra, extra\n"
        "charutils::AddItem(PChar, LOC_INVENTORY, itemutils::GetItem(PItem)\n"
    )
    assert _verify_dsp_mail_source(tmp_path) is None


def test_augmented_preview_fingerprint_binds_specific_encoded_instance(monkeypatch):
    from workbench.server_admin.auction_house import augmented_delivery as ad
    monkeypatch.setattr(ad, "_verify_dsp_mail_source", lambda root: None)
    monkeypatch.setattr(ad, "_resolve_recipients", lambda service, **kwargs:
                        [{"char_id": 7, "char_name": "Buyer"}])
    monkeypatch.setattr(ad, "inspect_augmented_reward",
                        lambda **kwargs: {"encoded_inventory_extra_hex":
                                          "07" * 24 if kwargs["augments"][0]["value"] == 1 else "08" * 24,
                                          "requested_augments": kwargs["augments"]})
    class FakeService:
        def item_snapshot(self, item_id):
            return {"name": "Test Sword", "stack_size": 1}
    a = ad.preview_augmented_delivery(
        service=FakeService(), environment=ENV, server_root="/source",
        character_id=7, item_id=123, augments=[{"id": 7, "value": 1}],
    )
    b = ad.preview_augmented_delivery(
        service=FakeService(), environment=ENV, server_root="/source",
        character_id=7, item_id=123, augments=[{"id": 7, "value": 2}],
    )
    assert a["preview_token"] != b["preview_token"]
    assert a["quantity"] == 1
