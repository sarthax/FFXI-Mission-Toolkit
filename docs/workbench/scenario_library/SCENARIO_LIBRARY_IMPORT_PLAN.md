# Scenario Library Import Plan (DRAFT)

Draft-only. Never auto-publish; owner approval is required per scenario.

1. **Fixture shape**: each catalog entry keeps the `xiheadless` native payload verbatim plus `provenance`, `evidence_class`, `confidence`; Toolkit fields are derived, not substituted.
2. **Stage A**: import entries with `support_status: supported` as drafts into the drafts DB (#1410).
3. **Stage B**: add item/key-item expectations (G-01), then import partial entries.
4. **Stage C**: quest/mission readback (G-02), then promote quest candidates after dat-extractor verification (G-03).

## Top 10 recommended first slices

1. SL-MOG-009 (already runnable)
2. SL-NPC-001 Argus event
3. SL-ZONE-001 settle
4. SL-PARTY-001 party formation (recorded pass)
5. SL-ASLT-001 Leujaoam entry
6. SL-ITEM-001 item possession (needs G-01)
7. SL-KI-001 key item (needs G-01)
8. SL-MSN-WOTG-01..05 (WoTG missions 1-5 sample; replaces the earlier Zon-Fobun slot per owner direction)
9. SL-MSN-WOTG-06..10 (WoTG missions 6-10 sample; replaces the earlier Ardea slot)
10. SL-ZONE-002 zone_to

## Proposed next issues

- Item/key-item expectation and oracle in XiHeadless
- Quest state readback tool
- Zone-qualified NPC id verifier
- Toolkit draft import for `scenario-library-draft/1`
