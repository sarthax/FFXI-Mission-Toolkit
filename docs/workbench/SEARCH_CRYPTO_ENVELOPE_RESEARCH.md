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

The fixed-offset non-AH subset decoded is:

- `ID_LIST (0x01)`: requested count at `0x10`, `uint32` character IDs from `0x12`, capped to 20 and available complete entries;
- `GROUP_LIST (0x02)`: party/alliance/linkshell IDs at `0x10`, `0x14`, `0x18`, `0x1C`;
- `SEARCH_COMMENT (0x08)`: player ID at `0x10`.

### `SEARCH` / `SEARCH_ALL` packed filter grammar

Current LSB `_HandleSearchRequest()` defines the packed block as:

```text
uint8 query_size at frame[0x10]
packed query bytes at frame[0x11 : 0x11 + query_size]
```

Entries begin with a 5-bit `SearchType`. Most entry types then consume one `sortDescending` bit and one `isPresent` bit. `Friend`, `Linkshell`, `Linkshell2`, `Comment`, and `Flags2` skip those two ordinary control bits.

The toolkit independently mirrors LSB `unpackBitsLE()` and decodes only fields whose widths are directly used by the maintained parser:

| SearchType | Value width / behavior |
|---|---|
| `Name (0x00)` | 5-bit raw name length, then 7 bits per character; store at most 15 chars while still consuming the declared raw length |
| `Area (0x01)` | 10-bit area ID; store at most 15 areas while still consuming later entries |
| `Nation (0x02)` | 2 bits |
| `Job (0x03)` | 5 bits |
| `Level (0x04)` | 8-bit minimum + 8-bit maximum |
| `Race (0x05)` | 4 bits |
| `Flags1 (0x06)` | 16 bits |
| `Rank (0x10)` | 8-bit minimum + 8-bit maximum |
| `Comment (0x11)` | 32 bits, no ordinary sort/present bits |
| `Linkshell (0x0B)` / `Linkshell2 (0x13)` | 32-bit linkshell ID, no ordinary sort/present bits |
| `Friend (0x0C)` | zero-width marker setting `friends_only=true` |
| `Flags2 (0x16)` | 32 bits, no ordinary sort/present bits; replaces the final flags value exactly as LSB does |

For friend searches, the parser also follows LSB's post-query tail:

```text
uint16 requested_count at 0x11 + query_size
uint32 character IDs immediately after it
```

The toolkit caps decoded friend IDs to LSB's source limit of 200 and to the number of complete IDs available before the 20-byte search trailer.

Current enum values `Id`, `Party`, `LinkshellRank`, `Unknown0E`, and `Language` are preserved by numeric/name identity but remain `known_enum_unhandled_by_lsb_parser` because current `_HandleSearchRequest()` assigns no payload semantics to them. Unknown numeric entry types remain explicit `unknown_entry_type`. No width is guessed for either category.

Every packed entry retains its bit start/end offsets, type ID/name, control bits, decoded value, and status. Truncated value fields stop at the declared query boundary and produce diagnostics instead of reading into the trailer or guessing missing bits.

Auction House request/history bodies remain deliberately opaque in this branch.

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

A successful result is cryptographically verified. Cryptographic validation by itself still assigns no response semantics; semantic promotion is a separate layer.

## Validated non-AH server response semantics

`search_response_decode.decode_validated_outbound()` structurally parses only responses whose outbound crypto result already passed the explicit predecessor-state, framing, decrypt, and post-decrypt MD5 gates. `search_response_evidence.decode_validated_outbound()` is the semantic trust gate layered above that structural parser.

Current source-backed response families are:

- `0x80` — search list. LSB writes `uint16 total_results` at `0x0E`, data size at `0x08`, and a size-prefixed packed entity stream beginning at `0x18`.
- `0x88` — search comment. Current LSB fixes total wire length `204`, byte `0x08 = 154`, `0x0A = 0x80`, `0x0E = 1`, player ID at `0x18`, comment-length constant `124` at `0x1C`, comment region beginning at `0x1E`, and a zero terminator at `0x9A`.
- `0x82` — shared party/linkshell list discriminator. The type alone is deliberately insufficient to choose a family.

### Packed response entities

The list decoders mirror the LSB packet constructors and `packBitsLE()` ordering. Each entity is preceded by its encoded byte count. Supported source-emitted fields are:

- Name: 4-bit length + 7-bit characters;
- Area: 10 bits;
- Nation: 2 bits;
- Job: main 5 bits + sub 5 bits;
- Level: main 8 bits + sub 8 bits;
- Race: 4 bits;
- Rank: 8 bits;
- Flags1: 16 bits;
- Id: 20 bits;
- LinkshellRank: three 8-bit ranks + three 32-bit linkshell IDs;
- Unknown0E: preserved 32-bit raw value;
- Comment: 32-bit search-comment type;
- Flags2: 32 bits;
- Language: 16 bits.

Unknown packed entity types stop semantic decoding for that entity and preserve the raw remainder rather than guessing a width. Nonzero byte-alignment padding is retained as a diagnostic.

### Shared `0x82` evidence policy

Party and linkshell constructors both emit response type `0x82`, so the toolkit never labels an otherwise ambiguous packet from the discriminator alone.

Strong promotion paths are:

- an exact validated `GROUP_LIST` predecessor with nonzero party/alliance ID -> party list;
- an exact validated `GROUP_LIST` predecessor with nonzero linkshell ID -> linkshell list;
- without predecessor context, a fully decoded entity containing the source-unique `LinkshellRank` layout may structurally infer linkshell list.

A well-formed `0x82` lacking either exact predecessor evidence or the unique linkshell structure remains `party_or_linkshell_list`. If exact predecessor fields and payload structure contradict each other, `search_response_evidence` downgrades the result to `ambiguous_conflicting_predecessor_and_payload_structure`, clears the family-dependent total-results interpretation, preserves both `uint8` and `uint16` observations at `0x0E`, and sets semantic promotion false.

### Fixed-layout `0x88` evidence policy

For search-comment responses, crypto validation is not enough. The semantic gate additionally requires all source-fixed constructor facts to match. A crypto-valid `0x88` with a wrong packet length, fixed size byte, final flag, count byte, comment-length constant, or terminator remains preserved but loses decoded semantic fields and is marked `crypto_validated_source_layout_mismatch`.

Auction House response types remain deliberately opaque and are not decoded by this slice.

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
- fixed-field ID-list/group-list/search-comment validation;
- packed `SEARCH` and `SEARCH_ALL` filters spanning name/area/nation/job/level/race/rank/flags/comment/friend entries;
- friend ID-tail extraction and count cap;
- known-but-unhandled SearchType preservation;
- declared query-block truncation failing closed;
- validated `0x80` search-list entity decoding;
- ambiguous and predecessor-resolved `0x82` party/linkshell handling;
- source-unique `LinkshellRank` structural inference;
- predecessor/payload conflict downgrade;
- validated `0x88` search-comment decoding plus fixed-layout mismatch rejection;
- unsupported crypto-valid response types remaining opaque.

The CI-enumerated lobby/capture regression exercises the integrated search classification/decryption imports and normal flow path. Focused crypto/filter/response fixtures retain the positive protocol vectors.

## Current non-goals

This slice does not:

- auto-pair outbound frames with predecessor requests by timestamps or heuristics;
- infer or guess missing rolling state;
- invent widths or semantics for SearchType values current LSB itself leaves unhandled;
- decode Auction House search/history request or response bodies;
- decode unsupported/unknown search response families from resemblance alone;
- promote request/response semantics when endpoint direction, framing, decryption, state, MD5, or source-layout evidence fails;
- classify a search flow from framing alone without the independent verified lobby `cache_ip/cache_port` handoff.

## Next safe step

The highest-value next input is a **real search/cache capture tied to a verified lobby handoff**. The toolkit can now validate inbound crypto, decode fixed/packed search requests, validate explicit outbound state, and decode supported non-AH response families without heuristic predecessor pairing. Automated session sequencing should wait for real capture evidence with frame-level ordering strong enough to associate responses with the correct inbound state without guessing.
