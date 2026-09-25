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
