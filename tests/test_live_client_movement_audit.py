"""Read-only Ashita v4 movement capability audit never invokes write-like methods."""
from pathlib import Path
from lupa import LuaRuntime

SOURCE = (Path(__file__).resolve().parents[1] / "addons/workbench_live/workbench_movement_audit.lua").read_text()

def test_api_presence_does_not_execute_write_methods():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
        write_calls=0
        entity = {}
        function entity:SetPosition() write_calls=write_calls+1; error('must not write') end
        function entity:GetLocalX() return 5 end
        memory = {}
        function memory:GetWarpPointer() write_calls=write_calls+1; error('must not dereference') end
        core = {}
        function core:GetMemoryManager() return memory end
        packet = {}
        function packet:AddOutgoingPacket() write_calls=write_calls+1; error('must not inject') end
        function get_entity() return entity end
    ''')
    audit = lua.execute(SOURCE)
    report = audit.inspect(lua.globals().core, lua.globals().get_entity, lua.globals().packet)
    assert report["mode"] == "read_only"
    assert report["movement_verified"] is False
    assert report["memory_write_api_candidates"]["warp_pointer"] is True
    assert report["packet_api_candidates"]["add_outgoing_packet"] is True
    assert lua.globals().write_calls == 0

def test_missing_interfaces_report_unverified():
    lua = LuaRuntime(unpack_returned_tuples=True)
    audit = lua.execute(SOURCE)
    report = audit.inspect(None, None, None)
    assert report["memory_manager_present"] is False
    assert report["movement_verified"] is False
    assert "movement verified=no" in audit.summary(report)
