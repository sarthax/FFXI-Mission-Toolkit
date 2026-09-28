# Capture / Logger Format Audit

Status: evidence inventory and ingestion backlog
Last audited: 2026-09-28

## Purpose

The original capture ingestion scope prioritized Assault, Nyzul, Salvage, packet/event, NPC, path, combat, and mission-adjacent evidence. This audit revisits logger families that were historically outside that immediate scope but have future Workbench value.

Architectural distinction:
- Capture-owned sources belong to a specific session and can use capture identity, provenance, correlation, and Feature Trace.
- Persistent reference telemetry is collected outside one capture and must keep its own dataset/source identity.
- Interactive/non-persistent helpers are not parser targets until they produce durable output.

Audited sources:
- Captain: https://github.com/sruon/captain
- Bundled Wiggo reference addons under vendor/reference_addons/wiggo-addons-1

## Already covered

PacketLogger / PacketViewer, EventView/IDView, CapLog, NPCLogger SQLite and legacy Lua, ActionView, PathLog, HPTrack, KITrack, LevelRangeTrack, Widescan, and AttackDelay are already represented by current capture ingestion.

## P0 — MissionTrack

Captain source: addons/missiontrack.lua

Storage:
- global text log: <root>/<player>_missions.log
- capture-owned text log: <captureDir>/<player>_missions.log.

Evidence:
- listens to GP_SERV_COMMAND_MISSION
- diffs prior/current eight-word mission/quest payloads
- emits timestamped state changes with player X/Y/Z and zone
- decodes main mission progress, quest offer/complete bitfields, nation/RotZ/CoP/SoA/RoV, ToAU/WoTG completion, Assault progress, Campaign, and TVR-related state.

Recommended normalized family: capture_progress_events with timestamp, zone/XYZ, port, progress type/domain, subject/field, action, previous/current value, raw fields JSON, and exact source-block provenance.

Why P0: this is direct mission/quest transition evidence and should feed Feature Trace and mission dependency validation.

## P0 — ShopStock

Captain source: addons/shopstock.lua

Storage: SQLite BuyList.db and SellList.db, written both globally and inside captures.

Buy fields:
NpUniqueNo/NpcUniqueNo, NpcName, NpcZone, GuildInfo, ItemNo, ItemName, ItemPrice, ShopIndex, Skill.

Sell/appraisal fields:
NpcUniqueNo, NpcName, NpcZone, ItemNo, ItemName, Price.

Recommended model: generic vendor-stock observations with shop type, buy/sell direction, NPC identity/zone, item identity, price, shop index, guild info, skill, and source row identity.

Potential graph use: NPC SELLS_ITEM / BUYS_ITEM evidence and shop migration validation.

## P0 — GuildStock

Captain source: addons/guildstock.lua

Storage: SQLite BuyList.db and SellList.db, global and capture-owned.

Fields:
NpcUniqueNo, NpcName, NpcZone, ItemNo, ItemName, Count, Max, Hidden, Price.

Recommended model: share the vendor-stock logical family with ShopStock but preserve guild stock count/max/hidden semantics.

## P1 — SpawnTrack

Captain source: addons/spawntrack.lua

Storage: CSV globally per player/zone and capture-owned <captureDir>/<zone>.csv.

Columns:
MobName, UniqueNo, DefeatedAt, DespawnedAt, SpawnedAt, DefeatToSpawnDiff, DespawnToSpawnDiff, XDefeated, YDefeated, ZDefeated, XSpawn, YSpawn, ZSpawn.

Collection note: default/light mode uses naturally observed packets; extended mode actively polls entities. Preserve collection mode when known rather than treating both as equivalent provenance.

Potential use: spawn-point, respawn-timer, and NM behavior validation.

## P1 — WeatherTrack

Captain source: addons/weathertrack.lua

Storage: persistent per-player SQLite database <root>/<player>.db. The source explicitly states it is passive/global and is not stored inside Captain captures.

Fields:
ZoneNo, ZoneName, PreviousWeatherStartTime, PreviousWeatherNumber, PreviousWeatherOffsetTime, StartTime, WeatherNumber, WeatherOffsetTime.

Architecture: import as external telemetry with its own dataset/source identity. Only correlate to captures by zone/time after temporal identity is established.

Potential use: weather-gated spawns/events, elemental/weather mechanics, quest conditions, and server/client weather timing.

## P1 — CraftTrack

Captain source: addons/crafttrack.lua

Storage: CSV globally and capture-owned.

Fields include timestamp/result/grade/count, result item, crystal, up to eight materials, up to eight lost materials, skill-up fields, and synthesis animation/effect fields.

Potential use: recipe/output validation, HQ/failure behavior, material loss, and crafting migration validation.

## P1 — CheckParam

Captain source: addons/checkparam.lua

Storage: capture-owned CSV when enabled.

Columns:
recvTime, syncId, acc, atk, offacc, offatk, rangeacc, rangeatk, eva, def.

Collection note: generates /checkparam requests and assembles several returned battle messages into one record.

Potential use: equipment/stat validation and combat formula research.

## P1/P2 — POITrack

Captain source: addons/poitrack.lua

Storage: persistent per-player/per-zone SQLite DB, not capture-owned.

Fields: uniqueId, name, x, y, z.

Current POIs include Treasure Chest, Treasure Coffer, ???, Harvesting Point, Logging Point, Mining Point, Excavation Point, and Warhorse Hoofprint.

Architecture: external entity-position evidence dataset; reconcile by real ID + zone where possible.

## P2 — ConquestTrack

Captain source: addons/conquesttrack.lua

Storage: persistent CSV <root>/<player>_conquest.csv, not capture-owned.

Contains timestamp, balance/alliance, 27 region owner/rank/graphics groups, current nation standings/percentages, next tally, conquest points, and beastmen state.

Architecture: persistent world-state telemetry.

## Historical vendor-price family — PriceLog / findPrice

Bundled sources:
- vendor/reference_addons/wiggo-addons-1/pricelog/pricelog.lua
- vendor/reference_addons/wiggo-addons-1/findprice/findPrice.lua

Storage:
- per-zone simple/<zone>.log
- per-zone raw/<zone>.log
- persistent Lua database.lua / price_database.lua.

Simple observations include incoming 0x03D Price Response, item id/name, appraisal/resale price, character, zone, and NPC. The raw sibling includes packet hex.

Persistent DB fields include item id/name, price, character, zone, and NPC.

Relationship to ShopStock: overlapping vendor domain but distinct historical source family. PriceLog/findPrice focuses on NPC resale/appraisal; Captain ShopStock records structured buy stock and sell/appraisal data with NPC IDs.

Priority: P1 historical compatibility.

## Context / non-persistent tools

### PlayerInfo
Current Captain implementation is UI-only. It displays player identity/jobs, zone, XYZ/rotation, Vana'diel weekday/time, moon phase/percent, local time, and capture/retail state. It does not currently persist a database despite an old type annotation. This likely explains some remembered moon/world data, but WeatherTrack is the real persisted weather logger.

### TargetInfo
Live target enrichment helper for model/hitbox/graph size/speed/level and optional /check requests. No durable log in the audited implementation.

### ImmunityTrack
Tracks spell immunity/resistance in memory and reports summaries to chat. No structured persistent file currently.

### ZoneDump
Interactive entity query/watch tool. Current implementation reports results through messages and does not define a normal persisted capture dataset.

### PacketBridge
Streams packets over local UDP; transport rather than durable storage. PacketLogger/PacketViewer remains the durable input.

### VersCheck
No evidence dataset.

## Existing-family variants to regression-test

Captain also contains eventviewv2.lua, hptrackv2.lua, npcloggerv2.lua, and pathlogv2.lua. These are not assumed to be new logical families. Real samples should be checked against current parsers; schema differences should get explicit adapters rather than silent compatibility assumptions.

## Proposed implementation order

1. MissionTrack — highest direct value to Feature Trace and mission/backport validation.
2. ShopStock + GuildStock — common vendor-stock logical model with source-specific schemas.
3. SpawnTrack — capture-owned spawn timing/location evidence.
4. WeatherTrack external telemetry importer — establishes reusable non-capture telemetry architecture.
5. PriceLog/findPrice historical vendor-price compatibility.
6. CraftTrack + CheckParam.
7. POITrack + ConquestTrack external telemetry.

Every new parser/importer should preserve source hash, exact row/block identity where supported, conservative ownership, safe re-ingestion, explicit graph identity, and no forced capture attribution for persistent global telemetry.

## Conclusion

The earlier Assault/Nyzul-focused scope did omit useful logging families. The key omissions are broader than vendor/weather: MissionTrack is a major mission-evidence gap, while ShopStock/GuildStock, SpawnTrack, WeatherTrack, PriceLog/findPrice, CraftTrack, CheckParam, POITrack, and ConquestTrack all have credible Workbench value.