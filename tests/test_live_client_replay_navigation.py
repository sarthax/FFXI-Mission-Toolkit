"""Replay remains navigable after the final frame."""
import pytest
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.replay import RecordedTelemetryReplay


def observation(timestamp):
    return {"schema_version":1,"client_id":"demo","client_version":"fixture",
            "character":"Test","adapter":"fixture","observed_at":timestamp,
            "position":{"zone_id":100,"x":float(timestamp),"y":0,"z":0,"heading":0},
            "entities":[]}


def test_replay_end_previous_restart_and_resume():
    replay=RecordedTelemetryReplay("demo",[observation(n) for n in range(1,5)])
    registry=ReplayRegistry()
    registry.add("demo", replay)
    for _ in range(4):
        registry.advance("demo")
    assert registry.status()[0]["remaining_frames"]==0
    assert registry.status()[0]["frame_position"]==4
    assert registry.navigate("demo","previous").snapshot.position.x==3
    assert registry.advance("demo").snapshot.position.x==4
    assert registry.navigate("demo","restart").snapshot.position.x==1
    assert registry.status()[0]["remaining_frames"]==3
    assert registry.advance("demo").snapshot.position.x==2
    with pytest.raises(StopIteration):
        registry.navigate("demo","restart") and registry.navigate("demo","previous")
