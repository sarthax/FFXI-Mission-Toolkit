"""Operator diagnostics are atomic, bounded, and never client-sourced."""
import json

import pytest

from workbench.devtools.research.entity_runtime_snapshot_writer import publish_snapshot
from workbench.devtools.research.entity_runtime_snapshot_spool import RuntimeSnapshotSpool


def entry():
    return {"source":"server_runtime","zone":87,"server_entity_id":17215539,
            "instance_id":"map-1","observed_at":1000.,"state":"active"}


def test_atomic_publish_can_be_consumed(tmp_path):
    path = publish_snapshot(tmp_path,[entry()])
    assert path.name == "entity_runtime_snapshot.json"
    assert json.loads(path.read_text())["producer"] == "server_diagnostic"
    assert RuntimeSnapshotSpool(tmp_path)(zone=87,server_entity_id=17215539,
                                         instance_id="map-1")["state"] == "active"
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_update_keeps_previous_snapshot(tmp_path):
    path = publish_snapshot(tmp_path,[entry()])
    prior = path.read_bytes()
    bad = dict(entry(),source="client")
    with pytest.raises(ValueError):
        publish_snapshot(tmp_path,[bad])
    assert path.read_bytes() == prior


def test_refuses_oversized_batch(tmp_path):
    with pytest.raises(ValueError):
        publish_snapshot(tmp_path,[entry()] * 257)
