"""Direct Ashita live sampler state-machine regression without output recordings."""
from pathlib import Path
import pytest

ADDON = Path(__file__).resolve().parents[1] / "addons" / "workbench_live"


def test_direct_live_sampling_does_not_require_file_and_respects_lifecycle():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute("""
        package.path = addon_dir .. '?.lua;' .. package.path
        local current = 100
        os.time = function() return current end
        local sends = {}
        local starts, stops = 0, 0
        local function capture(id, now)
            return {
                source_identity='123:Hero', character='Hero',
                client_id=id, client_version='unverified-ashita-v4-api',
                adapter='ashita-v4-api-experimental', schema_version=1,
                observed_at=now, position={zone_id=235,x=1,y=2,z=3,heading=0},
                entities={}
            }
        end
        local live = require('workbench_live_direct').new({
            capture=capture,
            start_bridge=function(id) starts=starts+1; return true end,
            stop_bridge=function() stops=stops+1 end,
            send=function(id, frame) sends[#sends+1]=frame; return true end,
        })
        assert(live.start('ashita-a'))
        live.sample()
        live.sample()
        current=101
        live.sample()
        assert(#sends==2)
        assert(sends[1]:find('"client_id":"ashita-a"',1,true))
        assert(starts==1)
        live.stop()
        assert(not live.active())
        assert(stops>=1)
    """)


def test_direct_live_refuses_source_changes_or_unavailable_bridge():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute("""
        package.path = addon_dir .. '?.lua;' .. package.path
        local who='Hero'
        local sends = 0
        local function capture(id, now)
            return {
                source_identity='123:'..who, character=who,
                client_id=id, client_version='unverified-ashita-v4-api',
                adapter='ashita-v4-api-experimental', schema_version=1,
                observed_at=now, position={zone_id=235,x=1,y=2,z=3,heading=0},
                entities={}
            }
        end
        local live = require('workbench_live_direct').new({
            capture=capture,
            start_bridge=function() return false end,
            send=function() sends=sends+1; return true end
        })
        assert(not live.start('ashita-b'))
        assert(not live.active())
        live=require('workbench_live_direct').new({
            capture=capture, start_bridge=function() return true end,
            stop_bridge=function() end,
            send=function() sends=sends+1; return true end
        })
        assert(live.start('ashita-b'))
        who='Other'
        live.sample()
        assert(not live.active())
        assert(sends==0)
    """)


def test_transient_bridge_failure_retries_without_recording_or_identity_reset():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute("""
        package.path = addon_dir .. '?.lua;' .. package.path
        local clock = 100
        os.time = function() return clock end
        local starts, sends = 0, 0
        local direct = require('workbench_live_direct').new({
            capture=function(id, now) return {
                source_identity='123:Hero', character='Hero', client_id=id,
                client_version='unverified-ashita-v4-api',
                adapter='ashita-v4-api-experimental', schema_version=1,
                observed_at=now,
                position={zone_id=235,x=1,y=2,z=3,heading=0}, entities={}
            } end,
            start_bridge=function() starts=starts+1; return true end,
            stop_bridge=function() end,
            send=function() sends=sends+1; return sends~=1 end,
        })
        assert(direct.start('ashita-a'))
        direct.sample()
        assert(direct.active())
        assert(starts==2 and sends==2)
        clock=101
        direct.sample()
        assert(direct.active())
        assert(sends==3)
    """)


def test_direct_live_zoning_pauses_then_resumes_without_reprovision():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute("""
        package.path = addon_dir .. '?.lua;' .. package.path
        local observation = require('workbench_observation')
        local tick, zone, sends = 100, 235, 0
        os.time = function() return tick end
        local transitioning = false
        local direct = require('workbench_live_direct').new({
            capture=function(id, now)
                if transitioning then
                    local core = {GetMemoryManager=function() return {
                        GetParty=function() return {
                            GetMemberIsActive=function() return 0 end
                        } end,
                        GetEntity=function() return {} end
                    } end}
                    return observation.capture_ashita(core, function() end, id, now, false)
                end
                return {source_identity='123:Hero',character='Hero',
                    client_id=id,client_version='unverified-ashita-v4-api',
                    adapter='ashita-v4-api-experimental', schema_version=1,
                    observed_at=now, position={zone_id=zone,x=1,y=2,z=3,heading=0}, entities={}}
            end,
            start_bridge=function() return true end,
            stop_bridge=function() end,
            send=function() sends=sends+1; return true end,
        })
        assert(direct.start('ashita-a'))
        direct.sample()
        transitioning=true; tick=101; direct.sample()
        assert(direct.active())
        transitioning=false;zone=107; tick=102; direct.sample()
        assert(direct.active() and sends==1)
        tick=103; direct.sample()
        assert(direct.active() and sends==2)
    """)
