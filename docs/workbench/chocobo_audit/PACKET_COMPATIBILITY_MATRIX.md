# Packet Compatibility Matrix (source-read only; none validated)

| Packet | LSB | DSP | Status | Note |
|---|---|---|---|---|
| s2c 0x032 event (no params) | used | `event.cpp` | present | |
| s2c 0x033 event string | used (naming) | `startEventString` | present | name-entry reply untested |
| s2c 0x034 event + 8 params | used | `event.cpp` | present | headless records params |
| c2s 0x05B event end/update | used | `packet_system.cpp:2626` | present | offsets match; Option override caveat |
| c2s 0x036 NPC trade | used | present | present | no item extra access in Lua |
| s2c 0x020 item attr | extdata | `inventory_item.cpp:48` | present | headless discards bytes |
| s2c 0x00D mount model | custom props | `char.cpp:114` hard-coded | missing | re-derive layout |
| s2c 0x069 racing | yes | none | missing | |
| s2c 0x073 toteboard | yes | none | missing | |
| s2c 0x074 chocobo list | yes | DSP 0x074 = party-invite answer (c2s) | collision-check | direction differs; verify |
| c2s 0x09B race request | yes | none | missing | |
