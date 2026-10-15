"""Runtime evidence must fail closed without exact identity and fresh timestamp."""
import pytest

from workbench.devtools.research.entity_runtime_sample import (
    classify_supplied_sample, validate_runtime_sample,
)


def sample():
    return {"source":"server_runtime", "zone":87, "server_entity_id":17215539,
            "instance_id":"instance-a", "observed_at":1000.0, "state":"active"}


def validate(s, now=1001.0):
    return validate_runtime_sample(s, now=now, zone=87,
        server_entity_id=17215539, instance_id="instance-a")


def test_fresh_sample_is_classified():
    s = sample()
    assert validate(s)["fresh"] is True
    result = classify_supplied_sample(zone=87, server_entity_id=17215539,
                                      instance_id="instance-a", now=1001., sample=s)
    assert result["runtime_status"] == "active"


@pytest.mark.parametrize("key,value", [
    ("source","client"), ("zone",88), ("server_entity_id",1),
    ("instance_id","instance-b"), ("observed_at",990.0),
    ("observed_at",1005.0), ("state","unknown"),
])
def test_invalid_samples_cannot_prove_runtime_state(key, value):
    s = sample()
    s[key] = value
    with pytest.raises(ValueError):
        validate(s)
    result = classify_supplied_sample(zone=87, server_entity_id=17215539,
                                      instance_id="instance-a", now=1001., sample=s)
    assert result["runtime_status"] == "unknown"
