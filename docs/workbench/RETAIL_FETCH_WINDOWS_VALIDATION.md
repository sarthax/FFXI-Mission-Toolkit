# Selective retail downloader — Windows validation (2026-10-18)

Tested: PR #1069, commit `646614d62a373c3dc02dae4512357a22ee3d2b3e`
(`feature/selective-pol-retail-fetch-20261018`), in an isolated worktree.
Host: Windows 10 Pro 10.0.19043, rustc/cargo 1.98.0, pinned Kuluu rev `a7752b3a`.

## Results matrix

| Stage | Result | Evidence |
|---|---|---|
| Windows debug build + `cargo test` | PASS | 7/7 tests; first build 9m, no warnings |
| Release build | PASS | `cargo build --release` 1m15s, no warnings |
| Executable launches | PASS (minor) | No args prints usage, exit 1. `--help` is not a flag; it falls through to the same usage error |
| Manifest listing (`--list --file FFXiMain.dll`) | PASS | `FFXiMain.dll latest=30261006_0`; `pc001.pol.com` resolved to 124.150.156.107, TCP 53001 reachable, no auth needed |
| Version history (`--history`) | PASS | 5 versions, below |
| Plan (`--plan`) | PASS | Printed "nothing downloaded"; output dir unchanged |
| Single-file download | **PASS** | First attempt was blocked by the session classifier; rerun after explicit user permission. `FFXiMain.dll` [30261006_0], 2901584 bytes, exit 0 |
| SHA-256 / PE header / size / manifest consistency | PASS | Size equals manifest decoded bytes (2901584); independent `sha256sum` matches the printed digest `042884888eea4fadac183e520f2ae9f8c4fa267860e685048e1880efd358e872`; MZ/PE signature, machine 0x14c (x86), DLL flag set; FileSig check passed inside the tool |
| Re-run against existing output | PASS | Refused to overwrite, exit 1, file unchanged, no stray temp files |
| Toolkit `binary_index` import | PASS | Index produced (3.8 MB JSON, kept in gitignored `exports/`); PDB string `FFXiMain___Win32_Retail` found. File never executed or loaded |
| Overwrite prevention | PASS (unit) | `publishes_without_replacing_existing_files` |
| Path traversal | PASS (unit) | `disallows_escape_paths` |
| Corrupt / truncated / oversized payloads | PASS (unit) | 3 tests added here; 10/10 total |
| Invalid signature (`FileSig` mismatch) | NOT TESTED | Check exists in `main.rs` but has no fixture test, because it sits inside `run()` |
| Symlink safety | PARTIAL | Dangling-symlink test is `#[cfg(unix)]` only. Windows symlink / reparse point NOT TESTED |
| Network timeout | NOT TESTED | Upstream sets `IO_TIMEOUT` on read and write; no connect timeout; no test |
| Unbounded upstream manifest decode | FAIL (known gap) | See below |

## Historical versions (from manifest, `--history`)

| Stamp | Decoded bytes | Transfer bytes |
|---|---|---|
| 30020917_0 | 1262080 | 1183255 |
| 30210706_0 | 2878544 | 2151611 |
| 30260805_0 | 2901584 | 2175329 |
| 30260904_0 | 2901584 | 2175564 |
| 30261006_0 (current) | 2901584 | 2175178 |

The manifest lists these stamps. Whether the server still serves their payloads is untested.
Plan for current: `30261006_0/Direct/FFXiMain.dll.slc`.

## Safety findings

1. Upstream `Session::manifest()` calls `lz::decode_direct` with no output cap
   (`Vec::with_capacity(coded.len() * 2)`, unbounded growth). The selected-file path is bounded; the manifest path is not.
2. Upstream `recv()` accepts frames up to `MAX_STREAM_LEN` = 1 GiB and allocates that up front.
3. `fetch()` preallocates `len` bytes; main.rs caps this at 128 MiB first, so it is bounded here.
4. `FileSig` is a legacy checksum (length, byte sum, 4 bytes of MD5), not cryptographic authentication.
5. `--plan` and `--history` perform network reads but write nothing.
6. `Cargo.lock` is not committed, so dependency resolution is not reproducible. `tools/retail_fetch/target/` is not gitignored.

## Toolkit integration assessment (existing infrastructure)

- Binary Inspector (`/binaryinspector`, `workbench.client.binary.inspector`) and the
  `workbench.client.cli.binary_index` CLI already take an absolute path anywhere on disk, with
  `--client-build`, `--label` and `--source-snapshot-id`. They record SHA-256/SHA-1/MD5, PE metadata, imports and
  exports, and store a CLIENT_BINARY Artifact. Indexes go under the gitignored `.workbench/client-binaries/<build>/`.
- Recommended path: download into `.workbench/client-binaries/<stamp>/FFXiMain.dll`, then run `binary_index` with
  `--client-build <stamp>`. That keeps retail binaries apart from DSP server artifacts and gives historical comparison
  through the existing `client.binary-diff` tool. No parallel artifact system is needed.
- Gap: the downloader prints SHA-256 to the console only. It does not write a provenance sidecar (source host,
  stamp, manifest signature, timestamp).
- GUI: keep the CLI standalone for now. A thin Binary Inspector action ("fetch version") is worth adding only after a
  verified real download.

## Next slice

1. (Done above.) Download one older stamp (e.g. `30210706_0`) to confirm historical payloads are still served, then diff with `client.binary-diff`.
2. Add a `.provenance.json` sidecar written by the downloader.
3. Commit `Cargo.lock`, ignore `target/`, and cap the manifest decode (patch upstream or wrap).
4. Make the fixture test for signature mismatch reachable by moving the verify step out of `run()`.
