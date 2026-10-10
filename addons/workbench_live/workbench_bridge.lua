-- Optional read-only Ashita v4 bridge peer; explicitly provisioned via local configuration.
-- No game commands, memory writes or packet mutation. Network errors never
-- terminate the existing JSONL exporter.
local M = {}
local alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local function b64(data)
    return ((data:gsub('.', function(x)
        local bits, v = '', x:byte()
        for i=8,1,-1 do bits = bits .. ((v % 2^i - v % 2^(i-1) > 0) and '1' or '0') end
        return bits
    end) .. '0000'):gsub('%d%d%d?%d?%d?%d?', function(bits)
        if #bits < 6 then return '' end
        local n = 0
        for i=1,6 do if bits:sub(i,i)=='1' then n=n+2^(6-i) end end
        return alphabet:sub(n+1,n+1)
    end) .. ({'', '==', '='})[#data%3+1])
end
local function json_string(v)
    assert(type(v)=='string' and #v <= 128 and v:match('^[%w_.:-]+$'), 'invalid bridge identifier')
    return '"' .. v .. '"'
end
local function length_prefix(n, bytes)
    local out = {}
    for i=bytes-1,0,-1 do out[#out+1]=string.char(math.floor(n / (256^i)) % 256) end
    return table.concat(out)
end
function M.new(options, notify, load_error)
    -- Even if an older entry point passes Lua require()'s true sentinel,
    -- never throw from the addon command callback.
    if type(options) ~= 'table' then options = {enabled=false} end
    local source, sequence, last_error = nil, 0, nil
    -- Reasons never include token/session values; asserts below use fixed text.
    local function fail(reason)
        last_error = reason
        return false, reason
    end
    local function close()
        source, sequence = nil, 0
    end
    local function start(client_id)
        close()
        last_error = nil
        if load_error then return fail('settings file failed to load: '..tostring(load_error)) end
        if options.enabled ~= true then return fail('settings missing or bridge disabled (enabled ~= true)') end
        local ok, err = pcall(function()
            assert(options.host == '127.0.0.1', 'bridge requires IPv4 loopback')
            local port=options.port
            assert(type(port)=='number' and port==math.floor(port) and port>0 and port<=65535, 'invalid bridge port')
            local session=json_string(options.session_id)
            local generation=json_string(options.generation)
            local token=options.token
            assert(type(token)=='string' and #token>=32 and #token<=256 and token:match('^[%w_-]+$'), 'invalid bridge token')
            local id=json_string(client_id)
            assert(type(options.connect)=='function', 'missing socket connector')
            -- Preflight: distinguishes unreachable receiver from bad settings. Sends nothing.
            local probe, perr = pcall(options.connect, options.host, port)
            assert(probe, 'receiver unreachable: '..(tostring(perr):gsub('^.-:%d+: ','')))
            pcall(function() perr:close() end)
            source = client_id
            -- Credentials persist across addon reloads, so the receiver must see
            -- strictly increasing sequences; a wall-clock base guarantees that.
            sequence = math.floor(os.time() * 1000)
        end)
        if not ok then close(); return fail((tostring(err):gsub('^.-:%d+: ',''))) end
        return true
    end
    local function observe(client_id, json)
        if not source then return false end
        local ok, err=pcall(function()
            assert(client_id == source, 'bridge source changed')
            assert(type(json)=='string' and #json<=65536, 'invalid bridge telemetry size')
            local line=json:gsub('%s+$','')
            assert(#line>0 and #line<=65536, 'invalid bridge telemetry')
            sequence=sequence+1
            local body='{"schema_version":1,"lane":"telemetry","kind":"observation","client_id":'
                ..json_string(source)..',"session_id":'..json_string(options.session_id)
                ..',"generation":'..json_string(options.generation)..',"sequence":'..sequence
                ..',"request_id":null,"payload_base64":"'..b64(line)..'"}'
            assert(#body<=96*1024, 'bridge frame exceeds limit')
            local frame_wire=length_prefix(#body,4)..body
            local peer=assert(options.connect(options.host,options.port))
            local transferred, transfer_err=pcall(function()
                assert(peer:settimeout(0.1), 'unable to set short network timeout')
                local hello='{"client_id":'..json_string(source)..',"session_id":'..json_string(options.session_id)
                    ..',"generation":'..json_string(options.generation)..',"token":"'..options.token..'"}'
                local hello_wire=length_prefix(#hello,2)..hello
                local hs, herr=peer:send(hello_wire)
                assert(hs==#hello_wire,herr or 'partial bridge handshake send')
                local fs, ferr=peer:send(frame_wire)
                assert(fs==#frame_wire,ferr or 'partial bridge telemetry send')
            end)
            pcall(function() peer:close() end)
            assert(transferred,transfer_err)
        end)
        if not ok then close(); last_error='telemetry send failed: '..tostring(err); if notify or options.message then (notify or options.message)('Bridge disconnected: '..tostring(err)) end; return false end
        return true
    end
    return {start=start, observe=observe, stop=close, active=function() return source~=nil end, last_error=function() return last_error end}
end
return M
