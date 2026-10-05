# Capture protocol classification — evidence model

Status: backend research slice on `feature/capture-protocol-research-next`.

This layer sits above generic PCAP/PCAPNG parsing and bidirectional TCP reconstruction. It is deliberately fail-closed: endpoint, framing, direction, cryptographic validation, and message semantics are separate claims and are promoted only when evidence supports each one.

## Current family inventory

| Family | Evidence | Current state | Payload semantics |
|---|---|---|---|
| Lobby / character service | `IXFF`, declared size, known command/layout, MD5, command direction | `ffxi_lobby`, verified only when all structural checks pass | Known lobby fields only; raw bytes retained |
| Search / cache endpoint | Exact verified `ResponseNextLogin.cache_ip/cache_port` TCP handoff plus clear length/`IXFF` framing | `ffxi_search_endpoint`, structurally inferred at flow level | Raw/framed bytes always retained |
| Search inbound request | Verified cache endpoint role + client->server direction + FFXI cipher decrypt + clear framing + post-decrypt MD5 | per-frame verified inbound evidence | Request type; fixed fields for `ID_LIST`, `GROUP_LIST`, `SEARCH_COMMENT` only |
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

LandSandBoat establishes the clear search framing:

- little-endian total length at offset `0x00`;
- literal `IXFF` at offsets `0x04..0x07`;
- encrypted/validated region beginning at offset `0x08`.

`search_framing.scan_range()` recognizes complete clear-header frame candidates. A search-looking header without the exact verified lobby cache handoff still remains `unknown_tcp`.

Once the exact cache endpoint role is known, `search_framing.resolve_crypto_direction()` establishes which reconstructed direction is client -> search server. Only that direction may enter the inbound decrypt path.

The inbound key is derived from source-backed evidence:

```text
MD5(fixed 16-byte SearchHandler prefix || final 4 bytes of the frame)
```

The toolkit implements the FFXI/LandSandBoat cipher variant independently in `ffxi_blowfish.py`. It is not interchangeable with generic textbook Blowfish: the FFXI packet primitive uses its own round function while retaining the standard Blowfish-style key schedule and standard pi-derived seed constants.

`search_crypto_envelope.decrypt_inbound_frame()` decrypts only the source-defined aligned region. Trusted request semantics are exposed only after:

1. exact verified cache endpoint role;
2. client -> server direction;
3. successful FFXI-cipher transformation;
4. declared frame length equals observed length;
5. `IXFF` remains present;
6. post-decrypt MD5 matches.

Failed decryption/validation remains preserved as evidence and does not produce trusted packet fields.

For compatibility, flow-level search classification remains structurally inferred and the generic frame status remains `encrypted_or_opaque`; stronger per-frame results live under `inbound_decryption`, `decryption_validated`, validated packet type, and validated request evidence.

### Currently decoded validated inbound requests

- `ID_LIST (0x01)`: requested count at `0x10`, character IDs from `0x12`, with LSB's 20-entry/data-length cap.
- `GROUP_LIST (0x02)`: party/alliance/linkshell IDs at `0x10`, `0x14`, `0x18`, `0x1C`.
- `SEARCH_COMMENT (0x08)`: player ID at `0x10`.

`SEARCH/SEARCH_ALL` bit-packed bodies remain opaque. Auction House request/history bodies remain deliberately opaque on this branch.

### Search outbound boundary

Server -> client search encryption is stateful. LSB extends the key with four bytes obtained from a previously decrypted inbound request, then hashes the full rolling 24-byte key state for outbound encryption. The toolkit therefore does not attempt stateless outbound decryption and never applies the inbound key derivation to reverse-direction frames.

## Map/game transport and verified 0x000A handshake

LandSandBoat fills `ResponseNextLogin.server_ip/server_port` from the selected zone endpoint and the modern map service listens on UDP. A TCP flow hitting that numeric endpoint is transport-mismatched evidence and remains `unknown_tcp`.

For UDP, endpoint equality alone yields only structurally inferred `ffxi_map_endpoint` evidence with raw UDP payload preserved.

The initial non-encrypted client zone-login datagram can be verified more strongly:

```text
0x1C common world transport header
+ 0x5C inner GP_CLI_COMMAND_LOGIN packet
+ 0x10 final transport MD5 trailer
= 0x88 bytes total
```

`map_framing.inspect_login_datagram()` requires exact length, opcode `0x000A`, declared size `0x005C`, final MD5 over the complete inner packet, and valid `LoginPacketCheck`. `protocol_metadata` additionally requires the verified map endpoint to be the UDP destination because the packet is C -> S.

A fully verified frame uses `classification_validated=true`, certainty `verified`, and the scope `verified_lobby_handoff_plus_verified_map_0x000A_udp_handshake`. Character/ticket/account/platform/language and unknown inner fields remain intentionally opaque.

## Exact normalized-packet correlation

For a verified client-to-map `0x000A`, the complete `0x5C` inner packet can be compared with existing `capture_raw_packets` evidence. Matching is byte-for-byte only; timestamps are not matching criteria. Zero matches are `unmatched`, one is `matched`, duplicates are `ambiguous`, and `automatic_merge_performed=false` always.

## PCAP metadata integration

Normal PCAP ingestion remains authoritative for frame parsing, TCP reconstruction, gap/retransmission/conflict evidence, raw frame/range persistence, existing plaintext chunk promotion, and validated lobby insertion. The protocol metadata pass operates only on persisted evidence from the same capture/source and exposes results through existing JSON metadata without schema, route, template, navigation, or CI-workflow changes.

No fuzzy merge is attempted across captures, hosts, nearby timestamps, payload similarity, or common ports.

## Regression coverage

Synthetic coverage now includes:

- lobby structural/MD5 cases and resynchronization;
- search framing/truncation/resynchronization;
- exact cache-endpoint and direction resolution;
- deterministic FFXI-cipher block compatibility and round trip;
- encrypted inbound search request -> decrypt -> framing + MD5 validation;
- corrupted ciphertext failing closed;
- reverse-direction search traffic remaining undecrypted;
- validated `SEARCH_COMMENT` field extraction from encrypted wire evidence;
- fixed-field `ID_LIST`, `GROUP_LIST`, and `SEARCH_COMMENT` body validation;
- map TCP transport mismatch;
- exact UDP map-endpoint association;
- valid/invalid map `0x000A` handshake cases;
- reverse-direction map-login rejection;
- exact normalized raw-packet correlation;
- idempotent PCAP reingestion.

The existing PCAP/TCP tests remain authoritative for legacy parsing and reassembly behavior.

## Not yet claimed

This slice does **not** claim:

- stateless server -> client search decryption;
- `SEARCH/SEARCH_ALL` bit-packed filter semantics;
- Auction House search/history request-body semantics;
- post-login encrypted map/game semantics;
- world/map TCP framing;
- gameplay meaning from changing unknown fields;
- storage/account subflow semantics;
- timestamp-only correlation;
- automatic cross-capture session merging.

The highest-value search validation target is now a real search/cache capture tied to a verified lobby handoff. For outbound search, the next decoder step must explicitly carry rolling state from a previously validated inbound packet. For map/game, the next step remains evidence-backed correlation of real post-login UDP observations with normalized world packets or explicit server/client provenance.

See `SEARCH_CRYPTO_ENVELOPE_RESEARCH.md` and `MAP_UDP_HANDSHAKE_RESEARCH.md` for focused evidence notes.
