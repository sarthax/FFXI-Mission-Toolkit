# Search/cache crypto-envelope and decryption research

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

After decryption, `SearchHandler::validatePacket()` calculates MD5 over `frame[0x08 : length - 0x14]` and compares it with the 16 bytes at `frame[length - 0x14 : length - 0x04]`. Only after that validation succeeds does LSB read the request type at offset `0x0B`.

## FFXI Blowfish compatibility

The FFXI/LandSandBoat packet cipher is **not wire-compatible with a generic textbook Blowfish library**. The key schedule uses the standard Blowfish P/S seed constants, but the packet primitive uses the FFXI-specific round behavior represented by the maintained server protocol implementation.

`workbench.captures.ffxi_blowfish` is a clean, dependency-free implementation of the protocol behavior. It uses the published standard Blowfish pi-derived seed constants as algorithm data, independently implements the FFXI round behavior, and uses little-endian `uint32` packet words matching the observed server wire path. It does not vendor or copy the maintained server's GPL implementation source.

A deterministic compatibility vector is retained in the focused regression fixture:

```text
key        = 6A15DA0320124399517BDF754E670064
plaintext  = 0001020304050607
ciphertext = 00D103BFB60109A0
```

Decrypting that ciphertext with the same key returns the original block.

## Direction and state boundary

Inbound and outbound search crypto are not independently symmetric.

After a validated inbound decrypt, LSB copies four decrypted bytes from `length - 0x18` into key bytes `20..23`. Combined with the inbound wire seed in key bytes `16..19`, this produces the 24-byte rolling state used by server-side encryption.

The toolkit therefore separates the two operations:

- `search_framing.resolve_crypto_direction()` automatically decrypts only frames proven client -> verified search endpoint;
- server -> client decryption is **not auto-paired by timestamp or flow ordering**;
- `derive_outbound_state(inbound_wire, inbound_decrypted)` requires the exact matching validated inbound observation and returns the explicit 24-byte state;
- `decrypt_outbound_frame(outbound_wire, state)` requires that explicit predecessor state.

This avoids silently pairing an outbound frame with the wrong request when multiple frames/ranges are interleaved.

## Inbound implementation

`search_crypto_envelope.inspect_frame()` records:

- clear header range;
- final 4-byte inbound seed;
- deterministic `MD5(fixed16 || seed4)` derived cipher key;
- exact encrypted byte span;
- exact post-decrypt MD5 input/hash offsets;
- packet-type offset `0x0B` with its value withheld until validation;
- outbound rolling-state dependency.

`search_crypto_envelope.decrypt_inbound_frame()`:

1. inspects the envelope;
2. derives the per-frame key;
3. decrypts only the aligned encrypted span;
4. preserves the clear header and trailing seed;
5. validates declared length and `IXFF`;
6. validates post-decrypt MD5;
7. exposes request type only if every gate succeeds.

Failed candidates remain evidence but do not expose trusted request semantics. The top-level framing status remains `encrypted_or_opaque` for metadata compatibility; stronger results live under `inbound_decryption` / `decryption_validated`.

## Validated inbound request fields

After framing + direction + decryption + MD5 succeed, request types are named from the maintained `TCPREQUESTTYPE` values. Unknown validated values remain numeric and `UNKNOWN`.

The fixed-offset non-AH subset currently decoded is:

- `ID_LIST (0x01)`: requested count at `0x10`, `uint32` character IDs from `0x12`, capped to 20 and available complete entries;
- `GROUP_LIST (0x02)`: party/alliance/linkshell IDs at `0x10`, `0x14`, `0x18`, `0x1C`;
- `SEARCH_COMMENT (0x08)`: player ID at `0x10`.

`SEARCH`/`SEARCH_ALL` remain body-opaque because their bit-packed filter grammar is a larger parser. All Auction House request/history bodies remain deliberately opaque in this branch.

## Explicit outbound state handoff

For one exact validated inbound pair, `derive_outbound_state()` constructs:

```text
key[0:16]  = fixed SearchHandler prefix
key[16:20] = inbound wire frame final 4 bytes
key[20:24] = inbound decrypted bytes[length-0x18 : length-0x14]
```

The helper refuses mismatched wire/decrypted lengths or an inbound candidate that does not pass the complete validation gate.

`decrypt_outbound_frame()` then:

1. requires a validated 24-byte predecessor state;
2. requires clear length/`IXFF` framing;
3. requires the outbound final 4 bytes to equal state `key[16:20]`, matching the server write path;
4. derives the outbound cipher key as `MD5(state[0:24])`;
5. decrypts the same aligned packet region;
6. validates the post-decrypt MD5.

A successful result is cryptographically verified, but **response payload semantics remain `unknown_opaque`**. This branch does not assign party/search/AH response schemas merely because the ciphertext can be validated.

## Regression coverage

Synthetic coverage includes:

- deterministic FFXI-cipher block compatibility and round trip;
- aligned-block rejection;
- exact inbound key derivation and encrypted span;
- endpoint-role direction gating;
- encrypted inbound `SEARCH_COMMENT` -> decrypt -> framing + MD5 -> player ID;
- corrupted inbound ciphertext failing closed;
- reverse-direction frame remaining untouched by automatic inbound logic;
- exact 24-byte outbound state extraction from a validated inbound request;
- synthetic server response encrypted with that state -> decrypt -> framing + MD5 validation;
- wrong predecessor state rejected before outbound decryption;
- existing ID-list/group-list/search-comment fixed-field validation.

The CI-enumerated lobby/capture regression exercises the integrated search classification/decryption imports and normal flow path. Focused crypto fixtures retain the positive cipher/state vectors.

## Current non-goals

This slice does not:

- auto-pair outbound frames with predecessor requests by timestamps or heuristics;
- infer or guess missing rolling state;
- decode server response payload semantics;
- decode `SEARCH`/`SEARCH_ALL` bit-packed request grammar;
- decode Auction House search/history request or response bodies;
- promote request/response semantics when endpoint direction, framing, decryption, state, or MD5 validation fails;
- classify a search flow from framing alone without the independent verified lobby `cache_ip/cache_port` handoff.

## Next safe step

The highest-value next input is a **real search/cache capture tied to a verified lobby handoff**. The toolkit can now validate inbound frames directly and can validate outbound encryption when the exact predecessor state is known. Automated session sequencing should wait for real capture evidence with frame-level ordering strong enough to associate responses with the correct inbound state without heuristics.
