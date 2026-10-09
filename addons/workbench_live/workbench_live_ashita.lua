-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Experimental Ashita v4 API source. Explicit start; no offsets or game writes.
addon.name = 'workbench_live'
addon.author = 'FFXI Mission Toolkit contributors'
addon.version = '0.2.0-experimental'
addon.desc = 'Read-only observation export; client build unverified.'
require('common')
local observation = require('workbench_observation')
local exporter = require('workbench_export').new({
    directory = addon.path,
    exists = ashita.fs.exists,
    message = function(text) print('Workbench Live: ' .. text) end,
    supports_inventory = true,
    capture = function(id, now, inventory) return observation.capture_ashita(AshitaCore, GetEntity, id, now, inventory) end,
})
ashita.events.register('command', 'workbench_live_command', function(e)
    -- Only simple explicit IDs are accepted; no shell commands or paths are parsed.
    local args = {}
    for token in e.command:gmatch('%S+') do table.insert(args, token) end
    if args[1] ~= '/wblive' then return end
    e.blocked = true
    exporter.command(args[2], args[3], args[4])
end)
ashita.events.register('d3d_present', 'workbench_live_sample', exporter.sample)
ashita.events.register('unload', 'workbench_live_unload', function() exporter.stop() end)
