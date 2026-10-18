# Selective PlayOnline retail file fetcher

A standalone, read-only research utility using Kuluu's PlayOnline protocol client and
manifest validation. Requires Rust/Cargo, TCP access to `pc001.pol.com:53001`,
and review of Kuluu's GPL-3.0-or-later license prior to redistribution.

From `tools/retail_fetch`:

```powershell
cargo run --release -- --list --file FFXiMain.dll
cargo run --release -- --history --file FFXiMain.dll
cargo run --release -- --plan --file FFXiMain.dll
cargo run --release -- --file FFXiMain.dll --output D:\\FFXI-Research\\retail
cargo run --release -- --file ROM/119/51.DAT --output D:\\FFXI-Research\\retail
```

`--version 3022...` may select an exact manifest version when still retained.
Use the manifest's exact stamp, not a guessed release date. Historical payloads
may be unavailable. Files remain under their manifest-relative paths.
The executable rejects path traversal and does not touch an installed client.
Existing files are never overwritten. It validates each reconstructed file
against Kuluu's manifest signature and uses a verified temporary file with create-new semantics.

No network calls happen during import; the fetch only occurs when explicitly run.

Use `--history --file FFXiMain.dll` to enumerate every version stamp and
complete-file compressed size advertised by the current patch manifest before
selecting `--version EXACT_STAMP`. A listed historical entry does not guarantee
that the server still serves its payload.

**Validation:** GitHub Actions runs `cargo check` and `cargo test` using a
Linux Rust runner. Never claim successful compilation or downloading until the
workflow and an explicitly permitted live network test both succeed.

## Safe live-test sequence

1. Run `--list --file FFXiMain.dll` to discover the exact case-insensitive manifest name.
2. Run `--history --file FFXiMain.dll` and record the actual available stamps.
3. Run `--plan --file FFXiMain.dll [--version EXACT_STAMP]`; this reads the manifest and prints the selected file version, full-file transfer size and server patch path **without fetching file bytes**.
4. Only on a network host authorized to reach PlayOnline, run `--file FFXiMain.dll --output ...` into an isolated, trusted empty research directory. Never target a live client installation.
5. Record SHA-256 externally and analyze the DLL through the separate client Binary Inspector research workflow. No PlayOnline login is needed for the documented patch-server operation, but network access must be explicitly permitted.

CI now checks and tests the crate on both Linux and Windows runners, with no PlayOnline network test. Do not mistake a green CI build for a successful retail download.
