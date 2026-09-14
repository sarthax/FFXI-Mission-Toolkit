-----------------------------------------------------------
-- compat.lua — Framework Compatibility Layer for Packetlyzer
-- Detects Windower 4 or Ashita at load time and provides
-- a unified API for packet capture, commands, and sockets.
-----------------------------------------------------------
local compat = {}

compat.framework = nil  -- "windower" | "ashita" | nil

-- Internal callback storage
local _incoming_callbacks = {}
local _outgoing_callbacks = {}

-----------------------------------------------------------
-- Utility: safe callback invocation with error catching
-----------------------------------------------------------
local function invoke_callbacks(callbacks, ...)
    for i = 1, #callbacks do
        local ok, err = pcall(callbacks[i], ...)
        if not ok then
            compat.log('[Packetlyzer] Callback error: ' .. tostring(err))
        end
    end
end

-----------------------------------------------------------
-- Framework Detection and API Binding
-----------------------------------------------------------
if windower then
    -------------------------------------------------------
    -- Windower 4 detected
    -------------------------------------------------------
    compat.framework = "windower"

    function compat.on_incoming_packet(callback)
        _incoming_callbacks[#_incoming_callbacks + 1] = callback
    end

    function compat.on_outgoing_packet(callback)
        _outgoing_callbacks[#_outgoing_callbacks + 1] = callback
    end

    function compat.send_command(cmd)
        windower.send_command(cmd)
    end

    function compat.get_player_name()
        local player = windower.ffxi.get_player()
        if player then
            return player.name
        end
        return nil
    end

    function compat.log(msg)
        windower.add_to_chat(207, '[Packetlyzer] ' .. tostring(msg))
    end

    function compat.connect_socket(host, port)
        local socket_lib = require('socket')
        local tcp = socket_lib.tcp()
        if not tcp then
            return nil, "Failed to create TCP socket"
        end
        tcp:settimeout(5)
        local ok, err = tcp:connect(host, port)
        if not ok then
            tcp:close()
            return nil, "Connection failed: " .. tostring(err)
        end
        return tcp
    end

    -- Text rendering using Windower's texts library
    local texts = require('texts')

    function compat.create_text(initial_text)
        local settings = {
            pos = { x = 10, y = 10 },
            bg = { alpha = 180, red = 0, green = 0, blue = 0 },
            text = { font = 'Consolas', size = 10, alpha = 255, red = 255, green = 255, blue = 255 },
            padding = 4,
        }
        local t = texts.new(initial_text, settings)
        t:show()
        return t
    end

    function compat.update_text(text_obj, new_text)
        if text_obj then
            text_obj:text(new_text)
        end
    end

    function compat.show_text(text_obj)
        if text_obj then
            text_obj:show()
        end
    end

    function compat.hide_text(text_obj)
        if text_obj then
            text_obj:hide()
        end
    end

    function compat.destroy_text(text_obj)
        if text_obj then
            text_obj:hide()
            texts.destroy(text_obj)
        end
    end

    function compat.text_visible(text_obj)
        if text_obj then
            return text_obj:visible()
        end
        return false
    end

    -- Register Windower packet hooks that invoke stored callbacks
    windower.register_event('incoming chunk', function(id, data, modified, injected, blocked)
        invoke_callbacks(_incoming_callbacks, id, data, modified, injected, blocked)
    end)

    windower.register_event('outgoing chunk', function(id, data, modified, injected, blocked)
        invoke_callbacks(_outgoing_callbacks, id, data, modified, injected, blocked)
    end)

elseif ashita then
    -------------------------------------------------------
    -- Ashita detected
    -------------------------------------------------------
    compat.framework = "ashita"

    function compat.on_incoming_packet(callback)
        _incoming_callbacks[#_incoming_callbacks + 1] = callback
    end

    function compat.on_outgoing_packet(callback)
        _outgoing_callbacks[#_outgoing_callbacks + 1] = callback
    end

    function compat.send_command(cmd)
        -- v4: AshitaCore:GetChatManager():QueueCommand(-1, cmd)
        -- v3: AshitaCore:GetChatManager():QueueCommand(cmd, 1)
        local chat = AshitaCore:GetChatManager()
        if chat then
            -- Try v4 signature first, fall back to v3
            local ok = pcall(function() chat:QueueCommand(-1, cmd) end)
            if not ok then
                pcall(function() chat:QueueCommand(cmd, 1) end)
            end
        end
    end

    function compat.get_player_name()
        local ok, result = pcall(function()
            -- v4 API
            return AshitaCore:GetMemoryManager():GetParty():GetMemberName(0)
        end)
        if ok and result then return result end
        -- v3 API fallback
        ok, result = pcall(function()
            return AshitaCore:GetDataManager():GetParty():GetMemberName(0)
        end)
        if ok and result then return result end
        return nil
    end

    function compat.log(msg)
        print('[Packetlyzer] ' .. tostring(msg))
    end

    function compat.connect_socket(host, port)
        local socket_lib = require('socket')
        local tcp = socket_lib.tcp()
        if not tcp then
            return nil, "Failed to create TCP socket"
        end
        tcp:settimeout(5)
        local ok, err = tcp:connect(host, port)
        if not ok then
            tcp:close()
            return nil, "Connection failed: " .. tostring(err)
        end
        return tcp
    end

    -- Text rendering using Ashita font objects
    -- NOTE: Font API varies between Ashita v3 and v4. We wrap in pcall
    -- to gracefully handle API differences. The status text is cosmetic only.
    local _ashita_font_obj = nil
    local _ashita_font_visible = false

    function compat.create_text(initial_text)
        -- Try Ashita v3/v4 font creation with error handling
        local ok, result = pcall(function()
            local fm = AshitaCore:GetFontManager()
            if not fm then return nil end
            local font = fm:Create('packetlyzer_status')
            if not font then return nil end
            font:SetText(initial_text)
            font:SetPositionX(10)
            font:SetPositionY(10)
            font:SetFontFamily('Consolas')
            font:SetFontHeight(12)
            font:SetColor(0xFFFFFFFF)
            font:SetBold(false)
            -- Try SetVisibility (v3) then SetVisible (v4 alt)
            if font.SetVisibility then
                font:SetVisibility(true)
            elseif font.SetVisible then
                font:SetVisible(true)
            end
            return font
        end)

        if ok and result then
            _ashita_font_obj = result
            _ashita_font_visible = true
            return result
        else
            -- Font creation failed — log and continue without status text
            compat.log('Status text disabled (font API: ' .. tostring(result) .. ')')
            _ashita_font_obj = nil
            _ashita_font_visible = false
            return nil
        end
    end

    function compat.update_text(text_obj, new_text)
        if text_obj then
            pcall(function() text_obj:SetText(new_text) end)
        end
    end

    function compat.show_text(text_obj)
        if text_obj then
            pcall(function()
                if text_obj.SetVisibility then
                    text_obj:SetVisibility(true)
                elseif text_obj.SetVisible then
                    text_obj:SetVisible(true)
                end
            end)
            _ashita_font_visible = true
        end
    end

    function compat.hide_text(text_obj)
        if text_obj then
            pcall(function()
                if text_obj.SetVisibility then
                    text_obj:SetVisibility(false)
                elseif text_obj.SetVisible then
                    text_obj:SetVisible(false)
                end
            end)
            _ashita_font_visible = false
        end
    end

    function compat.destroy_text(text_obj)
        if text_obj then
            pcall(function()
                if text_obj.SetVisibility then
                    text_obj:SetVisibility(false)
                elseif text_obj.SetVisible then
                    text_obj:SetVisible(false)
                end
                AshitaCore:GetFontManager():Delete('packetlyzer_status')
            end)
            _ashita_font_obj = nil
            _ashita_font_visible = false
        end
    end

    function compat.text_visible(text_obj)
        return _ashita_font_visible
    end

    -- Register Ashita packet hooks that invoke stored callbacks
    -- Support both Ashita v4 (ashita.events.register) and v3 (ashita.register_event)
    if ashita.events and ashita.events.register then
        -- Ashita v4 API
        ashita.events.register('packet_in', 'packetlyzer_incoming', function(e)
            invoke_callbacks(_incoming_callbacks, e.id, e.data, e.modified, e.injected, e.blocked)
            return false
        end)

        ashita.events.register('packet_out', 'packetlyzer_outgoing', function(e)
            invoke_callbacks(_outgoing_callbacks, e.id, e.data, e.modified, e.injected, e.blocked)
            return false
        end)
    elseif ashita.register_event then
        -- Ashita v3 API
        ashita.register_event('incoming_packet', function(id, size, data)
            invoke_callbacks(_incoming_callbacks, id, data, false, false, false)
            return false
        end)

        ashita.register_event('outgoing_packet', function(id, size, data)
            invoke_callbacks(_outgoing_callbacks, id, data, false, false, false)
            return false
        end)
    else
        compat.log('ERROR: Could not register packet hooks (unknown Ashita version)')
    end

else
    -------------------------------------------------------
    -- No framework detected — limited functionality
    -------------------------------------------------------
    compat.framework = nil

    -- Log error about detection failure (using print as fallback)
    print('[Packetlyzer] ERROR: No supported framework detected (windower/ashita). Packet capture disabled.')

    -- Packet callbacks are stored but never invoked
    function compat.on_incoming_packet(callback)
        _incoming_callbacks[#_incoming_callbacks + 1] = callback
    end

    function compat.on_outgoing_packet(callback)
        _outgoing_callbacks[#_outgoing_callbacks + 1] = callback
    end

    -- send_command: no-op when no framework is available
    function compat.send_command(cmd)
        -- No framework available to send commands
    end

    -- get_player_name: returns nil when no framework is available
    function compat.get_player_name()
        return nil
    end

    -- log: falls back to print
    function compat.log(msg)
        print('[Packetlyzer] ' .. tostring(msg))
    end

    -- connect_socket: still functional via LuaSocket
    function compat.connect_socket(host, port)
        local ok_require, socket_lib = pcall(require, 'socket')
        if not ok_require then
            return nil, "Socket library not available: " .. tostring(socket_lib)
        end
        local tcp = socket_lib.tcp()
        if not tcp then
            return nil, "Failed to create TCP socket"
        end
        tcp:settimeout(5)
        local ok, err = tcp:connect(host, port)
        if not ok then
            tcp:close()
            return nil, "Connection failed: " .. tostring(err)
        end
        return tcp
    end

    -- Text rendering stubs (no-op when no framework available)
    function compat.create_text(initial_text)
        return nil
    end

    function compat.update_text(text_obj, new_text)
    end

    function compat.show_text(text_obj)
    end

    function compat.hide_text(text_obj)
    end

    function compat.destroy_text(text_obj)
    end

    function compat.text_visible(text_obj)
        return false
    end
end

return compat
