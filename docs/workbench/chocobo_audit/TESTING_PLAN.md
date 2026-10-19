# Testing Plan

Headless (xiheadless-dsp, unmodified here) can trigger an NPC, finish an event, trade, use an item, read inventory and log out.
Needs additions (separate PR in that repo, isolated diagnostics only): mid-event update with option, per-step 0x032/0x034 capture, 0x020 extdata exposure, mount/ChocoboIndex readout, relogin.

Per phase:
- P0: migration up/down + char delete; exdata round-trip across relog.
- P1: trade egg, raise chick via headless.
- P2: scripted day advance asserts stat deltas.
- P3: whistle with/without a registered chocobo; mount model vs capture.
- P4: breed/retire trade matrix.
- P5: race packets vs capture.

`validated` status requires `test:`, `runtime:` or `capture:` evidence.
