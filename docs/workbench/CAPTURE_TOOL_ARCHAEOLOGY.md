# Capture Tool Archaeology

Date: 2026-09-28

Purpose: track historical/current FFXI logging and packet-analysis tools that have been audited for persisted output. This document distinguishes actual ingestible evidence formats from tools that merely consume packets or render data on screen.

## Audited tool families

| Tool / family | Platform / era | Persisted evidence | Toolkit status | Notes |
| --- | --- | --- | --- | --- |
| Windower PacketViewer / z16 variants | Windower | per-opcode raw packet logs plus full/incoming/outgoing views | Supported | Canonical raw-packet ingestion already covers the per-opcode format; flat whole-session views are intentionally not duplicated when per-opcode files exist. |
| Captain PacketLogger | Ashita v4 / Captain | per-opcode incoming/outgoing logs plus full.log | Supported by PacketLogger/PacketViewer family | Captain documents the format as PVLV/VieweD-compatible and its source writes the same timestamped packet/hexdump shape. |
| Ashita Packeteer | Ashita | text packet dumps | Supported | Dedicated Packeteer adapter uses the vendored VieweD reader behavior. |
| MalRD PacketDB | Windower | SQLite PACKETS and CHATLOG | Supported | PACKETS -> canonical raw packets; CHATLOG -> canonical chat observations. |
| Windower Logger | Windower | daily `<player>_YYYY.MM.DD.log` chat files | Supported in this milestone | Optional timestamp may be absent; timestamp-less lines remain `ts=NULL`. |
| CaptureSuite / Captain CapLog | Windower/Ashita | chat/system text and tagged capture output | Supported | CapLog also converges into canonical chat observations. |
| NPCLogger generations | Windower/Ashita | SQLite and legacy Lua entity state; some generations preserve raw packet bytes | Supported | Rich SQLite/Lua schemas and raw_packet preservation are already covered. |
| ActionView | Windower/Ashita | SQLite and simple text action observations | Supported | Rich DB is preferred when both DB and simple text coexist. |
| EventView legacy / CapLog EView | Windower/Ashita | decoded event packets and fields | Supported | Includes per-zone and whole-session zone-unknown preservation. |
| Captain EventView v2 standalone | Ashita v4 / Captain current | per-zone full-datetime decoded packet dumps using a newer title/body writer | **Sample needed / parser gap** | Source audit shows the standalone writer differs from the legacy EventView header grammar. Do not claim support until a real emitted file is fixture-tested. |
| PathLog | Windower/Ashita | CSV NPC/player paths | Supported | Multiple historical/current path layouts are already handled. |
| HPTrack / KITrack / LevelRangeTrack / AttackDelay | CaptureSuite/Captain | text/SQLite mechanic observations | Supported | Existing capture parsers cover these families. |
| ShopStock / GuildStock / PriceLog/findPrice | CaptureSuite/Captain | SQLite/text vendor and guild pricing evidence | Supported | Current and historical schema variants are covered where verified. |
| WeatherTrack / POITrack / SpawnTrack / CheckParam / CraftTrack / ConquestTrack / MissionTrack | Captain / misc capture suites | SQLite/CSV/text structured observations | Supported | Stored in generic structured observations with promoted searchable fields. |
| Captain StatTrack | Captain | player and puppet CSV stat snapshots | Supported | Both verified generations are content-sniffed: player HP/MP/jobs/base stats and puppet HP/MP/melee/ranged/magic/base stats. |
| Capturebar | Windower | no persistent log; on-screen HUD only | Supported through OCR | Built-in OCR profile extracts zone/target/X-Z-Y/rotation/job/moon context from video/screenshots. |
| Windower QuestLog | Windower | none | Not an ingestion target | Consumes packet 0x056 and renders quest state to chat; no reusable file output in the audited source. |
| Windower Pricer | Windower | none | Not an ingestion target | Fetches FFXIAH sale data and writes to chat only; no capture file. This is distinct from Captain PriceLog/findPrice, which is supported. |
| Ashita ScanZone | Ashita | none | Not an ingestion target | Reads DAT/entity packet state and prints to console; no capture file in the audited source. |
| Captain PacketBridge | Ashita v4 | UDP forwarding stream, not a disk log | Runtime integration candidate | Re-emits packets to a UDP port; could become a live connector later, but there is no static file format to ingest. |
| PCAP / PCAPNG | network capture | raw network frames | Bounded support | Exact frames/endpoints/timestamps are preserved; only already-plaintext, fully validated FFXI UDP chunk streams are promoted. |

## Key findings from this pass

1. **Windower Logger was a real ingestion gap.** It writes daily chat files outside the CaptureSuite CapLog format. These now feed `capture_chat_observations`.
2. **Most “packet tools” are not new capture formats.** QuestLog, Pricer, ScanZone, and many gameplay addons inspect packet/memory state but do not leave reusable evidence files.
3. **Captain PacketLogger is not a new raw format.** Its source writes per-ID timestamped hexdumps intentionally compatible with PVLV/VieweD, so the existing canonical packet family remains the right adapter.
4. **Captain EventView v2 standalone output deserves its own compatibility fixture.** The current writer logs a full datetime, direction marker, type label, then a dumped parsed table. The legacy EventView parser expects an opcode/class/command header. A real emitted sample should be captured before implementing normalization.
5. **PacketBridge is a future live-input opportunity, not a file importer.** It forwards packet streams over UDP and could later feed a live capture adapter without inventing a disk format.

## Search scope

This pass reviewed:
- current Captain source and README,
- historical/current Windower addon mirrors,
- classic PacketViewer/Logger families,
- Ashita community packet/entity utilities,
- known capture-suite descendants and compatibility claims.

The search remains open-ended: old forum attachments, deleted repositories, Discord-only tools, or private capture scripts may still surface. When they do, add the real sample/schema here before declaring support.

## Next research boundary

The next planned capture-research milestone is **lobby/world/non-zone stream mapping**: determine which FFXI connections carry search, auction, storage/account, character-select, and related traffic; identify available historical/current capture tools or server implementations; and separate TCP/lobby evidence from the UDP map/zone stream already modeled.
