import pytest
from workbench.runtime.live_client.native_position_compare import PositionSample, compare_native_live

def sample(zone=98, x=208.563, y=242.187, z=32.064, at=100.0):
    return PositionSample(zone, x, y, z, at)

def test_matching_native_and_live_samples():
    result = compare_native_live(sample(), sample(x=208.6, at=100.2))
    assert result["matched"] and result["distance"] < 0.1

def test_zone_and_clock_guard():
    assert compare_native_live(sample(), sample(zone=99))["reason"] == "zone_mismatch"
    assert compare_native_live(sample(), sample(at=104))["reason"] == "samples_not_synchronized"

def test_disagreement_and_invalid_sample():
    result = compare_native_live(sample(), sample(x=214))
    assert not result["matched"] and result["reason"] == "position_mismatch"
    with pytest.raises(ValueError):
        sample(x=float("nan"))
    with pytest.raises(ValueError):
        sample(zone=0)
    with pytest.raises(ValueError):
        compare_native_live(sample(), sample(), tolerance=-1)
