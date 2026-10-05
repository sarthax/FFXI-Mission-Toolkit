# Search/cache crypto-envelope and inbound decryption research

Status: source-backed capture/protocol research on `feature/capture-protocol-research-next`.

## Proven inbound contract

Modern LandSandBoat `SearchHandler` accepts search/cache traffic over TCP. Clear framing remains:

- little-endian packet length at offset `0x00`;
- literal `IXFF` at offsets `0x04..0x07`;
- minimum observed packet length of 28 bytes.

For **client -> search server** traffic, `SearchHandler::decrypt()` performs a source-defined per-frame derivation:

1. start with the fixed 16-byte base prefix;
2. copy the frame's final 4 bytes into key bytes `16..19`;
3. calculate MD5 over those 20 key bytes;
4. use the resulting 16-byte digest to initialize the FFXI Blowfish variant;
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

## FFXI Blowfish compatibility

The FFXI/LandSandBoat packet cipher is **not wire-compatible with a generic textbook Blowfish library**. The key schedule uses the standard Blowfish P/S seed constants, but the packet primitive uses the FFXI-specific round function represented by the maintained server implementation.

`workbench.captures.ffxi_blowfish` is an independent, dependency-free implementation of that behavior. It uses standard Blowfish pi constants as data, the FFXI round behavior, and little-endian `uint32` packet words matching the server wire path. No GPL implementation code is copied into the MIT toolkit.

A deterministic compatibility vector is retained in the focused regression fixture:

```text
key        = 6A15DA0320124399517BDF754E670064
plaintext  = 0001020304050607
ciphertext = 00D103BFB60109A0
```

Decrypting that ciphertext with the same key returns the original block.

## Direction boundary

Inbound and outbound search crypto are not symmetric from capture evidence alone.

After an inbound decrypt, LSB copies four decrypted bytes from `length - 0x18` into key bytes `20..23`. Server-side encryption subsequently hashes the full 24-byte rolling key state. Therefore server -> client traffic is **not independently decryptable from an outbound frame alone** unless the preceding validated inbound state is available.

The toolkit consequently requires independent endpoint-role evidence before automatic decryption:

```text
direction_scope = client_to_search_server_only
applicability_requires_endpoint_role = true
```

`search_framing.resolve_crypto_direction()` derives the client-to-server direction from the verified lobby `cache_ip/cache_port` endpoint. Only that direction invokes inbound decryption. The reverse direction remains framed/opaque and carries an explicit direction-mismatch diagnostic.

## Toolkit implementation

`search_crypto_envelope.inspect_frame()` records the source-backed crypto envelope:

- clear header range;
- final 4-byte inbound seed;
- deterministic `MD5(fixed16 || seed4)` derived cipher key;
- exact encrypted byte span;
- exact post-decrypt MD5 input/hash offsets;
- packet-type offset `0x0B` with its value withheld until validation;
- outbound rolling-state dependency.

`search_crypto_envelope.decrypt_inbound_frame()` now performs the source-backed inbound operation:

1. inspect the envelope;
2. derive the per-frame key;
3. decrypt only the aligned encrypted span with `ffxi_blowfish`;
4. preserve the clear header and trailing seed bytes;
5. validate declared length and `IXFF`;
6. validate the post-decrypt MD5;
7. expose request type only if every gate succeeds.

Failed decrypt/validation attempts remain evidence with diagnostics and decrypted-candidate bytes, but they do not expose trusted request semantics.

The top-level framing status remains:

```text
decoder_status = encrypted_or_opaque
```

for metadata compatibility. Successful inbound frames carry their stronger result under `inbound_decryption` and set `decryption_validated=true`.

## Validated request types and fields

After framing + direction + decryption + MD5 succeed, the maintained request type table is used:

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

Unknown validated values remain numeric and `UNKNOWN`; no speculative name is assigned.

`search_request_decode.decode_validated_request()` currently decodes only the fixed-offset non-AH subset:

- `ID_LIST`: requested count at `0x10`, `uint32` character IDs from `0x12`, capped to 20 and available complete entries;
- `GROUP_LIST`: party/alliance/linkshell IDs at `0x10`, `0x14`, `0x18`, `0x1C`;
- `SEARCH_COMMENT`: player ID at `0x10`.

Each field carries source-backed offset/length evidence. `search_framing.resolve_crypto_direction()` automatically attaches this as `validated_request` after successful inbound decryption.

`SEARCH`/`SEARCH_ALL` remain body-opaque because their bit-packed filter grammar is a larger parser. All Auction House request/history bodies remain deliberately opaque in this branch to avoid collision with the parallel Auction House work.

## Regression coverage

Synthetic coverage now includes:

- deterministic FFXI-cipher block compatibility;
- encrypt/decrypt round trip;
- aligned-block rejection;
- exact inbound key derivation and encrypted span;
- endpoint-role direction gating;
- encrypted inbound `SEARCH_COMMENT` -> decrypt -> framing validation -> MD5 validation -> request type -> player ID;
- corrupted ciphertext failing closed before trusted request semantics;
- reverse-direction frame remaining undecrypted;
- existing ID-list/group-list/search-comment fixed-field validation.

The normal CI-enumerated lobby/capture regression also exercises the integrated search classification/decryption code path, while the focused positive cipher fixture remains a dedicated regression artifact.

## Current non-goals

This slice does not:

- decrypt server -> client traffic without prior validated inbound rolling state;
- infer or guess missing session state;
- decode `SEARCH`/`SEARCH_ALL` bit-packed filter grammar;
- decode Auction House search/history request bodies;
- promote a request type or fields when endpoint direction, framing, decryption, or MD5 validation fails;
- classify a search flow from framing alone without the independent verified lobby `cache_ip/cache_port` handoff.

## Next safe step

The highest-value validation target is now a **real search/cache capture tied to a verified lobby handoff**. Inbound frames can be tested directly against this implementation. Server -> client decryption should remain a separate stateful slice: it must carry forward the four decrypted key-continuation bytes from a previously validated inbound packet before any outbound semantics are trusted.
