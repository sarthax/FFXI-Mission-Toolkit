# Behavior Inspector closeout

Status: **mature evidence-first scripted-behavior inspector**  
Last reconciled: **2026-10-04**

Behavior Inspector is the Workbench surface for understanding what a server-side Lua actor or controller does without executing the script or inventing runtime semantics. It supports LandSandBoat and compatible legacy Topaz/DSP script styles through the shared scripted-behavior extraction model.

## Definition of Done

Behavior Inspector is considered at closeout state when all of the following remain true:

1. supported Lua hooks, callbacks, conditions, effects, state accesses, events, entity references, environment checks, and shared helpers are represented as source-proven evidence;
2. Plain Behavior is the default admin-facing explanation and Technical Graph preserves the complete extracted evidence model;
3. Plain Behavior uses one backend-generated projection contract rather than independently reimplementing semantics in the browser;
4. internal rule/helper plumbing is collapsed without hiding the guards, resolved helper identity, proven helper inputs/effects, state, targets, or source identity needed for drill-down;
5. timer, queue, and listener callbacks are represented as scheduling actions in their parent flow and as separate callback trigger flows, without duplicating callback-body results in the parent summary;
6. literal state transitions and event/outcome relationships are promoted only when the source structure proves them;
7. ambiguous helpers, dynamic predicates, unsupported Lua idioms, and unproven ordering remain explicit unknown/raw evidence instead of being guessed;
8. Plain View cards retain technical node identity and hand off to the same detail/Technical Graph evidence;
9. supported LSB, Topaz, and DSP-style fixtures plus complex combat/non-combat/state/callback/helper stress cases remain green in Workbench Regression;
10. future support for additional dynamic Lua idioms is additive evidence expansion and does not require reopening the foundational Behavior Inspector architecture.

## Extraction coverage

The current extraction/graph model covers the supported deterministic patterns for:

- NPC, mob, door/object, zone, global, and instance scripts;
- normal actor hooks such as interaction, trade, spawn, fight, death, event update, and event finish;
- timer, queue, and registered-listener callbacks;
- named player/entity/instance/zone/server state reads and writes;
- source-proven literal state transitions;
- key-item/item checks and effects where recognized;
- events/CSIDs and literal event outcome branches;
- event-outcome state/resource guards where the predicate is statically supported;
- actor/entity/world-state effects and generic API calls;
- direct and runtime-relative entity references;
- environment/context predicates such as supported weather/time/position/distance/group forms;
- exact `xi.<module>.<function>` shared-helper resolution with exact/ambiguous/unresolved states;
- one-level shared-helper input/effect/direct-call expansion;
- reachable bare-global helpers where the selected behavior actually references them.

Same-zone `Zone.lua`, `globals.lua`, and instance files may be shown as context. They are not promoted to dependencies unless another evidence path proves the relationship.

## Plain Behavior contract

Plain Behavior is the default presentation and groups evidence into:

**Trigger → Requirements → Actions / Events → Results / State Changes**

The production inspection service attaches an evidence-preserving `plain_behavior` projection to the technical graph payload. The browser renders that contract rather than maintaining a second semantic implementation.

The projection deliberately collapses implementation-only `rule`, raw `helper_call`, and nested helper-callee plumbing while preserving exact technical node IDs in the underlying graph.

Guard conditions are recovered even where the technical graph represents them as upstream `condition → rule` edges, so a trigger-descendant walk does not accidentally omit requirements.

Human-readable summaries use only labels and relationships already present in extracted evidence. They do not predict runtime outcomes.

## Callback ownership

Callbacks are a distinct behavioral boundary.

For timer, queue, and listener patterns:

- the enclosing hook shows that the callback is scheduled/registered;
- the callback becomes its own trigger flow;
- downstream callback effects are presented under the callback flow;
- callback-body observations that are also retained under the enclosing hook by the technical extractor are suppressed only in Plain View when their exact source line falls inside the proven callback source span;
- the Technical Graph keeps the complete duplicate technical observations for audit/debugging.

This prevents an admin summary from claiming that a delayed action happened immediately when the parent hook merely scheduled it.

## State and event semantics

Named state is normalized by scope and identity. Reads/writes can be correlated across hooks, but cross-hook execution order remains unproven unless a more specific source-local relationship establishes it.

Literal state transitions are surfaced only where the analyzer proves the selector/state identity, literal guard, and write back to that same canonical state.

Events follow the same conservative rule:

- starting and handling the same literal CSID can establish shared event identity;
- source-local event branch/outcome effects remain attached to the branch that contains them;
- state writes inside a branch may be connected to readers elsewhere as unordered cross-hook evidence;
- dynamic outcome predicates or unsupported nested conditions are not promoted to unconditional behavior.

## Shared helpers

Exact `xi.<module>.<function>` references are resolved against module-scoped globals.

- One exact definition may be expanded one level for upstream inputs, downstream effects, and direct calls.
- Multiple definitions remain ambiguous.
- Missing definitions remain unresolved.
- Raw helper call/callee plumbing is hidden from Plain Behavior after its meaningful helper/effect evidence has been retained.

The inspector does not recursively assume helper semantics beyond its bounded supported traversal.

## Technical Graph

Technical Graph remains the authoritative detailed evidence view for the extracted behavior graph.

It retains:

- exact node and edge identity;
- technical labels and metadata;
- source provenance;
- rule/helper scaffolding hidden by Plain View;
- callback-body observations retained for audit;
- upstream/downstream causal highlighting;
- filtering;
- pan/zoom/Fit/Reset controls;
- persistent node-detail inspector.

Selecting Plain Behavior evidence continues to drill into this same graph rather than creating a separate truth model.

## Safety / evidence boundaries

Behavior Inspector is static evidence analysis, not a Lua interpreter or runtime simulator.

It deliberately does **not** claim:

- runtime execution order from mere cross-hook references;
- that an event start necessarily reaches a particular finish/update handler;
- dynamic helper results that cannot be statically proven;
- meaning for unknown API calls beyond their extracted identity/arguments;
- semantics for compound/dynamic predicates that are outside supported patterns;
- that same-zone contextual controllers directly affect the selected actor without a proven dependency;
- mutation or server-side execution of the analyzed behavior.

Unsupported semantics remain visible as generic/raw Technical Graph evidence whenever extraction can preserve them safely.

## Regression baseline

Workbench Regression covers the scripted-behavior model and extraction families, including:

- generic LSB behavior extraction;
- mixed mob/NPC/object patterns;
- open-ended Lua/API preservation;
- visualizer graph construction;
- named state flow and verified transitions;
- instance/server-global lifecycle state;
- timer/queue/listener callbacks;
- combat stress cases;
- non-combat mission/event stress cases;
- environmental/context conditions;
- entity symbols, aliases, loops, runtime-relative references, and symbolic ranges;
- shared helpers and nested helper callees;
- legacy multi-server behavior search/inspection;
- Plain Behavior rule/helper collapse, guard recovery, callback partitioning, backend/UI contract parity, and drill-down preservation.

Src Layout Regression protects the packaged Behavior Inspector service/canonical-module boundary.

## Future additive work

New Lua idioms, new helper families, or deeper deterministic semantics may be added when real source evidence justifies them. Such additions should preserve the same fail-closed rules and focused regressions.

They are capability expansion, not unfinished foundational Behavior Inspector work.
