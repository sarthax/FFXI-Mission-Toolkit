-- Read-only API surface audit. Never dereference pointers or write memory/packets.
local M = {}
local function callable(parent, key)
    if parent == nil then return false end
    local ok, value = pcall(function() return parent[key] end)
    return ok and type(value) == 'function'
end
function M.inspect(core, entity_getter, packet_manager)
    local memory = nil
    if core and callable(core, 'GetMemoryManager') then
        local ok, result = pcall(function() return core:GetMemoryManager() end)
        if ok then memory = result end
    end
    local entity = nil
    if type(entity_getter) == 'function' then
        local ok, result = pcall(entity_getter)
        if ok then entity = result end
    end
    return {
        schema = 1, mode = 'read_only', movement_verified = false,
        memory_manager_present = memory ~= nil,
        memory_position_getters = {
            entity_x = callable(entity, 'GetLocalX'),
            entity_y = callable(entity, 'GetLocalY'),
            entity_z = callable(entity, 'GetLocalZ'),
        },
        memory_write_api_candidates = {
            warp_pointer = callable(memory, 'GetWarpPointer'),
            set_position = callable(entity, 'SetPosition'),
        },
        packet_api_candidates = {
            add_outgoing_packet = callable(packet_manager, 'AddOutgoingPacket'),
            inject_outgoing_packet = callable(packet_manager, 'InjectOutgoingPacket'),
        },
        note = 'Method presence does not establish a writable player pointer or server-accepted movement.'
    }
end
function M.summary(data)
    local function mark(v) return v and 'yes (unverified)' or 'not exposed' end
    return 'Ashita movement audit: read-only; warp pointer='..
        mark(data.memory_write_api_candidates.warp_pointer)..
        '; position setter='..mark(data.memory_write_api_candidates.set_position)..
        '; outgoing packet API='..mark(data.packet_api_candidates.add_outgoing_packet)..
        '; movement verified=no'
end
return M
