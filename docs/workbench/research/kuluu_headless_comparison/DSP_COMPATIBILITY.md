# Kuluu vs our DSP server: compatibility

Server under test: `<local DSP checkout>` (DSP lineage, `DSGame-server_64.exe`). Kuluu: `a7752b3`. Method: source comparison only; no Kuluu-to-DSP connection was needed to establish the first blocker (see below).

## Verified blocker 1 - authentication (source evidence)
| | DSP (`src/login/login_auth.cpp`) | Kuluu |
|---|---|---|
| Transport | plain TCP, port 54231 | `json`: TLS (TOFU verifier); `binary`: plain TCP |
| Request | **exactly 33 bytes**: name[16] + password[16] + code byte (0x10 login / 0x20 create) - handler gates on `session[fd]->rdata.size() == 33` (L82), code read at offset 32 | `json`: `{username,password,version,command}`; `binary`: **102-byte** payload (`auth_binary.rs PAYLOAD_LEN`, includes MAC address and a 5-byte loader version at offset 97) |
| Reply | 1 byte result, 33 bytes on success (L156/165) | `binary` expects a **21-byte** success reply (`RESPONSE_LEN`) carrying account id + 16-byte hash; `json` expects `session_hash` |
Result: neither Kuluu flavour can authenticate against DSP unchanged. `binary` is closest (also 0x10/0x20/0x30 command bytes) but the request length and reply length differ. **No server change is required if Kuluu gets a third flavour (`dsp`)**, which is a small client-side change - but it would be a fork/patch of a GPL project.

## Expected failure points after auth (not yet exercised)
1. **Lobby login 0x26**: DSP has no `session_hash`/0xFE packet; view socket sends 0x26 first, the data socket identifies with 0xA1(accid), view matched to account by client IP (FINDINGS.md). Kuluu's `lobby_client.rs` assumes the LSB sequence with `LobbyKey`/hash.
2. **Version lock**: Kuluu stamps a version (`FFXI_CLIENT_VER`, `LSB_CLIENT_VER`); DSP has no equivalent lobby comparison in our build; low risk, unknown.
3. **Map keying**: our client needed DSP-specific key handling (returning char: server stores key[16]-2, map side needs uint32@16 = 256; wrong key shows as `[md5-fail]`). Kuluu follows LSB key derivation; likely `md5-fail` until patched.
4. **Source-IP session binding**: DSP picks the character by `accounts_sessions.client_addr`; multiple bots need distinct local IPs (we use `XI_BIND_LOCAL=127.0.0.N`). Kuluu has no such option.
5. **Packet layouts**: DSP is far older; many S2C structs differ (our HP/MP/job parse initially read 0 using LSB parsers). Kuluu's `ffxi-proto` decoders are LSB-audited, so entity/player-state decoding is the highest-volume risk.
6. **Inventory containers/IDs**: DSP predates wardrobes 5-8 and has different capacity layout; Kuluu's `inventory.rs` assumes modern containers.
7. **Zoning**: LSB-style zone-in sequence (0x00A double-send, key rotation) is shared in outline; instance entry re-key differs per our Leujaoam work.
8. **Event protocol**: our DSP event layouts (0x32 and 0x34) matched upstream xiheadless; Kuluu's event handling is built for LSB menus and a retail DAT-driven event VM.
9. **Client DAT dependency**: Kuluu nav/geometry needs a retail install; a headless protocol-only run may avoid it (unverified).

## Checklist for a disposable-environment probe (not run)
- [ ] Use a throwaway account/char on a *separate* DSP stack or an isolated `accounts` row; never a real character; do not touch `dspdb_fresh` tables beyond a new account row the user approves.
- [ ] Run Kuluu `--auth-flavor binary` and confirm the server never answers (expected: hang or close; DSP logs nothing for non-33-byte reads).
- [ ] If a `dsp` flavour is patched in: confirm 0x26 on view, 0xA1 on data, char list parse.
- [ ] Confirm map-key derivation matches (`md5-fail` count).
- [ ] Capture first 50 map packets and diff parse results against `Game/PacketParsers.cs`.

## Conclusion
Kuluu **cannot connect to our DSP server today without client-side modification**; this is established by source (the 33-byte gate vs the 102-byte payload). It is a *protocol-generation mismatch*, not a configuration issue. Server modification is not recommended.
