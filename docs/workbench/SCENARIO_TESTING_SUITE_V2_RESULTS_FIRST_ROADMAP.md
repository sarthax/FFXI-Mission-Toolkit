# Scenario Testing Suite v2 — results-first delivery roadmap
Status: PROPOSAL / product not accepted. Owner direction 2026-10-24. Parent #1406; UX #1407; source gap #1348 comment 6393353853.

## North-star mockup and scope
A five-screen, spacious and human-readable application: **Scenario Test Hub → Game-aware Create/Review → Test Catalog → Preflight/Run → Run Results**. Design references are the five conceptual mockup images reviewed in the 2026-10-24 project conversation. The images are conceptual designs, NOT screenshots of implemented software and not evidence of current run capability. UI should prioritize readable sentences, a compact navigation sidebar, large evidence areas, clear status and drilldown, and optional Advanced JSON. Do not invent live stats, approved runners or successful trials.

**Product priority changed:** results and evidence first, then curated test/observation library, then publishing, then approachable authoring, then safe execution. AI/LLM agents can create provisional drafts before human editing becomes complete, but neither generated specifications nor AI rationales are trusted evidence, approved oracles, or run authorization.

## End-user stories and staged release gates
### R0 — Evidence-first read-only results viewer (highest priority)
Reuse existing Feature Testing imported runs / Validation history and offline observation receipts; build a coherent *non-executing* Run Results page, showing scenario and immutable revision, run identity, executor status and independent oracle verdict, source identities, environment/zone/server/toolkit/headless revisions, step-by-step **expected versus observed**, missing/contradictory evidence (UNKNOWN), logs/captures/screenshots where actually available, failure reason and compare-two-runs. Never turn merely 'task completed' or a reported PASS into an independently validated PASS. Provide honest empty/error fixtures, keyboard focus and 360px layout. Golden case: MOG-09; add a two-bot/zone or NPC result only where native evidence and contracts support it. ACCEPT: operator can locate a prior result and answer what happened, what was expected, why it passed/failed/unknown, and where raw provenance lives; no fabricated evidence.

### R1 — Typed game-aware behavior and evidence library
One machine-readable registry of *capabilities*, not one flat enum list. A row describes namespace/version, human name and example (e.g., 'Talk to an NPC' / 'Expect event to start'), category (zone/movement/NPC/event/party/inventory/KI/combat), parameter schema with game-object lookup source, backend adapter/runner + native name, preconditions/permissions, observed fields/collector, expected comparator/oracle, evidence provenance, unsupported-state message, tests, support tier. Build a provenance-preserving index from (a) existing XIHeadless ScenarioActionSchema/ScenarioExpectationSchema, (b) Toolkit supported observations/readbacks, (c) DSP/LSB/Topaz event/quest/mob Lua/server handlers and API instrumentation as candidate relationships, (d) actual packet captures (request→server response→state update) correlated with actor/zone/event and timestamps, and (e) live run logs. No source/packet inference alone grants executable action or proves a gameplay verdict.

**Crucial epistemic distinction:** server script defines possible transitions, captures show observed wire messages, XIHeadless runner schema defines callable instructions, readback defines measurable state, oracle defines pass criteria. Correlate them with evidence and confidence rather than assuming opcode→game action is universally one-to-one.

### R2 — Library ingestion, review and test catalog
Read-only import of XIHeadless scenario JSON and historic results to *drafts only* with source path, native payload version, run ID and schema provenance. Proposal #1348 comment 6393353853 found 28 files, perhaps 12–14 meaningful scenarios after dedup; these numbers are audit estimates, not approved content. Owner verifies A06 expected-failure probes and which scenarios are retained. Add categories/tags, searchable names and feature links, reviewed immutable published revision, status design-only/manual/read-only runnable/supervised runnable/blocked. Separate global Feature Catalog from Test Scenario Catalog. Existing hand-edited test_specifications.json remains seed/import.

### R3 — Human-oriented authoring & AI-assisted draft generation
Forms with Given/When/Then/And and clearly separate 'perform action' versus 'verify expected result'; structured NPC/zone/item/event/character/party pickers backed by resolved source IDs. UI generates adapter-native typed payloads, shows readable preview and per-step support level. AI can propose steps from behavior traces/capture evidence, and suggest sources, but must attach citation/confidence and pass deterministic validation; human reviews before publication. Invalid typed arrays and missing steps never crash render. Keep Advanced JSON optional, preserve draft revisions/CAS.

### R4 — Review, preflight and supervised run (contract gated)
Only allow RUN for a published immutable version with a reviewed runner-specific execution contract, resolved action support/oracle coverage, explicit sandbox environment, leased test account/role, approved safety policy and required fixtures, and no unhandled blocking step. XIHeadless executes; Toolkit does NOT reimplement game actions or send packets. Read-only MOG-09 and movement/NPC/party scenarios are distinct risk classes. Unsupported steps BLOCK the launch, never silently skip them and claim PASS. Distinguish dispatch accepted, executing, completed, and gameplay verdict. Actual operator-authorized disposable DSP and HEADLESS owner acceptance required for real E2E gate.

## Library-discovery method: from source and captures to scenario steps
1. Inventory native callable actions and expectations and published schema versions on XIHeadless; capture precise semantics, inputs and output states. Never infer action implementation from name alone.
2. Map Toolkit existing observations and read-only collectors and locate corresponding server handlers, commands, event/CSID/zone/entity tables through Feature Trace, Behavior Inspector, Dialog Browser and source indexes.
3. Capture controlled, **consented test-server** traces for one golden interaction: establish initial state, trigger one action (e.g. talk NPC), record inbound/outbound messages, server handler/event, timed observable state and final readback; redact identifiers and secrets. Raw packet capture alone is ambiguous (async updates, opcode reuse, entity IDs, multi-packet actions, version differences), so validate against source and readback.
4. Build a canonical evidence crosswalk: human intent → typed action or manual procedure → backend/native runner → packet/handler evidence → readback → assertion/oracle → provenance/confidence and current support tier.
5. Curate initial 10–15 diverse reviewed templates (including paired party and expected-fail probes *only* after owner classification); run negative cases. Promote to supported only after explicit evidence and independent test verification.
6. Reuse import scripts and captured evidence as **untrusted suggestions**, not a packet-replay execution path. Packet structure may describe observation; it cannot by itself define safe action authorization.

## Required principles and scope control
- Reuse routes/components/schema/draft guard from #1402 and offline reconciliation from #1399 where useful; replace the present product-facing authoring surface rather than preserving bad UX.
- Implement a small vertical golden path with reliable data and empty/fail cases before generalizing; avoid writing all six screens first as disconnected mock shells.
- Maintain PASS/FAIL/BLOCKED/UNKNOWN independently from task lifecycle; unavailable evidence = UNKNOWN, never 'inferred PASS'.
- Route behavior to XIHeadless, not direct server packet manipulation, GM commands or an improvised Toolkit executor.
- No new live DB, runtime, permissions or protected merge without separate owner approval.
- P0 owner review must exercise a nondeveloper's results interpretation and a no-code create→publish flow; a full supervised run is a later gate depending on external contract and local runtime access.

## Evidence / constraints
Related: #1197 #1200 #1202 #1255 #1259 #1260 #1261 #1262 #1267 #1403 #1406 #1407. Existing R8 navigation #1334 remains unmerged. Current validated browser 11 PASS on #1402 tested control behavior only, not product usability or actual runner workflow.

## Milestone acceptance
- **M1 Results readable:** real imported fixture with expected/observed and provenance; failure/unknown fixtures; reviewer can explain verdict.
- **M2 Library usable:** game terminology maps deterministically to typed native action/expectation or readback collector with source reference and honest support status; at least 10 characterized examples, not necessarily runnable.
- **M3 Catalog durable:** imported/reviewed scenario draft can be published as a versioned findable entry and reverted via new revision, never silent mutation.
- **M4 Drafts approachable:** human and AI-proposed drafts can round-trip through game-aware editor without raw backend terminology or JSON.
- **M5 Real supervised execution:** only when XIHeadless contract, leases, operator authorization, CI and local disposable run all proven; full audit trail and independent oracle verdict.
