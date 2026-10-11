-- Direct read-only observation sampler for Ashita bridge sessions.
-- Does not create JSONL recordings; frames are discarded if bridge is offline.
local observation = require('workbench_observation')
local M = {}
function M.new(options)
    local client_id, identity, last_attempt, paused, stable_zone, stable_count, reconnect_since
    local hz = options.sample_hz or 1
    assert(hz == 1 or hz == 5 or hz == 10 or hz == 20, 'invalid live sampling rate')
    local clock = options.now or os.time
    local function timestamp()
        local t = clock()
        assert(type(t) == 'number' and t == t and t > 0 and t < math.huge, 'invalid live sample clock')
        return t
    end
    local function stop(reason)
        client_id, identity, last_attempt, paused, stable_zone, stable_count, reconnect_since = nil, nil, nil, nil, nil, 0, nil
        if options.stop_bridge then options.stop_bridge() end
        if reason and options.message then options.message(reason) end
    end
    local function start(id)
        if client_id then return false, 'live session already active' end
        if type(id) ~= 'string' or #id > 64 or not id:match('^[%w_-]+$') then
            return false, 'invalid live instance ID'
        end
        local ok, frame = pcall(options.capture, id, timestamp())
        if not ok then return false, tostring(frame) end
        local source = frame.source_identity or frame.character
        if type(source) ~= 'string' or #source == 0 then return false, 'invalid player identity' end
        local started, reason = options.start_bridge(id)
        if not started then return false, 'bridge not started: '..tostring(reason or 'unknown reason') end
        client_id, identity, last_attempt, paused, stable_zone, stable_count, reconnect_since = id, source, nil, nil, nil, 0, nil
        return true
    end
    local function sample()
        if not client_id then return end
        local now = timestamp()
        if last_attempt and now - last_attempt < (1 / hz) - 0.000001 then
            if now < last_attempt then stop('Live telemetry stopped: system clock moved backwards') end
            return
        end
        last_attempt = now
        if paused and now - paused > 30 then
            stop('Live telemetry stopped: zoning recovery timed out')
            return
        end
        local ok, result = pcall(options.capture, client_id, now)
        if not ok then
            if observation.is_transition_error(result) then
                paused, stable_zone, stable_count = paused or now, nil, 0
                return
            end
            stop('Live telemetry stopped: '..tostring(result))
            return
        end
        if (result.source_identity or result.character) ~= identity then
            stop('Live telemetry stopped: character identity changed')
            return
        end
        if paused then
            stable_count = result.position.zone_id == stable_zone and stable_count + 1 or 1
            stable_zone = result.position.zone_id
            if stable_count < 2 then return end
            paused, stable_zone, stable_count = nil, nil, 0
        end
        local encoded = observation.encode(result)
        if not options.send(client_id, encoded) then
            reconnect_since = reconnect_since or now
            if now - reconnect_since > 15 then
                stop('Live telemetry stopped: bridge reconnect timed out; reconfigure if credentials expired')
                return
            end
            -- Reuse only the same explicit local session/credentials. Never change identity.
            if options.start_bridge(client_id) then
                if options.send(client_id, encoded) then reconnect_since = nil end
            end
        else
            reconnect_since = nil
        end
    end
    return {start=start, sample=sample, stop=stop, active=function() return client_id ~= nil end}
end
return M
