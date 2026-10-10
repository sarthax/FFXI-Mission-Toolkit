-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Experimental Ashita v4 API source. Explicit start; no offsets or game writes.
addon.name = 'workbench_live'
addon.author = 'FFXI Mission Toolkit contributors'
addon.version = '0.4.0-experimental'
addon.desc = 'Read-only observation export; client build unverified.'
require('common')
local observation = require('workbench_observation')
local bridge_config_ok, bridge_config = pcall(require, 'workbench_bridge_settings')
local bridge = require('workbench_bridge').new(bridge_config_ok and bridge_config or {enabled=false})
local direct = require('workbench_live_direct').new({
    capture = function(id, now) return observation.capture_ashita(AshitaCore, GetEntity, id, now, false, true) end,
    start_bridge = function(id) return bridge.start(id) end,
    stop_bridge = function() bridge.stop() end,
    send = function(id, frame) return bridge.observe(id, frame) end,
    message = function(msg) print('Workbench Live: ' .. msg) end,
})

local exporter = require('workbench_export').new({
    directory = addon.path,
    exists = ashita.fs.exists,
    message = function(text) print('Workbench Live: ' .. text) end,
    supports_inventory = true,
    on_frame = function(id, line) bridge.observe(id, line) end,
    capture = function(id, now, inventory) return observation.capture_ashita(AshitaCore, GetEntity, id, now, inventory) end,
})
local packets = require('workbench_packets').new({
    directory = addon.path, exists = ashita.fs.exists,
    message = function(text) print('Workbench Live: ' .. text) end,
    context = function()
        local context = exporter.context()
        if not context then return nil end
        local party = AshitaCore:GetMemoryManager():GetParty()
        local active = party:GetMemberIsActive(0)
        assert(type(active) == 'number' and active > 0, 'packet source is logged out')
        context.zone_id = party:GetMemberZone(0)
        local identity = tostring(party:GetMemberServerId(0)) .. ':' .. party:GetMemberName(0)
        assert(identity == context.source_identity, 'packet player identity changed')
        return context
    end,
})
ashita.events.register('packet_in', 'workbench_live_packet_in', function(e) packets.sample(e, 'incoming') end)
ashita.events.register('packet_out', 'workbench_live_packet_out', function(e) packets.sample(e, 'outgoing') end)
ashita.events.register('command', 'workbench_live_command', function(e)
    -- Only simple explicit IDs are accepted; no shell commands or paths are parsed.
    local args = {}
    for token in e.command:gmatch('%S+') do table.insert(args, token) end
    if args[1] ~= '/wblive' then return end
    e.blocked = true
    if args[2] == 'live' then
        if args[3] == 'start' then
            if exporter.context() then print('Workbench Live: stop JSONL export first'); return end
            local ok, err = direct.start(args[4])
            print(ok and 'Workbench Live: direct live telemetry started (no recording)' or ('Workbench Live: '..tostring(err)))
        elseif args[3] == 'stop' then direct.stop('Direct live telemetry stopped')
        elseif args[3] == 'status' then print('Workbench Live: direct telemetry '..(direct.active() and 'active' or 'inactive'))
        else print('Workbench Live: use live start <id>, live stop, live status') end
        return
    end
    if args[2] == 'packets' then packets.command(args[3], args[4]); return end
    if args[2] == 'bridge' then
        if args[3] == 'stop' then bridge.stop()
        elseif args[3] == 'start' then
            local context = exporter.context()
            if context then bridge.start(context.client_id) else print('Workbench Live: start telemetry before bridge') end
        elseif args[3] == 'status' then print('Workbench Live: Bridge '..(bridge.active() and 'active' or 'inactive'))
        else print('Workbench Live: use bridge start, bridge stop or bridge status') end
        return
    end
    if args[2] == 'stop' then packets.stop(); direct.stop(); bridge.stop() end
    exporter.command(args[2], args[3], args[4])
end)
ashita.events.register('d3d_present', 'workbench_live_sample', function()
    exporter.sample()
    direct.sample()
    if packets.active() and not exporter.context() then
        packets.stop('Packet export stopped: telemetry inactive or paused; restart explicitly after fresh telemetry.')
    end
end)
ashita.events.register('unload', 'workbench_live_unload', function() packets.stop(); direct.stop(); bridge.stop(); exporter.stop() end)
