# Capture protocol classification — evidence model

Status: backend research slice on `feature/capture-protocol-research-next`.

This layer sits above generic PCAP/PCAPNG parsing and bidirectional TCP reconstruction. It is deliberately fail-closed: endpoint, framing, direction, cryptographic state, validation, and message semantics are separate claims and are promoted only when evidence supports each one.

## Current family inventory

| Family | Evidence | Current state | Payload semantics |
|---|---|---|---|
| Lobby / character service | `IXFF`, declared size, known command/layout, MD5, command direction | `ffxi_lobby`, verified only when all structural checks pass | Known lobby fields only; raw bytes retained |
| Search / cache endpoint | Exact verified `ResponseNextLogin.cache_ip/cache_port` TCP handoff plus clear length/`IXFF` framing | `ffxi_search_endpoint`, structurally inferred at flow level | Raw/framed bytes always retained |
| Search inbound request | Verified cache endpoint role + client->server direction + FFXI cipher decrypt + framing + post-decrypt MD5 | per-frame verified inbound evidence | Fixed fields plus source-backed `SEARCH/SEARCH_ALL` packed filters |
| Search outbound response | Explicit 24-byte predecessor state + matching seed + decrypt + framing + MD5, followed by source-layout evidence | crypto-verified first; semantic promotion separate | Supported non-AH `0x80`, `0x82`, `0x88` layouts only |
| Map / game endpoint | Exact verified `ResponseNextLogin.server_ip/server_port` and UDP transport | `ffxi_map_endpoint`, structurally inferred from endpoint alone | Raw UDP payload retained |
| Map initial login | Exact verified map endpoint as UDP destination plus valid client `0x000A` structure | verified map-handshake evidence | Handshake structure only; semantic fields remain opaque |
| Other TCP / UDP | Insufficient evidence | unknown / endpoint-only | Opaque |

Default ports, timestamps, or signatures alone are never proof.

## Certainty vocabulary

- `verified` — demonstrated structure/source relationship passes its validation checks.
- `verified_observation` — directly observed transport/header fact.
- `structurally_inferred` — family association follows from verified evidence, but some semantics remain unproven.
- `unknown_opaque` — bytes retained without assigned meaning.
- `ambiguous` — more than one equally valid interpretation remains; classification fails closed.

## Lobby diagnostics

The lobby scanner preserves malformed/unknown evidence and reports truncation, unknown message types, invalid sizes, rejected candidates, framing resynchronization, and opaque trailing bytes. Diagnostics never weaken the requirement for a valid known lobby frame before promotion.

## Search/cache request path

LandSandBoat establishes clear search framing with a little-endian total length at `0x00`, literal `IXFF` at `0x04..0x07`, and an encrypted/validated region beginning at `0x08`.

`search_framing.scan_range()` recognizes complete clear-header frame candidates. A search-looking header without the exact verified lobby cache handoff remains `unknown_tcp`.

Once the cache endpoint role is known, `search_framing.resolve_crypto_direction()` establishes the client -> search-server direction. Only that direction enters automatic inbound decryption. The source-backed per-frame key is:

```text
MD5(fixed 16-byte SearchHandler prefix || final 4 bytes of the frame)
```

The toolkit implements the FFXI/LandSandBoat cipher variant independently in `ffxi_blowfish.py`. Trusted inbound semantics are exposed only after exact cache endpoint role, client->server direction, successful cipher transform, exact length, `IXFF`, and post-decrypt MD5 all validate.

### Decoded validated inbound requests

- `ID_LIST (0x01)`: requested count at `0x10`, character IDs from `0x12`, capped by source limit/data length.
- `GROUP_LIST (0x02)`: party/alliance/linkshell IDs at `0x10`, `0x14`, `0x18`, `0x1C`.
- `SEARCH_COMMENT (0x08)`: player ID at `0x10`.
- `SEARCH (0x03)` / `SEARCH_ALL (0x00)`: source-backed packed query grammar from `frame[0x11:]`, with query byte count at `0x10`.

Packed filters retain exact bit offsets, 5-bit `SearchType`, ordinary sort/present bits where current LSB consumes them, and decoded values only where current LSB assigns widths. Supported fields are Name, Area, Nation, Job, Level range, Race, Flags1, Rank range, Comment, Linkshell/Linkshell2 ID, Friend marker, and Flags2. Friend searches also decode the source-defined post-query ID tail, capped to 200 and complete available IDs.

SearchType members current LSB defines but leaves unhandled (`Id`, `Party`, `LinkshellRank`, `Unknown0E`, `Language`) remain named but semantically unassigned. Unknown numeric types remain unknown. Auction House request/history bodies remain opaque.

## Explicit search outbound state

Server -> client search encryption is stateful. After a validated inbound decrypt, the server state is:

```text
key[0:16]  = fixed SearchHandler prefix
key[16:20] = exact inbound wire frame final 4 bytes
key[20:24] = exact inbound decrypted bytes[length-0x18 : length-0x14]
```

`derive_outbound_state()` accepts only the exact matching wire/decrypted inbound pair. `decrypt_outbound_frame()` requires that 24-byte state, checks clear length/`IXFF`, requires the outbound final 4 bytes to match state `key[16:20]`, derives the cipher key as `MD5(state[0:24])`, decrypts the aligned region, and validates post-decrypt MD5.

This path is intentionally **not auto-wired by timestamp or nearest-frame heuristics**. Crypto validation proves the state relationship; response semantics require an additional source-layout evidence gate.

## Validated non-AH search responses

`search_response_decode.decode_validated_outbound()` performs structural parsing only after outbound crypto validation. `search_response_evidence.decode_validated_outbound()` is the fail-closed semantic promotion layer.

Supported source-backed discriminators/layouts are:

- `0x80` — search result list. `uint16 total_results` at `0x0E`, data size at `0x08`, size-prefixed packed entities from `0x18`.
- `0x88` — search comment. Current source fixes wire length 204, `0x08=154`, `0x0A=0x80`, `0x0E=1`, player ID at `0x18`, comment-length constant 124 at `0x1C`, comment region from `0x1E`, and terminator at `0x9A`.
- `0x82` — shared party/linkshell list discriminator. The type alone never proves which family it is.

Packed result entities decode only source-emitted widths: Name, Area, Nation, main/sub Job, main/sub Level, Race, Rank, Flags1, 20-bit Id, LinkshellRank with three ranks/IDs, preserved Unknown0E, Comment, Flags2, and Language. Unknown entity entry types stop that entity's semantic decode and preserve the raw remainder.

### `0x82` ambiguity policy

Strong promotion paths are:

- exact validated `GROUP_LIST` predecessor with nonzero party/alliance ID -> party list;
- exact validated `GROUP_LIST` predecessor with nonzero linkshell ID -> linkshell list;
- without predecessor context, fully decoded source-unique `LinkshellRank` layout -> structurally inferred linkshell list.

A well-formed `0x82` with no exact predecessor and no unique linkshell structure remains `party_or_linkshell_list`. If predecessor and payload structure contradict each other, semantic promotion fails closed as `ambiguous_conflicting_predecessor_and_payload_structure`; family-dependent totals are replaced by both raw `uint8` and `uint16` observations at `0x0E`.

### `0x88` fixed-layout policy

A crypto-valid `0x88` is not enough for semantic promotion. All source-fixed constructor facts must match. Wrong length, fixed size byte, final flag, count byte, comment-length constant, or terminator leaves raw/decrypted evidence intact but clears promoted semantic fields and reports `crypto_validated_source_layout_mismatch`.

Auction House search/history response bodies remain deliberately opaque.

## Map/game transport and verified `0x000A` handshake

LandSandBoat fills `ResponseNextLogin.server_ip/server_port` from the selected zone endpoint and modern map service uses UDP. A TCP flow hitting that endpoint remains transport-mismatched `unknown_tcp` evidence.

For UDP, endpoint equality alone yields only structurally inferred `ffxi_map_endpoint` evidence. The initial client zone-login can be verified more strongly as:

```text
0x1C common world transport header
+ 0x5C inner GP_CLI_COMMAND_LOGIN packet
+ 0x10 final transport MD5 trailer
= 0x88 bytes total
```

`map_framing.inspect_login_datagram()` requires exact length, opcode `0x000A`, declared size `0x005C`, final MD5 over the inner packet, and valid `LoginPacketCheck`. Direction must also be client -> verified map endpoint. Character/ticket/account/platform/language and unknown inner fields remain opaque.

## Exact normalized-packet correlation

For a verified client-to-map `0x000A`, the complete `0x5C` inner packet can be compared with existing `capture_raw_packets` evidence. Matching is byte-for-byte only; timestamps are not criteria. Zero matches are `unmatched`, one is `matched`, duplicates are `ambiguous`, and `automatic_merge_performed=false` always.

## PCAP metadata integration

Normal PCAP ingestion remains authoritative for frame parsing, TCP reconstruction, gaps/retransmissions/conflicts, raw frame/range persistence, existing plaintext chunk promotion, and validated lobby insertion. The protocol metadata pass operates only on persisted evidence from the same capture/source and exposes results through existing JSON metadata without schema, route, template, navigation, or CI-workflow changes.

No fuzzy merge is attempted across captures, hosts, nearby timestamps, payload similarity, or common ports.

## Regression coverage

Synthetic coverage includes lobby framing/MD5, search framing and crypto, fixed and packed inbound requests, explicit 24-byte outbound state, non-AH `0x80`/`0x82`/`0x88` response parsing, `0x82` ambiguity/conflict handling, fixed-layout `0x88` rejection, map transport/handshake failures, exact packet correlation, and idempotent reingestion.

Existing PCAP/TCP tests remain authoritative for legacy parsing and reassembly behavior.

## Not yet claimed

This slice does **not** claim:

- automatic response/predecessor pairing from timestamps or proximity;
- semantics/widths for SearchType values current LSB itself does not decode;
- Auction House search/history request or response semantics;
- unsupported search response families from resemblance alone;
- post-login encrypted map/game semantics;
- world/map TCP framing;
- gameplay meaning from changing unknown fields;
- storage/account subflow semantics;
- automatic cross-capture session merging.

The highest-value next validation target is a real search/cache capture tied to a verified lobby handoff. Inbound requests and supported outbound responses can now be validated without heuristic state association; automated sequencing should wait for real frame-order evidence strong enough to select the exact predecessor state without guessing.

See `SEARCH_CRYPTO_ENVELOPE_RESEARCH.md` and `MAP_UDP_HANDSHAKE_RESEARCH.md` for focused evidence notes.
