# Capture Search / Data Explorer milestone — promoted 2026-09-30

Status: **PROMOTED TO `main`**

Promotion head: `b85490723c73440abd35d1a0c69b9bba41e941cb`

## Completed milestone scope

The Capture discovery / forensics redesign is promoted as a complete usable milestone. The promoted surface includes:

- Capture Data Explorer replacing the former raw Capture Query workflow.
- Modular cross-capture Evidence Search for Events/Dialogue, Raw Protocol, Entities, Battle/Actions, Items/KIs, Vendors/Shops, Crafting, Chat/Text, Spatial/Movement, and Environment/World State.
- Exact row/source provenance with Source Locator drill-down.
- Provenance-safe Related Evidence from overlapping hashed source spans and identical SQLite source rows.
- Explicit non-temporal packet correlation using exact raw-byte equivalence and unique shared decoded-field matches.
- Deterministic entity-identity Related Evidence using capture + zone + numeric entity ID, with ambiguity guards for zone-less battle-action actors.
- Deterministic ordinary-item Related Evidence across structured item/vendor/crafting observations using explicit `item_id` only.
- Key-item IDs remain a separate namespace and are not joined to ordinary item IDs.
- Runtime regressions for entity identity ambiguity/zone rules and ordinary-item identity/namespace separation.

## Evidence rules retained

The promoted milestone deliberately does **not** treat any of the following as verified identity by itself:

- timestamp proximity;
- nearby packet sequence numbers;
- matching entity/item names;
- matching prices;
- same display text;
- same numeric value across unrelated namespaces;
- ambiguous packet-correlation candidates.

Temporal/alignment relationships remain available in their appropriate analysis views but are not promoted into verified Related Evidence.

## Follow-on enhancements — not promotion blockers

These remain worthwhile next work, but are explicitly outside the promoted milestone:

1. **Deterministic chat/native-source correlation** — link canonical chat and sibling normalized evidence only where `source_format` + `source_native_id` semantics are proven to identify the same native record. Verify PacketDB and other source namespaces before creating any hard relationship.
2. **Richer Related Evidence summaries** — show compact normalized context on result cards so users can understand why evidence is related without opening every raw row.
3. **Additional deterministic domain relationships** — add only where a stable explicit identity/key exists; do not regress to name/time heuristics.
4. **Real-user UX tuning** — adjust default panel expansion and promote high-frequency actions based on actual use.

## Next roadmap handoff

With this milestone promoted, Capture Search work returns to enhancement mode. The broader Workbench roadmap can move to the next active area while the follow-on capture items above remain independently schedulable.
