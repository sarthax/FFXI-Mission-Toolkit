-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Pure observation mapping and JSONL encoding; no process handles or game writes.
local M = {}
local transition_tag = {}
function M.is_transition_error(value)
    return type(value) == 'table' and value.tag == transition_tag
end

local function number(value)
    assert(type(value) == 'number' and value == value and value ~= math.huge and value ~= -math.huge,
           'observation requires finite numbers')
    return value
end
local function integer(value, low, high)
    number(value)
    assert(value == math.floor(value) and value >= low and value <= high, 'invalid observation index or zone')
    return value
end
local function text(value, nonempty)
    assert(type(value) == 'string' and #value <= 200 and (not nonempty or value:find('%S')),
           'invalid observation text')
    return value
end
local function position(mob, zone)
    assert(type(mob) == 'table', 'player/entity observation unavailable')
    return {zone_id = zone, x = number(mob.x), y = number(mob.y), z = number(mob.z),
            heading = number(mob.facing)}
end

function M.capture(ffxi, client_id, observed_at)
    text(client_id, true)
    number(observed_at)
    assert(type(ffxi) == 'table' and type(ffxi.get_info) == 'function'
        and type(ffxi.get_player) == 'function' and type(ffxi.get_mob_by_target) == 'function',
        'required Windower observation interfaces unavailable')
    local info = ffxi.get_info()
    assert(type(info) == 'table' and info.logged_in == true, 'client is not logged in')
    local zone = integer(info.zone, 1, 65535)
    local player, me = ffxi.get_player(), ffxi.get_mob_by_target('me')
    assert(type(player) == 'table' and type(me) == 'table', 'player observation unavailable')
    local name = text(player.name, true)
    assert(integer(player.index, 0, 65535) == integer(me.index, 0, 65535) and me.name == name,
           'player identity changed or observation mismatch')
    local frame = {schema_version = 1, client_id = client_id,
        client_version = 'unverified-windower-api', character = name,
        adapter = 'windower-api-experimental', observed_at = observed_at,
        position = position(me, zone), entities = {}}
    local seen = {[player.index] = true}
    for _, target in ipairs({'t', 'st', 'pet'}) do
        local mob = ffxi.get_mob_by_target(target)
        if mob ~= nil then
            assert(type(mob) == 'table', 'invalid entity observation')
            local index = integer(mob.index, 0, 65535)
            if not seen[index] then
                seen[index] = true
                table.insert(frame.entities, {client_index = index, kind = 'unknown',
                    name = text(mob.name, false), position = position(mob, zone)})
            end
        end
    end
    -- Reject mixed observations spanning logout, zone change or character selection.
    local after, last_player = ffxi.get_info(), ffxi.get_player()
    assert(type(after) == 'table' and after.logged_in == true and after.zone == zone
        and type(last_player) == 'table' and last_player.name == name and last_player.index == player.index,
        'client changed while sampling; restart observation explicitly')
    return frame
end

function M.capture_ashita(core, get_entity, client_id, observed_at, inventory)
    text(client_id, true)
    number(observed_at)
    local memory = assert(core:GetMemoryManager(), 'Ashita memory manager unavailable')
    local party = assert(memory:GetParty(), 'Ashita party interface unavailable')
    local entity = assert(memory:GetEntity(), 'Ashita entity interface unavailable')
    assert(integer(party:GetMemberIsActive(0), 0, 4294967295) ~= 0, 'player party slot is inactive')
    local server_id = integer(party:GetMemberServerId(0), 1, 4294967295)
    local index = integer(party:GetMemberTargetIndex(0), 1, 65535)
    local name = text(party:GetMemberName(0), true)
    local zone = integer(party:GetMemberZone(0), 1, 65535)
    local function entity_position(slot)
        -- SDK entity ZoneId is only populated for the local player under
        -- certain conditions; it cannot validate player or target location.
        -- Local entity observations use the party slot's current zone, which
        -- is rechecked with the player identity after sampling.
        return {zone_id = zone, x = number(entity:GetLocalPositionX(slot)),
                y = number(entity:GetLocalPositionY(slot)), z = number(entity:GetLocalPositionZ(slot)),
                heading = number(entity:GetHeading(slot))}
    end
    if get_entity(index) == nil or entity:GetName(index) ~= name then
        error(setmetatable({tag=transition_tag}, {__tostring=function() return 'player identity mismatch' end}), 0)
    end
    local frame = {schema_version = 1, client_id = client_id,
        client_version = 'unverified-ashita-v4-api', character = name,
        adapter = 'ashita-v4-api-experimental', observed_at = observed_at,
        source_identity = tostring(server_id) .. ':' .. name,
        position = entity_position(index), entities = {}}
    local target = assert(memory:GetTarget(), 'Ashita target interface unavailable')
    local target_index = integer(target:GetTargetIndex(0), 0, 65535)
    local subtarget_active = nil
    if type(target.GetIsSubTargetActive) == 'function' then
        subtarget_active = integer(target:GetIsSubTargetActive(), 0, 255)
    end
    local original_index = nil
    if subtarget_active ~= nil and subtarget_active ~= 0 then
        original_index = integer(target:GetTargetIndex(1), 0, 65535)
    end
    local seen, checks = {[index] = true}, {}
    local function optional(getter, slot, high)
        if type(entity[getter]) == 'function' then
            return integer(entity[getter](entity, slot), 0, high)
        end
        return nil
    end
    local function observe(slot, role, is_target)
        if seen[slot] then
            if role and type(seen[slot]) == 'table' then
                table.insert(seen[slot].target_roles, role)
            end
            return
        end
        if get_entity(slot) == nil then return end
        local entity_name = text(entity:GetName(slot), false)
        if not is_target and not entity_name:find('%S') then return end
        if #frame.entities >= 32 then frame.entities_truncated = true; return end
        local id = optional('GetServerId', slot, 4294967295)
        local item = {client_index = slot, kind = 'unknown', name = entity_name,
            server_entity_id = id ~= 0 and id or nil,
            raw_entity_type = optional('GetType', slot, 255),
            raw_spawn_flags = optional('GetSpawnFlags', slot, 4294967295),
            raw_status = optional('GetStatus', slot, 4294967295),
            target_roles = role and {role} or {}, position = entity_position(slot)}
        local message = is_target and 'target changed while sampling; restart observation explicitly'
            or 'entity changed while sampling; restart observation explicitly'
        local function recheck()
            assert(get_entity(slot) ~= nil and entity:GetName(slot) == entity_name
                and (id == nil or entity:GetServerId(slot) == id), message)
        end
        recheck()
        table.insert(checks, recheck)
        seen[slot] = item
        table.insert(frame.entities, item)
    end
    frame.observation_scope = inventory and 'bounded_loaded_entities' or 'selected_targets'
    frame.entities_truncated = false
    if target_index ~= 0 then
        local role = subtarget_active ~= nil and (subtarget_active ~= 0 and 'subtarget' or 'target') or nil
        observe(target_index, role, true)
    end
    if original_index ~= nil and original_index ~= 0 then observe(original_index, 'target', true) end
    if inventory then
        -- Pinned Ashita petinfo/chamcham enumerate GetEntity(0..2303).
        -- 32 is a Toolkit output policy, not a game table-size claim.
        for slot = 0, 2303 do
            observe(slot, nil, false)
            if frame.entities_truncated then break end
        end
    end
    for _, recheck in ipairs(checks) do recheck() end
    assert(target:GetTargetIndex(0) == target_index
        and (subtarget_active == nil or target:GetIsSubTargetActive() == subtarget_active)
        and (original_index == nil or target:GetTargetIndex(1) == original_index),
        'target changed while sampling; restart observation explicitly')
    assert(party:GetMemberIsActive(0) ~= 0 and party:GetMemberServerId(0) == server_id
        and party:GetMemberTargetIndex(0) == index and party:GetMemberName(0) == name
        and party:GetMemberZone(0) == zone,
        'client changed while sampling; restart observation explicitly')
    return frame
end

local function quote(value)
    return '"' .. value:gsub('[%z\1-\31\\"]', function(c)
        if c == '"' then return '\\"' end
        if c == '\\' then return '\\\\' end
        return string.format('\\u%04x', string.byte(c))
    end) .. '"'
end
local function numeric(value)
    number(value)
    return string.format('%.17g', value)
end
local function encode_position(p)
    return '{"zone_id":' .. p.zone_id .. ',"x":' .. numeric(p.x) .. ',"y":' .. numeric(p.y)
        .. ',"z":' .. numeric(p.z) .. ',"heading":' .. numeric(p.heading) .. '}'
end
function M.encode(frame)
    local entities = {}
    for _, entity in ipairs(frame.entities) do
        local roles = {}
        for _, role in ipairs(entity.target_roles or {}) do
            assert(role == 'target' or role == 'subtarget', 'invalid target role')
            table.insert(roles, quote(role))
        end
        table.insert(entities, '{"client_index":' .. entity.client_index .. ',"kind":"unknown","name":'
            .. quote(entity.name)
            .. (entity.server_entity_id ~= nil and ',"server_entity_id":' .. integer(entity.server_entity_id, 1, 4294967295) or '')
            .. (entity.raw_entity_type ~= nil and ',"raw_entity_type":' .. integer(entity.raw_entity_type, 0, 255) or '')
            .. (entity.raw_spawn_flags ~= nil and ',"raw_spawn_flags":' .. integer(entity.raw_spawn_flags, 0, 4294967295) or '')
            .. (entity.raw_status ~= nil and ',"raw_status":' .. integer(entity.raw_status, 0, 4294967295) or '')
            .. (entity.target_roles and ',"target_roles":[' .. table.concat(roles, ',') .. ']' or '')
            .. ',"position":' .. encode_position(entity.position) .. '}')
    end
    return '{"schema_version":1,"client_id":' .. quote(frame.client_id)
        .. ',"client_version":' .. quote(frame.client_version) .. ',"character":' .. quote(frame.character)
        .. ',"adapter":' .. quote(frame.adapter) .. ',"observed_at":' .. numeric(frame.observed_at)
        .. (frame.observation_scope and ',"observation_scope":' .. quote(frame.observation_scope)
            .. ',"entities_truncated":' .. tostring(frame.entities_truncated) or '')
        .. ',"position":' .. encode_position(frame.position) .. ',"entities":[' .. table.concat(entities, ',') .. ']}'
end
return M
