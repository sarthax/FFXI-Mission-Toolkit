-----------------------------------------------------------
-- serialize.lua — JSON Serialization for Packetlyzer
-- Converts Lua values to JSON strings with safety limits.
-- Handles unserializable types and nesting depth constraints.
-----------------------------------------------------------
local serialize = {}

-- Default maximum nesting depth
local DEFAULT_MAX_DEPTH = 3

-----------------------------------------------------------
-- Hex encoding lookup table (byte → 2-char lowercase hex)
-----------------------------------------------------------
local hex_chars = {}
for i = 0, 255 do
    hex_chars[i] = string.format('%02x', i)
end

-----------------------------------------------------------
-- JSON string escaping
-- Escapes special characters for valid JSON output.
-- Ensures no literal newlines appear in the output.
-----------------------------------------------------------
local escape_map = {
    ['"']  = '\\"',
    ['\\'] = '\\\\',
    ['\b'] = '\\b',
    ['\f'] = '\\f',
    ['\n'] = '\\n',
    ['\r'] = '\\r',
    ['\t'] = '\\t',
}

local function escape_string(s)
    s = s:gsub('[%z\1-\31\\"]', function(c)
        if escape_map[c] then
            return escape_map[c]
        end
        -- Control characters as unicode escapes
        return string.format('\\u%04x', string.byte(c))
    end)
    return s
end

-----------------------------------------------------------
-- to_json(value, max_depth)
-- Generic Lua value → JSON string conversion.
--
-- Handles: string, number, boolean, nil, table (object/array)
-- Unserializable types (userdata, function, thread): "<unserializable>"
-- Tables beyond max_depth: "<max depth exceeded>"
-----------------------------------------------------------
function serialize.to_json(value, max_depth)
    max_depth = max_depth or DEFAULT_MAX_DEPTH

    local function encode(val, depth)
        local vtype = type(val)

        if val == nil then
            return 'null'
        elseif vtype == 'boolean' then
            return val and 'true' or 'false'
        elseif vtype == 'number' then
            -- Handle integers vs floats
            if val ~= val then
                -- NaN
                return 'null'
            elseif val == math.huge or val == -math.huge then
                return 'null'
            elseif val == math.floor(val) and math.abs(val) < 2^53 then
                return string.format('%d', val)
            else
                return string.format('%.14g', val)
            end
        elseif vtype == 'string' then
            return '"' .. escape_string(val) .. '"'
        elseif vtype == 'table' then
            if depth >= max_depth then
                return '"<max depth exceeded>"'
            end

            -- Determine if this is an array or object
            -- A table is treated as an array if it has consecutive integer keys 1..#t
            local n = #val
            local is_array = true

            if n == 0 then
                -- Check if the table has any keys at all
                local has_keys = false
                for _ in pairs(val) do
                    has_keys = true
                    break
                end
                if has_keys then
                    is_array = false
                end
                -- Empty table with no keys → empty array
            else
                -- Verify all keys are 1..n
                local count = 0
                for _ in pairs(val) do
                    count = count + 1
                end
                if count ~= n then
                    is_array = false
                end
            end

            if is_array then
                local parts = {}
                for i = 1, n do
                    parts[i] = encode(val[i], depth + 1)
                end
                return '[' .. table.concat(parts, ',') .. ']'
            else
                -- Object: iterate all keys
                local parts = {}
                local keys = {}
                for k in pairs(val) do
                    keys[#keys + 1] = k
                end
                -- Sort keys for deterministic output
                table.sort(keys, function(a, b)
                    return tostring(a) < tostring(b)
                end)
                for _, k in ipairs(keys) do
                    local key_str = '"' .. escape_string(tostring(k)) .. '"'
                    local val_str = encode(val[k], depth + 1)
                    parts[#parts + 1] = key_str .. ':' .. val_str
                end
                return '{' .. table.concat(parts, ',') .. '}'
            end
        else
            -- userdata, function, thread → unserializable
            return '"<unserializable>"'
        end
    end

    return encode(value, 0)
end

-----------------------------------------------------------
-- packet_record(direction, opcode, raw_data, timestamp)
-- Build and serialize a Packet_Record JSON message.
--
-- direction: "s2c" or "c2s"
-- opcode: integer opcode value
-- raw_data: raw packet bytes as a string
-- timestamp: integer milliseconds since Unix epoch
--
-- Output format:
-- {"type":"packet","direction":"s2c","opcode":"0028","size":44,"data":"28000b00...","timestamp":1720000000123}
-----------------------------------------------------------
function serialize.packet_record(direction, opcode, raw_data, timestamp)
    -- Format opcode as 4-char zero-padded lowercase hex
    local opcode_str = string.format('%04x', opcode)

    -- Hex-encode raw_data
    local hex_parts = {}
    for i = 1, #raw_data do
        hex_parts[i] = hex_chars[string.byte(raw_data, i)]
    end
    local data_hex = table.concat(hex_parts)

    -- Build JSON manually for performance (fixed structure)
    local json = '{"type":"packet"'
        .. ',"direction":"' .. direction .. '"'
        .. ',"opcode":"' .. opcode_str .. '"'
        .. ',"size":' .. #raw_data
        .. ',"data":"' .. data_hex .. '"'
        .. ',"timestamp":' .. string.format('%d', timestamp)
        .. '}'

    return json .. '\n'
end

-----------------------------------------------------------
-- event_record(event_name, timestamp, params)
-- Build and serialize an Event_Record JSON message.
--
-- event_name: string name of the event (e.g. "action")
-- timestamp: integer milliseconds since Unix epoch
-- params: table of event parameters (serialized with depth limit)
--
-- Output format:
-- {"type":"event","event_name":"action","timestamp":1720000000456,"params":{...}}
-----------------------------------------------------------
function serialize.event_record(event_name, timestamp, params)
    -- Serialize params with depth limit
    local params_json = serialize.to_json(params or {}, DEFAULT_MAX_DEPTH)

    -- Escape event_name for safety
    local safe_name = escape_string(event_name)

    -- Build JSON manually for performance (fixed structure)
    local json = '{"type":"event"'
        .. ',"event_name":"' .. safe_name .. '"'
        .. ',"timestamp":' .. string.format('%d', timestamp)
        .. ',"params":' .. params_json
        .. '}'

    return json .. '\n'
end

return serialize
