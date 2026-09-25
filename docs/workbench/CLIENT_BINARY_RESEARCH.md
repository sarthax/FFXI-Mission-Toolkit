# Client Binary Research Pipeline

This pipeline provides read-only static indexing and comparison of Windows PE client binaries
(EXE/DLL) without building feature-specific logic into the Workbench.

## Inputs

The binary may remain anywhere on the local filesystem. It does **not** need to be copied into
the repository. Use an absolute path to an installed client binary or to a separately archived
client snapshot.

Example:

```
python client_binary_index.py "C:\path\to\FINAL FANTASY XI\FFXiMain.dll" ^
  --client-build 30191204_1 ^
  --label FFXiMain-30191204_1 ^
  --output .workbench/client-binaries/30191204_1/FFXiMain.dll.json ^
  --graph-db workbench.db ^
  --source-snapshot-id client:30191204_1
```

The `.workbench/client-binaries/` directory is gitignored. Store generated JSON indexes there;
do not commit proprietary client binaries.

## Indexed evidence

The dependency-free PE indexer records:

- SHA-256/SHA-1/MD5 hashes and file size
- PE32/PE32+ metadata, image base, entry point and subsystem
- sections and RVA/file-offset mapping
- imports and exports
- bounded ASCII and UTF-16LE strings

The canonical graph importer stores the binary as a CLIENT_BINARY Artifact and creates
CLIENT_SOURCE Evidence/Findings for PE metadata, sections, imports and exports. The bounded
string corpus is represented by one canonical Evidence record and remains searchable through
the binary index instead of creating thousands of graph Findings.

## Research tools

Read-only typed tools:

- `client.binary-info`
- `client.sections`
- `client.imports`
- `client.exports`
- `client.string-search`
- `client.address-evidence`
- `client.binary-diff`

These tools expose static evidence only. A string/import/export match does not prove runtime
behavior or feature support.

## Comparing builds

Index each binary independently, then compare the indexes:

```
python client_binary_diff.py ^
  .workbench/client-binaries/old/FFXiMain.dll.json ^
  .workbench/client-binaries/new/FFXiMain.dll.json ^
  --output .workbench/client-binaries/FFXiMain-old-vs-new.diff.json
```

The diff compares metadata, section layout, imports, exports, and string presence while ignoring
string address relocation by comparing strings by encoding + text.

## Scope boundary

This pipeline is deliberately read-only. It does not patch binaries, inject hooks, write bytes,
or promote feature-specific conclusions automatically. Deeper disassembly/xref analyzers can be
added later as optional evidence producers while retaining the same hash/snapshot/provenance
boundary.


## Real FFXI validation notes

The pipeline has been validated against real FFXI PE32/i386 client modules. In particular,
FFXiMain.dll may use a nonstandard executable `POL1` section and may report a virtual
executable `.text` section with zero raw bytes. The indexer therefore emits layout warnings
instead of assuming every executable RVA can be mapped to ordinary raw `.text` bytes.

This matters for later disassembly/xref work: imports, exports, hashes, resources, and string
evidence may still be usable even when ordinary code-section mapping is incomplete.
