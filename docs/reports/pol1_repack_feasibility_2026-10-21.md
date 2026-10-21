# POL1 repacking feasibility — experimental code path (2026-10-21)

**Status:** Nine focused synthetic tests (including 191 independently decoded randomized streams) and the original POL1 unpack fixture passed in GitHub Actions on commit `e2b398a917ce135826562e521fe6fe6e9e6517cc` (POL1 Repack Synthetic workflow run `39629832243`). **Retail repack loadability and packed-size fit UNKNOWN.** This is an experimental, read-only research workstream, not a production client patcher.

**Related:** [FFXI Client Patch Feasibility Audit (draft PR #1301)](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1301), [Wardrobe 5–8 research plan](wardrobe5-8_container_expansion_research_plan.md), and local handoffs HANDOFF_wardrobe5-8_decode.md / XREF_SUMMARY.md.

## 1. Which packing path?

The least-disruptive candidate is **same-size decoded-code edit → POL1 recompress → compare against original consumed POL1 stream capacity → replace only POL1 payload in an independent copy**. Only in-memory encoding, fitting, and a re-decode check are implemented; no replacement-on-disk function exists.

The experimental encoder operates on decoded bytes using the format understood by the existing decoder:

- 8 tokens per control byte, most-significant-bit first; 1 means literal, 0 means two-byte back-reference.
- 12-bit backward distance 1–4095; 4-bit match length encoded as length minus 3 (3–18).
- Bounded greedy matching, 64-candidate cap, 8 MiB decoded-code input limit.
- Original retail compressed bytes are not reproduced; different LZSS token streams may decode to identical output.
- A byte-capacity match is necessary but insufficient; POL1 loader initialization, integrity checks and launcher policies are unverified.

The alternative "unpack into a normal PE with a newly populated raw .text" can require section realignment, entry point, import/relocation, memory protection and loader changes. Historical FFXI unpacker research addresses analysis copies, not a proven retail-compatible repack.

External technical background (not verification for our clients): [FFXI POL1 unpacking discussion](https://atom0s.wordpress.com/2015/01/02/unpacking-ffxi-related-files/).

## 2. Reference geometry from prior research

| DLL revision | Decoded .text bytes | POL1 raw bytes | Ratio |
|---|---:|---:|---:|
| 30210706_0 | 3,272,270 | 1,967,464 | ~60% |
| 30261006_0 | 3,307,054 | 1,989,368 | ~60% |

These numbers were previously recorded in the Toolkit's retail fetch and binary comparison report; these DLLs were **not** accessed in this experiment.

A candidate compressed stream exceeding the original consumed stream is an in-place **STOP**, even when the overall POL1 raw section has apparently free bytes. A stream that fits this stricter boundary is **not** proof of successful loading.


## 2a. Critical correction: POL1 contains loader/bootstrap bytes

A decoded-code RVA **is not** a physical on-disk address. The earlier proof of concept mistakenly treated the entire raw POL1 section as available compressed stream space and zeroed the remainder in a *temporary in-memory image*. It never wrote a DLL, but its old "FITS_RAW_SECTION" status could have been misleading.

The PE entry point on the archived 2019 build maps **inside POL1**, near the end of the raw section (see docs/workbench/CLIENT_BINARY_RESEARCH.md). These bytes may belong to the bootstrap/unpacker code. Treating the entire section as overwriteable would risk destroying the loader.

**Correction implemented in this PR:**
- Independently measure the number of bytes actually consumed by the original LZSS stream before the expected .text output is complete.
- Restrict any candidate's budget to that original consumed stream prefix, not the full POL1 raw section size. When PE AddressOfEntryPoint maps into POL1, the candidate is also bounded by that location.
- If the original compressed stream overlaps the mapped entry-point offset, return UNSAFE_ORIGINAL_STREAM_BOUNDARY.
- Preserve all source bytes after the original compressed-stream boundary, including loader/suffix bytes, *even during in-memory verification*. Reject streams that only fit by consuming more of the section than the original stream.
- Report original_stream_consumed_bytes, protected_suffix_bytes, safe_stream_budget_bytes, entrypoint_section_offset, and protected_suffix_unchanged.

This **conservative budget** still does not establish that there are no additional loader bytes or pointers inside the original stream region, nor that the original loader accepts replacement compression. It simply removes one concrete false-positive/suffix-corruption hazard. Independently validating the retail loader and packed-stream termination remains required.

## 3. Implemented

- src/workbench/client/pol1_repack_experiment.py — in-memory encoder and read-only size report, full SHA-256s, headroom and candidate roundtrip validation, without disk writes.
- test_fixtures/test_client_pol1_repack_experiment.py — synthetic PE fixture, known-vector, overlap/history, random data, capacity overflow, malformed input and same-length modified-code tests.
- src/workbench/client/cli/pol1_repack_report.py — read-only CLI with mandatory full exact input SHA-256; no output file or patch mode.

For an **isolated research copy** of a licensed client, use the Toolkit environment, e.g.:

~~~powershell
py -3.11 -m workbench.client.cli.pol1_repack_report --expected-sha256 1ded20ac5df1b168220992365b63cfe7596af17326acf0e02f90a5a8388446ba C:\FFXI-Research\2021\FFXiMain.dll
py -3.11 -m workbench.client.cli.pol1_repack_report --expected-sha256 042884888eea4fadac183e520f2ae9f8c4fa267860e685048e1880efd358e872 C:\FFXI-Research\2026\FFXiMain.dll
~~~

This performs a read-only estimation, not a client edit. Before running, ensure these copies match the recorded hashes, that the Toolkit package is importable, and the input is not a live installation.

## 4. Verification and required evidence

**Verified:** GitHub Actions run `39629832243` passed the nine focused synthetic test methods and the existing original POL1 unpack fixture. Those methods include 191 deterministic randomized streams decoded by an independently implemented test oracle, input-hash rejection, loader-like suffix preservation, false raw-section-fit rejection and boundary-overlap refusal. Separately, a local exploratory 3.3 MB *synthetic* pattern round-tripped; neither check establishes retail-loader acceptance.

**Next gates:**

1. Completed on the cited code head: the new focused tests and original POL1 unpack fixture passed in the dedicated offline CI. Re-run if encoder/boundary code changes.
2. Run the read-only capacity report against archived *unchanged* 2021/2026 DLLs on Windows. Record candidate packed sizes and whether they fit the **original compressed-stream prefix** (not the whole POL1 raw section). If even unmodified decoded content fails to fit that consumed prefix, this greedy encoder is inadequate for in-place retail repacking.
3. Independently verify packed-stream decoding against a separate decoder or loader-equivalent fixture, including padding/termination.
4. Establish the original loader's consumption semantics, security directory/signature and launcher integrity behavior, without bypassing integrity controls.
5. If later authorized, any isolated copy patch must require exact hash and expected-byte checks, immutable source, independent destination, post-write PE verification and rollback. This write path is **not implemented**.

## 5. Wardrobe 5–8 remains separate

Repacking does not grow the old client's **13 inventory containers** into **18**. The older store, .data tables, handlers, menu, and equipment/network paths have structure-size assumptions. There is no evidence those would survive a code-only patch. **Do not deliver container IDs 13–16 to a 2019/2021 client.**

## Could not verify here

No original retail DLL bytes, Windows retail loader, client startup, Authenticode results, live packet capture or server data. Actual retail compressed-fit, load acceptance and Wardrobe 5–8 runtime functionality remain **UNKNOWN**.
