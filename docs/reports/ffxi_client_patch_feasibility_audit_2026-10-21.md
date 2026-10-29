# FFXI client patch feasibility audit — 2026-10-21

**Status:** Initial read-only feasibility assessment; **NO-GO for any installed-client, live, or retail-code patch**. Conditional GO for isolated, offline *synthetic* patch-tool validation and further static research.

**Scope:** Assess whether targeted Windows PE EXE/DLL modifications can be made reproducibly without breaking the loader, pointers, file integrity, POL1 initialization, or item-container behavior. First use case is backporting Mog Wardrobes 5–8 from retail FFXiMain.dll **30261006_0** to **30210706_0** (and, separately, the user's archived 2019 client). No client execution, DLL modification, packet injection, server update, or release was performed in this audit.

## 1. Evidence boundary and provenance

This is a repository/code/document review, not a Windows runtime experiment. Source documents were reviewed on Toolkit `main`, including:

- `AGENTS.md` (read-only/live-client restrictions, evidence rules).
- `docs/reports/wardrobe5-8_container_expansion_research_plan.md`.
- `docs/workbench/CLIENT_WARDROBE_CAPACITY_AUDIT.md`.
- `docs/workbench/CLIENT_BINARY_RESEARCH.md`.
- `docs/workbench/RETAIL_FETCH_WINDOWS_VALIDATION.md`.
- `src/workbench/client/pol1_unpack.py`, `src/workbench/client/cli/pol1_compare.py`, `test_fixtures/test_client_pol1_unpack.py`.
- Local-only `HANDOFF_wardrobe5-8_decode.md` and `XREF_SUMMARY.md`; **not** committed as executable images.
- Microsoft's [PE specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) and [executable-file-signing guidance](https://learn.microsoft.com/en-us/windows/win32/secbp/understanding-pe-signatures) for generic PE behavior.

| Reference | Recorded original SHA-256 | Evidence |
|---|---|---|
| `FFXiMain.dll` 30210706_0 | `1ded20ac5df1b168220992365b63cfe7596af17326acf0e02f90a5a8388446ba` | Archived retail version retrieved and size/hash/PE validated in the downloader research |
| `FFXiMain.dll` 30261006_0 | `042884888eea4fadac183e520f2ae9f8c4fa267860e685048e1880efd358e872` | Same, newer version; POL1 decoded for read-only comparison |
| Archived 2019 `FFXiMain.dll` | `514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f` | Different, user-supplied historical build; **not interchangeable** with 2021 baseline |

A SHA-256 is an exact-build identifier. The downloader's legacy FileSig verification is **not** proof of Authenticode validity, launcher acceptance, or in-memory loadability. No EXE patch path has been demonstrated; `FFXi.dll` and `FFXiMain.dll` are different modules.

## 2. Confirmed facts vs unverified properties

**Verified from inspected source and documented prior static experiments:**

1. `pol1_unpack.unpack_pol1` is a bounded read-only LZSS decoder. It recovers decoded `.text` bytes and computes a SHA-256, but has **no reverse encoder, image writer, patch manifest, or load test**. Its test exercises a synthetic POL1 stream and corruption rejection; it is not a patched-retail-binary test.
2. The FFXI PE places code in a nonstandard POL1-packed section, with virtual `.text` not directly backed by its own ordinary raw code. Decoded-text RVAs must **not** be treated as file offsets or directly patched in the original file.
3. Static analysis of 2021 vs 2026 found different structures: **13 vs 18** inventory container objects/capacity entries; new cases for modes 13–16 and /recycle; enlarged store and changed offsets. The old item packet paths had no identified per-container bounds check. Treat old-client receipt of container IDs 13–16 as unsafe until proven otherwise.
4. The 2026 capacity packet (`0x1C`) reader uses 18 u16 values from packet offset `0x24` (minimum accessed span `0x48`); the 2021 reader uses 13 u16 values from `0x14`. This is a **static read layout**, not a verified live wire capture or proof of a fully valid packet.
5. New-client command handlers, 18 UI objects, and a zero-capacity menu gate have been traced; that does **not** establish that every outbound inventory operation, equipment path, or server accepts these containers.

**Unknown or not validated:**

- Whether the exact 2019, 2021, or 2026 retail PE has an embedded/catalog Authenticode signature, and what validation policy is enforced at launch.
- The actual launcher/POL integrity-check behavior; whether a modified client starts, updates, gets restored, or fails.
- Whether a decoded-POL1 edit can be packed back losslessly, or whether a safe runtime-only patch approach exists.
- The precise loader/unpacker initialization sequence, code/data mapping, relocation and memory-protection details needed for a runtime modification.
- Whether there is usable section slack / a code cave, whether the old data tables can be safely relocated, and whether every consumer is covered by the current xref analysis.
- The 2019-specific wardrobe handler/store structure and the 2021 old-build menu builder and table bounds.
- A live `0x1C` capture from a confirmed newer-client-compatible server and reliable per-session version/capability detection.
- Windows load/launch, crash-free behavior, and old/new container operation regression tests.

## 3. Patch-method feasibility matrix

| Candidate technique | General feasibility | FFXI evidence today | Decision |
|---|---|---|---|
| Same-length replacement in an existing, *proven* data field | Low structural PE impact: offsets, section sizes and RVAs can stay fixed | No harmless FFXI field was proven nonexecuted/unvalidated | **Research only**. No retail edit yet |
| Same-length instruction replacement | Possible without shifting subsequent RVAs but affects instruction semantics, branches and side effects | Instruction alignment verified in selected decoded windows, not a safe write-back route | **NO-GO** |
| Add code/data in existing slack or a new PE section | PE tooling can map a new section with appropriate alignment/headers; all dependencies still matter | POL1 boot/unpack mapping and section layout have not been validated post-write | **NO-GO** |
| Unpack, modify, repack POL1 | Would preserve a normal on-disk client deployment if independently validated | Only unpacking exists; no packed-stream round trip or loader proof | **BLOCKED** |
| Runtime hook/injection | May avoid changing original on-disk hash | No safe entry point, process-architecture compatibility, loader-timing or rollback proof | **NO-GO** |
| Server-only Wardrobe 5–8 support for 2026 client | Avoids patching proprietary client binaries | Server audit documents known enum/SQL/packet gaps | **Separate server workstream**, controlled branch only |

Neither a successful same-size write nor an unchanged section table proves safe runtime behavior. Moving file bytes, modifying image virtual addresses, changing pointer values, and increasing an object-size assumption are **different** failure modes; avoid collapsing them into one.

## 4. Concrete technical risks and how to test them

| ID | Hazard / assessment | Evidence required before claim can improve | Severity |
|---|---|---|---|
| F-01 | File hash changes for any content modification; whether this blocks the FFXI client is unknown. | Exact original and modified SHA-256, publisher-signature verification on the isolated Windows host, launcher outcome | High / unverified |
| F-02 | PE file offset, RVA, VA, alignment and relocation are distinct. Unmanaged file insertion can invalidate references, while a controlled equal-length write need not move them. | Before/after section, directory, import/export, entry point, relocation, SizeOfImage and raw/virtual mapping reports | High |
| F-03 | POL1 decoded code is not directly writable to the packed DLL. | Bounded encode/decode round trip on **synthetic** POL1 fixtures; decoded hash match and corruption detection | Blocking |
| F-04 | Even a structurally valid PE can fail POL1 loader initialization or launcher policy. | Licensed, isolated Windows test: unchanged baseline, modified-copy launch, logs, process outcome, rollback verification; do not bypass integrity checks | Blocking |
| F-05 | Old inventory storage is structurally too small for new IDs; older packet handlers lack identified bounds checks. | Proof of safe bounds/allocations and all old store xrefs before **any** packet IDs >=13 are delivered | Critical |
| F-06 | Menu/commands are only one part of a valid wardrobe backport. | Traces/tests for alloc/free, initialization, inventory load/save, equip, move, sort, trade, UI, capacity and container version-counter refresh | Critical |
| F-07 | New `0x1C` packet length/layout and version gating not observed in a live compatible session. | Real authorized capture + decoder independent of the static listing; server writer and session-version fixture tests | Blocking |
| F-08 | Client updates or manual replacement can overwrite/reject any patched file. | Clean restore from immutable baseline; isolated install update/restore test; no production update suppression | Medium-high |
| F-09 | Runtime modifications can affect separate processes using the same on-disk file on future launch or shared injected components. | Test installation isolation, explicit process/module inventory, no modification to system/global DLL paths | Medium-high |

Generic signing note: changing hashed PE code normally invalidates a matching embedded/catalog signature, if present. The PE checksum and Authenticode hash are **not interchangeable**; changing a PE checksum is not a means to make a modified signature valid.

## 5. Safe proof-of-concept sequence (do not skip gates)

1. **Inventory only (read-only; immediate):** On an isolated Windows workstation, capture original hash, PE architecture, section headers/size/offsets, security directory, WinTrust/AuthentiCode result, ASLR/DEP flags, exports/imports and entry point for each exact build. Record the installed launcher behavior with **unmodified** binaries. Do not treat absence of an embedded cert as proof that the launcher does not verify hashes.
2. **Synthetic patcher preflight:** Using an entirely synthetic PE fixture, prove exact-build hash preconditions, expected-byte check, same-length byte replacement, refusal on unknown hash/mismatch, independent output file, post-write structural reindexing, and byte-for-byte restoration. No retail bytes, no executable client.
3. **Synthetic POL1 round trip:** Make a tiny synthetic packed image, decode -> encode -> decode and assert identical decoded bytes, format bounds and fail-closed parsing. This does not establish compatibility with the actual retail POL1 loader.
4. **Archived-copy diagnostics (read-only first):** On local copies of the licensed DLL, gather candidate patches and xrefs, map all section/raw/virtual offsets, and identify one benign **data-only** candidate with established reachability/consumers. Do not select an arbitrary code byte or assume unused padding.
5. **Controlled offline launcher compatibility test:** Only after owner/local-operator approval, test an explicitly separated client installation with a reversible, candidate-specific modified copy, record process start/crash/restore behavior, and verify the untouched baseline restores cleanly. Do not defeat launcher, anti-cheat, authentication or signature mechanisms.
6. **Inventory protocol safety:** Confirm the modern `0x1C` wire layout and server version strategy first; test modern client + server changes separately. Do not send IDs 13–16 to the old client until the old-client memory/store safety case is independently proven.
7. **Backport go/no-go review:** Require full instruction/data-xref coverage for new 13–16 storage, UI, allocation, persistence and outbound operations, with unit, static, and isolated-client regression evidence. If not feasible, prefer the modern-client/server path or a server-backed bank alternative.

**Windows read-only baseline commands (examples, in a licensed isolated copy):**

~~~powershell
Get-FileHash -Algorithm SHA256 'C:\FFXI-Research\2021\FFXiMain.dll'
Get-AuthenticodeSignature 'C:\FFXI-Research\2021\FFXiMain.dll' | Format-List *
~~~

Never run these sample paths against an unspecified production installation. Record output from both builds with the baseline research metadata; results are not yet present in this audit.

## 6. Acceptance and decision

**GO now:** source review; exact-build evidence catalog; existing read-only PE/POL1 decoding; synthetic PE patch/rollback tests; synthetic POL1 round-trip research; isolated Windows baseline fingerprint and signing diagnostics.

**STOP/NO-GO now:** any direct write to a deployed DLL/EXE; runtime injection; a distribution-ready client patch; claim of working 2019/2021 Wardrobe 5–8; delivery of new inventory IDs to an unexpanded old client; bypass of executable integrity controls.

**Local acceptance checklist (not executed here):**
- [ ] Capture original hashes and signing outcome for 2019, 2021 and 2026 target binaries.
- [ ] Produce verified section/reloc/PE-directory snapshots including security directory and code/data mapping.
- [ ] Record untouched baseline launcher startup and login on isolated install.
- [ ] Pass synthetic equal-length write, unknown-version refusal and lossless rollback tests.
- [ ] Pass independent synthetic POL1 encode/decode round trip, or formally reject the repack approach.
- [ ] Document and independently review a bounded *data-only* candidate if one exists.
- [ ] Keep real client modification on hold pending separate explicit approval and regression plan.

### Recommended next slice

Build a **read-only patch-preflight report** (build fingerprint + PE safety metadata + integrity/signature status + feasibility reasons) reusing the existing Binary Inspector, and add **synthetic-only** patch-manifest/rollback tests. Do not add a write action to the GUI or touch retail executable bytes. In parallel, pursue modern-client `0x1C` packet capture and Valhalla inventory-entry validation.

### Could not verify here

No Windows client, live process, client DATs, binary originals, symbol files, launcher telemetry, signature results, or server capture is accessible to this GitHub-only audit. No execution, PE write, POL1 re-encoding, or Windows loader test was done. Any empirical claim about successful launch, compatibility, or runtime safety remains **UNKNOWN**.
