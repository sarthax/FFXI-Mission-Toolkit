"""Bounded session spool behavior and durable segment tests."""
import json

import pytest

from workbench.captures.live_capture_spool import LiveCaptureSpool


def packet(sequence, **changes):
    value = dict(schema_version=1, client_id="ashita-a", session_id="s1",
                 sequence=sequence, observed_at_ns=1760000000000000000 + sequence,
                 direction="incoming", opcode=40, raw_hex="28040000",
                 is_injected=False, is_blocked=False, dropped_before=0)
    value.update(changes)
    return value


def test_bounded_queue_and_flush(tmp_path):
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1", queue_capacity=2)
    assert spool.enqueue(packet(1))
    assert spool.enqueue(packet(2))
    assert not spool.enqueue(packet(3))
    assert spool.health()["rejected"] == 1
    assert spool.drain() == 2
    # Producer records source loss and continues with the next sequence.
    assert spool.enqueue(packet(4, dropped_before=1))
    spool.close()
    assert spool.health()["persisted"] == 3
    assert spool.health()["queued"] == 0
    rows = [json.loads(line) for path in tmp_path.glob("*.jsonl") for line in path.read_text().splitlines()]
    assert [x["sequence"] for x in rows] == [1, 2, 4]


def test_reject_wrong_client(tmp_path):
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1")
    with pytest.raises(ValueError):
        spool.enqueue(packet(1, client_id="ashita-b"))


def test_existing_segment_is_never_overwritten(tmp_path):
    (tmp_path / "segment-000001.jsonl").write_text("existing")
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1")
    assert spool.enqueue(packet(1))
    with pytest.raises(FileExistsError):
        spool.drain()
    assert spool.health()["fault"] is not None
    assert (tmp_path / "segment-000001.jsonl").read_text() == "existing"

def test_disk_failure_preserves_queued_packet(tmp_path, monkeypatch):
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1")
    assert spool.enqueue(packet(1))
    def fail_open():
        raise OSError("disk unavailable")
    monkeypatch.setattr(spool, "_open_segment", fail_open)
    with pytest.raises(OSError):
        spool.drain()
    health = spool.health()
    assert health["queued"] == 1
    assert health["persisted"] == 0
    assert health["fault"] == "disk unavailable"


def test_nonblocking_offer_when_worker_lock_held(tmp_path):
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1")
    with spool._lock:
        assert not spool.enqueue(packet(1))
    assert spool.health()["rejected"] == 1

def test_clean_close_emits_checksums(tmp_path):
    from workbench.captures.live_capture_jsonl import parse_manifest
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1")
    assert spool.enqueue(packet(1))
    spool.close()
    client, session, entries = parse_manifest((tmp_path / "manifest.json").read_bytes())
    assert (client, session) == ("ashita-a", "s1")
    assert entries[0]["first_sequence"] == entries[0]["last_sequence"] == 1


def test_first_segment_does_not_record_phantom_range(tmp_path):
    from workbench.captures.live_capture_jsonl import parse_manifest
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1")
    assert spool.enqueue(packet(1))
    spool.close()
    _, _, entries = parse_manifest((tmp_path / "manifest.json").read_bytes())
    assert len(entries) == 1
    assert entries[0]["filename"] == "segment-000001.jsonl"
    assert not (tmp_path / "manifest.json.tmp").exists()


def test_existing_manifest_is_not_replaced(tmp_path):
    target = tmp_path / "manifest.json"
    target.write_text("existing evidence")
    spool = LiveCaptureSpool(tmp_path, "ashita-a", "s1")
    assert spool.enqueue(packet(1))
    with pytest.raises(FileExistsError):
        spool.close()
    assert target.read_text() == "existing evidence"
    assert not (tmp_path / "manifest.json.tmp").exists()
