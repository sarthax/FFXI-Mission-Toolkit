"""Safety contract: indexing, positions and missing observations cannot prove despawn."""
from workbench.devtools.research.entity_runtime_evidence import classify_runtime_entity


def test_index_and_absent_observation_are_not_runtime_proof():
    result = classify_runtime_entity(zone=100, server_entity_id=17215539,
                                     indexed_match={"status": "exact"},
                                     client_observation={"fresh": False})
    assert result["runtime_status"] == "unknown"
    assert result["indexed_status"] == "exact"
    assert result["confidence"] == "unverified"


def test_runtime_needs_matching_instance_and_freshness():
    base = dict(zone=100, server_entity_id=17215539, instance_id="instance-a")
    sample = dict(source="server_runtime", zone=100, server_entity_id=17215539,
                  instance_id="instance-b", fresh=True, state="despawned")
    assert classify_runtime_entity(**base, runtime_sample=sample)["runtime_status"] == "unknown"
    sample["instance_id"] = "instance-a"
    sample["fresh"] = False
    assert classify_runtime_entity(**base, runtime_sample=sample)["runtime_status"] == "unknown"
    sample["fresh"] = True
    result = classify_runtime_entity(**base, runtime_sample=sample)
    assert result["runtime_status"] == "despawned"
    assert result["confidence"] == "runtime_reported"


def test_untrusted_source_cannot_claim_hidden():
    result = classify_runtime_entity(zone=100, server_entity_id=17215539,
        instance_id="instance-a", runtime_sample={
            "source":"client", "zone":100, "server_entity_id":17215539,
            "instance_id":"instance-a", "fresh":True, "state":"hidden"})
    assert result["runtime_status"] == "unknown"
