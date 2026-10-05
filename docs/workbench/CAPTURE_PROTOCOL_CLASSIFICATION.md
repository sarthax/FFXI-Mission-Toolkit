# Capture protocol classification — evidence model

Status: backend research slice on `feature/capture-protocol-research-next`.

This layer sits above generic PCAP/PCAPNG parsing and bidirectional TCP reconstruction. It is deliberately fail-closed: endpoint, framing, direction, cryptographic state, validation, and message semantics are separate claims and are promoted only when evidence supports each one.

## Current family inventory

| Family | Evidence | Current state | Payload semantics |
|---|---|---|---|
| Lobby / character service | `IXFF`, declared size, known command/layout, MD5, command direction | `ffxi_lobby`, verified only when all structural checks pass | Known lobby fields only; raw bytes retained |
| Search / cache endpoint | Exact verified `ResponseNextLogin.cache_ip/cache_port` TCP handoff plus clear length/`IXFF` framing | `ffxi_search_endpoint`, structurally inferred at flow level | Raw/framed bytes always retained |
| Search inbound request | Verified cache endpoint role + client->server direction + FFXI cipher decrypt + framing + post-decrypt MD5 | per-frame verified inbound evidence | Fixed fields plus source-backed `SEARCH/SEARCH_ALL` packed filters |
| Search outbound response | Explicit 24-byte state derived from the exact validated inbound predecessor + matching state seed + decrypt + framing + MD5 | cryptographically verified only when explicit predecessor state is supplied | Response payload remains opaque |
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

The lobby scanner preserves malformed/unknown evidence and reports truncation, unknown message types, invalid sizes, rejected candidates, framing resynchronization, and opaque trailing bytes. Diagnostics never weaken the existing requirement for a valid known lobby frame before promotion.

## Search/cache framing and inbound decryption

LandSandBoat establishes clear search framing with a little-endian total length at `0x00`, literal `IXFF` at `0x04..0x07`, and an encrypted/validated region beginning at `0x08`.

`search_framing.scan_range()` recognizes complete clear-header frame candidates. A search-looking header without the exact verified lobby cache handoff remains `unknown_tcp`.

Once the cache endpoint role is known, `search_framing.resolve_crypto_direction()` establishes the client -> search-server direction. Only that direction enters the automatic inbound decrypt path.

The inbound key is:

```text
MD5(fixed 16-byte SearchHandler prefix || final 4 bytes of the frame)
```

The toolkit implements the FFXI/LandSandBoat cipher variant independently in `ffxi_blowfish.py`. It is not interchangeable with generic textbook Blowfish: the packet primitive uses FFXI-specific round behavior while retaining the standard Blowfish-style key schedule and pi-derived seed constants.

Trusted inbound semantics are exposed only after exact cache endpoint role, client->server direction, successful cipher transform, exact length, `IXFF`, and post-decrypt MD5 all validate. Failed candidates remain evidence and expose no trusted fields.

For metadata compatibility, flow-level search classification remains structurally inferred and generic frame status remains `encrypted_or_opaque`; stronger per-frame evidence lives under `inbound_decryption`, `decryption_validated`, validated request type, and validated request fields.

### Currently decoded validated inbound requests

- `ID_LIST (0x01)`: requested count at `0x10`, character IDs from `0x12`, with the 20-entry/data-length cap.
- `GROUP_LIST (0x02)`: party/alliance/linkshell IDs at `0x10`, `0x14`, `0x18`, `0x1C`.
- `SEARCH_COMMENT (0x08)`: player ID at `0x10`.
- `SEARCH (0x03)` / `SEARCH_ALL (0x00)`: source-backed packed query grammar from `frame[0x11:]`, with query byte count at `0x10`.

For packed search requests, each entry retains exact bit start/end offsets, 5-bit `SearchType`, ordinary sort/present control bits where current LSB consumes them, decoded width/value where current LSB assigns one, and an explicit status.

Current decoded packed fields are Name, Area, Nation, Job, Level range, Race, Flags1, Rank range, Comment, Linkshell/Linkshell2 ID, Friend marker, and Flags2. Friend searches additionally decode the source-defined post-query `uint16` count plus `uint32` character-ID tail, capped to 200 and available complete IDs.

SearchType enum members that current LSB defines but leaves to `_HandleSearchRequest()`'s default branch (`Id`, `Party`, `LinkshellRank`, `Unknown0E`, `Language`) remain named but semantically unassigned. Unknown numeric types remain numeric/unknown. The toolkit does not guess missing widths for either category.

Auction House request/history bodies remain deliberately opaque on this branch.

### Explicit search outbound state

Server -> client search encryption is stateful. After a validated inbound decrypt, the server state is:

```text
key[0:16]  = fixed SearchHandler prefix
key[16:20] = exact inbound wire frame final 4 bytes
key[20:24] = exact inbound decrypted bytes[length-0x18 : length-0x14]
```

`derive_outbound_state()` accepts only the exact matching wire/decrypted inbound pair and refuses an unvalidated predecessor.

`decrypt_outbound_frame()` requires that explicit 24-byte state, checks clear length/`IXFF`, requires the outbound final 4 bytes to match state `key[16:20]`, derives the cipher key as `MD5(state[0:24])`, decrypts the aligned region, and validates the post-decrypt MD5.

This helper is intentionally **not auto-wired by timestamp or nearest-frame heuristics**. A successful outbound result proves the cryptographic envelope and predecessor state relationship only; response payload semantics stay `unknown_opaque`.

## Map/game transport and verified 0x000A handshake

LandSandBoat fills `ResponseNextLogin.server_ip/server_port` from the selected zone endpoint and modern map service uses UDP. A TCP flow hitting that numeric endpoint remains transport-mismatched `unknown_tcp` evidence.

For UDP, endpoint equality alone yields only structurally inferred `ffxi_map_endpoint` evidence with raw payload retained.

The initial non-encrypted client zone-login datagram can be verified more strongly:

```text
0x1C common world transport header
+ 0x5C inner GP_CLI_COMMAND_LOGIN packet
+ 0x10 final transport MD5 trailer
= 0x88 bytes total
```

`map_framing.inspect_login_datagram()` requires exact length, opcode `0x000A`, declared size `0x005C`, final MD5 over the inner packet, and valid `LoginPacketCheck`. `protocol_metadata` additionally requires the verified map endpoint to be the UDP destination because the packet is C -> S.

A fully verified frame uses `classification_validated=true`, certainty `verified`, and scope `verified_lobby_handoff_plus_verified_map_0x000A_udp_handshake`. Character/ticket/account/platform/language and unknown inner fields remain opaque.

## Exact normalized-packet correlation

For a verified client-to-map `0x000A`, the complete `0x5C` inner packet can be compared with existing `capture_raw_packets` evidence. Matching is byte-for-byte only; timestamps are not criteria. Zero matches are `unmatched`, one is `matched`, duplicates are `ambiguous`, and `automatic_merge_performed=false` always.

## PCAP metadata integration

Normal PCAP ingestion remains authoritative for frame parsing, TCP reconstruction, gaps/retransmissions/conflicts, raw frame/range persistence, existing plaintext chunk promotion, and validated lobby insertion. The protocol metadata pass operates only on persisted evidence from the same capture/source and exposes results through existing JSON metadata without schema, route, template, navigation, or CI-workflow changes.

No fuzzy merge is attempted across captures, hosts, nearby timestamps, payload similarity, or common ports.

## Regression coverage

Synthetic coverage includes:

- lobby structural/MD5 cases and resynchronization;
- search framing/truncation/resynchronization;
- exact cache-endpoint and inbound-direction resolution;
- deterministic FFXI-cipher compatibility and round trip;
- encrypted inbound request -> decrypt -> framing + MD5 validation;
- corrupted inbound ciphertext failing closed;
- reverse-direction traffic remaining untouched by automatic inbound logic;
- validated `SEARCH_COMMENT` field extraction from encrypted wire evidence;
- fixed-field `ID_LIST`, `GROUP_LIST`, `SEARCH_COMMENT` validation;
- packed `SEARCH` / `SEARCH_ALL` filters including friend-tail IDs and source caps;
- known-but-unhandled SearchType preservation and packed-block truncation fail-closed behavior;
- exact 24-byte outbound state extraction from a validated inbound request;
- synthetic server response -> stateful decrypt -> framing + MD5 validation with semantics still opaque;
- wrong predecessor state rejection;
- map TCP transport mismatch and exact UDP endpoint association;
- valid/invalid map `0x000A` handshake cases and reverse-direction rejection;
- exact normalized raw-packet correlation;
- idempotent PCAP reingestion.

Existing PCAP/TCP tests remain authoritative for legacy parsing and reassembly behavior.

## Not yet claimed

This slice does **not** claim:

- automatic response/predecessor pairing from timestamps or proximity;
- search server-response payload semantics;
- semantics/widths for SearchType values current LSB itself does not decode;
- Auction House search/history request or response semantics;
- post-login encrypted map/game semantics;
- world/map TCP framing;
- gameplay meaning from changing unknown fields;
- storage/account subflow semantics;
- automatic cross-capture session merging.

The highest-value next validation target is a real search/cache capture tied to a verified lobby handoff. Inbound frames can now be decoded through both fixed-field and packed query paths; outbound frames can be cryptographically validated when the exact predecessor state is known. Automated session sequencing should wait for real evidence with sufficiently precise frame ordering to avoid heuristic state association.

See `SEARCH_CRYPTO_ENVELOPE_RESEARCH.md` and `MAP_UDP_HANDSHAKE_RESEARCH.md` for focused evidence notes.
