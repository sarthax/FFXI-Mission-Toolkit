# Capture protocol classification — evidence model

Status: backend research slice on `feature/capture-protocol-research-next`.

This note documents the deliberately conservative next layer above generic PCAP/PCAPNG parsing and bidirectional TCP reconstruction.

## Current family inventory

| Family | Current evidence | Classification state | Decoder state |
|---|---|---|---|
| Lobby / character service | IXFF framing, declared size, known command, fixed/validated variable layout, MD5 identifier, command direction | `ffxi_lobby` only when all structural checks pass | Known lobby fields only; raw packet always retained |
| Map/game handoff | Exact `server_ip` + `server_port` learned from verified lobby `ResponseNextLogin`; modern LSB fills these from selected zone IP/port and exposes map/game on UDP | `ffxi_map_endpoint`, **structurally inferred only when an observed UDP frame exactly matches that handoff endpoint in the same PCAP source** | UDP payload remains raw/opaque unless the pre-existing known-chunk promotion path independently validates it |
| Search / cache handoff | Exact `cache_ip` + `cache_port` learned from verified lobby `ResponseNextLogin`, plus LandSandBoat source-backed clear search framing when present | `ffxi_search_endpoint`, **structurally inferred**; clear framing is recognized only after the verified TCP handoff association | Clear 8-byte framing header recognized; encrypted/opaque payload retained without packet-type semantics |
| Other reconstructed TCP | No sufficient structural evidence | `unknown_tcp` | Opaque |
| Plaintext world/map UDP chunks | Existing complete-known-chunk-stream promotion in PCAP ingestion | Existing behavior unchanged | Existing packet-reference decoder path |

Default retail/private-server port numbers are not proof and are not used by the classifier.

## Certainty vocabulary

New research metadata uses the following values:

- `verified` — validated directly against a demonstrated structure/source relationship;
- `verified_observation` — transport fact directly present in the capture, such as SYN/FIN/RST or payload direction;
- `structurally_inferred` — association or framing follows from verified source/structure, but message semantics are not proven;
- `unknown_opaque` — bytes are retained without assigned semantics;
- `ambiguous` — more than one transport-compatible family has equally valid evidence, so classification fails closed.

Lobby decoded fields additionally distinguish `unknown_opaque` fields whose offsets are known but semantics remain intentionally unnamed.

## Lobby diagnostics

The validated lobby scanner reports, without promoting invalid data:

- `truncated_frame_candidate`;
- `unknown_message_type`;
- `invalid_declared_size`;
- `rejected_frame_candidate` with the structural rejection reason;
- `framing_resynchronization` with skipped raw bytes and exact range/sequence offsets;
- `opaque_trailing_bytes`.

A candidate still becomes a lobby message only when the pre-existing structural checks pass. Diagnostics do not weaken classification.

## Search/cache framing evidence

LandSandBoat `src/search/search_handler.cpp` establishes a limited framing fact that is useful before payload decryption:

- outgoing search packets write a little-endian packet length at offset `0x00`;
- outgoing search packets write literal `IXFF` at offsets `0x04..0x07`;
- encryption begins at offset `0x08`, leaving that framing header clear;
- incoming reads reject a packet when the observed read length differs from the little-endian `uint16` at offset `0x00` or the packet is shorter than 28 bytes;
- the search packet type is consumed only after decryption and post-decryption hash validation.

`search_framing.scan_range()` therefore recognizes only a **frame candidate** requiring:

```text
uint16_le(declared_size) >= 28
bytes[4:8] == "IXFF"
complete declared_size bytes present in one reconstructed contiguous range
```

It retains:

- exact range offset and TCP sequence start/end;
- the complete raw frame;
- the clear first 8 bytes;
- all bytes after offset 8 as `opaque_payload_hex`;
- truncation/resynchronization diagnostics.

It does **not** expose packet type, request meaning, auction/search/group semantics, MD5 result, Blowfish key material, or decrypted fields.

The signature alone is deliberately insufficient to name a flow `ffxi_search_endpoint`, because lobby traffic also uses IXFF-style clear framing. Search framing is attached to a family only when the same TCP endpoint exactly matches `cache_ip/cache_port` from a verified lobby `ResponseNextLogin`.

## Map/game handoff and transport

LandSandBoat `src/login/data_session.cpp` assigns `ResponseNextLogin.server_ip/server_port` from the selected zone IP/port. Maintained LSB deployment configuration exposes the map/game service on UDP. Therefore the TCP classifier treats a TCP flow whose IP/port matches `server_*` as **transport-mismatched evidence**, not as a verified or inferred world/map TCP family.

Such a TCP flow remains:

```text
protocol_family = unknown_tcp
classification_scope = handoff_endpoint_transport_mismatch
```

and carries a candidate like:

```text
protocol_family = ffxi_map_endpoint
expected_transport = udp
```

plus a `handoff_endpoint_transport_not_proven` diagnostic.

For raw PCAP frames, the post-processing pass now also checks observed UDP endpoints. When a UDP frame in the **same source file** exactly matches verified `ResponseNextLogin.server_ip/server_port`, only its frame metadata is annotated:

```text
protocol_family = ffxi_map_endpoint
classification_validated = false
classification_certainty = structurally_inferred
classification_scope = exact_udp_endpoint_from_verified_lobby_ResponseNextLogin
decoder_status = raw_udp_payload_preserved
cross_source_merge_performed = false
```

The raw UDP payload is not renamed, decrypted, reparsed, or promoted merely because the endpoint matches. Existing plaintext-known-chunk promotion remains an independent structural check.

## Session/transport observations

Known lobby commands can contribute verified phase evidence such as login setup, character/world query/list, character selection, and map/search handoff.

TCP lifecycle metadata is intentionally application-neutral and records only observed SYN/FIN/RST events and payload-frame counts per direction. It does not name a gameplay phase from TCP flags.

## Cross-flow correlation

`protocol_classification.classify_reconstructed_flows()` performs a staged pass:

1. validate lobby flows independently;
2. collect exact map/search endpoint tuples only from verified `ResponseNextLogin` messages;
3. attach expected transport from source-backed evidence (`udp` for modern-LSB map/game, `tcp` for search/cache);
4. compare reconstructed TCP flows against those tuples;
5. only for an exact transport-compatible search endpoint match, inspect reconstructed ranges for the source-backed clear search framing described above.

A search endpoint with no recognized clear frame keeps:

```text
classification_validated = false
classification_certainty = structurally_inferred
classification_scope = exact_transport_compatible_endpoint_association_only_payload_opaque
decoder_status = unknown_opaque
```

A search endpoint that also contains source-backed clear frame candidates uses:

```text
classification_validated = false
classification_certainty = structurally_inferred
classification_scope = verified_search_handoff_plus_source_backed_search_framing
decoder_status = encrypted_or_opaque
```

If multiple transport-compatible families ever claim the same endpoint, classification remains fail-closed and emits `ambiguous_protocol_family_classification`. A transport-incompatible endpoint is preserved as a candidate and diagnostic rather than being treated as a competing family.

No fuzzy merge is attempted across captures, hosts, nearby timestamps, similar payloads, or common port numbers.

## PCAP metadata integration

Normal PCAP ingestion still owns frame parsing, TCP reconstruction, range persistence, lobby message insertion, raw evidence, and the existing UDP known-chunk promotion path. After one source file is ingested, `protocol_metadata.refresh_source_flow_metadata()` reloads only that source file's persisted TCP flow/range rows, runs the conservative classifier, and merges classification fields back into `capture_network_flows.metadata_json`.

The same post-pass then uses verified lobby handoff evidence from those flows to annotate exact transport-compatible UDP frame records in `capture_structured_records`.

This post-pass explicitly records either:

```text
classification_metadata_provenance = same_source_file_reconstructed_flow_ranges
```

or, for map UDP matches:

```text
classification_metadata_provenance = same_source_file_lobby_handoff_to_udp_frame
```

and always:

```text
cross_source_merge_performed = false
```

No routes, templates, global navigation, or database schema changes are required for downstream capture viewers to inspect the metadata.

## Raw evidence policy

The persisted TCP ranges and PCAP frame records remain authoritative raw evidence. New diagnostics include observed raw slices where useful, plus exact offsets/sequence positions. Missing bytes are never synthesized and malformed/unknown candidates are not discarded merely because they cannot be decoded.

## Regression fixtures

`test_fixtures/test_capture_protocol_classification.py` uses small synthetic byte strings rather than binary capture blobs. It covers:

- valid MD5-backed `ResponseNextLogin`;
- decoded-field certainty metadata;
- lobby framing resynchronization after opaque prefix bytes;
- truncated known lobby frame preservation;
- unknown lobby command preservation;
- search clear-header framing and opaque payload retention;
- search framing resynchronization and truncation;
- map handoff TCP transport mismatch failing closed;
- exact search endpoint correlation;
- proof that a search-looking header without verified handoff evidence remains `unknown_tcp`;
- same numeric map/search endpoint with transport selecting search for TCP while preserving map as mismatched evidence.

The CI-enumerated `test_fixtures/test_capture_lobby_decoder.py` additionally exercises:

- PCAP ingestion surfacing search classification metadata without synthetic search messages;
- a synthetic UDP frame to the exact verified map handoff endpoint;
- preservation of that UDP payload as raw evidence while only metadata receives `ffxi_map_endpoint` association;
- idempotent reingestion.

Existing PCAP parser and TCP reconstruction tests remain the authority for frame parsing, gaps, retransmissions, overlap conflicts, and raw range preservation.

## Not yet claimed

This slice still does **not** claim:

- decrypted search/cache message types or field semantics;
- that every packet generation/server fork uses identical search payload encryption details;
- a world/map TCP message framing format;
- map/game UDP message semantics from endpoint correlation alone;
- gameplay meaning for changing unknown fields;
- storage/account subflow semantics;
- automatic cross-capture session merging;
- retail protocol identity from a port number or IXFF signature alone.

The highest-value next decoder work is a real search/cache capture tied to a verified lobby handoff. For map/game, the next evidence step is to compare a real same-session UDP capture against existing normalized world packet evidence and server packet structures without assuming endpoint correlation alone establishes packet meaning.
