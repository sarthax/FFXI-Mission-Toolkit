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
