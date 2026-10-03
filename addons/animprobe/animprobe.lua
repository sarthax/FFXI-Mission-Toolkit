addon.name    = 'animprobe';
addon.author  = 'valhalla-backport';
addon.version = '0.1';
addon.desc    = 'Injects a fake incoming 0x028 NPC-TP-finish packet for a chosen anim id on a chosen entity, and logs timestamped markers for procmon_dat_trace.py.';

require 'common';
local chat = require 'chat';
local ffi  = require 'ffi';

ffi.cdef[[
typedef struct { uint16_t y, mo, dow, d, h, mi, s, ms; } ap_systime_t;
void __stdcall GetLocalTime(ap_systime_t*);
]];

-- Real one-target category-11 (NPC TP finish) packet captured from Mumor (skill 2900, anim 2038).
-- Layout verified against fields.lua 0x028: target count @bit72 (10), category @82 (4),
-- param (skill id) @86 (16), target id @150 (32), anim @191 (12). Only those fields and the
-- actor id (bytes 5-8) are patched; everything else stays as captured.
local TEMPLATE_HEX = '28 14 91 1c 1f bd d2 04 01 01 2c d5 02 00 00 00 00 00 00 c0 87 02 40 60 fb 03 74 04 40 2e 00 00 00 00 00 31 09 39 38 00';

local READY_HEX = '28 14 13 1e 1f bd d2 04 01 01 dc 58 18 5d 19 00 00 00 00 c0 87 02 40 00 fe 10 81 6a c1 0a 00 00 00 00 00 00 00 00 00 02';
local ap = { pending = nil, actor = 0, sweep = nil, logpath = nil };

local function template()
    local t = T{};
    TEMPLATE_HEX:gsub('(%x%x)', function (x) t[#t + 1] = tonumber(x, 16); end);
    return t;
end

local function set_bits(t, start, n, val)
    for i = 0, n - 1 do
        local pos  = start + i;
        local idx  = math.floor(pos / 8) + 1;
        local mask = bit.lshift(1, pos % 8);
        if (bit.band(bit.rshift(val, i), 1) == 1) then
            t[idx] = bit.bor(t[idx], mask);
        else
            t[idx] = bit.band(t[idx], bit.bnot(mask));
        end
    end
end

local function stamp()
    local st = ffi.new('ap_systime_t');
    ffi.C.GetLocalTime(st);
    return ('%02d:%02d:%02d.%03d'):format(st.h, st.mi, st.s, st.ms);
end

local function msg(s) print(chat.header('animprobe'):append(chat.message(s))); end

local function mark(kind, a, b)
    if (ap.logpath == nil) then
        ap.logpath = addon.path .. 'markers.log';
    end
    local f, err = io.open(ap.logpath, 'a');
    if (not f) then msg('LOG OPEN FAILED: ' .. tostring(ap.logpath) .. ' ' .. tostring(err)); end
    if (f) then
        f:write(('%s\t%s\t%s\t%s\n'):format(stamp(), kind, tostring(a or ''), tostring(b or '')));
        f:close();
    end
end

local function msg(s) print(chat.header('animprobe'):append(chat.message(s))); end

local function play(anim, skill)
    if (ap.actor == 0) then msg('No actor set. Target the entity and use /ap actor, or /ap find <name>.'); return false; end
    local me = AshitaCore:GetMemoryManager():GetParty():GetMemberServerId(0);
    local p = template();
    -- actor id = packet bytes 5-8 = p[6]..p[9] (Lua is 1-based; byte 4 is the Size field)
    set_bits(p, 40, 32, ap.actor);
    set_bits(p, 86, 16, skill);
    set_bits(p, 150, 32, me);
    set_bits(p, 191, 12, anim);
    mark('PLAY', anim, skill);
    local r = T{};
    READY_HEX:gsub('(%x%x)', function (x) r[#r + 1] = tonumber(x, 16); end);
    for i = 6, 9 do r[i] = p[i]; end
    msg(('inject ready+finish: actor %d anim %d skill %d'):format(ap.actor, anim, skill));
    AshitaCore:GetPacketManager():AddIncomingPacket(0x28, r);
    ap.pending = { pkt = p, at = os.clock() + 1.5 };
    return true;
end

local function entity_at(idx)
    local em = AshitaCore:GetMemoryManager():GetEntity();
    return em:GetServerId(idx), em:GetName(idx);
end

local out_path = nil;
local function reply(kind, ...)
    out_path = out_path or (addon.path .. 'bridge\\outbox.txt');
    local f = io.open(out_path, 'a');
    if (f) then
        f:write(stamp() .. '\t' .. kind .. '\t' .. table.concat({ ... }, '\t') .. '\n');
        f:close();
    end
end

local run;

ashita.events.register('command', 'command_cb', function (e)
    local a = e.command:args();
    if (#a == 0 or (a[1] ~= '/ap' and a[1] ~= '/animprobe')) then return; end
    e.blocked = true;
    run(a);
end);

run = function (a)
    local c = (a[2] or ''):lower();

    if (c == 'actor') then
        local t = AshitaCore:GetMemoryManager():GetTarget();
        local idx = t:GetTargetIndex(t:GetIsSubTargetActive() and 1 or 0);
        local sid, name = entity_at(idx);
        if (sid == 0) then msg('Nothing targeted.'); return; end
        ap.actor = sid; msg(('Actor = %s (server id %d, index %d)'):format(name, sid, idx));
    elseif (c == 'find' and a[3]) then
        local want = a[3]:lower();
        for idx = 0, 0x8FF do
            local sid, name = entity_at(idx);
            if (sid ~= 0 and name ~= nil and name:lower() == want) then
                ap.actor = sid; msg(('Actor = %s (server id %d, index %d)'):format(name, sid, idx)); return;
            end
        end
        msg('No entity named ' .. a[3] .. ' in range.');
    elseif (c == 'play' and a[3]) then
        local anim, skill = tonumber(a[3]), tonumber(a[4] or 2899);
        if (play(anim, skill)) then msg(('played anim %d (skill id %d)'):format(anim, skill)); end
    elseif (c == 'sweep' and a[3] and a[4]) then
        ap.sweep = { cur = tonumber(a[3]), last = tonumber(a[4]), gap = tonumber(a[5] or 8), nextt = 0, skill = tonumber(a[6] or 2899) };
        mark('SWEEP_START', a[3], a[4]);
        msg(('sweep %d..%d every %ss'):format(ap.sweep.cur, ap.sweep.last, ap.sweep.gap));
    elseif (c == 'stop') then
        if (ap.sweep) then mark('SWEEP_STOP'); end
        ap.sweep = nil; msg('stopped.');
    elseif (c == 'mark') then
        mark('NOTE', a[3]); msg('marker written');
    else
        msg('/ap actor | /ap find <name> | /ap play <anim> [skillid] | /ap sweep <from> <to> [gapSec] [skillid] | /ap stop | /ap mark <text>');
        msg('Markers: ' .. addon.path .. 'markers.log');
    end
end

-- Toolkit bridge: poll bridge\inbox.txt (lines: seq<TAB>cmd<TAB>args...) by byte offset.
local inbox = { offset = 0, nextpoll = 0 };
local function poll_bridge(now)
    if (now < inbox.nextpoll) then return; end
    inbox.nextpoll = now + 0.5;
    local f = io.open(addon.path .. 'bridge\\inbox.txt', 'rb');
    if (not f) then return; end
    f:seek('set', inbox.offset);
    local data = f:read('*a') or '';
    f:close();
    local used = 0;
    for line in data:gmatch('([^\n]*)\n') do
        used = used + #line + 1;
        local parts = {};
        for field in (line .. '\t'):gmatch('([^\t]*)\t') do parts[#parts + 1] = field; end
        if (#parts >= 2) then
            local a = { '/ap', parts[2] };
            for i = 3, #parts do a[#a + 1] = parts[i]; end
            reply('cmd', parts[1], parts[2]);
            run(a);
        end
    end
    inbox.offset = inbox.offset + used;
end

ashita.events.register('d3d_present', 'present_cb', function ()
    poll_bridge(os.clock());
    if (ap.pending and os.clock() >= ap.pending.at) then
        AshitaCore:GetPacketManager():AddIncomingPacket(0x28, ap.pending.pkt);
        ap.pending = nil;
    end
    local s = ap.sweep;
    if (s == nil) then return; end
    local now = os.clock();
    if (now < s.nextt) then return; end
    if (s.cur > s.last) then mark('SWEEP_DONE'); ap.sweep = nil; msg('sweep finished.'); return; end
    play(s.cur, s.skill);
    s.cur = s.cur + 1;
    s.nextt = now + s.gap;
end);
