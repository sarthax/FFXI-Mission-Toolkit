# Stage 4: exact December 2019 Wardrobe 5–8 backport gates

**Status:** Read-only static audit; no Wardrobe 5–8 client functionality implemented, no binary patches generated. Date: 2026-10-21.

**Source:** User-provided original `FFXiMain.dll`, exactly 2,870,352 bytes, SHA-256 `514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f`. POL1 decoded `.text` 3,264,206 bytes; SHA-256 `af2126c057d86559bfad2e164f7f7fd0a26bbc89ab29ea9cbde5cea807c7d2b8`. PE32/x86 image base `0x10000000`. All RVAs below identify instructions in the **decoded** `.text`, not on-disk offsets. The original file was read only. Static code was examined with `objdump -D -b binary -m i386 -M intel --adjust-vma=0x10001000`; verify instruction entry alignment and callers independently before changing anything.

## User-verified smoke tests (separate experiments)

1. PE COFF timestamp-only change: game boot and map-server connection succeeded.
2. POL1 lazy recompression with explicit zero-distance stop token, unchanged decoded code: boot and map-server connection succeeded.
3. One behavior-equivalent decoded instruction substitution `TEST EDI, EDI` → `OR EDI, EDI`, then POL1 repack: **boot, map-server connection, menu interaction** succeeded, no errors reported.

Those are **owner-observed limited runtime passes**, not unit tests of Wardrobes 5–8, long-duration stability, inventory correctness or evidence that a modified instruction was executed. The owner was asked to restore the original following Stage 3; restoration after that test had **not yet been reported**.

## Directly observed 2019 structure

| Area | 2019 RVA / evidence | Boundary / result |
|---|---|---|
| `.data` wardrobe command records | `0x34B1B0`, `0x34B1C8`, `0x34B1E0`, `0x34B1F8` | Four consecutive 24-byte records: `/wardrobe` IDs **111**, `/wardrobe2` **112**, `/wardrobe3` **113**, `/wardrobe4` **114**. No exact `/wardrobe5`–`/wardrobe8` record found in the scanned `.data` table. Nonmatch is not proof that runtime feature support is absent. |
| Inbound packet handler registration | `0xE85D0` | Packet `0x1C` → `0xE97C0`; `0x1E` → `0xE9800`; `0x1F` → `0xE9860`; `0x20` → `0xE9940`. These are static function pointer registrations. |
| Packet `0x1C` ITEM_MAX | `0xE97C0` | Copies **13 capacity bytes** from packet `+0x04` to store `+0x152ED`; copies **13 little-endian u16 capacities** (26 bytes) from packet `+0x14` to store `+0x152FA`. u8 copy implemented as 3 DWORDs + 1 byte; u16 copy as 6 DWORDs + 1 WORD. |
| Capacity accessors | `0xE8C60` / `0xE8C80` | Indexed u8 at `store + containerID + 0x152ED`; indexed u16 at `store + 2 * containerID + 0x152FA`. The observed getter instructions do **not** check the container index before reading. |
| Inventory records | `0xE87B0`, store base `0x9860` | Direct indexed lookup of `[container][slot]`: **81 slots × 44-byte records**, hence per-container stride `0xDEC`; no visible container bound guard in this accessor. |
| 13-container sentinel | `0xE8810`, compare at `0xE8844` | A loop compares its container counter against **13** (`0x0D`) and returns sentinel 13 on failure. Shows a concrete 13-container assumption in one routine. |
| Item/quantity packet `0x1E` | `0xE9800` | Directly reads packet container byte at `+0x08` and slot at `+0x09`, then indexes `store + 0x9860 + (container*81 + slot)*44`. |
| Item-list packet `0x1F` | `0xE9860` | Reads container at packet `+0x0A` and slot at `+0x0B`, then uses same computed record address. |
| Item-attributes packet `0x20` | `0xE9940` | Reads container at packet `+0x0E` and slot at `+0x0F`, then uses same computed record address. |

**Safety finding:** In the inspected entry blocks for `0x1E/0x1F/0x20`, the raw packet container ID participates directly in record-address computation; no `<13` guard is visible before those accesses. A complete control-flow and server-ingress audit has **not** been performed. Given known 2019 fixed-size structures, treating IDs **13–16** as already supported could address beyond allocated storage. This is a **high-risk inference**, not a demonstrated runtime corruption or exploit. Do not send unsupported IDs or test malformed inventory packets against the live client.

## Comparison with existing newer-client research (not remeasured here)

The earlier `docs/reports/wardrobe5-8_container_expansion_research_plan.md` and `docs/workbench/CLIENT_WARDROBE_CAPACITY_AUDIT.md` independently identify the 2021 client as 13-container and the October 2026 client as 18-container. The 2026 build uses shifted capacity/store offsets, 18 pointer-backed UI container objects, additional mode cases, extra command handlers and a different packet `0x1C` u16 source offset (`+0x24` rather than the legacy `+0x14`). These are **prior report findings**, not evidence that simply transplanting constants into 2019 will be safe.

The `darkstar-to-valhalla` server audit documented on Toolkit main likewise identifies 13-container enums, old 0x1C layout, and persistence up to Wardrobe 4. That server would require separate compatible changes or an explicit client-format deployment boundary. Do not modify only one side of the protocol.

## New reproducible metadata-only tool

`python -m workbench.client.cli.wardrobe_2019_report "C:\\research\\original\\FFXiMain.dll"`

`workbench.client.wardrobe_2019_audit.audit_2019_wardrobe(image)` compares the exact source hash, decoded-code hash, four command records, and nine short decoded opcode anchors. It emits **only scalar/boolean JSON metadata**, never executable bytes, patched output or raw packet buffers. If the SHA-256 does not match the exact 2019 input, it returns `UNKNOWN_BUILD_FINGERPRINT` and makes no version-specific claims. The checks corroborate **known static anchors**, not all paths or runtime execution. Its test suite uses synthetic bytes only and runs on Windows and Linux.

## Fixed global item-store layout: newly verified structural blocker

**New exact-build static verification:** The unmodified December 2019 DLL was decoded again from its SHA-256-verified original. Fifteen instruction-byte anchors, including six new initialization/adjacent-field anchors, matched the documented RVAs. `objdump` disassembly supports the following layout. This is **static x86 evidence**, not a recovered C++ structure definition or execution trace.

| Evidence | Decoded .text RVA | Observed behavior |
|---|---|---|
| Global zero-initialized buffer setup | `0xF6BA7`, `0xF6BBE` | Loads fixed VA `0x1096DB60`, sets `ECX=0xFB7D`, executes `rep stosd` for **0x3EDF4 (257,524) bytes**. A global variable `0x104CDA04` receives the base pointer. The buffer lies within virtual `.data`, but outside the on-disk initialized `.data` bytes. |
| Active store pointer | `0xF6C26–0xF6C33` | Stores **buffer base+4** to the global active-store pointer `0x104CDA08`. Other routines dereference that active pointer. |
| Legacy item record base | `0xE87DF` (accessor), `0xE9823` etc. | Active store `+0x9860`; item record address `(container*81+slot)*44`. |
| Per-container stride and count | `0xE883E`, `0xE8844` | Increments pointer by `0xDEC` (3,564 bytes) and compares index against **13**. |
| First fields directly after inventory | `0xE885E`, `0xE8881` | Writes zero to DWORD at active store `+0x14D5C`; stores a derived pointer at `+0x14D60`. Other code consumes these fields. **They are not free padding.** |

**Calculation:** The legacy array begins at active store `+0x9860` and occupies `13 * 81 * 44 = 46,332` bytes (`0xB4FC`), ending *exclusively* at **`+0x14D5C`**. This exactly coincides with the next state field. Five more 81×44-byte containers would require **17,820 additional bytes (`0x459C`)**, moving the end of an in-place 18-container array to `+0x192F8` and overlapping the known `+0x14D5C` and `+0x14D60` fields.

Therefore, **NO-GO for increasing the loop bound, packet capacities, or container count in place**. Even if the total global buffer could hold the extra 17,820 bytes, those bytes are currently assigned to unrelated state; the aggregate buffer's available capacity is not interchangeable with contiguous free item-record space. Potential solutions such as a separate allocation, an indirection layer, or full field relocation require auditing pointer identity, constructors/destructors, all callers, and performance before any design choice.

The new `inspect_2019_store_layout` function returns metadata-only layout evidence, budget arithmetic, and a **fail-closed overlap gate**. The evidence status becomes verified only if the exact source and decoded hashes and all selected static x86 anchors match. Synthetic tests assert the collision and decline to claim verification if the anchors fail.

## Synthetic bounds oracle added

The Stage 4 module also provides a **pure offline address validator** for the original 13-container layout. For a container `c` and slot `s`, it returns `0x9860 + (c * 81 + s) * 44` **only** when `0 <= c <= 12` and `0 <= s <= 80`; every other value returns no address. Booleans and non-integer numeric values fail closed. This models the storage stride seen in the 2019 decoded code without dereferencing process memory.

`inspect_2019_item_packet_location` uses only the observed **static packet payload field offsets** (0x1E: container +0x08 / slot +0x09; 0x1F: +0x0A / +0x0B; 0x20: +0x0E / +0x0F). It refuses unsupported packet IDs, truncated buffers and container IDs 13–16/255 and slot 81/255. **This is a synthetic test oracle, not a live parser, not a packet filter and not a client modification.** No malformed packets were sent to the client or server. If handlers use additional packet framing or translations, those must be independently verified before applying this model.

## Go/no-go and next implementation slice

**GO:** Further read-only mapping, server/version compatibility planning, synthetic bounds tests, and standalone feature staging on a separate branch.

**NO-GO:** Sending IDs 13–16 to the existing 2019 client, extending capacities in packet 0x1C without allocating safely, or producing an installable Wardrobe 5–8 client patch based only on the compression smoke tests.

Priority order:

1. Map **all** packet consumers/egress and related inventory store accessors; identify where checks can be centralized, including `0x1E/0x1F/0x20`, item moves/sort, equipment sets and other non-obvious sinks. Distinguish packet-layout compatibility per connected client version.
2. Build explicit synthetic tests for **containerID 12 valid, 13–16 denied, 255 denied** against 2019 bounds; handle slot index 0/80/81 safely. Do not send these packets to a live process.
3. Reverse-engineer store allocation size, lifetime, all offsets that follow the store, and UI-object counts before designing 18-container expansion. Investigate the old mode-switch and command handler table and menu gate; do not grow a fixed table in place.
4. Independently verify the server 0x1C 2019 wire layout and a future version-gated 18-container format; no modern-format packet to an unmodified 2019 client.
5. Only after a reviewed compatible design and rollback criteria, authorize a **small, separately reviewed client change**—not broad Wardrobe enablement—and require offline decode/repack tests plus normal client menu/inventory regressions.

Related research: [POL1 feasibility PR #1303](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1303), [2019 Binary Inspector research](../workbench/CLIENT_BINARY_RESEARCH.md), [capacity audit](../workbench/CLIENT_WARDROBE_CAPACITY_AUDIT.md), [2021/2026 expansion comparison](wardrobe5-8_container_expansion_research_plan.md).
