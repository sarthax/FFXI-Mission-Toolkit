# December 2019 Mog Wardrobes 5–8 — alternative architecture decision record

**Status:** candidate designs under static review; **NO GO for sending IDs 13–16 to the 2019 client**. Date 2026-10-21.

## Why bank switching is worth investigating

Owner has demonstrated that their December 2019 `FFXiMain.dll` accepts POL1 recompression and a single behavior-equivalent decoded instruction edit, successfully booting, connecting and displaying menus. This proves only a narrow patch/repack pipeline. It does **not** imply the client can safely store four additional simultaneous wardrobes.

The original 2019 item record range is an embedded 13-container array (81 slots × 44 B per container), and attempting to append container 13 in place overlaps live context fields/capacity arrays. The original 2019 pointer `0x104CDA08` points to an active inventory context which can change: static code anchors show initial context rooted in global backing `0x1096DB60`, a fixed `0xFB7D`-dword backing clear, a fixed `0xEC20`-dword context reset, and multiple active-pointer assignment sites. See `wardrobe5-8_2019_client_static_audit_2026-10-21.md` and the read-only `wardrobe_2019_allocator.py` auditor. **Other context allocations and all consumers still need auditing.**

A banked design instead keeps only four *visible* wardrobes in the native 2019 client, while preserving separate authoritative server-backed inventories for two banks.

### Exact virtual-to-canonical ID map (do not assume contiguity)

Verified on the Valhalla server's existing `src/map/item_container.h`: visible Wardrobe 1 = ID **8**, Wardrobe 2 = **10**, Wardrobe 3 = **11**, Wardrobe 4 = **12**. **ID 9 is Mog Safe 2**, not a wardrobe.

| 2019 client visible ID | Bank A authoritative ID | Bank B *proposed* authoritative ID | UI label when B active |
|---|---:|---:|---|
| Wardrobe 1 — 8 | 8 | 13 | Wardrobe 5 (virtual display of 1) |
| Wardrobe 2 — 10 | 10 | 14 | Wardrobe 6 (virtual display of 2) |
| Wardrobe 3 — 11 | 11 | 15 | Wardrobe 7 (virtual display of 3) |
| Wardrobe 4 — 12 | 12 | 16 | Wardrobe 8 (virtual display of 4) |

The client must **never** receive container IDs 13–16 in any original 2019 packet handler. Backing IDs 13–16 remain server-internal until modern client support is separately added. In bank-B mode, packet 0x1C retains the original 13-entry legacy layout and the outgoing item list uses visible IDs 8/10/11/12 after validated translation.

## Zone-transition evidence changes the proposed activation model (2026-10-21)

Owner correctly observed that FFXI routinely rebuilds its visible inventory during zoning. Inspection of **Valhalla DSP `main`** confirms the server transmits the inventory again on each zone-entry handshake, but the server-side character object is **not guaranteed to reload from SQL on every zone**.

| Point in handshake | Verified server behavior | Bank-switch implication |
|---|---|---|
| `packet_system.cpp` `SmallPacket0x00A` | Zone-entry/session preparation; can operate on an existing `CCharEntity` | Must identify the incoming effective bank, whether or not character was reconstructed |
| `SmallPacket0x00C` | Sends `CInventorySizePacket` (`0x1C`) for the character | Bank capacities must be correct **before** this packet |
| `SmallPacket0x00F` | Calls `charutils::SendInventory(PChar)` | Bank-visible item contents must be correct **before** this packet |
| `charutils::SendInventory` | Resends visible inventory, Mog bags and 4 Wardrobes, then `CInventoryFinishPacket`; also resends equipment associations | Hidden bank must not leak; equipped-item references need consistent aliasing |
| `SmallPacket0x011` | Resends equipped slot/container references | Must not refer to a stale/hidden bank after a switch |
| `map.cpp` `recv_parse` with `PChar == nullptr` | Allocates `new CCharEntity`; calls `charutils::LoadChar` | New map session reloads authoritative inventory from SQL |
| `charutils::LoadChar` | Calls `LoadInventory` (SELECT from `char_inventory`) then `LoadEquip` | Persisted bank selection must be applied to the correct authoritative items when reconstructing |
| Existing map-session zoning | `0x00A` can reuse an existing `PChar`/storage objects; `CZone::CharZoneIn` does not itself reload `char_inventory` | Simply writing a database `selected_bank` and zoning is **insufficient** for this case |
| `map_close_session` | Deletes character on session shutdown/zone close; zoning does not clear `accounts_sessions` like logout | Cross-process reload and same-process reuse have different lifecycles |

Source paths: `src/map/packet_system.cpp`, `src/map/utils/charutils.cpp`, `src/map/map.cpp`, `src/map/zone.cpp` on [Valhalla main](https://github.com/sarthax/darkstar-to-valhalla/tree/main). This is server source evidence, **not** a captured 2019 client trace. In particular, no independent proof yet establishes exactly when the old client clears stale visible inventory slots while zoning.

### Revised recommendation: persistent selection, safe **zone-entry activation** (candidate)

- Maintain a persistent **requested/selected** bank (`selected_bank`, A or B) per character and a session's **effective/loaded** bank (`effective_bank`).
- A server-side authorized menu, in-game NPC or Toolkit control may request B **while online**, but must not immediately overwrite the old visible inventory. Indicate **"Bank B selected — takes effect after the next zone"**. The request survives later zoning and relogging.
- On an allowed zone-entry boundary, **before** `0x00C` and `0x00F`, gate any transition on transaction quiescence, exact character identity, saved item persistence, equipment and gear-set references, and client refresh acceptance. If the existing `PChar` is reused, rebuild/translate its four visible wardrobe containers and references safely from server-authoritative data. If `PChar` was reconstructed from SQL, apply the persisted selected bank as part of its initial inventory load. Both paths must use one canonical bank decision.
- Change `effective_bank` **only after** a safe, coherent transition is verified. If any gate fails, keep the previous effective bank; retain the requested bank as pending with an explicit error (never silently show the wrong bank). No automatic reset to A on zoning.
- Keep all client-facing container IDs in `0..12`, with wardrobes **8,10,11,12**. Never expose canonical B IDs 13–16 or modern-format packet 0x1C to the 2019 client.
- Verify with a **packet capture and controlled client test** that the old client really replaces/clears stale occupied slots and equipment/cache state during a zone-entry inventory download. The server's resend code **alone does not prove** full client cache reset.
- Same-zone teleports that do not trigger the full `0x00A/0x00C/0x00F` sequence, or zones that preserve the prior server object, **must not be assumed** to activate the change.

**Fallback:** Until all the above zone-entry gates are implemented and tested, keep the original logout/login selection as the safer baseline. A zone-activated selection is potentially a substantially better user experience, but no runtime bank switch exists today.

## Existing player commands as a switching control (2026-10-21 evidence)

**Verified on `sarthax/darkstar-to-valhalla` `main`:** In `src/map/packet_system.cpp` incoming chat packet `0x0B5` checks for an initial `!` and invokes `CmdHandler.call(PChar, ...)`. `src/map/commandhandler.cpp` dispatches `scripts/commands/<name>.lua` using `cmdprops.permission` and `cmdprops.parameters`, and authorizes when the permission is not greater than `PChar->m_GMlevel`. Therefore a **player-eligible command with permission 0** could request an inventory-bank change without replacing native menus or granting GM privileges. This is an input/authorization mechanism, not a working inventory refresh API.

Proposed syntax (examples, **not implemented**):

```text
!wardrobebank status
!wardrobebank A
!wardrobebank B
!wardrobebank apply
```

**Required server wiring:** The Lua command can safely call a new, narrowly scoped C++ binding or service for `requestBank` / `requestApply`. The existing command framework does **not** currently expose a generic `refreshWardrobeBank` routine; a command alone cannot atomically retarget storage.

**Available packet constructors:** `CInventorySizePacket` sends legacy `0x1C` capacities, `CInventoryItemPacket` sends `0x20` slot/item detail (with a **null-item/zero-content constructor path**, not yet validated as a clear instruction), `CInventoryAssignPacket` sends `0x1F` flags, `CInventoryFinishPacket` sends `0x1D` completion, and `CEquipPacket` sends `0x050` slot/container references. `charutils::SendInventory` currently sends **only occupied item slots** and then finish/equip data. On a mid-zone B-bank reload, empty slots in B that had items in A would receive no explicit clearing packet. **Resending the normal full inventory without a proven clear stage is insufficient to establish a consistent client state.**

**Unverified client gate:** The original 2019 client might interpret a fresh 0x1C/0x1D sequence as a reset, or it might retain stale 0x20 records and UI/equipment caches. We must not infer this from the server packet builders. Verify against a disposable character with one A-only slot, one B-only slot, different augments, and zero equipped/outstanding transactions. Capture both client-visible slots and server-side canonical records. Confirm old slot clears, new slot populates, selected bank survives zoning and reconnect, no duplication/loss, and controls remain blocked while the inventory UI is open or another transaction is pending. A subsequent test must separately cover equipped items and equipment sets.

**Safe first milestone:** permission-0 **status and queued-selection** command plus persistence and acknowledgments, followed by a verified **zone-triggered** apply. Implement instant command-triggered apply only after the client clear/rebuild protocol has passed controlled tests. Do not send canonical 13–16 to 2019 clients or manipulate the client's inventory memory directly. Fail closed if the handshake/caches cannot be proven safe.

## Candidate approaches and relative risk

### 1. Server-authoritative **login-time bank selection** (conservative initial baseline)

- Implement separate authoritative server storage and persistence for canonical containers 13–16.
- Record `active_wardrobe_bank=A|B` per character (or as a tightly controlled session setting).
- Allow bank selection **only while logged out** using an authorized server-side action, and apply it before inventory packets are constructed at login. The original client still receives exactly the old 13-container wire layout.
- On server ingress (move, sort, use, equip, gear-set), translate visible wardrobe IDs to canonical backing IDs through a single validated per-session mapping. On egress translate canonical IDs to the correct visible IDs **only for the selected bank**.
- Deny switching when inventory write transactions are pending, account/session state is ambiguous, unresolved items are equipped from the outgoing bank, or gear-set references cannot be remapped safely. A logout alone is not proof that all data were durably persisted; verify storage transactions and database state before toggling.
- This is an **alternate storage bank**, not simultaneous 8-wardrobe functionality. Hidden-bank equipment/gear-set selection is unavailable unless additional server semantics are proved.

**Why first:** no injected DLL, no client-mode table expansion, no requirement for the legacy client to parse a modern `0x1C` packet, and every test can begin with a reversible server-feature flag. It still requires invasive server plumbing and database changes—**not a trivial packet alias**.

### 2. **Immediate in-session bank toggle** without zoning (later)

Maintain the same server banks but allow a safe toggle while connected. Requires a synchronized begin/ack/commit/end protocol, a full visible-inventory refresh and client cache invalidation, equipment/gear-set reference reconciliation, and rejection of in-flight moves/sorts/equips. The current packet map shows 0x1C, 0x1E, 0x1F, 0x20 handlers, but no proven atomic bank-refresh behavior. **Do not prototype by merely swapping 81-slot blocks in client memory.** Clearing and overwriting a visible bank without server coordination may duplicate/loss items or leave dangling slot references.

### 3. **Sidecar memory in the same client process** (subsequent full 8-wardrobe option)

A patch to the original `FFXiMain.dll` may allocate a separate buffer (e.g., via its own allocator) with records for additional IDs, then redirect *all* ID-aware readers/writers there. A separate DLL is **not inherently necessary**: the patched DLL could own its buffer. However, active-context switching, static first-context lifetime, raw indexing, packet parsing, menu dispatch, item use, and equipment all need coordinated hooks or callsite changes. A sidecar buffer is not persistent: canonical item state still belongs to the server.

### 4. **External helper DLL / Ashita plugin** (tooling-oriented option)

A separate module could hold extra transient state or provide a visible overlay. It may make iteration/reversal easier, but it would still need a defined, authorized load mechanism, hooks/integration for the exact client build, shared context lifetime rules, protocol translation and server backing. An Ashita Lua addon could potentially provide a UI/proof-of-concept workflow without changing the retail client module, but any native inventory behavior must still be verified. **Merely loading an external DLL does not cause the 2019 client to understand new container IDs**, and no hook/injection or loader bypass is implemented here.

### 5. **Existing-bag vault or manual transfer** (fallback)

The server can potentially expose archived items through an existing older container (e.g., through controlled delivery/transfer). This is simpler than native 8-wardrobe support but cannot honestly be labelled simultaneous wardrobe functionality: item eligibility, slot capacity, equipment and ownership rules must be preserved; do not repurpose Mog Safe 2 (ID 9) or overwrite existing possessions.

## Server dependencies observed

As of inspection of `sarthax/darkstar-to-valhalla` `main`:

- `item_container.h`: IDs 0–12, `MAX_CONTAINER_ID = 13`; no canonical 13–16.
- `charentity.cpp`: existing container objects/lookup only through wardrobe4.
- `sql/char_storage.sql`: only four wardrobe capacity columns.
- `inventory_size.cpp`: the older 0x1C capacity packet has u8 and u16 entries for IDs 0–12 only.
- `packet_system.cpp` 0x029 movement validates both IDs against `MAX_CONTAINER_ID`; 0x03A sort obtains a container pointer and dereferences it without a guard (recorded null-dereference risk).
- Equipment paths explicitly test for known Wardrobe IDs; changing only the movement handler will not make bank-B items equip reliably.
- `charutils.cpp` inventory save/load and equipment/augments iterate known containers or explicitly enumerate wardrobes; these are additional aliases/persistence surfaces.

**Design consequence:** The server translation must centralize canonical IDs and ensure *all* command paths use them. An isolated network packet rewriting trick cannot guarantee that equipment, server-side scripts and persistence reference the same physical item.

## Candidate acceptance contract — login-time bank selection (not yet implemented)

1. **Legacy-client invariants:** old client only sees IDs 0–12; packet 0x1C retains its original length and offsets; each visible wardrobe has exactly the expected capacity and item slot semantics.
2. **Separate persistent banks:** toggling A→B→A reveals exactly the original items in bank A, with counts, augments and identity preserved; no duplicates, lost items or moved inventory.
3. **Atomic selection gate:** rejected if connected, inventory transactions pending, save status UNKNOWN, unresolved equipment references, or unverified account/character ownership.
4. **Exact ID mapping:** explicit `{8:13,10:14,11:15,12:16}` for B; ID 9 (Mog Safe 2) passes through unchanged. No arithmetic assumptions on wardrobe IDs.
5. **Operations:** test pickup/move/sort/equip/unequip/gear-set, login item load, logout save and reconnect. Reject unsupported flows rather than silently targeting the wrong bank.
6. **Rollback:** off by default; feature flag restores native bank-A behavior without touching the original client DLL or making existing bank-B items visible prematurely.
7. **Evidence:** synthetic end-to-end fixtures first, then an owner-authorized, isolated private-server integration test with explicit inventory snapshots before/after; no new container packets sent to an unmodified 2019 client.

## Decision / follow-ups

**Recommend a persistent server-authoritative bank selection mechanism, implementing #1 first and then investigating safe zone-entry activation described above before any immediate live-toggle.** It offers a valuable compatibility mode for the old client even if full eight-wardrobe simultaneous support eventually uses #3. Confirm separate server persistence, packet aliasing, equipment semantics, and lifecycle safety before issuing a live test. A full all-eight-native client would require a separate, substantially larger engineering effort.

**No implementation or executable modification is authorized by this decision record.** No proprietary binaries, decoded executable dumps, passwords or packet captures are committed.
