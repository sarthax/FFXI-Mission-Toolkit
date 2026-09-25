# Evidence-Aware LLM Research Architecture

Status: ROADMAP / P1
Baseline: 2026-09-25

## Current state

The toolkit already has a useful but narrow local-model integration:
- `llm_client.py` talks to Open WebUI/Ollama and treats model output as draft-only.
- `llm_db_tools.py` exposes read-only SQLite research tools.
- `llm_log.py` and the GUI preserve model interaction history.

Those constraints are good and should remain. The rework should expand capability by giving the model better *typed access to Workbench evidence*, not by relaxing evidence discipline.

## Architectural goal

The LLM should behave as a research/orchestration client of the Workbench, not as an authority and not as a privileged mutation engine.

A model should be able to:
1. receive a research question,
2. discover the relevant canonical feature/entity,
3. crawl bounded server/reference/client sources,
4. traverse the canonical graph,
5. compare source forks logically,
6. inspect bindings/C++/packets/build/runtime/client evidence,
7. identify contradictions and missing evidence,
8. propose migration/validation actions,
9. produce a reproducible research report carrying provenance.

It should not be able to silently turn a suggestion into a shipped SQL/Lua/C++/DAT change.

## Core services

### LLMProvider
Abstract provider contract:
- list_models()
- complete/chat()
- capabilities()
- usage/latency metadata

Initial implementations:
- OpenWebUIProvider
- OllamaDirectProvider (optional)
- future remote provider adapters where explicitly configured

The rest of the toolkit must not depend on Open WebUI response shapes directly.

### ResearchSession
Persist:
- research_session_id
- user question
- provider/model
- tool policy
- source/target snapshot IDs
- selected feature/entity roots
- tool calls and normalized results
- evidence IDs cited
- proposed findings
- final draft report
- verification state
- timestamps/usage

A session should be replayable against pinned snapshots.

### Typed Workbench tool registry

Prefer typed tools over arbitrary SQL. Raw read-only SQL remains an expert escape hatch.

Recommended tools:
- graph.search
- graph.trace
- feature.check
- feature.candidates
- server.schema
- server.logical_record
- server.compare
- entity.lookup
- entity.relationships
- cpp.symbol
- binding.lookup
- enum.lookup
- packet.lookup
- packet.handlers
- capture.backtrace
- build.target
- client.capability
- dat.lookup
- migration.plan
- migration.explain
- validation.status
- validation.plan
- reference.search
- reference.compare
- source.search
- source.read

Every result should include provenance fields where available:
- canonical node ID
- source snapshot
- Evidence ID
- file/path/location
- confidence
- status
- authority/source domain

### Bounded source crawler

Allow the research agent to crawl configured roots without requiring each path to be exposed by the GUI first.

Required controls:
- configured roots only
- source snapshots/pinned commits
- include/exclude glob rules
- maximum files/bytes/depth
- file-type allowlist
- no secret/key directories
- no writes
- tool-call/time/token budget

The crawler should combine exact text search, structural indexes, and semantic retrieval. Semantic retrieval never replaces exact-source verification.

### FindingProposal

Model-derived conclusions should enter a staging object rather than canonical truth.

Suggested fields:
- proposal_id
- research_session_id
- subject_id
- field/question
- proposed_value/conclusion
- status = PROPOSED
- supporting_evidence_ids
- contradicting_evidence_ids
- confidence requested by model
- deterministic verification requirement
- notes

Promotion to a canonical Finding must require either:
- deterministic analyzer/validator evidence, or
- explicit human review.

### Change proposals

LLM may generate:
- MigrationAction proposals
- patch/diff proposals
- analyzer recommendations
- validation plans
- package manifests

The model should not directly mutate source trees, databases, DATs, or packages. Application belongs to deterministic migration services with explicit review/authorization.

## Permission profiles

READ_ONLY_RESEARCH
- graph/database/source/reference reads
- report generation
- no mutation proposals applied

PROPOSE_CHANGES
- all read tools
- create FindingProposal/MigrationAction/patch proposals
- no automatic application

VALIDATION_ORCHESTRATOR
- all read tools
- invoke approved deterministic validators
- attach ValidationResult records
- no arbitrary code/SQL mutation

Future write-enabled automation, if ever added, should be narrower than filesystem or SQL access and operate only through typed migration actions.

## High-value workflows

### Feature research
"How is Excavation Duty implemented in LSB and what would DSP need?"
The model can gather Lua, SQL logical records, entities, C++/bindings, packets/build dependencies, compare with DSP, and return evidence-backed gaps plus migration proposals.

### Root-cause research
"Why does this Assault instance crash?"
Combine target source, instance SQL, entity membership, missing bindings/C++ APIs, capture evidence, and historical validation results.

### Client/server synchronization
"Why does server support exist but my 2019 client cannot use it?"
Combine server implementation, client capability evidence, packet support, command tables, DAT/EXE/DLL findings, and captures.

### Cross-fork discovery
"What LSB features can this DSP fork backport?"
Use canonical feature/dependency comparisons to discover candidates, but do not rank feasibility without explicit criteria/evidence.

### Research gap detection
Find graph paths ending in UNKNOWN/MISSING evidence and suggest the next deterministic analyzer or capture needed.

## Evaluation

Add model-independent fixtures with canned tool results to test that the research layer:
- cites evidence IDs
- preserves UNKNOWN and INFERRED
- reports contradictions
- does not claim absence from a missing edge
- does not convert reference/wiki evidence into server truth
- does not propose direct writes outside the proposal layer
- selects the correct typed tool for common research questions

Provider/model quality can then be evaluated separately from Workbench safety/evidence behavior.

## Migration from current implementation

1. Keep `llm_client.py` functional as a compatibility entry point.
2. Move provider behavior under `workbench/research/providers/`.
3. Wrap `llm_db_tools.py` as one tool provider rather than the complete LLM capability.
4. Add typed graph/server/packet/capture tools first.
5. Add ResearchSession persistence and provenance.
6. Update the GUI to render tool/evidence trails, proposed findings, contradictions, and verification state.
7. Add bounded source crawling.
8. Add proposal-generation hooks to the migration and validation engines.
9. Remove duplicated prompt/tool orchestration from GUI routes once the service layer is stable.
