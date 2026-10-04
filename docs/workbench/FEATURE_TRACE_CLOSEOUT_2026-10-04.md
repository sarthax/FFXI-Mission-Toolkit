# Feature Trace closeout — 2026-10-04

Status: **current merged provider-closure baseline**

Feature Trace is now mature enough to pause implementation and move into real-object testing. The current provider architecture supports deterministic, read-only navigation across server, client, capture, research, validation, package, and reference evidence without manufacturing canonical graph truth.

## Forward-closure matrix

| Source record | Explicit stored field(s) | Target | Relationship / basis | Fail-closed rule |
| --- | --- | --- | --- | --- |
| `reference_wiki_mappings` | `mapping_status`, `target_table`, `target_key` | exact indexed implementation row | `REFERENCE_MAPPING_TARGET` | Only `MAPPED` rows with one exact target resolve. Ambiguous, unresolved, duplicate, missing, unsafe, or composite-unclear targets produce no link. |
| `captures` | `client_build` | `identity_snapshots.version` | `CAPTURE_CLIENT_BUILD` | The stored build must resolve to exactly one client snapshot. Duplicate snapshots for the same build produce no link. |
| `research_sessions` | `feature_root` | canonical `features.feature_id` | exact provider→canonical feature closure | Literal ID only; missing or duplicate target produces no link. |
| `research_sessions` | `entity_root` | canonical `entities.entity_id` | exact provider→canonical entity closure | Literal ID only; missing or duplicate target produces no link. |
| `research_proposals` | `subject_id` | canonical node | generic exact subject closure | The ID must resolve in exactly one canonical namespace. Cross-namespace ambiguity produces no link. |
| `validation_runs` | `feature_id` | canonical `features.feature_id` | exact provider→canonical feature closure | Literal ID only; missing or duplicate target produces no link. |
| `validation_results` | `subject_id` | canonical node | generic exact subject closure | The ID must resolve in exactly one canonical namespace. Cross-namespace ambiguity produces no link. |
| `migrations` | `feature_id` | canonical `features.feature_id` | exact provider→canonical feature closure | Literal ID only; missing or duplicate target produces no link. |
| `migration_actions` | `artifact_id` | canonical `artifacts.artifact_id` | exact provider→canonical artifact closure | Literal ID only; missing or duplicate target produces no link. |

These closures are navigation evidence. They do **not** create or persist canonical `entity_relationships` rows as a side effect.

## Existing deterministic implementation wiring

The forward-closure work builds on the already-established deterministic provider relationships, including:

- item detail → base item;
- spawn → mob group;
- mob group → mob pool;
- mob group → drop rows;
- drop row → item;
- pet → mob pool;
- Blue Magic wiring → spell / mob skill where schema support exists;
- instance entity → instance;
- instance entity → uniquely matching NPC or mob where exact identity exists;
- client identity record → client snapshot;
- research proposal → research session;
- validation result → validation run;
- migration action / scope review → migration;
- reference mapping / review / alignment relationships.

## Safety contract

Feature Trace must continue to follow these rules:

- numeric coincidence is never identity;
- names are search/discovery aids, not identity joins;
- provider-native relationships remain read-only navigation evidence;
- ambiguous identities fail closed;
- duplicate target rows fail closed;
- missing evidence remains `UNKNOWN`, not `ABSENT`;
- static source relationships do not imply runtime ordering;
- runtime observations remain separate from implementation claims;
- generated focused-mode evidence is never silently persisted into the canonical graph.

## Regression coverage

The current regression suite covers:

- deterministic provider relationships;
- server drop-chain traversal;
- reference-wiki mapping target closure;
- capture → client-build snapshot closure;
- Research / Validation / Package → canonical closure;
- cross-namespace `subject_id` ambiguity rejection;
- duplicate target rejection;
- focused-mode and provider-generated evidence boundaries;
- no synthetic canonical graph edge creation during provider traversal.

The closure batch was merged through PRs #514, #516, and #521, with Workbench Regression and Src Layout Regression green on each slice.

## Current testing boundary

Feature Trace is at a good implementation stopping point. The next step should be real-data testing rather than speculative provider expansion.

Recommended test set:

1. one NPC/entity with SQL + Lua + client identity + capture evidence;
2. one mission/quest with research and validation records;
3. one mob with full spawn → group → pool/drop → item traversal;
4. one capture with a known client snapshot;
5. one reference-wiki claim/mapping into an implementation row;
6. one migration/package record tied to a canonical feature and artifact;
7. deliberately ambiguous examples to verify the UI visibly fails closed.

Future development should begin as a distinct phase: **reverse discovery** from a canonical feature/entity/artifact back to the Research sessions, Validation records, migrations, captures, and reference evidence that explicitly point to it. That work should preserve the same exact-ID and ambiguity rules rather than infer reverse identity from names or numeric similarity.
