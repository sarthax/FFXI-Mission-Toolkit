# FFXI Lobby, Search/Cache, and World/Map Stream Research

Date: 2026-09-28

Purpose: define the non-zone network evidence planes that the Capture subsystem does not yet decode, without conflating retail protocol behavior, private-server loader architecture, or ordinary Windower/Ashita world-packet hooks.

## Executive summary

FFXI network traffic is not one homogeneous packet stream.

For capture/research purposes, the useful model is:

1. **Lobby / character-service TCP**
2. **Search / cache TCP**
3. **World / map UDP**
4. **Private-server loader/auth/profile channels**, which may exist in emulator deployments but are not automatically evidence of retail protocol topology.

The toolkit already has strong support for addon-level world/map packet observations and bounded PCAP/PCAPNG frame preservation. It does **not** yet perform session-aware TCP stream reassembly and protocol decoding for lobby or search/cache traffic.

## Plane 1 — Retail lobby / character service

### Confirmed responsibilities

The XiPackets lobby protocol documentation identifies the lobby service as responsible for:

- FFXI service login/setup
- character list retrieval
- world list retrieval
- character selection
- character creation
- character deletion
- character rename
- lobby error/status handling

Character selection returns the information needed to connect to the game/world server and also supplies the search/cache server address and port.

### Transport and framing

XiPackets documents the retail lobby connection as TCP, normally using port 54001.

The common lobby packet header is structurally different from world/map packets:

- 32-bit packet size
- 32-bit `FFXI`/terminator value
- 32-bit command
- 16-byte MD5 identifier/checksum
- command-specific payload

This is **not** the 4-byte world packet header and must never be passed through the ordinary world-packet decoder.

### Client-capability relevance

The lobby response-key flow carries expansion/feature capability bits. XiPackets documents `excode_server2` feature bits including Wardrobes 3–8. This makes lobby evidence directly relevant to client-capability research, but decoding it from captured retail traffic should be implemented only after TCP stream reassembly and validated lobby framing exist.

## Plane 2 — Search / cache TCP

### Confirmed responsibilities

Current LandSandBoat search-server source independently confirms a separate TCP service for:

- player search
- search-all / ID-list requests
- party/group lists
- linkshell lists
- search comments
- auction-house listings
- auction-house history

Current request types include:

- `TCP_SEARCH_ALL`
- `TCP_ID_LIST`
- `TCP_GROUP_LIST`
- `TCP_SEARCH`
- `TCP_AH_HISTORY_SINGLE`
- `TCP_AH_HISTORY_STACK`
- `TCP_SEARCH_COMMENT`
- `TCP_AH_REQUEST_MORE`
- `TCP_AH_REQUEST`

Search filters include name, area, nation, job, level, race, party, linkshell, friend, rank, comment, language, and related flags.

### Transport and framing

LandSandBoat listens for search clients over TCP. Its search handler uses its own:

- packet-size framing
- `IXFF` marker on server-generated packets
- MD5 validation
- Blowfish encryption/decryption
- rolling/session key material

This protocol is distinct from both lobby packets and the UDP world/map packet chunks.

### What is **not** confirmed here

Do not classify arbitrary storage/account operations as search/cache traffic without packet or client evidence.

The current source clearly proves search, linkshell/party/comment, and auction functions. Storage/inventory traffic should remain attributed to whatever packet/service evidence actually demonstrates it.

## Plane 3 — World / map / zone UDP

This is the packet family the toolkit already understands best.

### Transport

World/map traffic uses UDP.

### Embedded packet chunks

After the relevant transport/session processing, the familiar FFXI packet chunk header is:

- 9-bit packet id/opcode
- 7-bit size value multiplied by 4
- 16-bit sync counter

This is the format exposed by PacketViewer, PacketLogger, Packeteer, PacketDB, EventView-derived evidence, and the toolkit's canonical raw-packet layer.

### Existing toolkit coverage

The Capture subsystem already supports:

- PacketLogger / PacketViewer
- PacketDB
- Packeteer
- NPCLogger-preserved raw bytes
- EventView raw/session evidence
- cross-source exact-byte packet correlation
- PCAP/PCAPNG frame preservation
- conservative promotion of already-plaintext UDP payloads when the complete payload validates as known FFXI chunks

The PCAP adapter does not guess decryption/compression state.

## Plane 4 — Private-server loader/auth/profile channels

Modern LandSandBoat exposes additional TCP endpoints such as:

- login view
- login data
- login auth
- profile
- internal ZMQ routing

Current LSB auth also uses TLS/JSON for xiloader authentication.

These are important when researching private-server deployments, but they must not be presented as proof that retail FFXI uses the same socket topology or payload grammar.

The Workbench should model these as **implementation-specific transport surfaces** tied to a server/fork snapshot, not universal retail protocol facts.

## Capture-tool visibility

### Windower/Ashita addon packet hooks

The ordinary addon packet ecosystem primarily exposes the world/map packet-chunk layer after the game client has already handled lower-level network/session transport.

That is why PacketViewer-style tools are excellent for mission/runtime research but generally do not provide lobby/search wire traffic.

### PacketBridge

Captain PacketBridge can forward addon-visible packet chunks over UDP. It is useful as a possible future live capture source, but it is still forwarding the addon/world-packet plane rather than magically exposing independent lobby/search TCP sockets.

### PCAP/PCAPNG

PCAP is the current toolkit path for preserving all connection planes without assuming protocol identity.

Today it preserves exact frames/endpoints/timestamps. Future lobby/search work should build on that evidence rather than adding port-only heuristics to `capture_raw_packets`.

## Proposed implementation sequence

### P1 — TCP flow reconstruction

Add a generic PCAP TCP-flow layer that:

- groups by normalized 5-tuple
- preserves direction as endpoint A/B until roles are proven
- tracks sequence numbers
- reconstructs contiguous byte ranges
- records gaps, retransmissions, overlap, and out-of-order segments
- never fabricates missing bytes
- keeps exact contributing frame references

Output should remain generic transport evidence first.

### P2 — Protocol classification by validated signatures

Classify reconstructed streams using structural evidence, not port numbers alone.

Candidate classes:

- `ffxi_lobby`
- `ffxi_search_cache`
- `lsb_xiloader_auth`
- `lsb_login_data`
- `lsb_profile`
- unknown TCP

Ports may be retained as supporting evidence, but should not be sufficient to declare a protocol.

### P3 — Lobby framing/decoder — IMPLEMENTED

Implemented on top of reconstructed TCP ranges. Classification requires a complete known-command packet with exact size/layout, IXFF terminator, and a valid MD5 identifier after zeroing the identifier field. No port-only classification is used. Validated messages are persisted in `capture_network_messages`, and consistent request/response direction may establish client/server endpoint roles.

Current useful records:

- request/response command
- packet size
- MD5 validation status
- world list
- character list metadata
- selected world/server endpoint
- returned search/cache endpoint
- expansion/feature bitfields where source layout is known

Sensitive authentication/session values should be preserved cautiously and not promoted into routine GUI summaries.

### P4 — Search/cache decoder

Implement session-aware search TCP framing only after a real capture fixture is available.

Requirements:

- TCP reassembly
- Blowfish state/key derivation matching the actual captured protocol generation
- MD5 validation
- request-type decoding
- auction/search/group/comment observations
- independent provenance for ciphertext and decoded records

### P5 — Cross-plane correlation

Once lobby/search decoders exist, correlate:

- lobby-selected character
- returned world/map endpoint
- returned search/cache endpoint
- subsequent TCP/UDP connections
- shared timestamps / server identity
- world/map capture sessions

This should create relationships between evidence planes without merging their source observations.

## Data-model recommendation

Do not put lobby/search records directly into `capture_raw_packets`.

Use a transport/protocol evidence layer such as:

- `capture_network_flows`
- `capture_network_messages`

with fields for:

- capture id
- source file
- flow id
- protocol family
- endpoint A/B
- transport
- message sequence
- timestamp/range
- ciphertext/raw bytes
- decoded payload/fields
- validation status
- decoder version
- exact contributing frame locators

World/map FFXI chunks can continue to use `capture_raw_packets`.

## Open questions

- Retail search/cache framing should be verified against a real retail PCAP and/or additional client reversing before assuming current LSB's implementation is byte-identical.
- Exact retail search/cache port assignment can vary by returned connection data; do not classify solely on 54002.
- Determine which non-zone features, beyond confirmed search/AH/group/comment operations, use the search/cache connection.
- Determine which inventory/storage flows remain world/map packets versus any separate service. Do not infer from feature names.
- Decide whether LSB/xiloader auth/profile traffic belongs in Capture ingestion or a separate server-integration diagnostics layer.
- Capture a real login-to-character-select-to-zone PCAP so endpoint handoff can be validated end-to-end.

## Source basis

Primary references used for this research:

- atom0s/XiPackets lobby protocol/header/notes and world header documentation
- current LandSandBoat `settings/default/network.lua`
- current LandSandBoat login `connect_engine`, `auth_session`, `data_session`, and lobby packet structures
- current LandSandBoat search listener/handler/request types

The distinction between retail protocol and private-server implementation is intentional and must be retained in future documentation and code.
