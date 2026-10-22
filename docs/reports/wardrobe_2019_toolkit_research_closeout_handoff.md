# December 2019 Wardrobe 5–8 client research: Toolkit closeout and future DSP handoff

**Date:** 2026-10-21  
**Current owner of research and reusable binary tooling:** `sarthax/FFXI-Mission-Toolkit`  
**Future implementation owner (when server work actually begins):** `sarthax/darkstar-to-valhalla` (DSP)  
**Cross-project acceptance:** `sarthax/xiheadless-dsp` when end-to-end tests become appropriate  
**Research PR:** [Toolkit #1312](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1312)  
**Compression tooling PR:** [Toolkit #1303](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1303)

## Scope and decision

The owner requested finishing the client research in **Mission Toolkit**. **Do not transfer source, open implementation issues, create branches, or change servers in DSP yet.** When implementation reaches the server workstream, use this document as the starting handoff rather than moving all exploratory commits. Retain reusable POL1/compression, exact-build inspection and synthetic fixtures in Toolkit; transfer design decisions, evidence references and only implementation-relevant code/tests to DSP by separately scoped, reviewed changes.

This research does **not** deliver a working Wardrobe 5–8 client. **Do not** enable new container IDs on the unmodified December 2019 client or install a Wardrobe expansion DLL based on the synthetic model.

## Binary identities and reproducibility

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| User-supplied original December 2019 `FFXiMain.dll` | 2,870,352 | `514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f` |
| Original POL1-decoded `.text` | 3,264,206 | `af2126c057d86559bfad2e164f7f7fd0a26bbc89ab29ea9cbde5cea807c7d2b8` |
| Stage 2 no-op repacked smoke-test DLL (outside GitHub) | 2,870,352 | `27636cc595280ad46a401cf2d0159a651b80c39d912f5748784944604a923d2c` |
| Stage 3 equivalent-instruction smoke-test DLL (outside GitHub) | 2,870,352 | `53e91099d0d773ccde227c53ad57986126d969751514b05e96d39210b6dc699c` |

No retail DLLs or decoded code bytes are checked into the Toolkit repository.

**Owner-observed limited Windows acceptance:** Stage 1 header timestamp-only change: game boot and map-server connection PASS. Stage 2 actual POL1 no-op repacking with explicit zero-distance stop: game boot and map-server connection PASS. Stage 3 one behavior-equivalent decoded instruction substitution `TEST EDI,EDI` → `OR EDI,EDI` followed by POL1 repack: game boot, map-server connection and basic menus PASS. These observations do not prove that Stage 3's instruction executed, exhaustive client compatibility, successful Wardrobe 5–8 behavior or long-duration stability. Confirm original DLL is restored and SHA-checked before any future runtime experiment; restoration **after Stage 3** was not separately confirmed in the research PR.

## Confirmed 2019 structures relevant to a backport

| Subsystem | Original-code evidence | Implementation consequence |
|---|---|---|
| Existing slash commands | `/wardrobe`.. `/wardrobe4` IDs **111–114** and 24-byte command records; separate 12-byte handler table | New slash commands require independent command registration and handler integration |
| Existing mode objects | Wardrobe 1→**8**, 2→**10**, 3→**11**, 4→**12** via constructor→vtable `+0x54` constant getters | Never derive mode from command ID or assume consecutive Wardrobe modes |
| Other occupied mode | `/bank2`, ID **115**, returns mode **9** through a distinct helper | Do **not** repurpose mode 9 |
| UI selection | At `0x1D4E8A`: `mode-2` switch on **11 cases, mode 2–12** | Proposed values 13–16 default; new dedicated mode and UI case handling required |
| Original UI-related pointers | **13 global pointers** `0x10621FBC..0x10621FEC`; selected update helper `0x212A00`; teardown/cleanup `0x212670`, free `0x3077A0` | New UI objects require reviewed allocation, updating, invalidation and teardown; these are not automatically inventory-record objects |
| Original inventory records | **13 containers × 81 slots × 44-byte records**, starting active-store `+0x9860` | Direct in-place 18-container growth collides with used memory |
| Immediately following fields | Legacy array ends at `+0x14D5C` where an **81-slot enumeration cursor**, then a pointer at `+0x14D60`, begin | Cannot append five containers by changing a loop bound |
| Active-store lifetime | Manager-selected pointer `0x104CDA08` and multiple assignment/clear sites; original store clear is **0x3B080 bytes** | Safe sidecar must be per-instance and handle switching, reset and teardown; complete allocator ownership still unknown |
| ITEM_MAX incoming 0x1C | **13 u8** capacities from packet `+0x04`; **13 u16** capacities from `+0x14` | Requires explicit per-client-version packet contract; do not send 18-container layout to 2019 |
| Item packet 0x1E/1F/20 | Container and slot fields directly index legacy records in selected handler entry blocks | Build real bounds checking and auditing of ingress/egress before enabling new IDs |
| Selected UI item helpers | Three observed `containerID < 13` guards and legacy capacity getter callers | Sidecar alone won't make new Wardrobes visible or usable |

The detailed **RVA-by-RVA evidence and qualifications** are in [Stage 4 technical report](ffximain_2019_wardrobe_backport_stage4.md). Newer 2026 client behavior is prior-build comparison evidence; do not transplant its constants into 2019 as if binary-compatible.

## EVB data-stream finding — keep separate from server persistence

The original code has **11 fixed-size `0x3B080` file-transfer-shaped calls**, six read-like and five write-like. A confirmed direct active-store read/write pair references `ZSU.evb`. Four other write-like wrappers reference `RCN%04d[%d].evb`, `REC.evb`, `RECN.evb`, `RECS.evb` and receive caller-supplied first-argument buffers. Other reads use stack-local buffers. **We do not know** whether any of these file workflows are authoritative server character-inventory persistence. Do not enlarge these transfers or make server schema decisions based only on the common byte count.

## Toolkit research artifacts and how to validate

The PR includes metadata-only modules:
- `src/workbench/client/wardrobe_2019_audit.py` and CLI `src/workbench/client/cli/wardrobe_2019_report.py`: SHA-256 gated aggregate static audit.
- `src/workbench/client/wardrobe_2019_command_ui.py`: slash-command records, handlers, original UI mode table, constructors/vtables and Bank2 mode.
- `src/workbench/client/wardrobe_2019_ui_objects.py`: selected 13 UI-global update and teardown instruction windows.
- `src/workbench/client/wardrobe_2019_packet_contract.py`: **offline-only** 2019 ITEM_MAX and item-record packet-shape guards.
- `src/workbench/client/wardrobe_2019_sidecar_model.py`: **hypothetical, metadata-only** ID 13–16 sidecar routing model; original 13-container array/cursor untouched. Four added Wardrobes require `4 × 81 × 44 = 14,256` **theoretical** bytes per simulated store. ID 17 is out of scope.

To validate the original DLL **outside CI**, from a checked-out research branch and with your own backed-up original on disk:

```powershell
$env:PYTHONPATH = "src"
py -3.11 -m workbench.client.cli.wardrobe_2019_report "C:\\path\\to\\original\\FFXiMain.dll"
```

The tool refuses to assert 2019-specific facts if the complete original DLL SHA-256 differs. The repo deliberately does not contain that DLL; GitHub CI exercises synthetic-only fixtures. Focused tests are in `test_fixtures/test_client_wardrobe_2019_*.py`, run on Windows and Ubuntu by `.github/workflows/client-2019-wardrobe-offline.yml`. CI success is **not** runtime acceptance.

## Explicit research exit criteria vs implementation gates

**Toolkit-side research can be considered documented** once the exact-build audit is independently reviewed against the original DLL, synthetic CI and broad Workbench CI pass on the reconciled head, the report and handoff remain consistent, and PR #1312 receives an authorized review/merge decision. It is reasonable to mark an unresolved finding `UNKNOWN` rather than inventing control flow.

**Deferred until the DSP implementation phase (not performed now):**
1. Reconcile DSP's specific inventory enums, character persistence, server inventory operations and client version policy against the exact DSP revision that will be modified.
2. Decide and verify an authenticated/trusted per-session client compatibility indicator before routing 13- versus 18-container packet formats.
3. Design a runtime-safe *per-store* extended allocation/sidecar; identify every legacy store/slot accessor and equipment, item move, packet, UI and snapshot consumer; define teardown and rollback.
4. Implement additional original-client command objects/mode entries and UI caches in a separate reviewed change with no reuse of mode 9.
5. Add XIHeadless synthetic and supervised real-client/server assertions; never send IDs 13–16 to an unmodified 2019 client.
6. Plan a narrowly scoped isolated local DLL trial with exact input/output fingerprints and rollback only after offline safety and integration gates pass.

## GitHub/reconciliation boundary

**Do not open new DSP branches/issues or copy this branch to DSP now.** Toolkit PR #1312 carries the verified research and reference implementations; PR #1303 carries POL1 work. The Toolkit research branch was diverged from `main` after concurrent R7 merges; preserve both histories. The files changed by incoming R7 commits showed no direct path overlap with the existing Wardrobe research paths when compared on 2026-10-21, but run an updated comparison and all required CI **after** a normal non-force reconciliation. No merge/review approval is implied by the owner's choice to finish research here first.

**Decision summary:** Finish and keep the client-side research in Toolkit. Transition **feature implementation ownership** to DSP **later, when server work actually begins**, with a narrow, evidence-backed handoff rather than wholesale transplantation of exploratory commits.
