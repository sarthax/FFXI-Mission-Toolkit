"""Regression coverage for reward retry server-environment isolation."""
import pytest

from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked
from workbench.server_admin.auction_house.reward_history_api import validate_retry_environment


ORIGINAL = {"name": "DSP-Test", "family": "dsp", "environment": "test"}


def test_retry_accepts_same_named_test_environment():
    assert validate_retry_environment(ORIGINAL, dict(ORIGINAL)) is None


@pytest.mark.parametrize(
    "active",
    [
        {"name": "Other-Test", "family": "dsp", "environment": "test"},
        {"name": "DSP-Test", "family": "topaz", "environment": "test"},
        {"name": "DSP-Test", "family": "dsp", "environment": "live"},
        {"name": "DSP-Test", "family": "dsp"},
        {},
    ],
)
def test_retry_rejects_mismatched_or_unknown_environment(active):
    with pytest.raises(LegacyTestExecutionBlocked, match="original named server environment"):
        validate_retry_environment(ORIGINAL, active)


def test_retry_rejects_old_campaign_missing_identity():
    with pytest.raises(LegacyTestExecutionBlocked):
        validate_retry_environment({"family": "dsp"}, ORIGINAL)
