# POL1 repacking feasibility — experimental code path (2026-10-21)

**Status:** The local operator verified both exact-build archives and found **GO for compressed-stream size feasibility** using bounded lazy depth 256 (+18,979 B 2021; +19,168 B 2026) on the `e6f0189` code head; every fitting candidate passed in-memory decoded round-trip and protected suffix preservation. The owner forwarded these local results, which have not been independently replayed in the GitHub-only session. **Retail loader, launcher integrity, and Wardrobe 5–8 support remain UNKNOWN and unapproved.** This is an experimental, read-only research workstream, not a production client patcher.

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

| DLL revision | Decoded .text bytes | Prior recorded POL1 section virtual size | Locally measured POL1 raw size | Original compressed stream consumed |
|---|---:|---:|---:|---:|
| 30210706_0 | 3,272,270 | 1,967,464 | 1,967,616 | 1,967,230 |
| 30261006_0 | 3,307,054 | 1,989,368 | 1,989,632 | 1,989,125 |

The decoded and virtual-size columns came from the prior Toolkit binary comparison; the raw-size and consumed-stream columns were forwarded from the local operator's verified read-only runs. Virtual versus raw section sizing explains differences of 152 bytes (2021) and 264 bytes (2026); independently reconfirm the PE section header fields if these sizes are later used in a writer. No retail DLL bytes were uploaded into the GitHub branch.

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

**Verified:** GitHub Actions run `39631931548` passed the 12 focused synthetic test methods and the existing original POL1 unpack fixture on both `ubuntu-latest` and `windows-latest`. Those methods include 191 deterministic randomized streams decoded by an independently implemented test oracle, input-hash rejection, loader-like suffix preservation, false raw-section-fit rejection and boundary-overlap refusal. Separately, a local exploratory 3.3 MB *synthetic* pattern round-tripped; neither check establishes retail-loader acceptance.

**Next gates:**

1. Completed on the cited code head: the new focused tests and original POL1 unpack fixture passed on both Windows and Linux in the dedicated offline CI. Re-run if encoder/boundary code changes.
2. Run the read-only capacity report against archived *unchanged* 2021/2026 DLLs on Windows. Record candidate packed sizes and whether they fit the **original compressed-stream prefix** (not the whole POL1 raw section). If even unmodified decoded content fails to fit that consumed prefix, this greedy encoder is inadequate for in-place retail repacking.
3. Independently verify packed-stream decoding against a separate decoder or loader-equivalent fixture, including padding/termination.
4. Establish the original loader's consumption semantics, security directory/signature and launcher integrity behavior, without bypassing integrity controls.
5. If later authorized, any isolated copy patch must require exact hash and expected-byte checks, immutable source, independent destination, post-write PE verification and rollback. This write path is **not implemented**.

## 5. Wardrobe 5–8 remains separate

Repacking does not grow the old client's **13 inventory containers** into **18**. The older store, .data tables, handlers, menu, and equipment/network paths have structure-size assumptions. There is no evidence those would survive a code-only patch. **Do not deliver container IDs 13–16 to a 2019/2021 client.**

## Could not verify here

No original retail DLL bytes, Windows retail loader, client startup, Authenticode results, live packet capture or server data. Actual retail compressed-fit, load acceptance and Wardrobe 5–8 runtime functionality remain **UNKNOWN**.

## 6. Offline hardening and compression sensitivity (2026-10-21 follow-up)

Subsequent source review added two **fail-closed** defenses to the in-memory feasibility check:

- The prefix-consumption counter now rejects zero-distance back-references immediately, truncated tokens and invalid backward distances. The older decoder tolerated a zero-distance token as a token-group terminator; the feasibility assessor intentionally rejects such ambiguous streams instead of assigning a writeable prefix. A **retail rejection may indicate a valid format variant**, rather than proving the DLL is corrupted: inspect the original loader before loosening this gate.
- The mapped PE entry point is now read only after validating DOS/PE signatures and the optional-header magic (PE32 or PE32+). Synthetic tests exercise malformed source images.

The encoder now supports three **bounded greedy match-search depths**: 16 (faster), 64 (default) and 128 (potentially smaller but more work). None guarantees a better compression ratio than another: greedy choice is not monotonic. These are research comparisons only. The full SHA-256 must match before any attempt to decompress or compare.

**Local read-only sensitivity examples:**

~~~powershell
$old = 'C:\FFXI-Research\2021\FFXiMain.dll'
$sha = '1ded20ac5df1b168220992365b63cfe7596af17326acf0e02f90a5a8388446ba'
py -3.11 -m workbench.client.cli.pol1_repack_report $old --expected-sha256 $sha --search-depth 16
py -3.11 -m workbench.client.cli.pol1_repack_report $old --expected-sha256 $sha --search-depth 64
py -3.11 -m workbench.client.cli.pol1_repack_report $old --expected-sha256 $sha --search-depth 128
~~~

Record original_stream_consumed_bytes, entrypoint_section_offset, safe_stream_budget_bytes, candidate_encoded_size, headroom_bytes, encoder_search_depth, status and in_memory_decoded_roundtrip. Compare the candidate against **the original stream prefix**, never the whole POL1 section. No output DLL is written.

**Evidence status:** The earlier nine-method suite passed on the referenced commit. A later suite added zero-distance and PE rejection plus configurable-search-depth regression tests; all 12 focused synthetic tests passed on Windows and Linux in run `39631931548`. Broader Workbench regression on that commit was still pending when last checked; full repository CI acceptance should be confirmed separately. The client originals remain unexamined here and loader/launcher acceptance remains UNKNOWN.

## 7. Consolidated read-only comparison and PE section-boundary validation

PR #1303 now offers a single hash-verified `--compare-depths` CLI invocation to measure all three bounded encoders on the same isolated input DLL. The JSON output reports original-stream consumption and protected suffix once, then emits depth 16, 64 and 128 candidate compressed sizes and headroom. `best_fit_depth` means the smallest qualifying compressed stream, **not** a recommendation to patch a retail DLL.

The preflight explicitly rejects POL1 raw on-disk data overlapping the PE section table, any other section's raw content, or data outside the input file. It validates entry-point metadata before decoding. This is a structural risk filter, not loader compatibility testing.

**Run separately against exact-hash archives, never installed clients:**

~~~powershell
$old = 'C:\FFXI-Research\2021\FFXiMain.dll'
$new = 'C:\FFXI-Research\2026\FFXiMain.dll'
$oldSha = '1ded20ac5df1b168220992365b63cfe7596af17326acf0e02f90a5a8388446ba'
$newSha = '042884888eea4fadac183e520f2ae9f8c4fa267860e685048e1880efd358e872'
py -3.11 -m workbench.client.cli.pol1_repack_report $old --expected-sha256 $oldSha --compare-depths
py -3.11 -m workbench.client.cli.pol1_repack_report $new --expected-sha256 $newSha --compare-depths
~~~

The CLI prints metadata/hash fields to stdout only, never executable bytes. Do not modify files, execute a patched client, or apply hooks on the strength of a compression-only result.

| Result | Meaning | Decision |
|---|---|---|
| `FITS_ORIGINAL_STREAM_BUDGET` | Candidate fits the originally consumed compressed prefix; in-memory suffix and decoded check pass | Research candidate only. Loader acceptance UNKNOWN |
| `EXCEEDS_ORIGINAL_STREAM_BUDGET` | Candidate exceeds the original consumed compressed prefix | NO-GO for fixed-prefix replacement at this depth |
| `UNSAFE_ORIGINAL_STREAM_BOUNDARY` | Compressed stream meets/overlaps mapped entry point | STOP: overlap with potential loader |
| Hash, PE or stream parse error | Exact build, layout or token assumptions fail | STOP and investigate; no write-back |

The output also exposes `pol1_raw_section_isolated`, `entrypoint_in_pol1`, and `entrypoint_boundary_safe`. An entry point outside POL1 may be legitimate for other PEs; it does not prove FFXI bootstrap boundaries.

**CI provenance:** Dedicated Windows and Linux POL1 tests passed with 12 methods at commit `6837500c110e94968d3243c002d5888fe4a4c833`. The subsequent all-depth comparison and raw-section isolation changes brought the focused suite to **14 synthetic methods**; Windows and Linux jobs both passed in POL1 run `39644369389` at code commit `c52905a2f1bbaa7f5742455d3ec4f69944f9a230`. The broad Workbench regression for that commit was still in progress at the time of verification. Earlier broad Workbench runs may be canceled on superseded commits; do not mistake them for completed approvals.

The original 2021/2026 DLL bytes remain unavailable to this GitHub session. Original consumed-stream lengths and NO-FIT results at depths 16/64/128 were recorded from the local operator; stronger compressor fit and loader acceptance remain UNKNOWN.

## 8. Exact-build local evidence and deeper compression follow-up (2026-10-21)

**Evidence status:** owner forwarded output from a local agent working with exact SHA-256-verified 2021 `30210706_0` and 2026 `30261006_0` files at Toolkit code commit `e9be7fb`. The agent confirmed no modifications to DLLs or repo; elapsed time ~11.8s and 13.1s on Linux/Python 3.13; these are reported observations and were posted verbatim to PR #1303. This GitHub-only session has not independently rerun the archives.

| Metric | 2021 | 2026 |
|---|---:|---:|
| Original stream consumed | 1,967,230 | 1,989,125 |
| POL1 raw suffix protected | 386 | 507 |
| Entry-point offset in POL1 | 1,967,232 | 1,989,136 |
| Depth 16 candidate / headroom | 1,980,554 / −13,324 | 2,002,606 / −13,481 |
| Depth 64 candidate / headroom | 1,969,588 / −2,358 | 1,991,495 / −2,370 |
| Depth 128 candidate / headroom | 1,967,927 / **−697** | 1,989,800 / **−675** |

**Current decision: NO-GO** for the existing depth-16/64/128 greedy compressor and for DLL write-back. No candidate fit the original consumed stream; in-memory candidate verification was consequently not attempted on those retail binaries. Decoded hashes reportedly agreed with earlier `pol1_report` JSONs.

### New bounded compression experiment

The Python encoder now supports `--search-depth` values `16`, `64`, `128`, `256`, `512`, and `1024`, plus optional `--lazy-match` with a single-byte lookahead. These alternatives are not guaranteed to improve size or runtime. The CLI preserves the prior baseline `--compare-depths` mode and adds `--compare-improved`, evaluating **five** configurations: greedy 256/512/1024 and lazy 128/256. Each candidate still goes through original-stream, PE-overlap, entry-point, and protected-suffix checks. No DLL write-back exists.

**Local read-only follow-up** (use the two previously verified archive paths; run each build separately):

~~~powershell
py -3.11 -m workbench.client.cli.pol1_repack_report $old --expected-sha256 1ded20ac5df1b168220992365b63cfe7596af17326acf0e02f90a5a8388446ba --compare-improved
py -3.11 -m workbench.client.cli.pol1_repack_report $new --expected-sha256 042884888eea4fadac183e520f2ae9f8c4fa267860e685048e1880efd358e872 --compare-improved
~~~

Run this on the newer PR head only after checking its CI. These deeper searches can be materially slower; record wall time and memory use when possible, and distinguish `FITS_ORIGINAL_STREAM_BUDGET` from actually validated loader acceptance. A first fit is **GO for subsequent independent loader research only**, not authorization to patch or install a retail DLL.

**Next gate:** if no configuration fits, investigate bounded two-step parsing, match-cost-aware parsing or byte-size optimization as a separate testable encoder algorithm. Do not take space from the loader suffix, enlarge sections, or bypass integrity controls merely to recover the missing ~700 bytes.

## 9. Owner-forwarded improved-compressor acceptance and independent stream identity check

**Local operator finding (2026-10-21):** Tested head `e6f0189763b37c63a9757dcbc6788c3dfe64acb1` on the same exact-SHA `30210706_0` and `30261006_0` DLLs. Seventeen focused synthetic methods passed locally. Runs took approximately 32 seconds each; the original DLL hashes were unchanged. In-memory round-trip and protected-suffix preservation passed for every fitting candidate. Original source files were never written or executed. These results were provided by the user from the local agent and posted to PR #1303; the original retail bytes were not uploaded to GitHub.

| Encoder | 2021 candidate / headroom | 2026 candidate / headroom |
|---|---:|---:|
| Greedy 256 | 1,967,353 / −123 | 1,989,242 / −117 |
| Greedy 512 | 1,967,236 / −6 | 1,989,131 / −6 |
| Greedy 1024 | 1,967,230 / **0** | 1,989,125 / **0** |
| Lazy 128 | 1,948,764 / **+18,466** | 1,970,465 / **+18,660** |
| Lazy 256 | **1,948,251 / +18,979** | **1,969,957 / +19,168** |

**Decision:** GO for compressed-stream **byte-capacity** feasibility on both original builds. The earlier NO-GO for baseline greedy depths 16/64/128 remains historically accurate. A candidate that fits is **not** authorization for a DLL write-back, load/launcher test, or Wardrobe 5–8 activation. The entry-point/startup loader's stream-consumption rules, termination/padding assumptions, PE security directory and launcher policy remain unverified.

**Forced-update note:** the agent's Git client reported a forced remote-tracking update. GitHub's exact two-SHA compare of `e9be7fb16d91e2dde6ce6f838e97476d0cb6a30a` to `e6f0189763b37c63a9757dcbc6788c3dfe64acb1` shows a fast-forward (`ahead_by=5`, `behind_by=0`, matching merge base). A different ref transition may explain the local warning; these two specific commits do not demonstrate a force push. Preserve shared-branch no-force rules.

**Further read-only inspection added after local run:** the assessor now records `original_stream_sha256`, `candidate_sha256`, `candidate_matches_original_stream`, and `candidate_common_prefix_bytes`. It also independently measures candidate stream consumption before accepting an in-memory round-trip. The aggregate CLI reports hash/equality evidence for each configuration, without revealing packed or decoded proprietary bytes. The intent is to check whether greedy depth 1024 equals the original stream *byte for byte*, not merely in length.

On the next local audit, rerun `--compare-improved` using the same exact-SHA copies and preserve the two new equality fields for greedy depth 1024 and lazy depth 256. Byte equality would strengthen format/tokenization evidence but is **not sufficient** to prove the original loader accepts a modified stream. The writer path remains intentionally absent.

## 10. Byte-identical originals and decoder-observed termination (2026-10-21)

The owner forwarded a third read-only local validation at branch head `372c7b48f85f450a56a5dc677ed6624d1d0ef265`. The local agent verified original full-file SHA-256 fingerprints for both `30210706_0` and `30261006_0`, reported **18 synthetic methods passing**, and established **byte-for-byte equality of the entire original compressed stream with greedy depth 1024** on both builds. For 2021 the compared stream spans 1,967,230 bytes (packed SHA-256 shortened `9bdbb3f9…1106`), and for 2026 1,989,125 bytes (`3156a211…2a43`). Common-prefix lengths equal the respective stream lengths. The locally generated lazy depth-256 variants are **not byte-identical** to those originals; matching prefix lengths were 627 / 628 bytes, candidate sizes 1,948,251 / 1,969,957 bytes, and headroom +18,979 / +19,168 bytes.

All fitting streams reportedly passed the Toolkit's in-memory decoder round-trip, with the original 386-byte (2021) and 507-byte (2026) raw POL1 suffixes unchanged. This result strengthens confidence that the *particular original streams* follow the documented token grammar and greedy parser choice at depth 1024. It is **not evidence that a different retail stream is accepted by the actual loader**. The local agent's complete hash values exist in its out-of-repository scratchpad comment file; only abbreviated packed hashes were passed into this GitHub session and must not be reconstructed or guessed.

GitHub confirms the `e6f0189` to `372c7b4` transition is a four-commit fast-forward, and all three corresponding workflows passed. No force-push is supported by that specific commit relationship.

### New read-only decoder-observed terminal-group check

The experimental reporter now records **scalar metadata only** for the final decoded token in the original and candidate streams:

- Number of consumed compressed bytes, control groups and tokens.
- Number of tokens consumed from the final eight-flag group, remaining unused flag bits, and whether any unused flags were nonzero.
- Final token kind (literal/backreference), its nominal output byte count, actual bounded decoder output byte count, and whether the bounded decoder clipped the final match at the expected decoded `.text` limit.
- For a POL1-mapped entry point, the byte distance between the decoded stream's consumed end and the entry-point section offset.

These figures are from our **read-only software decoder**, which stops at the declared `.text` virtual size and ignores unused control bits in its final group. They do **not** describe actual retail-loader execution semantics. In particular, a shorter candidate may cause the loader to encounter old residual bytes unless the loader independently stops after producing the expected decoded byte count; *we have not verified that it does*. The tool does not clear residual bytes, relocate the loader, install a client, or write any DLL.

### Next local measurement

After the new focused CI is green, rerun both exact-hash verified archives using the same `--compare-improved` command. Record `original_decoder_termination` and each `candidate_decoder_termination` (especially greedy depth 1024 and lazy depth 256), plus `bytes_between_stream_end_and_entrypoint`. Preserve only JSON metadata; no raw bytes, assembler dumps, proprietary binary contents or modified DLLs in Git.

**Next evidence review before any write-path authorization:** independently inspect the authentic POL1 entry-point bootstrap in the exact builds (read-only disassembly) to determine its actual input-consumption stop condition, whether it uses expected decoded length or an explicit marker, and what instructions/data occupy the protected suffix. Document how PE security directory, Authenticode status and launcher verification might treat a modified copy **without bypassing checks**. If the loader's true behavior is not established, remain STOP for any on-disk writer and for old-client Wardrobe 5–8 IDs.

## 11. Exact owner-supplied 2019 DLL: compression fit and genuine stop marker

**Scope and provenance (2026-10-21):** The owner uploaded their original archived December 2019 `FFXiMain.dll` as an isolated research input, **SHA-256 `514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f`, 2,870,352 bytes**. Its `.text` decoded to **3,264,206 bytes** with SHA-256 `af2126c057d86559bfad2e164f7f7fd0a26bbc89ab29ea9cbde5cea807c7d2b8`, matching the earlier archived Binary Inspector result. The source DLL SHA-256 was rechecked after analysis and remained identical. No binary was modified, written back or executed.

Unlike the two later client builds, these compression measurements were produced using a **local read-only reproduction of the PR encoder algorithm** in an isolated Python script, **not by invoking the exact current PR CLI**. The source was compared to the PR implementation, but the measurements should still be independently repeated by a local agent running the latest Toolkit branch with the same fingerprint.

| 2019 measurement | Observed value |
|---|---:|
| Raw POL1 section | 1,964,032 B |
| POL1 section virtual size | 1,963,768 B |
| Decoded `.text` | 3,264,206 B |
| Original compressed prefix consumed | **1,963,522 B** |
| Original packed prefix SHA-256 | `a2379e36ccc72a20f06d180c20a5a934a6d82145c55889a72580c4ad32e1548c` |
| Raw-section suffix after decoded prefix | 510 B |
| Entrypoint offset within POL1 | 1,963,536 B |
| Bytes between decoded-prefix endpoint and entry point | 14 B |
| Greedy depth 1024 | 1,963,524 B (**−2 B** headroom, NO-FIT) |
| Lazy depth 128 | 1,945,052 B (**+18,470 B** headroom, FIT) |
| Lazy depth 256 | **1,944,536 B (+18,986 B headroom, FIT)** |

Both lazy candidates were fully decoded independently in memory back to the identical original `.text` and their token streams were completely consumed by the size-bounded decoder. The protected 510-byte raw-section suffix remained outside the virtual substitution. The lazy-256 compressed prefix SHA-256 was `086fb75670737afb3004d7545439e9627418d333efc2ba77cf410baa3e1cd919`; its common prefix with the original compressed stream was **628 bytes**. The greedy-1024 output differed from the original starting at compressed offset **303,988**, so the byte-identical results on 2021/2026 cannot be generalized to 2019.

### Important new evidence: 2019 decompressor uses an explicit stop marker

Read-only x86 disassembly using `objdump` on the **original** 2019 PE entry point (image VA `0x10B93610`, POL1 RVA `0xB93610`) revealed a small unpacking routine entered at VA **`0x10B936AB`**, with the critical block around VA **`0x10B936D6`** testing the low twelve bits of the back-reference word and branching to its return on a **zero distance**. The loop does **not** visibly terminate on reaching the declared decoded `.text` length; its control flow reaches the zero-distance terminator instead. This is static source-code interpretation only, not an execution trace.

An independent read-only compressed-token scan confirmed that the 2019 original's zero-distance marker **begins immediately at compressed-prefix offset 1,963,522**, following exactly **3,264,206** decoded bytes. The marker is the second token in the final control group, just after the bounded decoder stops on the first token. The original final match is three output bytes with no truncated match. The marker lies within the 14-byte region before the PE entry point (its two-byte zero-distance word is present); the remainder of the bootstrap/suffix remains protected.

**Critical implication:** A smaller stream is **not** load-ready just because a size-limited synthetic decoder round-trips. The lazy-128 and lazy-256 encoders currently emit **no terminal zero-distance token** themselves. With the original raw bytes left untouched after the shorter streams, the next original two-byte words at offsets 1,945,052 and 1,944,536 are **not** zero-distance terminators. Simply replacing the prefix while preserving trailing bytes therefore fails the observed 2019 stop-marker contract. It could make a real loader overrun its intended decompressed output, so **no writer or runtime test is approved**.

### In-memory stop-token prototype (research only)

The owner-provided 2019 DLL was also tested with an **in-memory synthetic stop marker**, following the actual 2019 unpacker's observed `distance==0` termination condition. The lazy-depth-256 encoded stream ends with 7 of 8 tokens used in its final control group and zero in the unused flag bit, so a **two-byte zero-distance word** suffices for the next token; no additional control byte is needed. Appending this word changes the in-memory candidate from **1,944,536 to 1,944,538 B**, leaving **18,984 B headroom** within the **1,963,522 B** original consumed-prefix budget. An independent token scanner stops on the synthetic marker after exactly **3,264,206 B decoded output**, and the size-bounded decoder still recovers the original code byte-for-byte.

This experiment is **not an on-disk DLL writer** and uses no installed client. It does not show that the launcher will accept a changed DLL, that surrounding bytes or any loader size parameter are safely handled, or that modified executable code is safe. In a second simulated case that only substituted a shorter prefix while retaining old following data, no marker appeared at the new endpoint: this invalidates that naive layout.

Toolkit research code now includes `_in_memory_zero_distance_terminated_stream` (appends an explicit stop token to a **standalone in-memory candidate** and verifies its synthetic token grammar). The read-only fit report exposes `synthetic_terminated_candidate.candidate_bytes_with_stop`, `headroom_with_stop_bytes` and `fits_original_prefix_budget`, **separately** from plain prefix compression fit. The marker requires two bytes if the final flag group has an unused backreference bit and three bytes if the final group is full. Neither variant writes a retail file.

**Next gate:** have a local agent run the updated PR CLI on the 2019 exact-SHA copy, verify the new marker-inclusive capacity fields and compare termination behavior in the authentic bootstrap. Only then consider the separately authorized design for reversible independent-copy testing; runtime safety and Wardrobe container changes remain unresolved.
### Follow-up tool and acceptance gate

The research assessor now includes a read-only `post_output_next_token` probe for a zero-distance marker after the declared decoded end, and `virtual_substitution_post_output_next_token` for its virtual, in-memory replacement with the original remaining bytes. This is **token-shape evidence only**, not retail loader emulation. Synthetic regression fixtures cover a properly marked stream and an unmarked shorter replacement.

Next: confirm this probe on the exact 2019 uploaded original via the current Toolkit CLI, plus static review for the 2021/2026 loader variants. If a later separately authorized experiment designs an end-marker-preserving format, require independent verification of decompressed bounds, marker placement, PE layout, game-launcher integrity and client-specific container safety before considering any on-disk changes. No original DLL, patched DLL, packed executable bytes or decoded executable contents may be committed to the repository.
