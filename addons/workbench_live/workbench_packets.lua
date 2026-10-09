-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Passive hook observations only; never modify an event, inject, or block packets.
local M = {}
local function integer(value, low, high)
    assert(type(value) == 'number' and value == math.floor(value) and value >= low and value <= high,
           'invalid packet observation integer')
    return value
end
local function quote(value, limit)
    assert(type(value) == 'string' and #value <= (limit or 200), 'invalid packet source text')
    return '"' .. value:gsub('[%z\1-\31\\"]', function(c) return string.format('\\u%04x', string.byte(c)) end) .. '"'
end
function M.new(options)
    local handle, source, sequence, bytes, second, count, dropped = nil, nil, 0, 0, nil, 0, 0
    local last_stop_reason, last_stop_counts
    -- Only the pinned example's emote IDs and Toolkit's existing event opcode.
    -- No chat/login/lobby/all-opcode profile or packet payload interpretation.
    local profile = {incoming={[0x034]=true,[0x05A]=true}, outgoing={[0x05D]=true}}
    local function stop(reason)
        if handle then
            last_stop_counts = {observations=sequence, rate_drops=dropped}
            pcall(function() handle:close() end)
        end
        handle, source = nil, nil
        if reason then
            last_stop_reason = reason
            options.message(reason)
        end
    end
    local function context()
        local value = assert(options.context(), 'start telemetry before packet observation')
        assert(type(value.client_id) == 'string' and type(value.source_recording) == 'string', 'missing packet source identity')
        if source then
            assert(value.client_id == source.client_id and value.source_recording == source.source_recording
                and value.source_identity == source.source_identity, 'packet source changed; restart explicitly')
        end
        integer(value.zone_id, 1, 65535)
        return value
    end
    local function fresh_context(now)
        local current = context()
        local telemetry_time = integer(current.last_observed_at, 0, 4102444800)
        assert(now >= telemetry_time, 'system clock moved backwards')
        assert(now - telemetry_time <= 5, 'telemetry context stale; restart packet observation after fresh telemetry')
        return current
    end
    local function sample(e, direction)
        if not handle or not profile[direction][e.id] then return end
        local ok, err = pcall(function()
            local now = integer(os.time(), 0, 4102444800)
            assert(not second or now >= second, 'system clock moved backwards')
            if second ~= now then second, count = now, 0 end
            local current = fresh_context(now)
            if count >= 10 then dropped = integer(dropped+1, 0, 4294967295); return end
            local size = integer(e.size, 4, 1024)
            assert(type(e.data) == 'string' and #e.data == size, 'original packet size mismatch')
            assert(type(e.injected) == 'boolean' and type(e.blocked) == 'boolean', 'packet hook flags unavailable')
            local raw = e.data:gsub('.', function(c) return string.format('%02X', string.byte(c)) end)
            local line = '{"schema_version":1,"kind":"ashita_packet_observation","profile":"event_emote",'
                .. '"client_id":' .. quote(current.client_id) .. ',"source_recording":' .. quote(current.source_recording)
                .. ',"adapter":"ashita-v4-api-experimental","client_version":"unverified-ashita-v4-api"'
                .. ',"sequence":' .. (sequence+1) .. ',"observed_at":' .. now .. ',"zone_id":' .. current.zone_id
                .. ',"direction":' .. quote(direction) .. ',"opcode":' .. integer(e.id, 0, 511)
                .. ',"size":' .. size .. ',"raw_hex":' .. quote(raw, 2048)
                .. ',"hook_stage":"addon_callback_original","is_injected":' .. tostring(e.injected)
                .. ',"is_blocked":' .. tostring(e.blocked) .. ',"dropped_before":' .. dropped .. '}\n'
            assert(context().zone_id == current.zone_id, 'packet zone changed while sampling')
            assert(#line <= 4096 and bytes + #line <= 4*1024*1024 and sequence < 10000, 'packet export limit reached')
            assert(handle:write(line), 'unable to write packets'); assert(handle:flush(), 'unable to flush packets')
            sequence, bytes, count = sequence+1, bytes+#line, count+1
        end)
        if not ok then stop('Packet export stopped: '..tostring(err)) end
    end
    local function command(action, mode)
        if action == 'stop' then stop('Packet export stopped.'); return end
        if action == 'status' then
            options.message(handle and ('Packets active; '..sequence..' observations, '..dropped..' rate-limit drops (unverified).')
                or ('Packets inactive.' .. (last_stop_counts and (' Previous export: '..last_stop_counts.observations
                    ..' observations, '..last_stop_counts.rate_drops..' rate-limit drops (unverified).') or '')
                    .. (last_stop_reason and (' Last stop: '..last_stop_reason) or '')))
            return
        end
        if action ~= 'start' or mode ~= 'event_emote' then options.message('Use packets start event_emote, packets stop or packets status.'); return end
        if handle then options.message('Stop packet observation before starting another.'); return end
        local ok, err = pcall(function()
            local current = fresh_context(integer(os.time(), 0, 4102444800))
            local path = options.directory .. '/packets-' .. current.source_recording .. '.jsonl'
            assert(not options.exists(path), 'packet file already exists; start a fresh telemetry recording')
            handle = assert(io.open(path, 'wb'))
            source, sequence, bytes, second, count, dropped = current, 0, 0, nil, 0, 0
            last_stop_reason, last_stop_counts = nil, nil
            options.message('Passive packet observations: '..path..'. Hook bytes are not verified wire traffic.')
        end)
        if not ok then stop('Unable to start packets: '..tostring(err)) end
    end
    return {command=command, sample=sample, stop=stop, active=function() return handle ~= nil end}
end
return M
