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

**Additional active-store pointer lifetime evidence:** After startup initializes the active pointer from the global buffer, function `0xF70F0` reads a pointer from a manager-indexed table (`0xF710A`) and assigns it to global `0x104CDA08` at `0xF7116`. Function `0xF7290` assigns a supplied pointer to the same global at `0xF7295`; `0xF9B3C` also restores that global from the manager pointer table. All four sites were confirmed by exact decoded instruction anchors. Thus **one fixed global address does not imply only one active store instance**. Complete ownership, lifetime, reuse, initialization/cleanup and concurrency behavior remain unknown; relocating only a single buffer is not a supported plan.

**Calculation:** The legacy array begins at active store `+0x9860` and occupies `13 * 81 * 44 = 46,332` bytes (`0xB4FC`), ending *exclusively* at **`+0x14D5C`**. This exactly coincides with the next state field. Five more 81×44-byte containers would require **17,820 additional bytes (`0x459C`)**, moving the end of an in-place 18-container array to `+0x192F8` and overlapping the known `+0x14D5C` and `+0x14D60` fields.

Therefore, **NO-GO for increasing the loop bound, packet capacities, or container count in place**. Even if the total global buffer could hold the extra 17,820 bytes, those bytes are currently assigned to unrelated state; the aggregate buffer's available capacity is not interchangeable with contiguous free item-record space. Potential solutions such as a separate allocation, an indirection layer, or full field relocation require auditing pointer identity, constructors/destructors, all callers, and performance before any design choice.

The new `inspect_2019_store_layout` function returns metadata-only layout evidence, budget arithmetic, and a **fail-closed overlap gate**. The evidence status becomes verified only if the exact source and decoded hashes and all selected static x86 anchors match. Synthetic tests assert the collision and decline to claim verification if the anchors fail.

## Per-instance clear, manager teardown and post-array inventory cursor

The original 2019 DLL was re-opened under SHA-256 gate on **2026-10-21**; independent `objdump` inspection and direct byte verification confirmed the following selected instruction sites. The work never altered or launched the source DLL.

| Observed path | Decoded .text RVA | Static instruction meaning |
|---|---|---|
| Manager slot initialized | `0xF6C01` | Writes an initial manager slot count **1** at global buffer base `+0x3B088`. |
| Manager slot selection | `0xF710A` | Retrieves the store pointer at `[manager + selected_index*4]` after comparing index to slot count at `+0x3B088`. |
| Per-instance clear | `0xF710D`, `0xF711E` | With the selected store as destination, `rep stosd` clears **0xEC20 DWORDs = 0x3B080 (241,792) bytes**. This is distinct from the **0x3EDF4-byte** initial global zero-clear. |
| Secondary initializer pointer selection | `0xF73E1`, `0xF740E` | Additional writes of a supplied store pointer to active-store global `0x104CDA08` during other state transitions. |
| Teardown enumerate active slots | `0xF6FF0` / `0xF7009` | Loops over the manager's counted slots, selects each store and calls cleanup routine `0xF7030`. |
| Conditional per-store cleanup | `0xF7030`, `0xF7050` | Checks pointer and activity byte at `[store+0xC]` before cleanup cascade; **not evidence of heap deallocation**. |
| Active-store pointer cleared | `0xF70D6`, `0xF6FE2` | Writes zero to active pointer during store teardown or global manager reset. |
| Post-inventory slot cursor | `0xE885E`, `0xE8881`, `0xE8890`, `0xE88A6`, `0xE88CC` | Uses fields at store `+0x14D5C` (counter) and `+0x14D60` (pointer into item records). Advances by **44 bytes**, checks counter against **0x51 = 81 slots**, and clears cursor pointer when exhausted. |

**Manager index guard is separate from container-ID safety:** The manager accessor at `0xF6EE0` masks its input index to 16 bits, compares it to the manager's count at `+0x3B088`, returns null for an out-of-range manager index, and otherwise returns a pointer from the manager's index table. These are exact disassembly/byte observations. This **does not validate inventory packet container IDs** (0x1E/1F/20), which use different address calculations. It shows the legacy client already has some bounds checks, but in a different subsystem.

**Strongest new constraint:** the state directly following the 13-container item array is a live inventory enumeration cursor, including a pointer into the legacy item array. Appending extra records would overwrite that cursor; relocating records independently would also require updating cursor creation/iteration and any other item-pointer holders. Moving just the global pointer is insufficient because the manager uses **indexed store instances**, and the per-instance reset actively initializes hundreds of thousands of bytes. The 241,792-byte clear is an observed per-store operation; it is *not* evidence of the allocator's minimum committed size for all possible instances.

An additional search for the active-store global's four-byte address found **1,046 raw byte-pattern occurrences** in the decoded code, many of which are clearly repeated load patterns; these are **candidate references, not 1,046 confirmed instructions or unique callers**. This underscores why a complete pointer-use and lifetime inventory is still necessary. A targeted cross-reference tool should independently decode these candidate sites rather than changing arbitrary byte matches.

The exact-build read-only audit now reports the manager slot count and selection sites, per-store clear size, shutdown reset/cleanup sites and inventory cursor offsets. It explicitly reports that the pointer-writer inventory, allocation size for every instance and object lifetime are **incomplete**, even when all static anchors match.

**Go/no-go:** Do not proceed with in-place expansion or relocating the item array yet. The next independent task should inventory all store-relative accessors and cursor consumers, inspect how additional manager slots are allocated and freed, and stage an in-memory hypothetical expansion model without changing any client or server packet.

## Additional store-global assignments and fixed-size transfer contracts

A targeted linear x86 disassembly plus separate direct original-byte checks found **15 apparent direct assignments** to the active-store global `0x104CDA08`, not merely the previously enumerated startup/manager writes. The newly inspected sites include `0x3FA7`, `0xF6D4D`, `0xF7694`, `0xF76ED`, and `0xF8A55`; existing sites occur around `0xF6BC6`, `0xF6C1C`, `0xF6C33`, `0xF6FE2`, `0xF70D6`, `0xF7116`, `0xF7295`, `0xF73E1`, `0xF740E`, `0xF9B3C`. Some set a store pointer while others clear or restore one. The linear disassembler emitted **1,045 candidate uses** of that global address in decoded code, vs **1,046 raw four-byte matches**; neither count establishes instruction-boundary correctness, function membership or 1,045 executed call sites. The exact observed bytes at all newly selected assignment anchors match the archived source. **Full control-flow and writer inventory remains unfinished**.

An independent search of the decoded executable for immediate DWORD `0x3B080` found exactly **eleven** fixed-size `push 0x3B080` instruction candidates, at RVAs `0x3FA1`, `0x40EC`, `0x418C`, `0x431B`, `0x43B9`, `0x445F`, `0x45B0`, `0x464D`, `0x46ED`, `0x478D`, `0x4818`. These sites fall in routines that appear to pass buffers and fixed counts to a common callee at `0x307CFF` (for example `0x3FA1` passes a buffer, `0x3B080`, count 1 and another pointer before calling that address). Nearby calls also pass smaller sizes like `0x1C` and `0x48`. The `0x3B080` constant **matches the full per-store clear footprint** from `0xF711E`. This is **strong evidence of fixed-size data transfer assumptions**, but whether the transfer is a persistent save format, debug snapshot, other file I/O or a wrapper remains **unconfirmed**. Do not enlarge that count or assume it is a container count.

**Read/write-like split verified statically:** Six `0x3B080` call sites (`0x3FA1`, `0x40EC`, `0x418C`, `0x431B`, `0x43B9`, `0x445F`) pass the buffer/count/stream arguments to `0x307CFF`. Five more (`0x45B0`, `0x464D`, `0x46ED`, `0x478D`, `0x4818`) call `0x307E16`. Disassembly at those two callee entrypoints shows both have four-argument wrappers invoking `0x30CA2D` before a core operation (`0x307D2E` for the first or `0x307E45` for the second), followed by `0x30CA7F`; this structure is consistent with **fread-like and fwrite-like** buffered stream operations. Both core helpers multiply size by element count. The file format, purpose, ownership and actual runtime execution are not established by this alone. **Do not treat the 241,792-byte footprint as a tunable serialization size until these call sites and downstream consumers are traced.**

These findings independently block any idea of extending the store array without reviewing both its consumers and the potential serialized/snapshotted representation. The read-only audit now includes candidate size sites and pointer assignments, while retaining explicit `False` for transfer semantics, complete writer enumeration and complete allocation/lifetime mapping. Synthetic tests check the bounded metadata and unknown classifications.

## Exact file-mode and EVB-adjacent string correlation (2026-10-21)

A fresh read-only inspection of the original verified PE's initialized `.data` section established four exact ASCII anchors:

| .data RVA | Observed literal | Evidence boundary |
|---|---|---|
| `0x3442D0` | `rb` | Explicit mode string passed to file-opening helper `0x307B5E` immediately before the fixed-size read-like calls |
| `0x34471C` | `wb` | Explicit mode string passed to the same file-opening helper immediately before the write-like calls |
| `0x34470C` | `ZSU.evb` | Nearby file-name literal |
| `0x344714` | `*.evb` | Nearby file-glob literal |

The exact decoded-code disassembly shows `push 0x3B080` followed by a four-argument call to `0x307CFF` (six read-like sites) or `0x307E16` (five write-like sites). The `rb` and `wb` mode strings at these call paths strengthen the file-transfer interpretation. However, the adjacent `.evb` strings are **not proven to be the specific files used by each of the eleven transfers**. The `.evb` extension and naming are not by themselves proof of inventory persistence; they may represent event files, snapshots, transient resources or something else.

**New reproducible tool:** `inspect_fixed_transfer_data_strings` confirms these four `.data` values by exact RVA, without emitting proprietary bytes; `inspect_2019_fixed_transfer_calls` independently scans bounded decoded code for the `push 0x3B080` instruction-shaped pattern followed within 18 bytes by a relative-call target. When run on the exact 2019 decoded original, the scanner found exactly **eleven** candidates, all associated with the expected six-read / five-write RVAs. The result is deliberately labeled *static byte candidates*: a pattern match cannot replace control-flow verification or prove a transfer was executed. Synthetic tests verify relative branch displacement, unexpected/unassociated immediate handling, wrong literals, and input-type/size rejections.

**Pointer arguments resolve into different classes:** Independent disassembly checked the destination/source argument pushed with each 241,792-byte transfer. At **read site `0x3FA1`**, a register also stored into active-store global `0x104CDA08` is passed directly; **write site `0x4818`** explicitly loads the active-store global before writing. The other five read-like sites (`0x40EC`, `0x418C`, `0x431B`, `0x43B9`, `0x445F`) pass **stack-local buffer addresses** computed via `lea`. The other four write-like sites (`0x45B0`, `0x464D`, `0x46ED`, `0x478D`) load their **caller-supplied first argument pointers** from stack slots. Function entry stack frames, call-site offsets and eight additional instruction anchors verify this parameter classification, but what those caller buffers contain or alias remains unresolved. Consequently, **nine of the eleven transfer sites cannot be described as directly transferring the current active-store pointer**. They may still refer to copies or related data; that needs a caller/dataflow audit.

**Specific EVB control-flow correlation:** The direct active-store **read-like** path pushes the `.data` address `0x1034470C` (`ZSU.evb`) at code RVA `0x3EE4`, opens with `rb` mode pushed at `0x3F8A`, and reads `0x3B080` bytes into EDI at `0x3FA1` (EDI is also assigned to the active-store global). The corresponding **write-like** path around `0x47D0` pushes the same `ZSU.evb` literal at `0x47E3`, opens with `wb` at `0x47FC`, and writes `0x3B080` bytes from the active-store pointer at `0x4818`. Exact original-source instruction bytes and relative stream-call destinations were checked read-only.

**Other four write-side EVB filenames resolved:** In four separate wrapper functions, source pointers are read from their **first function argument** after a fixed 0x104-byte stack-local allocation (the first wrapper saves an additional register). Their file-name argument is set from initialized `.data` literals:

| Fixed-size write site | Input pointer | `.evb` filename argument |
|---|---|---|
| `0x45B0` | First caller-supplied argument | `RCN%04d[%d].evb` (`.data` RVA `0x344720`) |
| `0x464D` | First caller-supplied argument | `REC.evb` (`0x344730`) |
| `0x46ED` | First caller-supplied argument | `RECN.evb` (`0x344738`) |
| `0x478D` | First caller-supplied argument | `RECS.evb` (`0x344744`) |

Static instruction evidence: filename pushes at RVAs `0x4579`, `0x4616`, `0x46B6`, `0x4756`; caller pointer loads at `0x45A6`, `0x4643`, `0x46E3`, `0x4783`. These are different named EVB file operations, *not four proven aliases of the active inventory store*. A separate caller tracing pass is required to identify the argument contents.
Filename construction includes helpers and branching; we have **not** recovered the final filesystem path, verified that these branches execute during normal gameplay, or established that the EVB format represents persistent character inventory. In particular, an `.evb` resource operation must not be equated with the server's character-inventory SQL storage without independent evidence.
**Interpretation change:** A fixed stream footprint is now evidenced, but we **cannot** assert this is the authoritative inventory save schema, that expanding item records requires enlarging these streams, or that copying the new client's packet fields will solve it. Before any changes to `0x3B080`, trace the source/destination pointers at each call site and verify the actual file or session-resource path. No client or server file was modified or executed in this research.

## Synthetic bounds oracle added

The Stage 4 module also provides a **pure offline address validator** for the original 13-container layout. For a container `c` and slot `s`, it returns `0x9860 + (c * 81 + s) * 44` **only** when `0 <= c <= 12` and `0 <= s <= 80`; every other value returns no address. Booleans and non-integer numeric values fail closed. This models the storage stride seen in the 2019 decoded code without dereferencing process memory.

`inspect_2019_item_packet_location` uses only the observed **static packet payload field offsets** (0x1E: container +0x08 / slot +0x09; 0x1F: +0x0A / +0x0B; 0x20: +0x0E / +0x0F). It refuses unsupported packet IDs, truncated buffers and container IDs 13–16/255 and slot 81/255. **This is a synthetic test oracle, not a live parser, not a packet filter and not a client modification.** No malformed packets were sent to the client or server. If handlers use additional packet framing or translations, those must be independently verified before applying this model.

## New design branch point: isolated sidecar for Wardrobes 5–8 (synthetic only)

The confirmed legacy memory collision means **an in-place 13→18 record-array expansion is rejected**. A safer conceptual alternative is to retain all 13 original container regions (IDs 0–12) at their untouched offsets and represent only new Wardrobes 5–8 (IDs 13–16) in a logically separate sidecar region. The original array stays at active-store offsets `0x9860..0x14D5B`, and the cursor at `+0x14D5C` / `+0x14D60` stays intact. The sidecar requires **4 × 81 × 44 = 14,256 bytes per store** *in this hypothetical model*. Container 17 (`/recycle` in 2026 research) is explicitly out of scope, and the real 2019 client still supports only the original 13 containers.

A new pure-Python **research-only** model, `workbench.client.wardrobe_2019_sidecar_model`, introduces synthetic manager-slot registration/activation/reset/retirement, monotonically increasing generation tokens, and a metadata-only address resolver. Only currently active, non-stale tokens can obtain offsets. The legacy path preserves exact original bounds; sidecar routing requires an explicit opt-in simulation flag and rejects IDs 17/18/255, slot 81+, invalid types, old generations, unregistered managers and stale references. The model never holds item records or bytes and never reads/writes client process memory, files, packets, or the DLL. Its default maximum manager-slot count is **an illustrative model bound**, not the observed client's allocator or manager-table capacity.

| Boundary | Synthetic design invariant | Real-client status |
|---|---|---|
| Legacy records | ID 0–12 route through store `+0x9860`, with slot 0–80 | Static offsets confirmed on exact 2019 DLL |
| New Wardrobes | ID 13–16 produce sidecar-relative offsets 0–14,255 only when simulated | **NOT IMPLEMENTED** |
| `/recycle` ID 17 | Rejected | Out of scope |
| Store switch/reset/teardown | A stale or inactive manager-generation token cannot resolve | Actual 2019 manager ownership and hookability **UNKNOWN** |
| Old inventory cursor | Original fields at `+0x14D5C`/`+0x14D60` preserved by design | Original code consumes cursor; confirmed |
| Packet 0x1C and item packets | No packets generated, received or parsed by this model | Protocol-safe routing **UNKNOWN** |
| Equipment/UI/save/restore | Not modelled | All **UNKNOWN** |

**Independent caller-search limitation:** A read-only scan of original decoded `.text` for direct x86 `CALL rel32` and near/short jump destinations equal to the four EVB write wrappers `0x4520`, `0x45F0`, `0x4690` and `0x4730` found **no direct references**. Searching literal VA pointers for those function entries in initialized `.data`, `.data1`, `.rdata` and the decoded `.text` also found no matches. This does **not** prove the helpers are unused: they may be reached through table-indexed, computed or other indirect dispatch, or addresses may require translation. Therefore their actual caller-provided contents remain **UNKNOWN**; do not treat the four EVB buffers as persistent inventory objects.

**Design acceptance still missing:** independent caller/CFG and store-owner lifetime mapping; a safe per-instance sidecar allocator/deallocator and every accessor hook; server-compatible 2019 versus 18-container packet 0x1C/0x1E–0x20 contracts; coherent cursor, equip, UI and item-moving semantics; field-safe serialization; regression testing and explicit user-authorized isolated-copy client trial. A synthetic sidecar design is a **research GO only**, not an installable patch or permission to send IDs 13–16 to the 2019 client.
## Stage 4 packet layout compatibility gate (synthetic-only)

An independent decode of the original December 2019 `FFXiMain.dll` confirmed packet **0x1C** handler RVA `0xE97C0` performs: `lea edx,[packet+4]`, copies **three DWORDs plus one byte** into the 13-byte table at active store `+0x152ED`, then `lea esi,[packet+0x14]` and copies **six DWORDs plus one WORD** into the 26-byte table at active store `+0x152FA`. The decoder uses bytes through input offset `0x2D` inclusive, for minimum handler read span `0x2E`. Bytes at packet offsets `0x11..0x13` are skipped by the handler and **not interpreted as an additional container table**. Item packet entry blocks `0x1E`, `0x1F`, `0x20` read location/slot at offsets `+0x08/+0x09`, `+0x0A/+0x0B`, `+0x0E/+0x0F` respectively and calculate legacy array addresses without an obvious `<13` check in those inspected blocks.

The prior [Wardrobe capacity audit](../workbench/CLIENT_WARDROBE_CAPACITY_AUDIT.md) establishes Valhalla's **52-byte (0x34)** existing 13-container ITEM_MAX packet (including the protocol header and rounding convention). This is a **server-source fixture length**—the 2019 client handler inspected here does not validate or require `0x34` in its body. The prior decoded October 2026 client analysis records **18 u8 capacities** sourced from packet `+0x04`, and **18 u16 capacities** sourced from packet `+0x24` through `0x47` (minimum `0x48` bytes). Those different layouts are not interchangeable.

A new `workbench.client.wardrobe_2019_packet_contract` module provides **offline-only** checks:

- `observe_2019_item_max_frame`: accepts *only* a caller-declared `0x1C` frame of exactly `0x34` bytes under the exact 2019 **DLL SHA-256**. It extracts 13 u8 and 13 u16 input values, expressly leaves `+0x11..+0x13` uninterpreted, and refuses unknown lengths, unknown builds and any purported modern-format frame. This is an intentionally narrow Valhalla fixture inspector, **not a production client parser** and **not verification of a real network capture**. The packet header identity is caller-declared, not cryptographically authenticated.
- `inspect_2019_legacy_item_frame`: extracts just the known location/slot fields of `0x1E/0x1F/0x20` using the existing bounded offline oracle; IDs 0–12 and slot 0–80 yield **metadata-only candidates**, while IDs 13–16, 17 and 255 or slot 81+ are denied. No existing sidecar simulation flag enables those IDs on the 2019 protocol.
- `describe_2019_vs_modern_capacity_contract`: separately reports the 2019 and prior-research modern layouts while explicitly marking the modern packet writer/parser, 2026 authoritative wire capture and per-session client-build negotiation **unimplemented/unverified**.

Seven new synthetic tests cover exact capacity offsets, deliberately nonzero skipped bytes, unverified frames of lengths `0x2E`, `0x48` and other sizes, wrong binary fingerprint, wrong packet IDs, malformed input, 13/16/255 container IDs, bad slot indexes and fail-closed modern-format gates. The CI path list now includes the new module and tests on both Windows and Linux.

**Important boundary:** `source_sha256` in this offline API is a *declared exact-build precondition*, not an authenticated login/session signal. Nothing here authorizes the server to infer client versions or transmit modern ITEM_MAX packets. Designing a real per-session compatibility signal and verifying its trust are prerequisites for live changes.
## Stage 4 container-aware UI helper gates (read-only 2019 x86)

Direct control-flow-aligned disassembly of the original exact-SHA December 2019 POL1-decoded `.text` found multiple capacity getter callers clustered in a client helper region near RVA `0x1E7F00..0x1E9200`. Three selected helpers have **explicit signed container-ID comparisons against `0x0D` (13)** immediately before they compute a record address and/or call the legacy capacity getter `0xE8C60`:

| Selected 2019 RVA | Instruction | Associated capacity getter call |
|---|---|---|
| `0x1E7FAC` | `cmp ebp,0x0D` followed by `jge` to failure/exit path | `0x1E7FDE` → `0xE8C60` |
| `0x1E830B` | `cmp ebp,0x0D` followed by `jge` to failure/exit path | `0x1E8343` → `0xE8C60` |
| `0x1E847E` | `cmp ecx,0x0D` followed by `jge` to failure/exit path | `0x1E8498` → `0xE8C60` |

An additional container-capacity use at `0x1E91C5` also calls `0xE8C60` during a capacity-iteration loop. Disassembly associates these functions with direct record-array computations and the `store + 0x9860` layout, so these are **container-aware UI/client helper paths**, not a claim that the *entire* 2019 Wardrobe menu builder or all window state transitions have been recovered. The bounded static observations nevertheless show that **simply adding a detached sidecar and sending capacities will not make IDs 13–16 pass these original helper guards**. A full UI integration needs safe, separately reviewed routing and mode/command/menu behavior rather than unconditional replacement of every `13` constant.

Seven additional short instruction anchors are included in the exact-client SHA-gated audit; `inspect_2019_container_ui_bounds` reports the three selected guards and four calls plus explicit `UNKNOWN` fields for the rest of the UI/control-flow graph. Two synthetic tests ensure the bound observations fail closed if verification cannot be established. No GUI interaction or modified executable was used for this audit.
## Stage 4 original 2019 Wardrobe slash-command → UI mode dispatch

**Source and method:** Independently decoded the SHA-256-verified archived December 2019 `FFXiMain.dll`, confirming the decoded `.text` fingerprint, and disassembled the exact function windows with x86 32-bit `objdump`. The source DLL, executable and game/server were not modified or executed. This is static, version-specific evidence, not a complete menu control-flow graph.

### Four command records and handlers

Each slash-command record is **24 bytes** (`name[16]`, command ID u16 at `+0x14`, flags u16 at `+0x16`). A separate 12-byte dispatch record is `{u32 commandID, u32 handlerVA, u32 flags}`. The original has:

| Name | ID | Name record `.data` RVA | Dispatch record `.data` RVA | Handler `.text` RVA | Mode-object global VA |
|---|---:|---|---|---|---|
| `/wardrobe` | 111 | `0x34B1B0` | `0x34C068` | `0x7CE80` | `0x1061E5D0` |
| `/wardrobe2` | 112 | `0x34B1C8` | `0x34C074` | `0x7CEA0` | `0x1061E5D4` |
| `/wardrobe3` | 113 | `0x34B1E0` | `0x34C080` | `0x7CEC0` | `0x1061E5D8` |
| `/wardrobe4` | 114 | `0x34B1F8` | `0x34C08C` | `0x7CEE0` | `0x1061E5DC` |

The four name records have flag word `0x51`; their dispatch-table flag DWORD is zero. Each handler loads its corresponding global mode-object pointer, pushes the zero option and that pointer, then directly calls **`0x1D1680`**. The preceding `0x7CE60` handler is `/case` (ID 110), *not* Wardrobe 1. **Neither new `/wardrobe5..8` command records nor handler table entries are present at these four original sites.** This doesn't establish that no other code implements related behavior.

### Shared helper, mode getter and eleven-case selector

The common helper `0x1D1680` performs several gating calls. Its success path at `0x1D16F0` loads the input mode-object pointer and global UI controller pointer `0x1061E588`, then calls **`0x1D4E70`**. The latter stores the object at `UIController+0x58`, calls the object's vtable getter **slot `+0x54`**, subtracts 2 from the returned mode, and performs an **unsigned comparison against 10**. Only resulting indexes 0–10 reach the 11-entry jump table at `0x1D4F64`. All other values branch to default target `0x1D4EFA`.

| Mode input | Jump-table entry RVA | UI pointer source global VA |
|---:|---|---|
| 2 | `0x1D4EB6` | `0x10621FC4` |
| 3 | `0x1D4EFA` | `0x10621FC0` (same target as default) |
| 4 | `0x1D4EC0` | `0x10621FCC` |
| 5 | `0x1D4EAB` | `0x10621FD0` |
| 6 | `0x1D4EA3` | `0x10621FD4` |
| 7 | `0x1D4E99` | `0x10621FD8` |
| 8 | `0x1D4EC8` | `0x10621FDC` |
| 9 | `0x1D4EF0` | `0x10621FEC` |
| 10 | `0x1D4ED3` | `0x10621FE0` |
| 11 | `0x1D4EDD` | `0x10621FE4` |
| 12 | `0x1D4EE5` | `0x10621FE8` |

The decoded original switch instructions at `0x1D4E8A` are `add eax,-2; cmp eax,10; ja default; jmp [eax*4+0x101D4F64]`. The branch is **unsigned**, so modes below 2 also take the default. Proposed modern modes **13–16 do not have dedicated switch cases** in this original routine and would follow its default if fed as mode integers. This does **not** prove the four existing `/wardrobe` command pointers evaluate to particular mode integers: that requires inspecting each mode object's construction and the vtable getter return value. Do not conflate command IDs 111–114 with UI mode IDs 2–12.

### New reproducible audit and negative tests

The read-only `workbench.client.wardrobe_2019_command_ui.inspect_2019_command_ui_dispatch` verifies all four `.data` name and handler records, matching per-handler object-global loads and `CALL rel32` targets, the common-helper forwarder, the UI vtable getter opcode, the exact selector and 11-entry jump table, and all eleven case pointer-global instructions. It returns **only scalar IDs/RVAs/booleans**, never original executable bytes. Its report is gated by the exact source DLL SHA-256 and decoded `.text` SHA-256 in the parent `audit_2019_wardrobe`; altered or unknown inputs are not promoted to supported build facts.

Six new synthetic negative/positive tests reject changed command IDs/names, misdirected handler pointers, altered helper call displacements, tampered mode getters/selectors and changed jump targets or globals. The dedicated cross-platform CI workflow has been extended to include the new source and test files.

**Remaining UI work:** Independently recover construction of `0x1061E5D0..DC` mode-object pointers, the old UI container-object pointer setup and teardown, all menu entry gates/labels and outgoing item/equipment operations. Only then assess whether separate-sidecar storage and safe versioned packets could be connected to a new UI mode. No installable Wardrobe DLL follows from this slice.
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
