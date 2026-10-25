# DSP Chocobo Raising Compatibility Audit

Target: `D:\Claude\dsp-branches` @ `f2d771e0fc818cf2b2a65aea123253f5f4be438c` (tracked tree clean; untracked GIT_VER, data/).
Reference: LSB `scripts/globals/hobbies/chocobo_raising/` and the C++ pieces named below. LSB licensing/attribution must be preserved on any ported file.

**Method: source-read only. Nothing was run in-game, no captures were replayed, no DB was touched. Therefore no finding is `validated`.**
Per-finding evidence (path:line) is in `dsp-audit-evidence.json`.

## Gap matrix

| # | Subsystem | LSB | DSP | Core (C++) | SQL | Lua | Packet | Tests | Pri | Cplx | Depends on |
|---|-----------|-----|-----|-----------|-----|-----|--------|-------|-----|------|-----------|
| A | Eggs/exdata | present | partial | exdata structs, `getExData/setExData` on CLuaItem, trade-slot item access | none | helper | none (0x020 already sends extra) | unit + headless 0x020 | P0 | M | - |
| B | Stable NPCs/events | present | partial | none | Mapitoto row (uncaptured), Pulonono y check | trainer scripts, Kiria-Romaria | verify csids | headless event walk | P0 | M | A,C,D |
| C | Packets | present | partial | likely none; check `m_event.Option` override | none | event_vm shim | capture-verify | capture replay | P0 | M | - |
| D | Persistence | present | missing | 6 bindings, `m_chocoboUserData`, delete-char cleanup | `char_chocobos`, `char_pet.chocobo_user_data` | - | none | relog persistence | P0 | M | - |
| E | Care/growth | present | missing | none beyond D | none | port ~7.2k lines (API shim) | none | scripted day-advance | P1 | L | A-D |
| F | Whistle/mount | present | partial | custom-properties bitfield, MOUNTED subpower flag, 0x00D mount word, speed/time | none | whistle.lua | 0x00D layout for CLIENT 30170905_5 | headless mount read + capture | P1 | L | D |
| G | Breeding/retire | present | missing | none beyond A/D | none | port | none | trade tests | P2 | M | A,D,E |
| H | Walks/stories/dig | present | partial | none | none | port walks | none | scripted | P2 | M | E |
| I | Racing | present | missing | 4 packets + handlers | race tables | port | 0x069/0x073/0x074/0x09B (DSP 0x074 collides) | - | P3 | XL | F |
| J | Headless | n/a | partial | none (client unchanged by this audit) | - | - | - | - | P0 | S | - |

## Confirmed reusable (source-verified, not runtime-verified)
- Generic event start/update/finish; 0x05B layout matches LSB's EVENTEND offsets (`packet_system.cpp:2626-2650`); `startEventString`, `updateEvent` exist.
- `item.h m_extra[0x18]` persists and is sent to the client.
- Rental whistle/License gating, chocobo digging packet + scripts.
- Trainer NPC rows (Hantileon, Zopago, Pulonono); default trigger csids numerically equal LSB intro csids 817/508/741.
- Lua `bit` library, `VanadielTime()`.

## Confirmed missing
Exdata accessors; egg/card structs; `char_chocobos`; `chocobo_user_data`; 6 chocobo bindings; personal-chocobo appearance/speed/time; Kiria-Romaria script; Mapitoto NPC; walks; all racing packets.

## Unknown, needs live testing
1. Other csids per trainer (only the intro csid matches) against this client build.
2. 0x00D mount word bit layout for personal chocobo.
3. Whether the `m_event.Option` override breaks option-driven menus.
4. Extra-byte preservation on item move/stack/split.
5. Retail option sequence for trainer menus (check `D:\Claude\Playthrough Captures` first).
6. Pulonono y (-5.35 vs LSB -6.35): `!checknav`/`!logpos`.

## Required core modifications (summary)
A: exdata + Lua accessors. D: bindings + char-delete cleanup. F: mountutils equivalent + char packet. C: possible Option override fix. I: new packets.

## Risks
Client-generation csid drift (see CLAUDE.md); live DB is MyISAM (no cascade); API aliasing (`getCharVar`/`getVar`, `messageName`/`messageSpecial`; `getTrade`, `isInEvent`, `hasCompletedQuest`, `registerCylindricalTriggerArea` absent); LSB approximations in its own README should not be treated as retail truth.

## Trainer CSID verification (2026-10-24, client pull same session)
Source: `mission_toolkit.py` events.yml, per-trainer entity event list (zones 230/234/241).
LSB `xi.chocoboRaising.csidTable` ids (intro, main, trade, rejection, chicks, debug) all exist on the trainer's own entity in this client:
- Hantileon (230): 817, 823, 826, 831, 852 present (also 821,822,824,825,827,829,830).
- Zopago (234): 508, 509, 512, 515, 542 present (also 510, 511, 513).
- Pulonono (241): 741, 742, 745, 748, 766 present (also 743, 744, 746).
Not yet verified: walk csids (298-300/304, 554-556/560, 810-812/816) and debug csids (862/551/773); option protocol (trade option 252).

## Option protocol evidence (2026-10-24)
- Captures: grep of D:\Claude\Playthrough Captures for Hantileon/Zopago/Pulonono hits only npclogger position tables (Sunbreeze, Periqia). NO capture of the raising menu exists, so retail option values are unverified.
- DSP 0x05B (`packet_system.cpp` SmallPacket0x05B): Result=u32@0x08, EventID=u16@0x12, update flag=byte@0x0E. Update -> OnEventUpdate(csid,Result); finish -> OnEventFinish. `m_event.Option != 0` overrides Result (server-set option); LSB trade handling `option == 252` arrives via Result unless Option override is set.
- DSP has `player:updateEvent` (lua_baseentity.cpp:3440); arg count/semantics vs LSB's onEventUpdateVCSTrainer usage still to compare.
- Next: capture a retail raising session (Hantileon menu + egg trade) before building P1; do not invent option values.

## Retail option protocol from ingested captures (2026-10-24)
User supplied 37 public captures (D:\Claude\Playthrough Captures\Chocobo Raising); ingested as content_type=unclassified, capture_id 792-828, 1.37M raw packets in capture_raw_packets (opcode strings are mixed-case '0X05B'/'0x05B': use upper()).
Capture 824 (Windurst, Pulonono, initial egg trade, 2022-01-14) decoded:
- S>C 0x034 csid 741 (intro, params 0,65372159,13408674,4095,4,...) -> C>S 05B result 0 upd 0 (finish).
- Player trades egg: C>S 0x036 (64 B, one item) -> S>C 0x034 csid 745 (trade csid) -> C>S 05B result 252 upd 1 (update) -> C>S 05B result 252 upd 0 (finish). Confirms LSB `csid==tradeCSID and option==252`.
- Main menu csid 742: ~27 C>S 05B upd 1 updates with option values 208,214,215,243,244,46,248,250,251, ending upd 0 result 215. Menu navigation = update packets; finish carries last option.
- csid 761 (no trade params) and 10008 appear after; 748 (rejection) not in this capture (see 'Trade Egg - Rejected' capture 825).
- Open: no visible S>C start packet for csid 742 after the 745 finish in the decode (start likely a startEvent from onEventFinish; recheck ordering with seq), and the S>C update replies (0x05B updateEvent responses) are not yet decoded.
Next: decode capture 825 (rejection 748) and the care-plan menu option values against LSB onEventUpdateVCSTrainer before building P1.

## Retail decode: trade, rejection, menu replies (2026-10-24, captures 824/825)
Packets: C>S 0x036 trade, S>C 0x034 event start, S>C 0x05C event update (8 x u32 @0x04), C>S 0x05B (result u32@8, update flag@0x0E, csid u16@0x12). Rows duplicate in capture_raw_packets (case-variant opcode); dedupe on seq.
- Trade accept: S>C start csid 745 -> S>C 05C `(0, 3, 0,0,0,0,0,0)` (p1 = raising location, 3 = Windurst; LSB `updateEvent(0, raisingLocation[zone], 0..)`) -> C>S 05B 252 upd1 -> C>S 05B 252 upd0 (finish).
- Rejection (wrong item): S>C start csid 748 `(0,0,0,0,3,..)` -> C>S 05B 244 upd1 -> S>C 05C `(0,0,0,0,2,1,0,0)` (p4 = stage, p5 = 1; LSB PRESENT_CHOCOBO_APPEARANCE=244 -> updateEvent(0,0,0,0,saved.stage,1,0,0)) -> finish 244.
- Main menu 742: option = low byte command (LSB `bit.band(option,0xFF)`, arg = option>>8). Observed commands 208,214,215,241,243,244,246?,248,250,251,46; replies e.g. 248 -> `(248,1,0,0,1,0,0,0)` or `(248,5242886,..,2,1)`, 241 -> `(4545,96,0,0,1,4,0,0)`, 251 -> `(251,0,460551,65536,..)`, 244 -> `(0,0,0xFFFFFFFF,0,1,1,0,0)`. LSB command table and reply shapes agree where checked; full per-command reply values not yet diffed.
Verdict: LSB's trade/rejection/option protocol matches retail for the commands decoded.
Scope note for P1: the trainer flow depends on LSB event_vm (1180 lines), event_playout, model, choco_data, constants, names, whistle, retirement (~7.2k lines Lua, modern LSB utils). It is a port, not a patch. Proposed split: P1a intro + egg trade + rejection + chocobo creation (needs choco_data/model/constants subset and newChocobo); P1b main menu VM and care plan.
