# Zone Entity Mismatch Report — initial comparison engine

This first slice adds a **read-only** evidence report comparing the indexed client
MobList/NPC names to DSP and LSB NPC/mob records, by **zone number** and
**mismatch type**. It does not modify the zone editor, server DB, or client DATs.

## Run

From the repository root, with the Python environment used by Mission Toolkit:

```powershell
python -m workbench.devtools.research.entity_mismatch_report --db src/workbench/devtools/indexing/ffxi_zone_database.db --zone 44 --format json --output zone44.json
python -m workbench.devtools.research.entity_mismatch_report --db src/workbench/devtools/indexing/ffxi_zone_database.db --zone 44 --format csv --output zone44.csv
```

Confirm the indexed database path in your local installation; the example path
is not guaranteed across migration layouts. Run the relevant client, DSP and
LSB index builders beforehand. The engine opens the SQLite database read-only.
The JSON contains source coverage, counts grouped by mismatch type, individual
source-attributed evidence rows, and interpretation limitations.

## Included classifications

- Missing in client index, missing in server NPC/mob index (only when both
  sources contain indexed records for this zone).
- Name mismatches after case/punctuation normalization; DSP vs LSB name
  disagreements are separate from client-vs-server disagreements.
- Same ID present in both NPC and mob tables, or DSP/LSB place the ID
  in different table types.
- Server-side zero XYZ and DSP/LSB XYZ differences greater than 1 world unit.
- Explicit missing/empty-index coverage instead of falsely reporting absent entities.

## Not yet covered / next implementation slices

1. Wire zone/type/source drill-down and CSV/JSON export into the
   `/gaps` browser; retain existing zero-position and unregistered modes.
2. Ingest a **typed client model catalog and positional capture evidence**
   keyed by client build, zone, entity ID, and observation timestamp; only then
   add model or client-vs-server position comparisons.
3. Add verified mob group/pool model resolution (do not compare an arbitrary
   pool model against an NPC model) and evidence-backed wrong-table candidates.
4. Compare multiple client builds and server snapshots, add match-provenance
   and exclusion/review decisions, then persist curated audit findings.
5. Cross-check zone-ID decoding and indexes against real captures and SQL for
   zones with nonstandard/instance actor ID allocation.

No automatic correction is performed. Zero coordinates may reflect scripted
placement; missing captures do not prove missing runtime entities.
