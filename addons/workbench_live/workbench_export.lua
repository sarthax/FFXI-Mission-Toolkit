-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Bounded, explicit JSONL export lifecycle. Writes local observation files only.
local observation = require('workbench_observation')
local M = {}
function M.new(options)
    local handle, client_id, identity, last_time, bytes
    local MAX_BYTES = 16 * 1024 * 1024
    local function stop(reason)
        if handle then pcall(function() handle:close() end) end
        handle, client_id, identity, last_time, bytes = nil, nil, nil, nil, 0
        if reason then options.message(reason) end
    end
    local function emit(frame, now)
        assert((frame.source_identity or frame.character) == identity, 'character identity changed; start a new export')
        local line = observation.encode(frame) .. '\n'
        assert(#line <= 65536 and bytes + #line <= MAX_BYTES, 'export size limit reached; start a new export')
        assert(handle:write(line), 'unable to write telemetry')
        assert(handle:flush(), 'unable to flush telemetry')
        bytes, last_time = bytes + #line, now
    end
    local function sample()
        if not handle then return end
        local now = os.time()
        if last_time and now == last_time then return end
        local ok, err = pcall(function()
            assert(not last_time or now > last_time, 'system clock moved backwards; start a new export')
            emit(options.capture(client_id, now), now)
        end)
        if not ok then stop('Export stopped: ' .. tostring(err)) end
    end
    local function command(action, id)
        if action == 'stop' then stop('Export stopped.'); return end
        if action == 'status' then options.message(handle and ('Exporting ' .. client_id .. ' (unverified build).') or 'Not exporting.'); return end
        if action ~= 'start' then options.message('Use start <unique-instance-id>, stop or status. Read-only, experimental.'); return end
        if handle then options.message('Stop the current export before starting another.'); return end
        if type(id) ~= 'string' or #id > 64 or not id:match('^[%w_-]+$') then
            options.message('Choose a unique instance ID containing 1–64 letters, digits, underscores or hyphens.'); return
        end
        local ok, err = pcall(function()
            local now = os.time()
            local frame = options.capture(id, now)
            local stem = options.directory .. '/telemetry-' .. id .. '-' .. now
            local output
            for suffix = 1, 100 do
                local candidate = stem .. '-' .. suffix .. '.jsonl'
                if not options.exists(candidate) then output = candidate; break end
            end
            assert(output, 'no unused export filename available')
            -- Launcher instances must use distinct IDs; existing exports are preserved.
            handle = assert(io.open(output, 'wb'))
            client_id, identity, last_time, bytes = id, frame.source_identity or frame.character, nil, 0
            emit(frame, now)
            options.message('Read-only experimental export: ' .. output .. '. Client build is unverified.')
        end)
        if not ok then stop('Unable to start: ' .. tostring(err)) end
    end
    return {command = command, sample = sample, stop = stop}
end
return M
