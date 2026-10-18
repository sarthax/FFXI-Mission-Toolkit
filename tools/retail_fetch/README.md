# Selective PlayOnline retail file fetcher

A standalone, read-only research utility using Kuluu's PlayOnline protocol client and
manifest validation. Requires Rust/Cargo, TCP access to `pc001.pol.com:53001`,
and review of Kuluu's GPL-3.0-or-later license prior to redistribution.

From `tools/retail_fetch`:

```powershell
cargo run --release -- --list FFXiMain.dll
cargo run --release -- --file FFXiMain.dll --output D:\\FFXI-Research\\retail
cargo run --release -- --file ROM/119/51.DAT --output D:\\FFXI-Research\\retail
```

`--version 3022...` may select an exact manifest version when still retained.
Use the manifest's exact stamp, not a guessed release date. Historical payloads
may be unavailable. Files remain under their manifest-relative paths.
The executable rejects path traversal and does not touch an installed client.
Existing files are never overwritten. It validates each reconstructed file
against Kuluu's manifest signature and uses temporary files before final rename.

No network calls happen during import; the fetch only occurs when explicitly run.
