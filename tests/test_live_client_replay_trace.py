"""Read-only trace follows replay cursor and respects zone boundaries."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.replay import RecordedTelemetryReplay


def frame(t, zone):
    return {"schema_version":1,"client_id":"sample","client_version":"fixture",
            "character":"Hero","adapter":"fixture","observed_at":t,
            "position":{"zone_id":zone,"x":t*5,"y":0,"z":t*3,"heading":0},
            "entities":[]}


def test_trace_endpoint_and_rewind():
    registry=ReplayRegistry()
    registry.add("sample",RecordedTelemetryReplay("sample",[frame(1,100),frame(2,100),frame(3,101),frame(4,100)]))
    client=TestClient(FastAPI())
    app=FastAPI()
    app.include_router(create_registry_router(registry))
    client=TestClient(app)
    assert client.get("/live-client/replay/trace?client_id=missing").status_code==404
    registry.advance("sample")
    registry.advance("sample")
    points=client.get("/live-client/replay/trace?client_id=sample").json()["points"]
    assert len(points)==2 and points[-1]["x"]==10
    registry.advance("sample")
    registry.advance("sample")
    assert [p["zone_id"] for p in client.get("/live-client/replay/trace?client_id=sample").json()["points"]]==[100,100,101,100]
    registry.navigate("sample","restart")
    assert len(client.get("/live-client/replay/trace?client_id=sample").json()["points"])==1


def test_trace_bounded():
    replay=RecordedTelemetryReplay("sample",[frame(i,i%2+100) for i in range(1,51)])
    for _ in range(50):replay.advance()
    points=replay.path_points(max_points=5)
    assert len(points)<=6 and points[-1]["frame"]==50
