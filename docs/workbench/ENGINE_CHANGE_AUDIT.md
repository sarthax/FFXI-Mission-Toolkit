# Engine Change Audit

Date: 2026-09-25

## Direct inspection

The repository contains `backport-workspace/dsp-engine-changes/` with a bundled `_example_change/` scaffold.

The scaffold explicitly requires two durable artifacts for each engine capability:
1. README.md describing the real gap, actual C++ change, and verification evidence.
2. A real scoped .diff captured against the DSP target checkout.

The current bundled example is intentionally a template/placeholder, not a real engine change.

## Architectural finding

The existing engine-change workspace is already evidence-oriented, but it is currently a human documentation convention rather than a machine-readable implementation/dependency model.

This audit therefore adds `engine_change_index.py` as the first integration layer. It indexes each change directory, records whether README/diff evidence exists, extracts changed paths and lightweight symbol hints from real diffs, and explicitly marks placeholder/template records.

It does not infer correctness or semantic equivalence.

## Required evolution

Each real engine change should eventually gain machine-readable metadata for:
- feature_id
- source snapshot
- target snapshot
- artifact(s)
- symbols
- declarations
- definitions
- Lua bindings
- enum/constant dependencies
- packet dependencies
- build targets
- compile conditions
- validation evidence
- migration state

The README/.diff pair remains valuable and should remain the durable human-review record.

## Important verified source finding

The existing `data/dsp_namespace_map.json` documents a real Topaz -> old-DSP API shape difference for `GetNPCByID`: Topaz accepts an instance object as its second argument, while the old DSP Lunar implementation expects a CBaseEntity and derives the instance from it. The project records that this caused a live server crash and that 193 call sites were mechanically corrected. This is precisely the class of incompatibility that name-only binding audits cannot detect.

## Additional verified finding

The SQL schema map records a real `mob_groups` identity difference: Topaz uses composite `(zoneid, groupid)` identity while DSP uses globally unique `groupid`. The project also records a separate content-duplication incident where ID collision checks alone missed existing logical content. This reinforces the universal rule that physical IDs and logical identity must remain separate.

## Next engine work

1. Upgrade `engine_change_index.py` from lightweight diff indexing to source/symbol indexing.
2. Add C++ declaration/definition extraction.
3. Resolve Lua binding registrations to C++ symbols.
4. Index enum/constants and packet references.
5. Detect build-system inclusion.
6. Emit standardized DependencyEdge and Implementation records.
7. Add target comparison without assuming identical C++ layouts or binding systems.
