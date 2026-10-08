"""Read-only telemetry producer schema and file-bridge compatibility."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge
from workbench.runtime.live_client.producer import TelemetryProducer


class Source:
    def __init__(self, client_id="demo"):
        self.client_id=client_id
        self.timestamp=1
    def observe(self):
        return {"schema_version":1,"client_id":self.client_id,
                "client_version":"unverified","character":"Hero",
                "adapter":"fixture","observed_at":self.timestamp,
                "position":{"zone_id":100,"x":5,"y":6,"z":7,"heading":8},
                "entities":[]}


def test_producer_to_file_bridge():
    with TemporaryDirectory() as folder:
        path=Path(folder)/"telemetry.jsonl"
        source=Source()
        producer=TelemetryProducer(path,"demo",source)
        bridge=FileTelemetryBridge(path,"demo")
        assert producer.sample_once()==1
        assert bridge.poll()==1
        assert bridge.feed.snapshot().position.x==5
        with pytest.raises(ValueError):
            producer.sample_once()
        source.timestamp=2
        assert producer.sample_once()==2
        assert bridge.poll()==1
        assert bridge.feed.snapshot().observed_at==2


def test_cross_client_rejected_before_write():
    with TemporaryDirectory() as folder:
        path=Path(folder)/"telemetry.jsonl"
        producer=TelemetryProducer(path,"demo",Source("wrong"))
        with pytest.raises(ValueError):
            producer.sample_once()
        assert not path.exists()
