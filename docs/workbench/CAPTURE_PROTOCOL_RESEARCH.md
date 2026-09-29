# Capture Protocol & Logger Research

_Last updated: 2026-09-28_

This note records the evidence behind Mission Toolkit capture-format support and the remaining
protocol-research boundaries. The user-facing support matrix lives at **Captures → Help /
Supported Formats** (`/captures/help`). This document is intentionally more technical.

## Evidence-handling rules

1. Preserve source observations before interpretation.
2. Do not manufacture a zone, direction, opcode, service role, or decoded packet type when the
   source does not prove it.
3. Keep independent observations independent even when they correlate.
4. Prefer content/schema signatures over historical folder names.
5. Treat derived/interchange formats separately from primary observations.
6. Keep zone/map packets, lobby packets, world/search traffic, and raw network frames in distinct
   namespaces until their protocol identity is established.

## Closed evidence-loss gaps

### PacketDB CHATLOG

MalRD PacketDB persists two observation tables relevant to captures:

- `PACKETS(PACKET_ID, RECEIVED_DT, DIRECTION, ZONE_ID, PACKET_TYPE, PACKET_SIZE, PACKET_SYNC, PACKET_DATA)`
- `CHATLOG(CHAT_ID, RECEIVED_DT, DIRECTION, ZONE_ID, CHAT_TEXT)`

Mission Toolkit now ingests both. Packet rows enter `capture_raw_packets`; chat rows enter the
generic `capture_chat_observations` table. Native PacketDB row IDs, source hashes, SQLite-row
provenance, timestamps, direction, and zone IDs are retained.

Source:
- https://github.com/MalRD/packetdb/blob/master/packetdb.lua

CapLog is dual-written into the same canonical chat table while retaining the legacy
`capture_caplog_chat` table for compatibility.

### Whole-session EventView / IDView simple logs

Historical CaptureSuite layouts can contain both per-zone EventView simple logs and a combined
whole-session `eventview/simple.log`. The combined file may contain real records absent from the
per-zone files.

The toolkit no longer drops these unique observations. When the file does not prove a zone, rows
are stored with:

`zone_db = "__UNKNOWN_ZONE__"`

This is deliberate evidence preservation, not a claim that the zone is unknowable forever.
Entity IDs, timestamps, nearby packets, or later correlation can resolve the zone without
rewriting what the original source actually said.

## Canonical chat observations

`capture_chat_observations` is the source-neutral chat/message store. Current sources include:

- PacketDB CHATLOG
- CapLog chat/system text

Fields include timestamp, direction where known, numeric zone ID where known, textual zone where
known, channel where proven, text, source format, and source-native identity.

Future chat-capable tools should target this table rather than creating another tool-specific
chat table unless their schema contains materially different semantics.

## Capturebar OCR

Wiggo32 Capturebar is an on-screen context HUD, not a file logger. Its default display format is:

`[zone]zone name - target (x,z,y) R(rotation) (mainjoblevel/subjoblevel) Moon: percent phase`

The OCR pipeline now has a dedicated `capturebar` capture profile and
`capturebar_overlay` layout template. When OCR text matches the actual default format it can
extract:

- zone ID and zone name
- displayed target/player name
- X/Y/Z
- rotation
- main/sub jobs and levels
- moon percentage and phase

The built-in layout intentionally does **not** invent crop coordinates. A real video layout must
still establish the screen rectangle.

Source:
- https://github.com/Wiggo32/capturebar/blob/main/capturebar.lua

## PCAP / PCAPNG network evidence

The toolkit now accepts classic PCAP and PCAPNG as lossless network evidence.

Current normalization preserves:

- capture timestamp
- link type
- source/destination IP
- source/destination TCP/UDP port
- transport type
- transport payload bytes
- complete captured frame bytes
- original/captured lengths
- source format/native frame identity
- exact byte offsets in the source capture
- conservative service hints for known FFXI/private-server ports

These rows live in `capture_network_observations`.

### Important boundary

A TCP/UDP payload from a packet capture is **not automatically a decoded FFXI application
packet**. It may be encrypted, framed, fragmented, belong to login/lobby/world/search traffic, or
be unrelated traffic. Therefore PCAP payloads are not inserted into `capture_raw_packets`
without a proven decoder/framing step.

This separation is intentional and is the foundation for future lobby/world research.

## Historical logger archaeology

A current Captain-family source audit found several tool families beyond the older Assault/Nyzul
capture set.

Primary source audited:
- https://github.com/sargonnasffxi/ffxiCaptureCaptain

### Persisted formats

#### StatTrack

`addons/extras/stattrack.lua` writes CSV.

Player schema:

`timestamp,hpmax,mpmax,mjob_no,mjob_lv,sjob_no,sjob_lv,STR,DEX,VIT,AGI,INT,MND,CHR`

Puppet schema:

`timestamp,maxhp,maxmp,maxmelee,maxranged,maxmagic,str,dex,vit,agi,int,mnd,chr`

Both are now ingested into `capture_structured_records` as `stattrack_csv` and
`puppet_stattrack_csv`.

Source:
- https://github.com/sargonnasffxi/ffxiCaptureCaptain/blob/main/addons/extras/stattrack.lua

### Runtime-only / non-file tools

These are useful capture ecosystem components but are **not separate persisted file formats** in
the audited revisions:

- **ImmunityTrack** — derives spell immunity/resist summaries from battle packets and emits
  messages.
- **PacketBridge** — streams all packets to localhost UDP, prefixing incoming/outgoing direction;
  default port is configurable (55555 in the audited source).
- **PlayerInfo** — on-screen player/zone/position/job HUD.
- **TargetInfo** — on-screen target/entity/model/speed HUD.
- **ZoneDump** — actively requests entity data; resulting packets are observable by normal packet
  loggers.
- **OBS integration** — starts/stops/splits OBS recordings with capture sessions.
- **VersCheck** — version/update helper, not capture evidence.

Sources:
- https://github.com/sargonnasffxi/ffxiCaptureCaptain/blob/main/addons/immunitytrack.lua
- https://github.com/sargonnasffxi/ffxiCaptureCaptain/blob/main/addons/packetbridge.lua
- https://github.com/sargonnasffxi/ffxiCaptureCaptain/blob/main/addons/playerinfo.lua
- https://github.com/sargonnasffxi/ffxiCaptureCaptain/blob/main/addons/targetinfo.lua
- https://github.com/sargonnasffxi/ffxiCaptureCaptain/blob/main/addons/zonedump.lua
- https://github.com/sargonnasffxi/ffxiCaptureCaptain/blob/main/addons/obs/obs.lua

### Derived/interchange tools

Additional searches found tools such as **kparser2** and **xipp** that consume or convert
PacketViewer-style evidence. kparser2 can represent converted PacketViewer observations as NDJSON.
These are useful interchange/analysis formats, but they are not treated as new primary capture
sources unless archived evidence is found only in the derived representation.

Examples:
- https://github.com/poroburu/kparser2
- https://github.com/cocosolos/xipp

## Lobby / world / search research

### What is established

Windower/Fenestra's lobby packet-event request documents an important limitation of normal addon
packet hooks: the familiar packet events correspond to the zone-server stream, while the client
also keeps a lobby/world connection that may be involved in cross-zone functions such as auction
house and search.

Source:
- https://github.com/Windower/Fenestra/issues/9

atom0s/XiPackets independently documents distinct `lobby/` and `world/` protocol families,
including lobby login, character selection/creation/deletion, world-list exchange, and world
server packets.

Sources:
- https://github.com/atom0s/XiPackets/tree/main/lobby
- https://github.com/atom0s/XiPackets/tree/main/world

LandSandBoat's xiloader also keeps separate login-data/login-view/login-auth ports and directly
references the XiPackets lobby protocol documentation.

Source:
- https://github.com/LandSandBoat/xiloader/blob/main/src/main.cpp

### Architecture decision

Do **not** extend `capture_raw_packets` to mean every packet on every FFXI-related socket.

Future protocol decoding should layer on `capture_network_observations` and produce explicit
connection-role observations, for example:

- ZONE / MAP
- LOGIN DATA
- LOGIN VIEW
- LOGIN AUTH
- LOBBY
- WORLD
- SEARCH
- UNKNOWN

Only after framing/protocol identity is established should decoded messages be promoted to a
protocol-specific canonical observation model.

### Research sequence

1. Collect known-good PCAP/PCAPNG sessions covering login → character select → zone entry.
2. Identify TCP/UDP flows by endpoint/port and lifecycle.
3. Compare framing against XiPackets lobby/world documentation and LandSandBoat/xiloader.
4. Record protocol role with confidence/evidence rather than port-only certainty.
5. Add lobby/world/search decoders independently of the existing zone packet decoder.
6. Correlate decoded cross-zone observations with canonical chat, entity, storage/AH/search, and
   client capability evidence where appropriate.

## Remaining research targets

- PacketDB `ZONES` and `PACKET_DEFINITION` as historical reference metadata.
- PacketBridge live UDP adapter if real-time intake becomes useful.
- PacketViewer-derived NDJSON only if historical evidence exists solely in that representation.
- Additional archived Windower/Ashita forum/Discord tools for which source or real samples can be
  recovered.
- Explicit retail-vs-private port/service-role evidence; port hints alone are not authoritative
  protocol classification.
