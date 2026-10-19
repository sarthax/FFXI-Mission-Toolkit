# LSB Porting Roadmap (estimates rough, unvalidated)

| Phase | Scope | Files | Prereqs | Risks | Regression tests | Acceptance | Est |
|---|---|---|---|---|---|---|---|
| 0 Prereqs | exdata accessors, 6 bindings, migration, API shim, csid verification, headless gaps | `lua_item.*`, `lua_trade_container.*`, new `items/exdata/*`, `lua_baseentity.*`, `charentity.h`, `charutils.cpp`, `sql/char_chocobos.sql`, `char_pet.sql` | this audit | MyISAM, csid drift | existing item/trade/save | exdata + persistence round-trip across relog | 1.5-2 wk |
| 1 Initial raising | trainer scripts, event_vm shim, egg trade, chick | `Hantileon/Zopago/Pulonono/Kiria-Romaria.lua`, `scripts/globals/hobbies/chocobo_raising/*` | 0 | option protocol | Chocobo-on-the-Loose quest unchanged | raise a chick via headless | 2 wk |
| 2 Growth/care | care_plan, model, daily tick | module files | 1 | time/day math | scripted days | stats advance | 1.5 wk |
| 3 Personal chocobo | mountutils, char packet, whistle | `char.cpp`, `zone_in.cpp`, `battleentity.cpp`, `chocobo_whistle.lua` | 0,1 | 0x00D layout | rental whistle unchanged | model matches capture | 2 wk |
| 4 Extended | breeding, retirement, walks, stories | module files, Finbarr/Mapitoto | 2 | Mapitoto uncaptured | trade matrix | breed + retire | 2 wk |
| 5 Racing | 4 packets, tables, handlers | `packets/*`, `packet_system.cpp` | 3 | 0x074 direction | - | race completes | 4+ wk |

Recommended first slice: Phase 0 exdata accessors + persistence (A+D), plus the headless event-update/exdata diagnostics.
