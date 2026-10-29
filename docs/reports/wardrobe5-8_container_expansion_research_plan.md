# Wardrobe 5-8 container expansion: findings and research plan

Status: research (static analysis only). Date: 2026-10-18.
Scope: retail `FFXiMain.dll` 30210706_0 (old) vs 30261006_0 (new), POL1-decoded `.text`, image base 0x10000000. All addresses are RVAs.
No DLL was executed or modified and no binaries are committed. Raw reports live in the gitignored
`exports/retail_downloader_validation/decoded_reports/` (`XREF_SUMMARY.md` Addenda 1-6, `HANDOFF_wardrobe5-8_decode.md`, JSON reports).

## 1. Verified findings (new build)

| Layer | Finding |
|---|---|
| Commands | 24-byte records in .data (name[16], i16 id @+0x14, u16 flags @+0x16). New table RVA 0x355408; old 0x34c280. New adds `/wardrobe5-8` (ids 118-121) and `/recycle` (122). |
| Dispatch | lookup 0x77AD0 (old 0x76D10) -> dispatcher 0x80DC0 -> handler table @0x356E30 (12-byte `{id, handlerVA, flag}`, terminator 0x1d4) -> `handler(buf, 0x10354de0, id)`. |
| Mode wrapper | 0x1DAF70 (old 0x1D31E0): same gate chain; new adds mode 0x11 case, `[obj+0x70/0x71]` flags, arg3 branch, extra vtable call. |
| Mode sink | 0x1DC880 (old 0x1D69D0). Mode object @0x10663470 (vtable 0x10338cb8; slot 0x58 setter, 0x54 getter of `[this+8]`). 18-entry jump table @0x1DC9E0 (old: 11 entries, modes 2-12). Modes 13-16 = wardrobe5-8, 17 = /recycle. |
| UI container objects | 18 globals `0x10666e2c..70`, each 0x13bc bytes, 81 slots x 24 B @+0x6c (ctor 0x21C010, init stores 0x165c0d..0x165e82, free 0x166f30..). Modes 13-16 -> `e5c,e60,e64,e68`; 17 -> `e70`; mode 9 -> `e6c`. A derived cache refreshed by 0x21C380 when `[this+0x14]` != `[store+0x198c8]`. |
| Item store | global 0x104dfd98; records at `store+0x9868` (old 0x9860): `[container][81]` x 44 bytes, container stride 0xDEC, 18 containers. Accessor 0xEB490. |
| Packets | registration 0xEB2B0 (old 0xE9270), same 19 ids in both builds. 0x1C ITEM_MAX 0xEC4A0 (old 0xEA460); 0x1E 0xEC4F0 (0xEA4A0); 0x1F 0xEC550 (0xEA500); 0x20 0xEC630 (0xEA5E0); 0x1D 0xEC6C0 (0xEA670); 0x26 0xEC730 (0xEA6B0). 0x1E/0x1F/0x20 identical old vs new except record base. No bounds check on the container byte. |
| Capacity tables | New: u8 caps `store+0x19891` (18 entries), u16 caps `store+0x198a4` (18 entries, from pkt+0x24). Old: 13 + 13 at `store+0x152ed` / `+0x152fa` (u16 source pkt+0x14). Accessors 0xEB940 (u8) and 0xEB960 (u16). |
| Menu gate | Builder near 0x1F3C60 calls 0xEB940(container); if 0 it calls `0x118b60(menu, 5, entryId)` for entryId in {6,7,3,10..16}. Entries 13-16 exist only if the server's ITEM_MAX gives a non-zero capacity. |

Conclusion: the new client stores and displays containers 13-16 with no code-level restriction beyond the capacity gate.

## 2. Unknown / not established
* Server behaviour for containers 13-16 and the exact 0x1C layout the server must send.
* Final action of `0x118b60` (remove vs grey out; only its search loop was decoded).
* Old-build menu builder and handler-table extent; flag bits @record+0x16; the 4th stack slot read in 0x1DAF70.
* Purpose of new imports (CreateProcessA, CLSIDFromString, FindWindowA; GlobalFree removed) and the import clusters at 0x1BCC3C-0x1BCE7F and 0x30FBBE-0x30FE4C (not decoded).

## 3. Research plan (in order)
1. Capture a real 0x1C ITEM_MAX packet from the new client against a server that supports wardrobe5-8; confirm the u8/u16 layout and capacities for containers 13-16.
2. Decode `0x118b60` fully and the guards `0x1CC470` / `0xF97A0` in the menu builder.
3. Audit other consumers of the 18-container tables (equipment, Mog House, storage windows, trade) and outbound packets (item move 0x29, sort 0x3A, ...): check for container-id validation and hard-coded 13.
4. Pull client DAT text/menu data for the wardrobe5-8 labels (dat-extractor) so the strings are real, not guessed.
5. Locate the old-build menu builder (use old cap-table offset `store+0x152ed`).
6. Decode the import clusters; identify flag semantics at record+0x16.

## 4. Implications

### Server (supporting the 2026 client) - expected scope
Not verified against this repo's server code; confirm against the Valhalla DSP tree before relying on it.
* Container constants and capacity storage for wardrobe 5-8 in the DB.
* 0x1C packet with 18 u8 + 18 u16 capacities at the new offsets; item-load packets (0x1F/0x20) for containers 13-16.
* Move/sort/use/equip logic and Lua must accept the new ids; retest wardrobe 1-4.
* First confirm which client version the server is locked to.

### Backporting to the old client
Not a small patch; treat as a separate project:
* The item store and capacity tables moved offsets because the struct grew; all dependants shift.
* The command table and handler table are fixed-size `.data` arrays with no slack; the mode switch, menu builder and 0x1DAF70 changed.
* The binary is POL1-packed, so a patch means unpack/edit/repack or a runtime patcher.
* Safety: the old client's item handlers do not bounds-check the container byte against a 13-container store. Sending containers >= 13 to it would likely corrupt adjacent memory (inferred; old store size not measured).
* Patching a client for a private server is fine for research; do not distribute patched binaries or commit them.

Recommended order: confirm target client version -> capture 0x1C -> server-side support on a branch -> only then consider old-client patching.

## 5. Method notes
* PE relocations cover only .data/.rdata, so code xrefs were validated by function-start alignment (16-byte, after 0x90/0xCC) plus linear Capstone decode.
* Capstone 5.0.7 under system `py -3.11` with `PYTHONPATH=".;src"`; the `.venv` has no Capstone (pip SSL failure, not bypassed).
* Toolkit services used: `workbench.client.pol1_unpack`, `binary_index.PEImage`, `cli/pol1_report.py`. No Toolkit source changed.

## 6. Client patch feasibility audit (2026-10-21)

A separate [read-only FFXI Client Patch Feasibility Audit](ffxi_client_patch_feasibility_audit_2026-10-21.md) now records the verified PE/POL1/tooling baseline, unresolved signing/loader/launcher questions, hazards, and gated local test checklist.

**Current decision:** NO-GO for deployed or retail-code binary edits, runtime injection, or an old-client Wardrobe 5–8 backport. GO for read-only exact-build inspection, synthetic PE patch/rollback experiments, synthetic POL1 encode/decode research, and isolated untouched-client baseline testing. Successful POL1 decode does not establish safe repacking or a working client patch. The modern-client server-compatibility path remains a separate workstream.
