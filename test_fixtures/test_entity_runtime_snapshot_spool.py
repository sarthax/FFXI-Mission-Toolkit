"""Read-only spool parser rejects missing, oversized and ambiguous snapshots."""
import json

from workbench.devtools.research.entity_runtime_provider import TrustedRuntimeProvider
from workbench.devtools.research.entity_runtime_snapshot_spool import RuntimeSnapshotSpool


def _sample():
    return {"source":"server_runtime","zone":87,"server_entity_id":17215539,
            "instance_id":"instance-a","observed_at":1000.0,"state":"active"}


def test_server_sample_round_trip(tmp_path):
    (tmp_path/"entity_runtime_snapshot.json").write_text(json.dumps({
        "producer":"server_diagnostic","entities":[_sample()]}))
    provider = TrustedRuntimeProvider(RuntimeSnapshotSpool(tmp_path))
    assert provider.inspect(zone=87, server_entity_id=17215539,
                            instance_id="instance-a", now=1001.)["runtime_status"] == "active"


def test_ambiguous_records_fail_closed(tmp_path):
    (tmp_path/"entity_runtime_snapshot.json").write_text(json.dumps({
        "producer":"server_diagnostic","entities":[_sample(), _sample()]}))
    provider = TrustedRuntimeProvider(RuntimeSnapshotSpool(tmp_path))
    assert provider.inspect(zone=87, server_entity_id=17215539,
                            instance_id="instance-a", now=1001.)["runtime_status"] == "unknown"


def test_untrusted_marker_and_oversize_fail_closed(tmp_path):
    file = tmp_path/"entity_runtime_snapshot.json"
    file.write_text(json.dumps({"producer":"client","entities":[_sample()]}))
    spool = RuntimeSnapshotSpool(tmp_path)
    assert spool(zone=87,server_entity_id=17215539,instance_id="instance-a") is None
    file.write_bytes(b"x"*(64*1024+1))
    assert spool(zone=87,server_entity_id=17215539,instance_id="instance-a") is None
