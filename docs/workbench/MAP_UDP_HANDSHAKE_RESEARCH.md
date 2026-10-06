# Map/game UDP handshake research

Status: evidence-backed capture/protocol research on `feature/capture-protocol-research-next`.

## Verified source facts

Modern LandSandBoat assigns `ResponseNextLogin.server_ip/server_port` from the selected zone endpoint and the map service listens on UDP. The map socket forwards each UDP datagram unchanged to `MapNetworking::handle_incoming_packet()`.

Before a map session is established, `MapNetworking::recv_parse()` accepts a non-encrypted client login only after structural validation:

1. the common world transport header is `0x1C` bytes;
2. the first inner packet id, masked with `0x01FF`, is `0x000A`;
3. XiPackets documents that inner `GP_CLI_COMMAND_LOGIN` packet as `0x005C` bytes;
4. the separate final 16-byte transport checksum matches MD5 over the complete inner packet;
5. `LoginPacketCheck` matches the byte-sum validation used by the server.

The minimum structurally complete datagram for this handshake is therefore:

```text
0x1C common transport header
+ 0x5C inner GP_CLI_COMMAND_LOGIN packet
+ 0x10 transport MD5 trailer
= 0x88 bytes
```

XiPackets documents `GP_CLI_COMMAND_LOGIN` as C -> S, opcode `0x000A`, declared inner size `0x005C`.

## Toolkit behavior

`workbench.captures.map_framing.inspect_login_datagram()` recognizes only this initial non-encrypted handshake. It verifies:

- opcode `0x000A`;
- declared inner size `0x005C`;
- transport MD5 trailer over the complete inner packet;
- `LoginPacketCheck` byte-sum.

It intentionally does **not** decode character id, account/ticket material, platform, language, or unknown fields. The complete raw datagram and opaque inner packet remain available.

`protocol_metadata` combines this structural proof with the exact `ResponseNextLogin.server_ip/server_port` handoff and transport direction. A frame becomes verified map-handshake evidence only when:

- it is UDP;
- the verified map endpoint is the datagram destination;
- the `0x000A` structure passes all checks above.

A structurally matching payload in the reverse direction fails closed with `map_login_direction_mismatch`.

Verified frames use:

```text
protocol_family = ffxi_map_endpoint
classification_validated = true
classification_certainty = verified
classification_scope = verified_lobby_handoff_plus_verified_map_0x000A_udp_handshake
decoder_status = verified_handshake_structure_payload_fields_opaque
```

Endpoint-only UDP traffic remains only `structurally_inferred` and keeps `raw_udp_payload_preserved`.

## Regression coverage

Small synthetic fixtures cover:

- valid `0x000A` handshake;
- bad transport MD5;
- bad `LoginPacketCheck`;
- wrong opcode;
- truncation;
- same-PCAP verified lobby handoff + client-to-map handshake;
- reverse-direction rejection;
- raw payload preservation;
- idempotent reingestion.

## Still unknown

This work does not claim framing or semantic decode for encrypted post-login map datagrams. After the verified `0x000A`, LandSandBoat uses session Blowfish state, validates packet checksums, and decompresses packet data before inner packet parsing. Those later stages should not be reproduced in the capture pipeline until a real capture/session key source or another demonstrably valid evidence path is available.

The next safe map/game step is cross-plane evidence correlation: link verified map-session UDP observations to already-normalized world packet evidence only through exact raw/structural matches or explicit source provenance, never by timestamp similarity alone.
