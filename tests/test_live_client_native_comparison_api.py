from types import SimpleNamespace
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router
from pathlib import Path

def test_native_xyz_compare_requires_local_live_client(monkeypatch):
    manager=ManagedLiveReceiver()
    app=FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client=TestClient(app)
    url="/live-client/bridge/position/compare-native"
    payload={"client_id":"ashita-a","zone_id":98,"x":208.563,"y":242.187,"z":32.064}
    assert client.post(url,json=payload).status_code==403
    origin={"origin":"http://testserver"}
    assert client.post(url,json=payload,headers=origin).status_code==409
    monkeypatch.setattr(manager,"status",lambda _:{"connected":True,"snapshot":SimpleNamespace(
        observed_at=time.time(),position=SimpleNamespace(zone_id=98,x=208.563,y=242.187,z=32.064))})
    result=client.post(url,json=payload,headers=origin)
    assert result.status_code==200,result.text
    assert result.json()["matched"] is True
    assert result.json()["mode"]=="read_only"
    assert client.post(url,json={**payload,"zone_id":99},headers=origin).json()["reason"]=="zone_mismatch"
    assert client.post(url,json={**payload,"x":"NaN"},headers=origin).status_code==422

def test_live_console_has_native_comparison_control():
    template=(Path(__file__).resolve().parents[1]/"gui/templates/live_client_bridge.html").read_text()
    assert 'id="native-position-compare"' in template
    assert "request('position/compare-native'" in template
    assert "/wbprobe position" in template
