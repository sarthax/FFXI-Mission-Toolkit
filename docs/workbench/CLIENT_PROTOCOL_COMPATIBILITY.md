# Client Protocol Compatibility Records

This is a **read-only evidence model** for comparing client packet-layout observations across binary builds. It complements, rather than replaces, the existing Binary Inspector string/command/byte probes in `workbench.client.binary_probes`.

## First fixture

`client_protocol_records/wardrobe_item_max_2021_2026.json` describes packet `0x1C` ITEM_MAX for 2021 and 2026 FFXiMain.dll build fingerprints. The offsets originate in local decoded-client research reports and are **INFERRED** until independently verified against disassembly or a captured packet. No proprietary binaries or decoded executable bodies are checked in.

Run the offline fixture:

```shell
python test_fixtures/test_client_protocol_compatibility.py
```

`workbench.client.protocol_compatibility.load_record()` validates the record. `compare_builds()` identifies fields whose offsets, widths, or counts differ. It does not declare compatibility, infer packet direction, infer a client version from a connection, or upgrade evidence confidence.

## Interpretation rules

- A command string or byte hit is evidence of presence, **not** a packet-layout proof.
- A missing probe result is UNKNOWN, not evidence of feature absence.
- A decoded static-analysis assertion is INFERRED unless independently validated.
- A captured wire packet can verify observed bytes for that session/build, but does not prove all possible client versions.
- A client store offset is not a packet wire offset.
- Overlapping field spans can be intentional: the old handler's 17-byte copy starts at 0x04, while its u16 table starts at 0x14. Do not interpret copy count as container count.
- A server writer must not emit a modern packet to an unverified legacy client.

## Follow-on work

1. Verify the precise `0x1C` handler reads with a versioned disassembler transcript and/or read-only packet capture.
2. Add a source-backed server packet-layout record and compare the server against each client build.
3. Extend the new read-only Protocol Compatibility section in Binary Inspector into a dedicated tab, with filterable records and navigable evidence links. The first section is implemented on `/binaryinspector`; it does not yet offer file uploads, editable records, or capture ingestion.
4. Investigate a reliable session client-build capability signal **before** enabling a modern packet format.

This milestone does not change any client or server binary, packet, SQL schema, or inventory behavior.

## Initial GUI integration

The Binary Inspector page now renders packaged JSON protocol records and field-level layout differences without requiring a local DLL path. The records are loaded via `workbench.client.binary.inspector.list_protocol_records()`; invalid records are shown as errors instead of silently treated as compatible. Build hashes, evidence status and source references remain visible. This is a **section** in the existing page, not yet a tab. No protocol record is persisted to the graph by merely viewing the page.
