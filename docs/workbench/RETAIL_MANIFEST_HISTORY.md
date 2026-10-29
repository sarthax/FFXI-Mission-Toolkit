# Historical PlayOnline manifest snapshots (first vertical slice)

The Retail Version Explorer previously cached only latest stamps in
`_manifest_cache.json`. Per-file `--history` read the **current** PlayOnline
manifest; it did not preserve the full history or provide arbitrary dated
manifest retrieval.

This slice adds a complete observed-history export to the existing Rust client
and an **offline, content-addressed** Python snapshot catalog. It does not yet
add historical-manifest ingestion controls to the GUI and does not claim a
2022 snapshot has been obtained.

## Capture

Build `tools/retail_fetch` with `cargo build --release`. An explicitly
authorized operator can then run:

```powershell
tools/retail_fetch/target/release/ffxi-retail-selective --export-history-json > history.json
```

The export contains every file/revision *currently advertised* by PlayOnline,
with stamp, decoded bytes, transfer bytes, and direct server path. This does
**not** mean the historical payload is still downloadable.

For programmatic use, `workbench.client.retail.history.capture_current(root)`
runs that explicit network command and stores it. For offline imports use
`store_snapshot(raw_json_bytes, root)`, then `search(root, file_contains="ROM/",
stamp="30220101_0")`.

Snapshots are stored as `snapshots/<sha256>.json` and independent
append-only observation records in `observations.jsonl`. Repeated observations
of identical manifest data reuse the same snapshot. Different records for one
file/stamp produce an explicit `CONFLICTING_MANIFESTS` status. The search API
reports availability `UNKNOWN`, never `AVAILABLE`, unless actual retrieval
is separately verified. An old stamp is **not** equivalent to a historical
patch-date snapshot.

## Next milestones

1. Expose immutable snapshot listing, import, capture and historical search in
   Retail Version Explorer. Keep local installed-client indexing distinct.
2. Discover genuine older manifest sources (archived PlayOnline patch manifests,
   community-held client and installer backups, Kuluu/POLUtils research).
   Record source URL, acquisition time, original bytes and trust tier.
3. Revalidate historical payload availability with plan/fetch on a trusted
   operator machine. Preserve explicit `UNKNOWN`, `NOT_ADVERTISED`,
   `DOWNLOAD_VERIFIED` and `TRANSFER_FAILED` states.
4. Add side-by-side byte-level and DAT-aware comparison with exact snapshot
   citations, not just PE metadata.
5. Add bounded input and manifest-decoder network safety and cross-process
   snapshot locking before routine automated capture.

No existing client is modified, and no retail binaries are committed.
