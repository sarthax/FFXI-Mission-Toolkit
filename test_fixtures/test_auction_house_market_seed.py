import pytest
from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked
from workbench.server_admin.auction_house.market_seed import execute_market_seed


class _Svc:
    class schema:
        family_hint = "dsp_topaz"
    connection = None


def test_execute_requires_confirmation_before_touching_db():
    env = {"name": "DSP", "family": "dsp", "environment": "test", "is_active": True, "enabled": True}
    with pytest.raises(LegacyTestExecutionBlocked):
        execute_market_seed(_Svc(), env, mode="clear", confirmation="wrong", feature_enabled=True)


def test_blocked_when_not_test_environment():
    env = {"name": "DSP", "family": "dsp", "environment": "live", "is_active": True, "enabled": True}
    with pytest.raises(LegacyTestExecutionBlocked):
        execute_market_seed(_Svc(), env, mode="clear", confirmation="DSP", feature_enabled=True)
