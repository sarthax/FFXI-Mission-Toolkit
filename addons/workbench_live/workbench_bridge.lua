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
    local function send_event(client_id, json, lane, kind)
        if not source then return false end
        local ok, err=pcall(function()
            assert(client_id == source, 'bridge source changed')
            assert(type(json)=='string' and #json<=65536, 'invalid bridge event size')
            local line=json:gsub('%s+$','')
            assert(#line>0 and #line<=65536, 'invalid bridge event')
            sequence=sequence+1
            local body='{"schema_version":1,"lane":"'..lane..'","kind":"'..kind..'","client_id":'
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
    local function observe(client_id, json)
        return send_event(client_id, json, 'telemetry', 'observation')
    end
    local function capture(client_id, json)
        return send_event(client_id, json, 'capture', 'capture_event')
    end
    local function ping()
        if not source then return fail('bridge not started') end
        local ok, err = pcall(function()
            sequence = sequence + 1
            local hello='{"client_id":'..json_string(source)..',"session_id":'..json_string(options.session_id)
                ..',"generation":'..json_string(options.generation)..',"token":"'..options.token..'"}'
            local frame='{"schema_version":1,"lane":"control","kind":"heartbeat","client_id":'
                ..json_string(source)..',"session_id":'..json_string(options.session_id)
                ..',"generation":'..json_string(options.generation)..',"sequence":'..sequence
                ..',"request_id":null,"payload_base64":""}'
            local peer=assert(options.connect(options.host,options.port))
            local completed, error_text=pcall(function()
                assert(peer:settimeout(0.5), 'cannot set probe timeout')
                assert(peer:send(length_prefix(#hello,2)..hello), 'handshake failed')
                assert(peer:send(length_prefix(#frame,4)..frame), 'heartbeat failed')
                assert(peer:shutdown('send'), 'probe shutdown failed')
                local header=assert(peer:receive(4))
                local count=0
                for i=1,4 do count=count*256+header:byte(i) end
                assert(count>0 and count<=2048, 'invalid heartbeat response size')
                local response=assert(peer:receive(count))
                assert(response:find('"client_id":'..json_string(source),1,true), 'receiver identity mismatch')
                assert(response:find('"session_id":'..json_string(options.session_id),1,true), 'receiver session mismatch')
                assert(response:find('"generation":'..json_string(options.generation),1,true), 'receiver generation mismatch')
                local is_probe = response:find('"kind":"command"',1,true) ~= nil
                assert(is_probe or response:find('"kind":"heartbeat"',1,true), 'invalid control response')
                if is_probe then
                    assert(response:find('"payload_base64":"Y2FwYWJpbGl0aWVzX3Byb2Jl"',1,true),
                           'unsupported control command')
                else
                    assert(response:find('"payload_base64":"cmVhZF9vbmx5"',1,true),
                           'receiver not in read-only mode')
                end
                if is_probe then
                    local request_id=response:match('"request_id":"([%w_.:-]+)"')
                    assert(request_id and #request_id <= 128, 'invalid control request id')
                    sequence = sequence + 1
                    local reject='{"schema_version":1,"lane":"control","kind":"reject","client_id":'
                        ..json_string(source)..',"session_id":'..json_string(options.session_id)
                        ..',"generation":'..json_string(options.generation)..',"sequence":'..sequence
                        ..',"request_id":'..json_string(request_id)
                        ..',"payload_base64":"dW5zdXBwb3J0ZWRfZ2FtZV93cml0ZXM="}'
                    local reply_peer=assert(options.connect(options.host,options.port))
                    local sent, send_error=pcall(function()
                        assert(reply_peer:settimeout(0.5), 'cannot set response timeout')
                        assert(reply_peer:send(length_prefix(#hello,2)..hello), 'response handshake failed')
                        assert(reply_peer:send(length_prefix(#reject,4)..reject), 'response frame failed')
                    end)
                    pcall(function() reply_peer:close() end)
                    assert(sent,send_error)
                end
                assert(response:find('"client_id":'..json_string(source),1,true), 'receiver identity mismatch')
                assert(response:find('"generation":'..json_string(options.generation),1,true), 'receiver generation mismatch')
            end)
            pcall(function() peer:close() end)
            assert(completed,error_text)
        end)
        if not ok then return fail('read-only heartbeat failed') end
        return true, 'authenticated read-only round-trip confirmed; no movement capability'
    end
    return {start=start, observe=observe, capture=capture, client_id=function() return source end, ping=ping, stop=close, active=function() return source~=nil end, last_error=function() return last_error end}
end
return M
