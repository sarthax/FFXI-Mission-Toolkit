-- Opt-in single-use GM diagnostic text capture. Never records ordinary chat.
local M = {}
local function quote(s)
    return '"' .. tostring(s):gsub('\\','\\\\'):gsub('"','\\"')
        :gsub('\n','\\n'):gsub('\r','\\r'):gsub('[%z\1-\31]', ' ') .. '"'
end
function M.new(opts)
    local armed_until = 0
    local active = false
    local function arm()
        if not opts.bridge_active() then return false, 'start Live Bridge first' end
        active = true
        armed_until = opts.now() + 20
        return true, 'capture armed for 20 seconds; run !getmobaction in game'
    end
    local function stop()
        active, armed_until = false, 0
    end
    local function on_text(e)
        if not active then return end
        if opts.now() > armed_until or not opts.bridge_active() then stop(); return end
        local message = e and (e.message or e.text)
        if type(message) ~= 'string' or #message > 512 then return end
        -- Only command-specific responses; never ship tells, party, shout, or arbitrary chat.
        if not message:match('current action ID is %d+') then return end
        local id = message:match('(%d+) current action ID is %d+')
        if not id then return end
        local json = '{"type":"gm_mob_action","observed_at":'..math.floor(opts.now())
          ..',"server_entity_id":'..id..',"message":'..quote(message)..'}'
        local ok = opts.send(json)
        stop()
        if ok then opts.notify('GM action response captured via bridge')
        else opts.notify('GM response not sent; bridge unavailable') end
    end
    return {arm=arm, stop=stop, on_text=on_text, active=function()
        return active and opts.now() <= armed_until end}
end
return M
