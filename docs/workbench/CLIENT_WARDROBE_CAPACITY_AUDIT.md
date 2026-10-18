# Wardrobe capacity compatibility audit

The 2026 FFXiMain.dll analysis reports 18 inventory containers and capacity-dependent menu entries. The 2021 analysis reports 13 containers. These findings are static research, not proof of runtime support.

Mission Toolkit already maps location IDs 13–16 to Mog Wardrobe 5–8 in `src/workbench/editors/character/inventory_slots.py`. Its capacity lookup checks whether the connected `char_storage` table contains the corresponding columns. This does not establish server packet support.

Before changing DSP, inspect the authoritative server source for packet 0x1C layout and capacity serialization, inventory load packets 0x1E–0x20, item movement, equipment sets, and persistence. Capture a compatible 2026 login packet sequence and compare capacities with UI state. Avoid sending containers 13–16 to the 2021 client until bounds safety is established.

Evidence handoff: `HANDOFF_wardrobe5-8_decode.md` and `XREF_SUMMARY.md` under local gitignored `exports/retail_downloader_validation/decoded_reports/`. Keep retail binaries and decoded executable images out of Git.
