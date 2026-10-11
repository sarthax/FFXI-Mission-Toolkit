from pathlib import Path
from workbench.runtime.live_client.telemetry import decode_frame

ROOT = Path(__file__).resolve().parents[1]

def test_live_entity_streaming_integrated():
    live=(ROOT/"addons/workbench_live/workbench_live_ashita.lua").read_text()
    sampler=(ROOT/"addons/workbench_live/workbench_live_direct.lua").read_text()
    observation=(ROOT/"addons/workbench_live/workbench_observation.lua").read_text()
    viewer=(ROOT/"gui/templates/zone_view3d.html").read_text()
    assert "capture_entities = function(id, now)" in live
    assert "id, now, true, true, 128" in live
    assert "now - entity_last >= 0.5" in sampler
    assert "entity_cache = nil" in sampler
    assert "entity_limit or 32" in observation
    assert "id=\"ashita-live-entities\" type=\"checkbox\" checked" in viewer
    assert "entity.server_entity_id ?? entity.client_index" in viewer

def test_decoder_preserves_bounded_entity_stream():
    payload={"schema_version":1,"client_id":"ashita-a","client_version":"v4",
       "character":"Tester","adapter":"ashita-v4-api-experimental","observed_at":1000.,
       "position":{"zone_id":98,"x":1.,"y":2.,"z":3.,"heading":0.},
       "observation_scope":"bounded_loaded_entities","entities_truncated":True,
       "entities":[{"client_index":i+1,"server_entity_id":10000+i,"name":"Mob",
       "position":{"zone_id":98,"x":float(i),"y":0.,"z":0.,"heading":0.}} for i in range(128)]}
    frame=decode_frame(payload)
    assert len(frame.entities)==128
    assert frame.entities_truncated
    assert frame.entities[127].server_entity_id==10127
