-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Experimental Windower API source. Explicit start; no offsets or game writes.
_addon.name = 'workbench_live'
_addon.author = 'FFXI Mission Toolkit contributors'
_addon.version = '0.1.0-experimental'
_addon.commands = {'wblive'}
local observation = require('workbench_observation')
local exporter = require('workbench_export').new({
    directory = windower.addon_path,
    exists = windower.file_exists,
    message = function(text) windower.add_to_chat(207, 'Workbench Live: ' .. text) end,
    capture = function(id, now) return observation.capture(windower.ffxi, id, now) end,
})
windower.register_event('addon command', exporter.command)
windower.register_event('prerender', exporter.sample)
windower.register_event('logout', function() exporter.stop('Logged out; export stopped.') end)
windower.register_event('unload', function() exporter.stop() end)
