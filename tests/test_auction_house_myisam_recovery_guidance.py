"""Read-only DSP MyISAM recovery guidance contracts."""
import pytest

from workbench.server_admin.auction_house.recovery_guidance import myisam_recovery_guidance


@pytest.mark.parametrize("operation", ["player_listing", "player_purchase"])
def test_recovery_guidance_never_claims_crash_atomicity(operation):
    result = myisam_recovery_guidance(operation, auction_id=23, character_id=45)
    assert result["atomic"] is False
    assert result["crash_window"] is True
    assert result["automatic_recovery_safe"] is False
    assert result["auction_id"] == 23
    assert result["character_id"] == 45
    assert any("never auto-replay" in step for step in result["operator_checks"])


def test_purchase_requires_seller_settlement_check():
    result = myisam_recovery_guidance("player_purchase")
    assert any("delivery_box" in step for step in result["operator_checks"])


def test_listing_requires_duplicate_item_guard():
    result = myisam_recovery_guidance("player_listing")
    assert any("Do not restore" in step for step in result["operator_checks"])


@pytest.mark.parametrize("operation,auction_id,char_id", [
    ("unsupported", None, None), ("player_listing", 0, None),
    ("player_purchase", None, -1),
])
def test_invalid_recovery_requests_fail_closed(operation, auction_id, char_id):
    with pytest.raises(ValueError):
        myisam_recovery_guidance(operation, auction_id=auction_id, character_id=char_id)
