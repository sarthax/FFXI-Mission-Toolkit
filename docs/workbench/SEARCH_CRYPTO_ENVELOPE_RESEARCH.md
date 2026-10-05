# Search/cache crypto-envelope research

Status: source-backed capture/protocol research on `feature/capture-protocol-research-next`.

## Proven inbound contract

Modern LandSandBoat `SearchHandler` accepts search/cache traffic over TCP. Clear framing remains:

- little-endian packet length at offset `0x00`;
- literal `IXFF` at offsets `0x04..0x07`;
- minimum observed packet length of 28 bytes.

For **client -> search server** traffic, `SearchHandler::decrypt()` then performs a source-defined per-frame derivation:

1. start with the handler's fixed 16-byte base prefix;
2. copy the frame's final 4 bytes into key bytes `16..19`;
3. calculate MD5 over those 20 key bytes;
4. use the resulting 16-byte digest to initialize Blowfish;
5. decrypt aligned 8-byte blocks beginning at frame offset `0x08`.

The encrypted word count mirrors LSB exactly:

```text
words = floor((length - 12) / 4)
words -= words % 2
encrypted bytes = words * 4
```

After decryption, `SearchHandler::validatePacket()` calculates MD5 over:

```text
frame[0x08 : length - 0x14]
```

and compares it to the 16 bytes at:

```text
frame[length - 0x14 : length - 0x04]
```

Only after that validation succeeds does LSB read the request type at offset `0x0B`.

The source-defined request type names currently exposed by LSB are:

| Value | Name |
|---:|---|
| `0x00` | `SEARCH_ALL` |
| `0x01` | `ID_LIST` |
| `0x02` | `GROUP_LIST` |
| `0x03` | `SEARCH` |
| `0x05` | `AH_HISTORY_SINGLE` |
| `0x06` | `AH_HISTORY_STACK` |
| `0x08` | `SEARCH_COMMENT` |
| `0x10` | `AH_REQUEST_MORE` |
| `0x15` | `AH_REQUEST` |

Unknown validated request bytes remain numeric and are reported as `UNKNOWN`; no speculative name is assigned.

## Direction boundary

This derivation must not be applied blindly to server -> client traffic.

After an inbound decrypt, LSB also copies four decrypted bytes from `length - 0x18` into key bytes `20..23`. Server-side `encrypt()` subsequently hashes the full 24-byte rolling key state. Therefore the outbound key is **not independently reconstructable from the outbound frame alone** unless the preceding inbound state is known and successfully decrypted.

The toolkit consequently marks this contract:

```text
direction_scope = client_to_search_server_only
applicability_requires_endpoint_role = true
```

Once the verified cache-server endpoint role is known, `search_framing.resolve_crypto_direction()` marks each framed observation with the resolved client-to-server direction and whether the inbound derivation is applicable. Server-to-client frames receive an explicit direction-mismatch diagnostic rather than a usable inbound-key claim.

## Toolkit implementation

`workbench.captures.search_crypto_envelope.inspect_frame()` records, without decrypting:

- clear header range;
- final 4-byte per-frame inbound seed;
- deterministic MD5-derived Blowfish key for the inbound contract;
- exact encrypted byte span;
- exact post-decrypt MD5 input and expected-hash offsets;
- packet-type offset `0x0B`, with value intentionally withheld;
- the rolling-state dependency required for server -> client encryption.

`search_framing.scan_range()` attaches this information under `crypto_envelope` to accepted clear-framing candidates while retaining the existing top-level:

```text
decoder_status = encrypted_or_opaque
```

for metadata compatibility. The presence of envelope metadata does not mean decryption succeeded.

`search_crypto_envelope.validate_decrypted_frame()` accepts already-decrypted inbound candidate bytes and repeats the full source-backed gate: declared length, `IXFF`, then post-decrypt MD5. A packet type and source-defined request name are returned only after all checks pass. A known value is marked `known_request_type=true`; an unlisted value remains `UNKNOWN` with the validated numeric byte preserved.

## Validated basic request fields

`workbench.captures.search_request_decode.decode_validated_request()` layers a deliberately small request-body decoder on top of that validator. It currently exposes only fields that current LSB reads directly at fixed offsets:

### `ID_LIST` (`0x01`)

- requested count: `uint16` at `0x10`;
- character IDs: `uint32[]` from `0x12`;
- count is capped exactly as LSB does: requested count, maximum 20, and the number of complete IDs available before the 20-byte search trailer.

### `GROUP_LIST` (`0x02`)

- party ID: `uint32` at `0x10`;
- alliance ID: `uint32` at `0x14`;
- linkshell ID 1: `uint32` at `0x18`;
- linkshell ID 2: `uint32` at `0x1C`.

### `SEARCH_COMMENT` (`0x08`)

- player ID: `uint32` at `0x10`.

Every decoded field carries offset/length certainty metadata. Truncated bodies remain validated at the frame level but are not decoded past the available bytes.

Known request types not covered above remain body-opaque. In particular, this slice does **not** decode `SEARCH`/`SEARCH_ALL` bit-packed filters or any Auction House request/history body, even after type validation.

## Current non-goals

This slice does not:

- introduce a Blowfish dependency;
- vendor a Blowfish implementation;
- guess session state;
- decrypt server -> client traffic without prior inbound state;
- assign request semantics from encrypted bytes;
- decode `SEARCH`/`SEARCH_ALL` bit-packed filter grammar;
- decode Auction House search/history request bodies;
- promote a packet type when framing or post-decrypt MD5 fails;
- classify a search flow from framing alone without the independent verified lobby `cache_ip/cache_port` handoff.

## Next safe step

A later decoder slice can add an isolated Blowfish implementation or optional dependency only after a fixture proves byte-for-byte compatibility with LSB. The first target should be a synthetic inbound frame generated from the same source contract, followed by a real capture tied to a verified lobby search/cache handoff. Server -> client decryption should remain a separate stateful step because it depends on key continuation extracted from a successfully decrypted inbound packet.
