-----------------------------------------------------------
-- packetlyzer.lua — Main Addon for Packetlyzer
-- Captures all inbound/outbound packets and game events,
-- buffers during disconnection, and streams over TCP.
-----------------------------------------------------------
addon.name      = 'packetlyzer';
addon.author    = 'Packetlyzer';
addon.version   = '1.0.0';
addon.desc      = 'Captures and streams packets to the Packetlyzer analyzer.';

local compat = require('compat')
local serialize = require('serialize')

-----------------------------------------------------------
-- Configuration
-----------------------------------------------------------
local DEFAULT_HOST = '127.0.0.1'
local DEFAULT_PORT = 52985

local FIFO_BUFFER_MAX = 200     -- Max records when disconnected
local SEND_QUEUE_MAX = 5000     -- Max messages in send queue

-----------------------------------------------------------
-- State
-----------------------------------------------------------
local state = {
    host = DEFAULT_HOST,
    port = DEFAULT_PORT,
    socket = nil,
    connected = false,

    -- FIFO buffer for disconnected state (oldest at index 1)
    fifo_buffer = {},

    -- Send queue for messages that failed to send (oldest at index 1)
    send_queue = {},

    -- Reconnection backoff
    reconnect_interval = 5,     -- Current retry interval in seconds
    last_reconnect_attempt = 0, -- os.time() of last attempt

    -- Status text box
    status_text = nil,          -- Text object (framework-specific)
    status_visible = true,      -- Whether text box should be visible
}

-----------------------------------------------------------
-- Timestamp helper
-- Returns milliseconds since Unix epoch
-----------------------------------------------------------
local _socket_lib = nil
local _socket_lib_checked = false
local _time_offset = nil  -- offset to convert socket.gettime() to epoch if needed

local function get_timestamp()
    -- Prefer socket.gettime() for sub-second precision if available
    if not _socket_lib_checked then
        _socket_lib_checked = true
        local ok, lib = pcall(require, 'socket')
        if ok and lib and lib.gettime then
            _socket_lib = lib
            -- Detect if socket.gettime() returns epoch or uptime.
            -- If the value is much less than os.time(), it's likely uptime.
            local st = lib.gettime()
            local ot = os.time()
            if st < 1000000000 then
                -- Clearly not epoch (epoch seconds are > 1.7 billion in 2024+)
                -- Store offset: epoch_seconds - uptime_seconds
                _time_offset = ot - st
            else
                _time_offset = 0
            end
        end
    end
    if _socket_lib then
        return math.floor((_socket_lib.gettime() + _time_offset) * 1000)
    end
    return os.time() * 1000
end

-----------------------------------------------------------
-- Status Text Box
-- Displays "Packetlyzer: Connected" or "Packetlyzer: Disconnected"
-----------------------------------------------------------
local function update_status_text()
    if not state.status_text then
        return
    end
    local text
    if state.connected then
        text = 'Packetlyzer: Connected'
    else
        text = 'Packetlyzer: Disconnected'
    end
    compat.update_text(state.status_text, text)
end

-----------------------------------------------------------
-- FIFO Buffer Management
-- Used when socket is disconnected. Max 200 records.
-- Discards oldest when full.
-----------------------------------------------------------
local function buffer_record(record)
    local buf = state.fifo_buffer
    if #buf >= FIFO_BUFFER_MAX then
        table.remove(buf, 1)
    end
    buf[#buf + 1] = record
end

-----------------------------------------------------------
-- Send Queue Management
-- Used when socket send fails. Max 5000 messages.
-- Discards oldest when full.
-----------------------------------------------------------
local function queue_message(message)
    local q = state.send_queue
    if #q >= SEND_QUEUE_MAX then
        table.remove(q, 1)
    end
    q[#q + 1] = message
end

-----------------------------------------------------------
-- Socket Send
-- Attempts to send a message over the TCP socket.
-- Returns true on success, false on failure.
-----------------------------------------------------------
local function socket_send(message)
    if not state.socket then
        return false
    end

    local ok, err = state.socket:send(message)
    if not ok then
        compat.log('Socket send error: ' .. tostring(err))
        state.connected = false
        state.socket = nil
        update_status_text()
        return false
    end

    return true
end

-----------------------------------------------------------
-- Flush FIFO buffer (oldest first) then send queue
-- Called on successful reconnection.
-----------------------------------------------------------
local function flush_buffers()
    -- Flush FIFO buffer first (oldest → newest)
    local fifo = state.fifo_buffer
    state.fifo_buffer = {}
    for i = 1, #fifo do
        if not socket_send(fifo[i]) then
            -- Send failed during flush; re-buffer remaining
            for j = i, #fifo do
                queue_message(fifo[j])
            end
            return
        end
    end

    -- Flush send queue (oldest → newest)
    local queue = state.send_queue
    state.send_queue = {}
    for i = 1, #queue do
        if not socket_send(queue[i]) then
            -- Send failed during flush; re-buffer remaining
            for j = i, #queue do
                queue_message(queue[j])
            end
            return
        end
    end
end

-----------------------------------------------------------
-- Forward a serialized record (string) to the socket.
-- If disconnected, buffer it in the FIFO buffer.
-- If send fails, queue it in the send queue.
-----------------------------------------------------------
local function forward_record(serialized_message)
    if not state.connected then
        buffer_record(serialized_message)
        return
    end

    if not socket_send(serialized_message) then
        queue_message(serialized_message)
    end
end

-----------------------------------------------------------
-- Connection Management
-----------------------------------------------------------
local function attempt_connect()
    local sock, err = compat.connect_socket(state.host, state.port)
    if sock then
        state.socket = sock
        state.connected = true
        state.reconnect_interval = 5  -- Reset backoff on success
        compat.log('Connected to ' .. state.host .. ':' .. state.port)
        update_status_text()
        -- Flush buffered records
        flush_buffers()
        return true
    else
        compat.log('Connection failed: ' .. tostring(err))
        state.connected = false
        state.socket = nil
        update_status_text()
        return false
    end
end

local function check_reconnect()
    if state.connected then
        return
    end

    local now = os.time()
    if now - state.last_reconnect_attempt >= state.reconnect_interval then
        state.last_reconnect_attempt = now
        if not attempt_connect() then
            -- Exponential backoff: double interval, cap at 60s
            state.reconnect_interval = math.min(state.reconnect_interval * 2, 60)
        end
    end
end

-----------------------------------------------------------
-- Packet Callbacks
-- Registered via compat layer. Build Packet_Records and forward.
-- These are READ-ONLY: never modify, block, or alter packets.
-----------------------------------------------------------
compat.on_incoming_packet(function(id, data, modified, injected, blocked)
    local timestamp = get_timestamp()
    local message = serialize.packet_record('s2c', id, data, timestamp)
    forward_record(message)
end)

compat.on_outgoing_packet(function(id, data, modified, injected, blocked)
    local timestamp = get_timestamp()
    local message = serialize.packet_record('c2s', id, data, timestamp)
    forward_record(message)
end)

-----------------------------------------------------------
-- Game Event Hooks
-- Framework-specific event registration for game events.
-- Build Event_Records and forward them.
-----------------------------------------------------------
if compat.framework == "windower" then

    windower.register_event('action', function(act)
        local timestamp = get_timestamp()
        local message = serialize.event_record('action', timestamp, act)
        forward_record(message)
    end)

    windower.register_event('zone change', function(new_id, old_id)
        local timestamp = get_timestamp()
        local params = { new_zone_id = new_id, old_zone_id = old_id }
        local message = serialize.event_record('zone change', timestamp, params)
        forward_record(message)
    end)

    windower.register_event('login', function(name)
        local timestamp = get_timestamp()
        local params = { name = name }
        local message = serialize.event_record('login', timestamp, params)
        forward_record(message)
    end)

    windower.register_event('logout', function(name)
        local timestamp = get_timestamp()
        local params = { name = name }
        local message = serialize.event_record('logout', timestamp, params)
        forward_record(message)
    end)

    windower.register_event('incoming text', function(original, modified, original_mode, modified_mode, blocked)
        local timestamp = get_timestamp()
        local params = {
            original = original,
            modified = modified,
            original_mode = original_mode,
            modified_mode = modified_mode,
            blocked = blocked,
        }
        local message = serialize.event_record('incoming text', timestamp, params)
        forward_record(message)
    end)

    windower.register_event('outgoing text', function(original, modified, blocked)
        local timestamp = get_timestamp()
        local params = {
            original = original,
            modified = modified,
            blocked = blocked,
        }
        local message = serialize.event_record('outgoing text', timestamp, params)
        forward_record(message)
    end)

    windower.register_event('chat message', function(message_text, sender, mode, gm)
        local timestamp = get_timestamp()
        local params = {
            message = message_text,
            sender = sender,
            mode = mode,
            gm = gm,
        }
        local message = serialize.event_record('chat message', timestamp, params)
        forward_record(message)
    end)

    -- Prerender hook for reconnection checks
    windower.register_event('prerender', function()
        check_reconnect()
    end)

elseif compat.framework == "ashita" then

    -- Ashita uses packet-based event detection. Game events like action,
    -- zone change, login, logout are detected via specific packet opcodes.
    -- The compat layer already forwards raw packets. Here we additionally
    -- capture events by detecting known opcodes and emitting Event_Records.

    -- Action event (opcode 0x0028 incoming)
    ashita.events.register('packet_in', 'packetlyzer_action_event', function(e)
        if e.id == 0x0028 then
            local timestamp = get_timestamp()
            local params = { raw_opcode = 0x0028, size = #e.data }
            local message = serialize.event_record('action', timestamp, params)
            forward_record(message)
        end
        return false
    end)

    -- Zone change event (opcode 0x000B incoming = zone in, 0x000A = zone start)
    ashita.events.register('packet_in', 'packetlyzer_zone_event', function(e)
        if e.id == 0x000B then
            local timestamp = get_timestamp()
            local params = { zone_packet_id = e.id }
            local message = serialize.event_record('zone change', timestamp, params)
            forward_record(message)
        end
        return false
    end)

    -- Login event (opcode 0x000A incoming triggers zone/login sequence)
    ashita.events.register('packet_in', 'packetlyzer_login_event', function(e)
        if e.id == 0x000A then
            local timestamp = get_timestamp()
            local name = compat.get_player_name()
            local params = { name = name or '' }
            local message = serialize.event_record('login', timestamp, params)
            forward_record(message)
        end
        return false
    end)

    -- Logout detection (opcode 0x000E outgoing or server disconnect)
    ashita.events.register('packet_out', 'packetlyzer_logout_event', function(e)
        if e.id == 0x000E then
            local timestamp = get_timestamp()
            local name = compat.get_player_name()
            local params = { name = name or '' }
            local message = serialize.event_record('logout', timestamp, params)
            forward_record(message)
        end
        return false
    end)

    -- Incoming text (opcode 0x0017 incoming = chat/server message)
    ashita.events.register('packet_in', 'packetlyzer_incoming_text_event', function(e)
        if e.id == 0x0017 then
            local timestamp = get_timestamp()
            local params = { packet_id = e.id }
            local message = serialize.event_record('incoming text', timestamp, params)
            forward_record(message)
        end
        return false
    end)

    -- Outgoing text (opcode 0x00B5 or 0x00B6 outgoing = chat)
    ashita.events.register('packet_out', 'packetlyzer_outgoing_text_event', function(e)
        if e.id == 0x00B5 or e.id == 0x00B6 then
            local timestamp = get_timestamp()
            local params = { packet_id = e.id }
            local message = serialize.event_record('outgoing text', timestamp, params)
            forward_record(message)
        end
        return false
    end)

    -- Chat message (opcode 0x0017 with specific modes = player chat)
    -- Note: This overlaps with incoming text; both are emitted per spec requirement 3.5
    ashita.events.register('packet_in', 'packetlyzer_chat_msg_event', function(e)
        if e.id == 0x0017 then
            local timestamp = get_timestamp()
            local params = { packet_id = e.id, type = 'chat_message' }
            local message = serialize.event_record('chat message', timestamp, params)
            forward_record(message)
        end
        return false
    end)

    -- Prerender/frame hook for reconnection checks
    ashita.events.register('d3d_present', 'packetlyzer_reconnect', function()
        check_reconnect()
        return false
    end)

end

-----------------------------------------------------------
-- Port Command Handler
-- Handles: //packetlyzer port <number>
-----------------------------------------------------------
local function handle_port_command(args)
    if not args or args == '' then
        compat.log('Current port: ' .. state.port)
        return
    end

    local num = tonumber(args)
    if not num or num ~= math.floor(num) or num < 1 or num > 65535 then
        compat.log('Invalid port. Must be an integer between 1 and 65535.')
        return
    end

    state.port = num
    compat.log('Port set to ' .. num)

    -- Close existing connection and reconnect to new port
    if state.socket then
        state.socket:close()
        state.socket = nil
    end
    state.connected = false
    state.reconnect_interval = 5
    state.last_reconnect_attempt = 0
    attempt_connect()
end

-----------------------------------------------------------
-- Show/Hide Command Handlers
-----------------------------------------------------------
local function handle_show_command()
    if state.status_visible then
        return -- No-op if already visible
    end
    state.status_visible = true
    compat.show_text(state.status_text)
end

local function handle_hide_command()
    if not state.status_visible then
        return -- No-op if already hidden
    end
    state.status_visible = false
    compat.hide_text(state.status_text)
end

-----------------------------------------------------------
-- Command Registration
-----------------------------------------------------------
if compat.framework == "windower" then
    windower.register_event('addon command', function(command, ...)
        local args_table = {...}
        local args = table.concat(args_table, ' ')

        if command == 'port' then
            handle_port_command(args)
        elseif command == 'show' then
            handle_show_command()
        elseif command == 'hide' then
            handle_hide_command()
        elseif command == 'help' then
            compat.log('Commands: //packetlyzer port <number> | show | hide')
        else
            compat.log('Unknown command. Use //packetlyzer help')
        end
    end)

elseif compat.framework == "ashita" then
    ashita.events.register('command', 'packetlyzer_command', function(e)
        -- Parse command: /packetlyzer port <number>
        local cmd = e.command
        if not cmd then return false end

        local prefix, rest = cmd:match('^/packetlyzer%s+(%S+)%s*(.*)')
        if not prefix then return false end

        if prefix == 'port' then
            handle_port_command(rest)
            e.blocked = true
            return true
        elseif prefix == 'show' then
            handle_show_command()
            e.blocked = true
            return true
        elseif prefix == 'hide' then
            handle_hide_command()
            e.blocked = true
            return true
        elseif prefix == 'help' then
            compat.log('Commands: /packetlyzer port <number> | show | hide')
            e.blocked = true
            return true
        end

        return false
    end)
end

-----------------------------------------------------------
-- Initial Connection
-- Attempt to connect on addon load.
-----------------------------------------------------------
compat.log('Packetlyzer loading...')

-- Create status text box showing initial "Disconnected" state
state.status_text = compat.create_text('Packetlyzer: Disconnected')

attempt_connect()
if not state.connected then
    state.last_reconnect_attempt = os.time()
    compat.log('Will retry connection in ' .. state.reconnect_interval .. ' seconds.')
end
compat.log('Packetlyzer loaded. Framework: ' .. tostring(compat.framework))

-----------------------------------------------------------
-- Addon Unload
-- Destroy the status text box and release resources.
-----------------------------------------------------------
if compat.framework == "windower" then
    windower.register_event('unload', function()
        compat.destroy_text(state.status_text)
        state.status_text = nil
        if state.socket then
            state.socket:close()
            state.socket = nil
        end
    end)
elseif compat.framework == "ashita" then
    ashita.events.register('unload', 'packetlyzer_unload', function()
        compat.destroy_text(state.status_text)
        state.status_text = nil
        if state.socket then
            state.socket:close()
            state.socket = nil
        end
    end)
end
