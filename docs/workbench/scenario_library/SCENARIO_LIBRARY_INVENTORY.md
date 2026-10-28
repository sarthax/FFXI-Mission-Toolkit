# Scenario Library Inventory (DRAFT, not execution-validated)

Coordinator: #1348. Machine-readable source of truth: `scenario_catalog_draft.json` (schema `scenario-library-draft/1`).
**`support_status` meaning:** `supported` = a native schema action AND readback collector exist for the scenario. It does NOT mean executed, result-authenticated, oracle-approved, client-id-verified or publishable. Those are separate machine fields (`source_schema_compatible`, `runner_result_authenticated`, `oracle_independently_verified`, `client_id_verified`, `eligible_for_publish`); all except `source_schema_compatible` are false for every entry, and `execution_validated` is false everywhere.
Evidence labels: source-supported, capture-observed, previously-executed, locally-validated, unverified.

Totals: 46 candidates, 15 characterized, 2 failure-injection probe groups (kept separate).

| ID | Domain | Tier | Support | Confidence | Evidence | Title |
|---|---|---|---|---|---|---|
| SL-PARTY-001 | parties | characterized | supported | high | previously-executed, source-supported | Leader invites member; party forms (Bastok Markets) |
| SL-NPC-001 | npc-interaction | characterized | partial | medium | source-supported | Talk to Argus starts an event (Port Bastok) |
| SL-ASLT-001 | instanced-content | characterized | partial | medium | capture-observed, source-supported | Leujaoam Sanctum entry via Runic Seal (Caedarva Mire) |
| SL-ZONE-001 | zone-transitions | characterized | partial | high | previously-executed | Character settles in a zone and sees entities |
| SL-ZONE-002 | zone-transitions | candidate | unknown | low | unverified | Zone-to command changes zone |
| SL-COMBAT-001 | combat | candidate | unknown | low | source-supported | kill_all clears nearby mobs |
| SL-COMBAT-002 | combat | candidate | unknown | low | source-supported | rest_hp restores hpp |
| SL-DIAG-001 | dialog-csid | candidate | partial | medium | source-supported | sweep_npcs enumerates NPC events in a zone |
| SL-MOG-009 | inventory | characterized | supported | high | previously-executed, locally-validated | MOG-09 Toolkit catalog scenario |
| SL-INV-001 | inventory | candidate | partial | medium | source-supported | INV-OBS-01 inventory observation spec |
| SL-ITEM-001 | inventory | characterized | partial | medium | source-supported | Item possession after trade or quest reward |
| SL-KI-001 | key-items | characterized | partial | medium | source-supported | Key item granted by NPC |
| SL-QUEST-ARDEA | missions-quests | characterized | partial | medium | source-supported | Ardea: ROCK_RACKETTER |
| SL-QUEST-AQUILLINA | missions-quests | candidate | unknown | medium | source-supported | Aquillina: A_FLASH_IN_THE_PAN |
| SL-QUEST-BRYGID | missions-quests | candidate | unknown | medium | source-supported | Brygid: BRYGID_THE_STYLIST/BRYGID_THE_STYLIST_RETURNS |
| SL-QUEST-DEGENHARD | missions-quests | characterized | partial | medium | source-supported | Degenhard: THE_BARE_BONES |
| SL-QUEST-ZONFOBUN | missions-quests | characterized | partial | medium | source-supported | Zon-Fobun: THE_CURSE_COLLECTOR |
| SL-QUEST-POWHATAN | missions-quests | candidate | unknown | medium | source-supported | Powhatan: GUEST_OF_HAUTEUR/WELCOME_TO_BASTOK |
| SL-QUEST-EVI | missions-quests | candidate | unknown | medium | source-supported | Evi: PAST_PERFECT |
| SL-QUEST-VALAHMOLKO | missions-quests | candidate | unknown | medium | source-supported | Valah Molkot: A_LADY_S_HEART |
| SL-QUEST-TALIB | missions-quests | candidate | unknown | medium | source-supported | Talib: BEAUTY_AND_THE_GALKA/SHADY_BUSINESS |
| SL-QUEST-BABENN | missions-quests | candidate | unknown | medium | source-supported | Babenn: RIDING_ON_THE_CLOUDS/THE_ELEVENTH_S_HOUR |
| SL-QUEST-ELKI | missions-quests | candidate | unknown | medium | source-supported | Elki: HEARTS_OF_MYTHRIL/THE_ELEVENTH_S_HOUR |
| SL-QUEST-ROSEL | missions-quests | candidate | unknown | medium | source-supported | Rosel: FLYERS_FOR_REGINE/ROSEL_THE_ARMORER |
| SL-QUEST-RAIMBROY | missions-quests | candidate | unknown | medium | source-supported | Raimbroy: FLYERS_FOR_REGINE/THE_SWEETEST_THINGS |
| SL-QUEST-PAOUALA | missions-quests | characterized | partial | medium | source-supported | Paouala: SLEEPLESS_NIGHTS |
| SL-QUEST-CHAMAMA | missions-quests | candidate | unknown | medium | source-supported | Chamama: INSPECTOR_S_GADGET/IN_A_PICKLE |
| SL-QUEST-OHBIRUDOHB | missions-quests | candidate | unknown | medium | source-supported | Ohbiru-Dohbiru: FOOD_FOR_THOUGHT/OVERNIGHT_DELIVERY |
| SL-QUEST-ANGELICA | missions-quests | characterized | partial | medium | source-supported | Angelica: A_POSE_BY_ANY_OTHER_NAME |
| SL-QUEST-KUROIDOMOI | missions-quests | candidate | unknown | medium | source-supported | Kuroido-Moido: MAKING_AMENDS/MAKING_AMENS |
| SL-QUEST-KOPUROPOPU | missions-quests | candidate | unknown | medium | source-supported | Kopuro-Popuro: A_GREETING_CARDIAN/LEGENDARY_PLAN_B |
| SL-MSN-SD-1 | missions-nation | characterized | partial | medium | source-supported | San d'Oria mission 1: Smash The Orcish Scouts |
| SL-MSN-SD-2 | missions-nation | candidate | unknown | low | source-supported | San d'Oria mission 2: Bat Hunt |
| SL-MSN-SD-3 | missions-nation | candidate | unknown | low | source-supported | San d'Oria mission 3: Save The Children |
| SL-MSN-SD-4 | missions-nation | candidate | unknown | low | source-supported | San d'Oria mission 4: The Rescue Drill |
| SL-MSN-SD-5 | missions-nation | candidate | unknown | low | source-supported | San d'Oria mission 5: The Davoi Report |
| SL-MSN-BA-1 | missions-nation | characterized | partial | medium | source-supported | Bastok mission 1: The Zeruhn Report |
| SL-MSN-BA-2 | missions-nation | candidate | unknown | low | source-supported | Bastok mission 2: Geological Survey |
| SL-MSN-BA-3 | missions-nation | candidate | unknown | low | source-supported | Bastok mission 3: Fetichism |
| SL-MSN-BA-4 | missions-nation | candidate | unknown | low | source-supported | Bastok mission 4: The Crystal Line |
| SL-MSN-BA-5 | missions-nation | candidate | unknown | low | source-supported | Bastok mission 5: Wading Beasts |
| SL-MSN-WI-1 | missions-nation | candidate | unknown | low | source-supported | Windurst mission 1: The Horutoto Ruins Experiment |
| SL-MSN-WI-2 | missions-nation | candidate | unknown | low | source-supported | Windurst mission 2: The Heart Of The Matter |
| SL-MSN-WI-3 | missions-nation | characterized | partial | medium | source-supported | Windurst mission 3: The Price Of Peace |
| SL-MSN-WI-4 | missions-nation | candidate | unknown | low | source-supported | Windurst mission 4: Lost For Words |
| SL-MSN-WI-5 | missions-nation | candidate | unknown | low | source-supported | Windurst mission 5: A Testing Time |

## Headless asset revalidation

Scanned `scenarios/*.json` (10 files) and `docs/evidence/**/scenario*.json` in the read-only headless checkout b-pr170. The earlier 28-file / ~12-14 distinct figure is NOT re-asserted: this pass found 10 top-level scenario files plus the pr7 acceptance scenario.json files, many of which are failure-injection probes (A06 route/cancel, A11-2 absent invite). Only the A11-1 party pair is recorded as passing end to end (passed=2, failed=0 on each side). Distinct reusable behaviours found: party formation, NPC talk, Leujaoam entry, idle/settle, sweep, patrol. No exact dedup count is claimed beyond that.

## Domains not researched in this pass

Missions (getCurrentMission), status effects, doors/switches/teleports, Feature Trace and Behavior Inspector outputs, packet captures. These have no candidates; see the gap report.

## Provenance notes

Nation mission facts (rank 1-2, 15 missions) come from DSP main `febdc00209` NPC scripts via `_extract_dsp_missions.py` -> `dsp_mission_extract.json`. Per owner direction (2026-10-24), LSB/WoTG-sourced scenarios were REMOVED: their dialog/event ids are shifted versus DSP/Valhalla and DSP has no WoTG mission scripts. WoTG is not part of this library.

DSP quest facts come from `dsp-branches` main `febdc00209` scripts and `sql/npc_list.sql` (19 NPC scripts, `dsp_source_extract.json`). npc_list ids were checked against the script zone with the id>>12 rule only; the client-id offset is NOT verified (project caveat).
