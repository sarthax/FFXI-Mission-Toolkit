# 2019 FFXiMain.dll — Wardrobe 5–8 backport boundary audit

**Date:** 2026-10-21  
**Scope:** Original December 2019 client `FFXiMain.dll`, full-file SHA-256 `514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f`, 2,870,352 B; unpacked `.text` SHA-256 `af2126c057d86559bfad2e164f7f7fd0a26bbc89ab29ea9cbde5cea807c7d2b8`. All code addresses below are **RVAs** relative to image base `0x10000000`. The original is analyzed **read-only** outside GitHub. No proprietary binary or decoded executable is committed.

## Prior local acceptance (owner-observed)

1. PE COFF timestamp-only smoke test: game boots and connects to map server.
2. No-op lazy POL1 recompression, with explicit zero-distance terminator: game boots and connects to map server. Marker-inclusive compression headroom on exact original: **18,984 B**.
3. One-byte decoded instruction replacement (`TEST EDI,EDI` → `OR EDI,EDI`), recompressed with explicit marker: **game boots, connects to map server, menus usable**. The owner reported no errors.

These results are narrow smoke tests, not proof of comprehensive gameplay or Wardrobe support. **The owner has not yet reported restoring the exact original after Stage 3; require verified restoration before another installed-client experiment.**

## Exact 2019 code and data findings

The dedicated `workbench.client.wardrobe_2019_audit` helper checks this **exact source hash**, decodes the expected original `.text`, and checks bounded code motifs plus original command-table values. Its output contains metadata only, never executable bytes.

| Evidence | 2019 observation | Confidence |
|---|---|---|
| Global inventory store pointer used by code | `0x104CDA08` | Verified static operand |
| Raw store record base | `store+0x9860` | Verified at item-record handler RVA `0xE9940` |
| Indexed record layout | `81` slots/container × `44` bytes/slot = `0xDEC` bytes/container | Verified arithmetic in bounded handler window; interpretation inferred |
| Byte capacity accessor | `0xE8C60`, reads `store+0x152ED+container` | Verified static instruction operand |
| Word capacity accessor | `0xE8C80`, reads `store+0x152FA+2*container` | Verified static instruction operand |
| Capacity packet handler (0x1C) | `0xE97C0`, copies from packet `+0x04` to `store+0x152ED`, then from packet `+0x14` to `store+0x152FA` | Verified handler registration and bounded copy instructions |
| Packet 0x1E/0x1F record handlers | `0xE9800` / `0xE9860`; respective container and slot selectors feed `store+0x9860` | Verified registration and bounded indexing motifs; upstream safety UNKNOWN |
| Packet 0x20 item attribute handler | `0xE9940`, reads packet bytes `+0x0E` / `+0x0F` as container/slot selectors, indexes `store+0x9860` | Verified registration and bounded instructions; no local container guard visible in this window; **upstream safety unknown** |
| UI inventory mode dispatch candidate | `0x1D4CA0`: compares `(mode - 2)` with `0x0A`, dispatch table `0x101D4DF8` | Verified instruction operands, inferred 11-case mode range **2–12** |
| UI inventory cache dispatch candidate | `0x1D4E80`: likewise compares `(mode - 2)` with `0x0A`, dispatch table `0x101D4F64` | Verified instruction operands, inferred 11-case mode range **2–12** |

**Packet registration now independently verified:** original 2019 decoded function at RVA `0xE85D0` registers a handler VA and packet ID with adjacent `push imm32; push imm8` pairs. These establish `0x1C → 0xE97C0`, `0x1E → 0xE9800`, `0x1F → 0xE9860`, `0x20 → 0xE9940`, `0x1D → 0xE99D0`, and `0x26 → 0xE9A10`. The earlier tentative use of `0x1F` to describe function `0xE9940` was incorrect; it is registered as **0x20**. Handler registration is verified static code evidence, but actual runtime invocation and upstream bounds remain unverified.

### Hard memory-layout collision if container 13 is simply enabled

For a hypothetical 14th container (ID 13) with the same record layout:

- Its first record would begin at `0x9860 + (13 × 81 × 44) = 0x14D5C` relative to the inventory store.
- Its 81-slot range would be `[0x14D5C, 0x15B48)`.
- Existing observed inventory state is referenced at `store+0x14F78`, which falls **inside** that range.
- The existing 13-entry u8 capacity table `[0x152ED, 0x152FA)` and 13-entry u16 table `[0x152FA, 0x15314)` **also lie inside** that range.

Thus expanding a numeric container limit or sending container ID 13 directly to the original record indexing is **NOT SAFE**. The record range would alias active unrelated store state. The physical store allocation and every referencing callsite must be understood and changed together; compression headroom does not provide that storage.

### Original 2019 slash commands have conflicting IDs

Command table records are 24 bytes in original `.data`, with the name in the first 16 bytes and command ID at `+0x14`. The exact 2019 original has:

| Command | ID |
|---|---:|
| `/wardrobe` | 111 |
| `/wardrobe2` | 112 |
| `/wardrobe3` | 113 |
| `/wardrobe4` | 114 |
| `/sendpost` | 118 |
| `/layout` | 119 |
| `/remodel` | 120 |

The 2026 command table assigns IDs **118–121** to Wardrobes 5–8 (see `wardrobe5-8_container_expansion_research_plan.md`); the 2019 meanings of IDs 118–120 are already occupied. **Do not copy the modern command identifiers** into the legacy dispatcher without a separate allocation and complete dispatch review.

## Reproduction

Run locally against an **untouched** archival copy, not a modified or installed DLL:

```powershell
$env:PYTHONPATH="src"
py -3.11 -m workbench.client.cli.wardrobe_2019_report "C:\path\to\original-2019\FFXiMain.dll"
```

The command rejects any file whose entire SHA-256 differs from the exact 2019 original; it never writes a DLL, modifies a packet, or accesses the game/server. The accompanying synthetic test suite covers the overlap calculations, command semantics, fingerprint-failure rejection, and inspection bounds, without bundling actual game code.

## Stage 4 decision and engineering gates

**Current decision: GO for detailed static research; NO-GO for enabling new containers or sending new inventory packets to the old client.**

Before proposing the first functional Wardrobe patch:

1. **Inventory allocation safety:** Map the 2019 record-store allocation, initialization, consumers of `store+0x9860`, capacities, and other fields through the full lifetime. Choose a design that preserves all existing data and supports 18 containers; do not enlarge in place across unrelated fields.
2. **Network safety:** Use the now verified 2019 `0x1C/0x1E/0x1F/0x20` handler registration to map full callers and packet wire bounds. Add fail-closed validation for container IDs and slots before writing. Verify modern versus legacy `0x1C` packet lengths and all affected server paths separately.
3. **UI safety:** Map both 11-case inventory mode dispatch tables, associated container-object globals, constructors/destructors, handlers, and command-table/translation resources. A capacity-only edit will not create valid new menu branches.
4. **Server compatibility:** The DSP/Valhalla source documented in `CLIENT_WARDROBE_CAPACITY_AUDIT.md` currently only supports containers 0–12 across enum, storage objects, SQL persistence and packet `0x1C`. Do not send 13–16 until the server and specific client can negotiate a verified compatible protocol.
5. **Validation:** Prove bounds via synthetic tests before isolated client trials. Keep backup/restore, exact file hashes, original loader/layout, and rollback procedures. Never exercise new IDs on the unmodified 2019 client.

Stage 3's single-instruction boot success establishes that the **pack-edit-repack** pipeline is viable, but it does not make the above memory, packet, and UI changes safe.
