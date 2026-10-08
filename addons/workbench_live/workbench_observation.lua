-- Copyright (c) FFXI Mission Toolkit contributors. MIT license (repository LICENSE).
-- Pure observation mapping and JSONL encoding; no process handles or game writes.
local M = {}

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
    assert(get_entity(index) ~= nil and entity:GetName(index) == name, 'player identity mismatch')
    local frame = {schema_version = 1, client_id = client_id,
        client_version = 'unverified-ashita-v4-api', character = name,
        adapter = 'ashita-v4-api-experimental', observed_at = observed_at,
        source_identity = tostring(server_id) .. ':' .. name,
        position = entity_position(index), entities = {}}
    local target = assert(memory:GetTarget(), 'Ashita target interface unavailable')
    local target_index = integer(target:GetTargetIndex(0), 0, 65535)
    if target_index ~= 0 and target_index ~= index and get_entity(target_index) ~= nil then
        local target_name = text(entity:GetName(target_index), false)
        -- Published IEntity server identity is distinct from the memory slot.
        -- Older interfaces may omit the getter; zero remains unknown.
        local target_id = nil
        if type(entity.GetServerId) == 'function' then
            local id = integer(entity:GetServerId(target_index), 0, 4294967295)
            if id ~= 0 then target_id = id end
        end
        local target_position = entity_position(target_index)
        assert(target:GetTargetIndex(0) == target_index and get_entity(target_index) ~= nil
            and entity:GetName(target_index) == target_name
            and (target_id == nil or entity:GetServerId(target_index) == target_id),
            'target changed while sampling; restart observation explicitly')
        table.insert(frame.entities, {client_index = target_index, server_entity_id = target_id,
            kind = 'unknown', name = target_name, position = target_position})
    end
    frame.observation_scope = inventory and 'bounded_loaded_entities' or 'selected_targets'
    frame.entities_truncated = false
    if inventory then
        -- Pinned Ashita petinfo/chamcham enumerate GetEntity(0..2303).
        -- 32 is a Toolkit output policy, not a game table-size claim.
        local seen = {[index] = true}
        for _, item in ipairs(frame.entities) do seen[item.client_index] = true end
        for slot = 0, 2303 do
            if not seen[slot] and get_entity(slot) ~= nil then
                local entity_name = text(entity:GetName(slot), false)
                if entity_name:find('%S') then
                    if #frame.entities >= 32 then frame.entities_truncated = true; break end
                    local id = nil
                    if type(entity.GetServerId) == 'function' then
                        id = integer(entity:GetServerId(slot), 0, 4294967295)
                    end
                    local p = entity_position(slot)
                    assert(get_entity(slot) ~= nil and entity:GetName(slot) == entity_name
                        and (id == nil or entity:GetServerId(slot) == id),
                        'entity changed while sampling; restart observation explicitly')
                    table.insert(frame.entities, {client_index = slot, kind = 'unknown',
                        name = entity_name, position = p, server_entity_id = id ~= 0 and id or nil})
                end
            end
        end
        for _, item in ipairs(frame.entities) do
            assert(get_entity(item.client_index) ~= nil and entity:GetName(item.client_index) == item.name
                and (item.server_entity_id == nil or entity:GetServerId(item.client_index) == item.server_entity_id),
                'entity changed while sampling; restart observation explicitly')
        end
        assert(target:GetTargetIndex(0) == target_index,
               'target changed while sampling; restart observation explicitly')
    end
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
        table.insert(entities, '{"client_index":' .. entity.client_index .. ',"kind":"unknown","name":'
            .. quote(entity.name)
            .. (entity.server_entity_id ~= nil and ',"server_entity_id":' .. integer(entity.server_entity_id, 1, 4294967295) or '')
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
