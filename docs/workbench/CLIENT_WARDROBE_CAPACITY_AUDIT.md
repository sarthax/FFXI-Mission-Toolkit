# Wardrobe capacity compatibility audit

The 2026 FFXiMain.dll analysis reports 18 inventory containers and capacity-dependent menu entries. The 2021 analysis reports 13 containers. These findings are static research, not proof of runtime support.

Mission Toolkit already maps location IDs 13–16 to Mog Wardrobe 5–8 in `src/workbench/editors/character/inventory_slots.py`. Its capacity lookup checks whether the connected `char_storage` table contains the corresponding columns. This does not establish server packet support.

Before changing DSP, inspect the authoritative server source for packet 0x1C layout and capacity serialization, inventory load packets 0x1E–0x20, item movement, equipment sets, and persistence. Capture a compatible 2026 login packet sequence and compare capacities with UI state. Avoid sending containers 13–16 to the 2021 client until bounds safety is established.

Evidence handoff: `HANDOFF_wardrobe5-8_decode.md` and `XREF_SUMMARY.md` under local gitignored `exports/retail_downloader_validation/decoded_reports/`. Keep retail binaries and decoded executable images out of Git.

## Authoritative server source inspection (2026-10-18)

Repo: [sarthax/darkstar-to-valhalla, main](https://github.com/sarthax/darkstar-to-valhalla/tree/main). **Important:** GitHub metadata advertises `master` as default, but `main` exists and is explicitly the inspected ref; do not accidentally substitute `master`.

Confirmed on `main`:

- [`src/map/item_container.h`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/item_container.h) enumerates locations 0–12 only; `MAX_CONTAINER_ID = 13`.
- [`src/map/entities/charentity.cpp`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/entities/charentity.cpp) constructs per-character container objects only through wardrobe4; `getStorage` switch only covers these known containers, with a debug check against `MAX_CONTAINER_ID`. [`charentity.h`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/entities/charentity.h) declares only four wardrobe pointers.
- [`sql/char_storage.sql`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/sql/char_storage.sql) has wardrobe, wardrobe2, wardrobe3, wardrobe4 columns, but no wardrobe5–8 columns.
- [`src/map/packets/inventory_size.cpp`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/packets/inventory_size.cpp) sends packet 0x1C capacity entries only for containers 0–12; u8 entries at offsets 0x04–0x10 and u16 entries at 0x14–0x2C. It sets packet `size = 0x1A`, whose unit/header convention must be checked before changing the layout. It uses `1 + GetSize()` and `1 + GetBuff()`; do not infer that an all-zero uninitialized container is advertised as zero without checking packet semantics.
- [`src/map/utils/charutils.cpp`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/utils/charutils.cpp) `LoadCharStorage`, `SendInventory`, and `SaveCharInventoryCapacity` enumerate only through wardrobe4. Other inventory loops depend on `MAX_CONTAINER_ID`.
- [`src/map/packets/inventory_assign.cpp`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/packets/inventory_assign.cpp) emits type 0x1F from item location/slot; [`inventory_item.cpp`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/packets/inventory_item.cpp) emits type 0x20 with location at packet offset 0x0E. Existing individual packet classes are not, by themselves, proof of compatibility with 13–16.

**Conclusion:** `main` is missing end-to-end Wardrobe 5–8 support at enum/object/schema/load/save/0x1C capacity level. This is a confirmed source gap, not merely a hypothesis from the DLL. Do not patch 0x1C alone. Prior to implementation, inspect inventory movement validation, equip paths, SQL migrations, packet framing, and compatibility with older clients; add regression fixtures, then test with a newer client in a controlled environment.

## Inventory operation safety follow-up (2026-10-18)

- [`packet_system.cpp`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/packet_system.cpp), `SmallPacket0x029` near line 921: explicitly rejects source/destination locations `>= MAX_CONTAINER_ID` before calling `getStorage`.
- Same file, `SmallPacket0x03A` near line 1296: directly calls `PChar->getStorage(RBUFB(data,0x04))` and then dereferences `PItemContainer->GetSize()` with no intervening null check. `CCharEntity::getStorage` returns null for unsupported IDs. **Potential invalid-container crash path; source-derived risk, not runtime reproduced.** Fix independently with early bounds/null validation and regression tests before extending container support.
- `charutils::MoveItem` also assumes its caller supplied a valid location and dereferences `getStorage`; review all entry points before broadening IDs.
- `CBasicPacket` holds a 0x104-byte buffer; `CInventorySizePacket` uses `size = 0x1A`, while writing u16 capacities through byte offset 0x2C. The size-field unit and client 0x1C wire framing still need verification; these are **not** necessarily contradictory.

### Research stop/go criterion

Proceed to server implementation only after confirming the 2026 0x1C packet layout and identifying the server's inventory ingress validation surface. Treat a general retail-client decompilation or 2021 binary backport as out of scope.

## Packet 0x1C framing clarified (2026-10-18)

[`src/map/packets/basic.h`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/packets/basic.h) defines `length() = 2 * (ref<uint8>(1) & ~1)` and a setter that rounds packet length to a 4-byte boundary. Thus the existing `CInventorySizePacket` header value `size = 0x1A` corresponds to **52 bytes** (0x34), not 26. The final existing u16 capacity is written at offsets 0x2C–0x2D, within the 52-byte buffer. The 13 u8 entries occupy 0x04–0x10; 0x11–0x13 are not written by this constructor; the 13 u16 entries occupy 0x14–0x2D. The remaining bytes 0x2E–0x33 are initialized to zero by the base packet constructor. This resolves the previously open size-unit question.

**Do not extrapolate** a new 18-container packet by simply appending five entries: the newer client's packet 0x1C handler must be inspected for exact wire offsets and expected length. The client-side *store* offsets (0x19891 and 0x198a4) from the binary report are not packet offsets. The current 13-container layout is proven from server source; the 18-container wire layout remains unverified.

## Decoded client ITEM_MAX comparison (2026-10-18)

Evidence source: local read-only analysis artifacts `HANDOFF_wardrobe5-8_decode.md` and `XREF_SUMMARY.md` (Addenda 5–6), comparing decoded retail builds 30210706_0 and 30261006_0. The binaries were not executed and are not included in this repository.

| Field | 2021 client 30210706_0 | 2026 client 30261006_0 |
| --- | --- | --- |
| Handler RVA | `0xEA460` | `0xEC4A0` |
| u8 capacity source | packet `+0x04`, 17 copied bytes (13 container capacities) | packet `+0x04`, 18 copied bytes (18 container capacities) |
| u16 capacity source | packet `+0x14`, 13 entries (26 bytes) | packet `+0x24`, 18 entries (36 bytes) |
| Last source byte used by u16 copy | `0x2D` | `0x47` |
| Minimum byte span needed by these reads | `0x2E` | `0x48` |

**Implementation consequence:** the new u16 capacity table is relocated by 0x10 bytes, so merely extending the existing 52-byte server packet's old u16 table is incorrect. A modern-format capacity packet must cover at least 72 bytes (0x48); given Valhalla's 4-byte packet-length rounding, 72 is representable, but exact emitted header and any intervening reserved bytes require tests. Do not infer that the 17/18 copied u8 bytes all represent independent capacity IDs: the old 17-byte copy overlaps the first u16 table byte at 0x14; inspect the decoded handler for precise copy semantics if implementing a writer.

**Safety/compatibility:** this is static evidence of two different inbound client layouts, **not** evidence that Valhalla can identify the client build or that modern-format packets can be safely sent to legacy clients. Gate format selection on a verified per-session capability signal, or maintain separate compatible server/client deployments. The newer client's behavior with a legacy-format 0x1C packet has not been runtime tested.

Next work: verify exact handler instruction listings and capture a real 2026 packet 0x1C; map session/version detection and tests before any wardrobe enablement. Do not commit DLLs or decoded executable images.
