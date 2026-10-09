-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Bounded, explicit JSONL export lifecycle. Writes local observation files only.
local observation = require('workbench_observation')
local M = {}
function M.new(options)
    local handle, client_id, identity, last_time, bytes, inventory, source_recording, last_frame
    local MAX_BYTES = 16 * 1024 * 1024
    local zoning, paused_since, stable_zone, stable_count, last_attempt
    local function stop(reason)
        if handle then pcall(function() handle:close() end) end
        handle, client_id, identity, last_time, bytes, inventory = nil, nil, nil, nil, 0, false
        zoning, paused_since, stable_zone, stable_count, last_attempt = false, nil, nil, 0, nil
        if reason then options.message(reason) end
    end
    local function emit(frame, now)
        assert((frame.source_identity or frame.character) == identity, 'character identity changed; start a new export')
        local line = observation.encode(frame) .. '\n'
        assert(#line <= 65536 and bytes + #line <= MAX_BYTES, 'export size limit reached; start a new export')
        assert(handle:write(line), 'unable to write telemetry')
        assert(handle:flush(), 'unable to flush telemetry')
        bytes, last_time, last_frame = bytes + #line, now, frame
    end
    local function sample()
        if not handle then return end
        local now = os.time()
        if last_attempt and now == last_attempt then return end
        if last_attempt and now < last_attempt then stop('Export stopped: system clock moved backwards; start a new export'); return end
        last_attempt = now
        if paused_since and now - paused_since >= 30 then
            stop('Export stopped: transition recovery timed out after 30 seconds; start a new export'); return
        end
        local ok, err = pcall(function()
            assert(not last_time or now > last_time, 'system clock moved backwards; start a new export')
            local frame = options.capture(client_id, now, inventory)
            assert((frame.source_identity or frame.character) == identity, 'character identity changed; start a new export')
            if paused_since then
                stable_count = frame.position.zone_id == stable_zone and stable_count + 1 or 1
                stable_zone = frame.position.zone_id
                if stable_count < 2 then return end
                emit(frame, now)
                paused_since, stable_zone, stable_count = nil, nil, 0
                options.message('Export resumed after two coherent player samples; skipped interval remains a recording gap.')
            else
                emit(frame, now)
            end
        end)
        if not ok then
            if zoning and observation.is_transition_error(err) then
                if not paused_since then
                    paused_since = now
                    options.message('Export paused: player identity mismatch; retrying original identity for up to 30 seconds. No frames recorded while paused.')
                end
                stable_zone, stable_count = nil, 0
            else
                stop('Export stopped: ' .. tostring(err))
            end
        end
    end
    local function command(action, id, mode)
        if action == 'stop' then stop('Export stopped.'); return end
        if action == 'status' then options.message(handle and (paused_since and ('Paused ' .. client_id .. '; no frames recorded, bounded transition recovery.') or ('Exporting ' .. client_id .. ' (build verification pending; informational).')) or 'Not exporting.'); return end
        if action ~= 'start' then options.message('Use start <unique-instance-id>, stop or status. Read-only, experimental.'); return end
        if handle then options.message('Stop the current export before starting another.'); return end
        if type(id) ~= 'string' or #id > 64 or not id:match('^[%w_-]+$') then
            options.message('Choose a unique instance ID containing 1–64 letters, digits, underscores or hyphens.'); return
        end
        if mode ~= nil and ((mode ~= 'inventory' and mode ~= 'inventory-zoning') or not options.supports_inventory) then
            options.message('Unsupported observation mode; use start <id> or start <id> inventory on Ashita.'); return
        end
        inventory = mode == 'inventory' or mode == 'inventory-zoning'
        zoning = mode == 'inventory-zoning'
        local ok, err = pcall(function()
            local now = os.time()
            local frame = options.capture(id, now, inventory)
            local stem = options.directory .. '/telemetry-' .. id .. '-' .. now
            local output
            for suffix = 1, 100 do
                local candidate = stem .. '-' .. suffix .. '.jsonl'
                if not options.exists(candidate) then output = candidate; break end
            end
            assert(output, 'no unused export filename available')
            -- Launcher instances must use distinct IDs; existing exports are preserved.
            source_recording = output:match('([^/\\]+)%.jsonl$')
            handle = assert(io.open(output, 'wb'))
            client_id, identity, last_time, bytes = id, frame.source_identity or frame.character, nil, 0
            paused_since, stable_zone, stable_count, last_attempt = nil, nil, 0, now
            emit(frame, now)
            options.message('Read-only experimental export: ' .. output .. '. Build verification pending (informational; export started).')
        end)
        if not ok then stop('Unable to start: ' .. tostring(err)) end
    end
    return {command = command, sample = sample, stop = stop, context = function()
        if not handle or paused_since then return nil end
        return {client_id=client_id, source_identity=identity, source_recording=source_recording,
                zone_id=last_frame.position.zone_id, last_observed_at=last_time}
    end}
end
return M
