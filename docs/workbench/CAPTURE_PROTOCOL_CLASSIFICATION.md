# Capture protocol classification — evidence model

Status: backend research slice on `feature/capture-protocol-research-next`.

This note documents the deliberately conservative next layer above generic PCAP/PCAPNG parsing and bidirectional TCP reconstruction.

## Current family inventory

| Family | Current evidence | Classification state | Decoder state |
|---|---|---|---|
| Lobby / character service | IXFF framing, declared size, known command, fixed/validated variable layout, MD5 identifier, command direction | `ffxi_lobby` only when all structural checks pass | Known lobby fields only; raw packet always retained |
| World / map handoff | Exact `server_ip` + `server_port` learned from a verified lobby `ResponseNextLogin` | `ffxi_world_endpoint`, **structurally inferred endpoint association only** | Opaque; no TCP/world framing semantics asserted |
| Search / cache handoff | Exact `cache_ip` + `cache_port` learned from a verified lobby `ResponseNextLogin` | `ffxi_search_endpoint`, **structurally inferred endpoint association only** | Opaque; no search framing semantics asserted |
| Other reconstructed TCP | No sufficient structural evidence | `unknown_tcp` | Opaque |
| Plaintext world/map UDP chunks | Existing complete-known-chunk-stream promotion in PCAP ingestion | Existing behavior unchanged | Existing packet-reference decoder path |

Default retail/private-server port numbers are not proof and are not used by the new classifier.

## Certainty vocabulary

New research metadata uses the following values:

- `verified` — validated directly against a demonstrated structure/source relationship;
- `verified_observation` — transport fact directly present in the capture, such as SYN/FIN/RST or payload direction;
- `structurally_inferred` — association follows from verified structure, but the later payload/framing has not itself been proven;
- `unknown_opaque` — bytes are retained without assigned semantics;
- `ambiguous` — more than one supported family has equally valid evidence, so classification fails closed.

Lobby decoded fields additionally distinguish `unknown_opaque` fields whose offsets are known but semantics remain intentionally unnamed.

## Lobby diagnostics

The validated lobby scanner now reports, without promoting invalid data:

- `truncated_frame_candidate`;
- `unknown_message_type`;
- `invalid_declared_size`;
- `rejected_frame_candidate` with the structural rejection reason;
- `framing_resynchronization` with skipped raw bytes and exact range/sequence offsets;
- `opaque_trailing_bytes`.

A candidate still becomes a lobby message only when the pre-existing structural checks pass. Diagnostics do not weaken classification.

## Session/transport observations

Known lobby commands can contribute verified phase evidence such as login setup, character/world query/list, character selection, and world/search handoff.

TCP lifecycle metadata is intentionally application-neutral and records only observed SYN/FIN/RST events and payload-frame counts per direction. It does not name a gameplay phase from TCP flags.

## Cross-flow correlation

`protocol_classification.classify_reconstructed_flows()` performs a two-stage pass:

1. validate lobby flows independently;
2. collect exact world/search endpoint tuples only from verified `ResponseNextLogin` messages, then compare reconstructed flows against those tuples.

An exact handoff match proves an endpoint association, not the later protocol framing. Therefore world/search matches keep:

```text
classification_validated = false
classification_certainty = structurally_inferred
classification_scope = exact_endpoint_association_only_payload_opaque
decoder_status = unknown_opaque
```

If one endpoint is simultaneously claimed as both world and search, classification remains `unknown_tcp` and emits `ambiguous_protocol_family_classification`.

No fuzzy merge is attempted across captures, hosts, nearby timestamps, similar payloads, or common port numbers.

## Raw evidence policy

The caller's reconstructed TCP ranges remain authoritative raw evidence. New diagnostics include observed raw slices where useful, plus exact offsets/sequence positions. Missing bytes are never synthesized and malformed/unknown candidates are not discarded merely because they cannot be decoded.

## Regression fixture

`test_fixtures/test_capture_protocol_classification.py` uses small synthetic byte strings rather than binary capture blobs. It covers:

- valid MD5-backed `ResponseNextLogin`;
- decoded-field certainty metadata;
- framing resynchronization after opaque prefix bytes;
- truncated known frame preservation;
- unknown command preservation;
- exact world endpoint correlation;
- exact search endpoint correlation;
- insufficient-evidence fail-closed behavior;
- ambiguous world/search endpoint collision.

Existing PCAP parser and TCP reconstruction tests remain the authority for frame parsing, gaps, retransmissions, overlap conflicts, and raw range preservation.

## Not yet claimed

This slice does **not** claim:

- a search/cache message framing format;
- a world/map TCP message framing format;
- gameplay meaning for changing unknown fields;
- storage/account subflow semantics;
- automatic cross-capture session merging;
- retail protocol identity from a port number alone.

The next decoder work should begin only after a real search/cache or world stream sample can be tied to server/client source structures or a repeatable framing pattern.
