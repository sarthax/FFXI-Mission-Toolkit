# Review validation — 2026-10-18

PR #1069, reviewed head f434d03f7c3765178f80c563dc543f16931fc2d3.

Source inspection used the GitHub connector because the local checkout did not
contain the PR branch and Git fetch failed to connect to the configured proxy.

## Fixes

- Repeat Kuluu's cab patch in this standalone Cargo root, pinned to the same
  revision. Dependency workspace patches are not inherited. ffxi-install calls
  the fork's public uncompressed_offset, folder_index, and read_folder APIs.
- Replace check-then-fs::write staging with NamedTempFile exclusive creation.
  The old staging write could truncate an existing file or follow a symlink
  introduced between the existence check and write. Final publication still
  uses an atomic hard link that refuses existing destinations.
- Add regression tests for existing-file preservation and dangling symlinks.

## Build and test limitations

Both cargo check --manifest-path tools/retail_fetch/Cargo.toml and cargo test
--manifest-path tools/retail_fetch/Cargo.toml were attempted and exited 127:
cargo: command not found. No compilation or test pass is claimed. Dependency
resolution and these fixes must be checked on a Rust-equipped host.

## API and integrity review

At pinned Kuluu revision a7752b3a6a9c570b5af0011e89af6268615e8c14,
manifest and patch_client are public modules. The used Server, Session,
decode_direct_payload, manifest::parse and FileSig APIs match the call sites.
ffxi-install also depends on flate2, md-5, msi and unrar; the latter requires
native build tooling.

current() selects the last manifest version; direct/direct_len select a complete
file rather than an incremental delta. Decoded bytes are checked against FileSig
before staging: length, signed-byte sum and the first four MD5 digest bytes.
This is the legacy protocol content check, not a cryptographic signature
authenticating the manifest. The decoder allocates its output before the check,
so the declared 128 MiB limit is not a hard decompression memory limit.
Output must be a trusted isolated research directory: parent symlinks are not
a filesystem sandbox. Existing destination names are refused atomically.

## Network result

The policy snapshot has no TCP domain or IP grants. A five-second-bounded
getent lookup produced no address; a socket connection attempt with a three-second
connect timeout failed at DNS with "Temporary failure in name resolution".
No TCP handshake was established; remote port availability is unknown.
Git HTTPS also failed immediately because the configured proxy was unreachable.
PlayOnline testing stopped here; no proxy bypass was attempted.

No manifest or FFXiMain.dll was downloaded. SHA-256, size and exact retail stamp
are unavailable. No proprietary binaries were committed and no FFXI installation
was modified. Do not merge on the basis of this source-only validation.
