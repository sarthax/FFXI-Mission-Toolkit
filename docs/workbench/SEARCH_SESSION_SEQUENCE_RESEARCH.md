# Search/cache session sequencing evidence policy

Status: source-backed capture/protocol research on `feature/capture-protocol-research-next`.

## Purpose

Search server responses use rolling cryptographic state derived from a prior validated client request. The toolkit already supports explicit state handoff. This layer adds a conservative automatic pairing path for reconstructed traffic while preserving the rule that uncertain order must fail closed.

## Ordering facts

TCP sequence numbers are meaningful only inside one direction. Client->server and server->client sequence values are independent spaces, so they are never compared to order request/response frames.

Timestamps are retained as observations but are not used to choose a predecessor.

PCAP/PCAPNG ingestion assigns monotonically observed capture frame numbers. TCP reconstruction retains the frame numbers that contributed bytes to each reconstructed contiguous range. `search_framing.scan_directions()` now copies this provenance onto every recovered search frame as a coarse interval:

```text
frame_number_min .. frame_number_max
```

The interval is intentionally range-level rather than falsely claiming byte-level packet provenance.

## Strict pairing rule

`search_session_sequence.sequence_validated_session()` may pair a server response with a validated inbound request only when all of the following hold:

1. endpoint role already proves the client->search-server and server->client directions;
2. client->server reconstruction contains no gap or conflicting overlap that could hide a state-changing request;
3. both candidate frames retain capture frame-number provenance;
4. the inbound range's latest contributing capture frame is strictly before the outbound range's earliest contributing capture frame;
5. no inbound provenance interval overlaps the outbound start;
6. the latest proven inbound application frame before that outbound frame successfully decrypts and validates;
7. the exact inbound wire/decrypted pair produces a valid 24-byte outbound state;
8. the outbound frame validates with that exact state.

Only after those gates may the existing non-AH response decoder/evidence policy promote supported response semantics.

## Fail-closed cases

Automatic sequencing is refused when any of these conditions apply:

- missing capture frame-number provenance;
- overlapping inbound/outbound capture-order intervals;
- client->server TCP reconstruction gaps;
- conflicting client->server overlap bytes;
- a later inbound frame exists but fails crypto/MD5 validation;
- predecessor state derivation fails;
- outbound seed/state or crypto validation fails.

The implementation never falls back to an older valid request merely because the latest observed inbound candidate is unusable. That would risk applying stale rolling state.

## Metadata

Search flow metadata now exposes `session_sequence` alongside `framing_evidence`.

Key fields include:

- `ordering_basis = capture_frame_interval_strict_before_only`;
- `timestamps_used_for_pairing = false`;
- `tcp_sequence_compared_across_directions = false`;
- per-response predecessor/outbound capture intervals;
- state derivation evidence;
- outbound crypto validation;
- supported response evidence when validation succeeds;
- explicit diagnostics when pairing cannot be proven.

Flow-level protocol classification remains `ffxi_search_endpoint` / structurally inferred. Successful per-frame sequencing does not silently upgrade the entire TCP flow to a universally decoded protocol stream.

## Regression coverage

`test_capture_search_session_sequence.py` covers:

- validated inbound request -> strictly later outbound response -> state derivation -> decrypt -> source-backed response promotion;
- overlapping capture provenance intervals -> `cross_direction_order_unresolved`;
- client-stream gap -> entire automatic state sequence blocked;
- later invalid inbound candidate -> no fallback to an older valid state.

The normal CI-enumerated lobby/capture regression reaches the sequencing path through `protocol_classification` for its search endpoint sample, while the focused fixture retains the positive stateful protocol vector.

## Remaining validation target

The next high-value input remains a real search/cache PCAP or PCAPNG tied to a verified lobby `cache_ip/cache_port` handoff. The strict sequencer is now ready to report which real request/response relationships are provable and which remain unresolved without using timing heuristics.
