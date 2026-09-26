# Client Binary Research Pipeline

This pipeline provides read-only static indexing, comparison, and bounded deeper analysis of Windows PE client binaries (EXE/DLL) without building feature-specific logic into the Workbench.

## Inputs

The binary may remain anywhere on the local filesystem. It does **not** need to be copied into the repository. Use an absolute path to an installed client binary or to a separately archived client snapshot.

Example indexing command:

```
python client_binary_index.py "C:\\path\\to\\FINAL FANTASY XI\\FFXiMain.dll" ^
  --client-build 30191204_1 ^
  --label FFXiMain-30191204_1 ^
  --output .workbench/client-binaries/30191204_1/FFXiMain.dll.json ^
  --graph-db workbench.db ^
  --source-snapshot-id client:30191204_1
```

The `.workbench/client-binaries/` directory is gitignored. Store generated JSON indexes there; do not commit proprietary client binaries.

## Indexed evidence

The dependency-free PE indexer records:

- SHA-256/SHA-1/MD5 hashes and file size
- PE32/PE32+ metadata, image base, entry point and subsystem
- sections and RVA/file-offset mapping
- imports and exports
- bounded ASCII and UTF-16LE strings
- layout warnings for executable virtual content that cannot be mapped safely to raw file bytes

The canonical graph importer stores the binary as a CLIENT_BINARY Artifact and creates CLIENT_SOURCE Evidence/Findings for PE metadata, sections, imports and exports. The bounded string corpus is represented by one canonical Evidence record and remains searchable through the binary index instead of creating thousands of graph Findings.

## Read-only research tools

Typed tools:

- `client.binary-info`
- `client.sections`
- `client.imports`
- `client.exports`
- `client.string-search`
- `client.address-evidence`
- `client.binary-diff`
- `client.byte-search`
- `client.xrefs`
- `client.function-candidates`
- `client.import-refs`

The first seven operate from precomputed indexes. The deeper byte/xref/function-candidate tools require the original indexed binary to still be accessible at its recorded path. If it is not accessible, the tool returns `BINARY_UNAVAILABLE` rather than inventing evidence.

## Deeper binary analysis

`client_binary_analyze.py` and `workbench.client.binary_deep` add a dependency-free deeper static layer.

### Bounded byte/pattern search

Hex patterns support one-byte wildcards:

```
python client_binary_analyze.py FFXiMain.dll pattern "E8 ?? ?? ?? ?? 83 C4 04" --executable-only
```

Pattern matches are exact byte observations and therefore reported as VERIFIED byte evidence. Search is bounded by pattern length, result count, section filters, and small context windows.

### Xref candidates

The xref scanner accepts one RVA, VA, or file offset and looks for:

- x86/x64-style relative CALL/JMP/Jcc encodings whose displacement resolves to the target;
- little-endian absolute VA values;
- little-endian RVA values.

Example:

```
python client_binary_analyze.py FFXiMain.dll xrefs --rva 0x123456
```

These are intentionally **xref candidates**, not authoritative decoded references. Relative-control-flow hits remain INFERRED because a byte scanner does not independently prove instruction boundaries. Raw pointer/value matches are also INFERRED because constants can occur as data.

### Function-entry candidates

The function-candidate pass collects:

- the PE entry point;
- export RVAs;
- executable-section targets of direct `CALL rel32` byte patterns.

Example:

```
python client_binary_analyze.py FFXiMain.dll functions
```

PE entry point/export locations are verified seeds, but this output does **not** claim recovered function bodies or semantic function identities. Direct-call targets remain INFERRED until corroborated by disassembly, symbols, another client build, or runtime evidence.

## Comparing builds

Index each binary independently, then compare the indexes:

```
python client_binary_diff.py ^
  .workbench/client-binaries/old/FFXiMain.dll.json ^
  .workbench/client-binaries/new/FFXiMain.dll.json ^
  --output .workbench/client-binaries/FFXiMain-old-vs-new.diff.json
```

The diff compares metadata, section layout, imports, exports, and string presence while ignoring string address relocation by comparing strings by encoding + text.

## Real FFXI validation

The pipeline has been validated against real FFXI PE32/i386 modules supplied outside source control: `FFXiMain.dll`, `FFXiResource.dll`, `FFXiVersions.dll`, and `FFXi.dll`.

`FFXiMain.dll` demonstrated a nonstandard executable `POL1` section and a virtual executable `.text` section with zero raw bytes. This is why deeper analysis iterates executable sections with actual raw bytes rather than assuming code always lives in ordinary raw `.text`.

The supplied FTABLE/VTABLE pair remains a separate DAT/index evidence layer and is not folded into executable analysis.

## Scope boundary

This pipeline is deliberately read-only. It does not patch binaries, inject hooks, write bytes, or promote feature-specific conclusions automatically.

The dependency-free deeper layer stops at bounded pattern observations, conservative xref candidates, and candidate entry points. Full instruction decoding, control-flow graph recovery, decompilation, and symbol/function semantic recovery should be implemented later as optional evidence producers with explicit tool/version provenance rather than silently changing the meaning of the core evidence.

## Real DLL deeper pass (2026-09-25)

The supplied `FFXiMain.dll` (SHA-256 `514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f`, 2,870,352 bytes) was analyzed without copying its bytes into source control. It is PE32/i386 at image base `0x10000000`. Its entry point RVA `0xB93610` maps to file offset `0x28DC10` in executable `POL1` (`0x9B4000`, raw offset `0xAE600`, raw size `0x1DF800`). The executable `.text` RVA `0x1000` has virtual size `0x31CECE` and zero raw bytes. All four exports (`DllCanUnloadNow`, `DllGetClassObject`, `DllRegisterServer`, `DllUnregisterServer`) point into that unmapped virtual `.text`, so this file alone does not supply their code bodies.

The byte scanner finds 1,678 distinct candidate entry RVAs, including the mapped PE entry point; direct-call-derived candidates remain INFERRED. An xref scan to the entry point found zero candidates. In `POL1`, broad `FF 15` and `FF 25` searches yield 351 and 77 byte matches respectively; many operands are outside mapped image addresses, underscoring the false-positive risk of byte scanning through packed content.

The new `import-refs` command and `client.import-refs` tool check only PE32 `FF 15`/`FF 25` absolute operands that match an actual import address table slot (`iat_rva`, distinct from the import lookup thunk). On this file they return **22 candidates** (20 calls, 2 jumps), including byte patterns pointing to `CreateThread`, `FindFirstFileA`, and `GetKeyboardLayout`. These are exact operand/IAT address matches, but opcode alignment and execution are unverified; each result remains INFERRED. Example: `python client_binary_analyze.py FFXiMain.dll import-refs`.

Next validation needs either an optional decoder with versioned provenance and reachable instruction boundaries, or runtime/unpacked memory evidence for the virtual `.text`. No semantic feature or recovered function claim follows from this packed on-disk image alone.

## GUI and feature-presence probes (2026-09-26)

**Binary Inspector page** — `/binaryinspector` (nav: Client > Binary Inspector), backed by `binary_inspector.py`. Read-only. Shows layout warnings, sections, imports grouped by DLL, exports, string search, byte-pattern search (wildcards, optional executable-only) and diff against a second binary. It deliberately does **not** expose xref, function-candidate or import-ref passes (heuristic, mostly false positives on packed FFXiMain). Diff and byte results currently render as raw structures.

**DAT Inspector page** — `/datinspector`, backed by `dat_inspector.py`. Structure confirmation only (resolve id -> file, hash, header, which `xi_tinkerer` parsers accept it). Asset/model viewing is intentionally out of scope; XI-Tools/XI-Viewer already cover that.

**Feature-presence probes** — `workbench/client/binary_probes.py`, test `test_fixtures/test_binary_probes.py`. A probe (string or byte pattern) run against a client binary is persisted like the DAT adapter's records: `Capability` (`CLIENT_BINARY_PROBE`), snapshot-scoped `CapabilityObservation` (value has match count, samples, binary name, SHA-256 = build fingerprint) and `Evidence`. A hit is `VERIFIED`; a miss stays `UNKNOWN`, never absent, because packed FFXiMain.dll cannot prove absence. A probe with a `feature` id also writes a `CapabilityRequirement`, so Feature Checker reports `REQUIRED_CAPABILITIES_VERIFIED` or `UNKNOWN_REQUIRED_CAPABILITY`. Re-running is idempotent.

Real finding on the supplied FFXiMain.dll: strings `/wardrobe`, `/wardrobe2`, `/wardrobe3`, `/wardrobe4` exist; `wardrobe 8` not found (UNKNOWN, not proof of absence).

**Probe sets (proof of concept)** — saved as `client_probe_sets/*.json` (`{name, description, binary, probes:[{name, kind, needle}]}`); first set is `mog_wardrobe.json`. The Binary Inspector page lists them with a Run button (`?run_set=<file>`), served by `binary_inspector.list_probe_sets()` / `run_probe_set()`. The GUI run is read-only and does **not** persist observations; persisting still goes through `binary_probes.persist_probes()` from Python. Real result on the supplied client: `/wardrobe`, `/wardrobe2`, `/wardrobe4` VERIFIED; `/wardrobe5`, `/wardrobe8` UNKNOWN.

Not built: GUI to create/edit probe sets, a persist-to-graph button, Client Overview / Build page showing fingerprints.
