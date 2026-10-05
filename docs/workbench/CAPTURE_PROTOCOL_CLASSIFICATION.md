# Capture protocol classification — evidence model

Status: backend research slice on `feature/capture-protocol-research-next`.

This layer sits above generic PCAP/PCAPNG parsing and bidirectional TCP reconstruction. It is deliberately fail-closed: endpoint, framing, direction, and message semantics are separate claims and are promoted only when the available evidence supports each one.

## Current family inventory

| Family | Evidence | Current state | Payload semantics |
|---|---|---|---|
| Lobby / character service | `IXFF`, declared size, known command/layout, MD5, command direction | `ffxi_lobby`, verified only when all structural checks pass | Known lobby fields only; raw bytes retained |
| Search / cache | Exact verified `ResponseNextLogin.cache_ip/cache_port` TCP handoff plus source-backed clear length/`IXFF` framing when present | `ffxi_search_endpoint`, structurally inferred | Bytes after clear offset 8 remain encrypted/opaque |
| Map / game endpoint | Exact verified `ResponseNextLogin.server_ip/server_port` and UDP transport | `ffxi_map_endpoint`, structurally inferred from endpoint alone | Raw UDP payload retained |
| Map initial login | Exact verified map endpoint as UDP destination plus valid client `0x000A` structure | verified map-handshake evidence | Handshake structure only; semantic fields remain opaque |
| Other TCP / UDP | Insufficient evidence | unknown / endpoint-only | Opaque |

Default ports, timestamps, or signatures alone are never proof.

## Certainty vocabulary

- `verified` — demonstrated structure/source relationship passes its validation checks.
- `verified_observation` — directly observed transport/header fact.
- `structurally_inferred` — family association follows from verified evidence, but message semantics are not proven.
- `unknown_opaque` — bytes retained without assigned meaning.
- `ambiguous` — more than one equally valid interpretation remains; classification fails closed.

## Lobby diagnostics

The lobby scanner preserves malformed/unknown evidence and reports:

- `truncated_frame_candidate`;
- `unknown_message_type`;
- `invalid_declared_size`;
- `rejected_frame_candidate`;
- `framing_resynchronization`;
- `opaque_trailing_bytes`.

Diagnostics never weaken the existing requirement for a valid known lobby frame before promotion.

## Search/cache framing

LandSandBoat `src/search/search_handler.cpp` demonstrates a limited pre-decryption framing fact:

- little-endian total length at offset `0x00`;
- literal `IXFF` at offsets `0x04..0x07`;
- bytes beginning at offset `0x08` enter the encrypted/validated payload path.

`search_framing.scan_range()` therefore recognizes only complete clear-header frame candidates. Packet type, request meaning, auction/search/group semantics, Blowfish keys, and decrypted fields remain opaque. A search-looking header without the exact verified lobby cache handoff remains `unknown_tcp`.

## Map/game transport and verified 0x000A handshake

LandSandBoat fills `ResponseNextLogin.server_ip/server_port` from the selected zone endpoint and the modern map service listens on UDP. A TCP flow hitting that numeric endpoint is therefore transport-mismatched evidence and remains `unknown_tcp`.

For UDP, endpoint equality alone yields only:

```text
protocol_family = ffxi_map_endpoint
classification_validated = false
classification_certainty = structurally_inferred
classification_scope = exact_udp_endpoint_from_verified_lobby_ResponseNextLogin
decoder_status = raw_udp_payload_preserved
```

The initial non-encrypted client zone-login datagram can be verified more strongly. Source/reference evidence establishes:

```text
0x1C common world transport header
+ 0x5C inner GP_CLI_COMMAND_LOGIN packet
+ 0x10 final transport MD5 trailer
= 0x88 bytes total
```

`map_framing.inspect_login_datagram()` requires all of the following:

1. exact `0x88` datagram length;
2. inner opcode low 9 bits equal `0x000A`;
3. inner declared size equals `0x005C`;
4. final 16 bytes equal MD5 of the complete `0x005C` inner packet;
5. `LoginPacketCheck` equals the documented byte-sum over inner bytes from offset `0x08` onward.

`protocol_metadata` adds a direction requirement: XiPackets documents client `0x000A` as C -> S, so the verified map endpoint must be the UDP destination. Reverse-direction structural matches stay inferred and emit `map_login_direction_mismatch`.

A fully verified frame uses:

```text
classification_validated = true
classification_certainty = verified
classification_scope = verified_lobby_handoff_plus_verified_map_0x000A_udp_handshake
decoder_status = verified_handshake_structure_payload_fields_opaque
```

Character id, ticket/account material, platform, language, and unknown fields are intentionally not promoted by this layer.

## Exact normalized-packet correlation

For a verified client-to-map `0x000A`, the preserved `0x5C` inner packet can be compared with already-normalized `capture_raw_packets` evidence in the same capture.

This correlation is deliberately exact-only:

- raw hex is parsed to bytes;
- the complete inner packet must be byte-for-byte identical;
- timestamps are not used as a matching criterion;
- zero matches -> `unmatched`;
- one match -> `matched`;
- multiple byte-identical matches -> `ambiguous`;
- `automatic_merge_performed = false` in every case.

The metadata records SHA-256 of the compared inner bytes and peer row references, but does not create or merge canonical packet rows.

## PCAP metadata integration

Normal PCAP ingestion remains authoritative for:

- frame parsing;
- TCP reconstruction;
- gaps/retransmissions/conflicts;
- raw frame/range persistence;
- existing plaintext known-chunk promotion;
- validated lobby message insertion.

After one source file is ingested, the protocol metadata post-pass operates only on evidence already persisted for that capture/source. It exposes family/framing evidence through existing flow/frame metadata without schema, route, template, navigation, or CI workflow changes.

No fuzzy merge is attempted across captures, hosts, nearby timestamps, payload similarity, or common ports.

## Regression coverage

Synthetic fixtures now cover:

- valid and invalid lobby framing/MD5 cases;
- search clear framing, truncation, and resynchronization;
- exact cache-endpoint correlation and signature-only fail-closed behavior;
- map TCP transport mismatch;
- exact UDP map-endpoint association;
- valid map `0x000A` handshake;
- bad transport MD5;
- bad `LoginPacketCheck`;
- wrong opcode;
- truncated/oversized login datagrams;
- reverse-direction map-login rejection;
- exact normalized raw-packet correlation;
- idempotent PCAP reingestion.

The existing PCAP/TCP tests remain authoritative for legacy parsing and reassembly behavior.

## Not yet claimed

This slice does **not** claim:

- decrypted search/cache message types or fields;
- post-login encrypted map/game message semantics;
- Blowfish/session-key recovery;
- world/map TCP framing;
- gameplay meaning from changing unknown fields;
- storage/account subflow semantics;
- timestamp-only correlation;
- automatic cross-capture session merging.

The next high-value search target is a real search/cache capture tied to a verified lobby handoff. For map/game, the next step is evidence-backed correlation of real post-login UDP observations with already-normalized world packets or explicit server/client provenance, without attempting decryption unless key provenance is demonstrable.

See also `docs/workbench/MAP_UDP_HANDSHAKE_RESEARCH.md` for the focused map-handshake evidence notes.
