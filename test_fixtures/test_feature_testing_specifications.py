"""Contract tests for non-executable, versioned test specifications."""
import copy
import pytest
from workbench.server_admin.feature_testing.test_specifications import (
    specifications, specification, validate_spec,
)


def test_seeded_specifications_are_valid_and_isolated():
    specs = specifications()
    assert len(specs) == 2
    mog = specification("moghancement", "MOG-09")
    inv = specification("inventory_observation", "INV-OBS-01")
    assert mog["execution_status"] == "verified_runner"
    assert len(mog["assertions"]) == 6
    assert inv["execution_status"] == "design_only"
    assert inv["runner"] == "unassigned"
    assert specification("missing", "UNKNOWN") is None


def test_rejects_unverified_runner_binding():
    inv = copy.deepcopy(specification("inventory_observation", "INV-OBS-01"))
    inv["execution_status"] = "verified_runner"
    inv["runner"] = "xiheadless_observation_v1"
    with pytest.raises(ValueError, match="no verified"):
        validate_spec(inv)


def test_rejects_unsafe_or_unbound_definitions():
    mog = copy.deepcopy(specification("moghancement", "MOG-09"))
    mog["script"] = "os.system('echo bad')"
    with pytest.raises(ValueError, match="unexpected"):
        validate_spec(mog)
    mog = copy.deepcopy(specification("moghancement", "MOG-09"))
    mog["assertions"][0]["operation"] = "eval"
    with pytest.raises(ValueError, match="unsupported"):
        validate_spec(mog)
    mog = copy.deepcopy(specification("moghancement", "MOG-09"))
    mog["observations"].append("../secrets")
    with pytest.raises(ValueError, match="unsupported"):
        validate_spec(mog)


def test_spec_routes_remain_read_only_and_visible():
    from workbench.server_admin.feature_testing.router import test_specifications_api, test_specification_api
    assert len(test_specifications_api()["specifications"]) == 2
    assert test_specifications_api()["execution_enabled"] is False
    assert test_specification_api("moghancement", "MOG-09")["schema_version"] == 1
