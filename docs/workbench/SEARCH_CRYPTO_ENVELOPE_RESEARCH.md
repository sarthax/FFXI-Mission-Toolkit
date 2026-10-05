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

## Direction boundary

This derivation must not be applied blindly to server -> client traffic.

After an inbound decrypt, LSB also copies four decrypted bytes from `length - 0x18` into key bytes `20..23`. Server-side `encrypt()` subsequently hashes the full 24-byte rolling key state. Therefore the outbound key is **not independently reconstructable from the outbound frame alone** unless the preceding inbound state is known and successfully decrypted.

The toolkit consequently marks this contract:

```text
direction_scope = client_to_search_server_only
applicability_requires_endpoint_role = true
```

and does not claim outbound decryption.

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

`search_crypto_envelope.validate_decrypted_frame()` accepts already-decrypted candidate bytes and performs only the post-decrypt MD5 gate. A packet type is returned only when that MD5 matches.

## Current non-goals

This slice does not:

- introduce a Blowfish dependency;
- vendor a Blowfish implementation;
- guess session state;
- decrypt server -> client traffic without prior inbound state;
- assign search, party, auction-house, linkshell, or comment semantics from encrypted bytes;
- promote a packet type when the post-decrypt MD5 fails;
- classify a search flow from framing alone without the independent verified lobby `cache_ip/cache_port` handoff.

## Next safe step

A later decoder slice can add an isolated Blowfish implementation or optional dependency only after a fixture proves byte-for-byte compatibility with LSB. The first target should be a synthetic inbound frame generated from the same source contract, followed by a real capture tied to a verified lobby search/cache handoff. Server -> client decryption should remain a separate stateful step because it depends on key continuation extracted from a successfully decrypted inbound packet.
