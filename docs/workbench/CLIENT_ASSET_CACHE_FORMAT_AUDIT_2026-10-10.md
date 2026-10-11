# Client DAT / xi-tinkerer integration audit — 2026-10-10

## Existing verified code surfaces

- `src/workbench/editors/items/client_asset_cache.py`: lazy, per-installation SQLite cache for English client item DAT records and extracted PNG icons. Existing Character Editor inventory and Auction House item views consume it. Cache health/freshness work is tracked separately by PR #919.
- `src/workbench/client/dat/inspector.py`: read-only file-ID/path lookup, empirically attempted parsers, previews, raw header and generic block-chain inventory. No format is recognized solely on the basis of a DAT ID.
- `src/workbench/client/dat/global_tables.py`: direct xi-tinkerer DMSG reads for key-item and assault-mission text (with historical MassExtractor XML fallback); this is an importer, not the shared item-icon cache.
- Dialog indexing and dialog drift tooling already maintain searchable text stores; avoid duplicating these tables in the icon cache.
- Japanese/English auto-translate and client text reference data already feed the wiki translation/client-terms workflow; do not create a second authority.

## Registered Inspector parser surface (binding version dependent)

The existing DAT Inspector lists `parse_dialog`, `parse_dmsg_table`, `parse_xistring_table`, `parse_entity_names`, `parse_events`, `parse_menu_table`, `parse_item_info`, `parse_status_info`, `parse_auto_translate`, and `parse_furniture_data`. The updated `parser_capabilities()` explicitly distinguishes locally callable methods from registered-but-unavailable methods. A callable parser still does *not* establish that a particular DAT uses that format.

The generic header section scan recognizes numeric block tags 32 (texture), 41 (skeleton), 42 (mesh), and 43 (animation), but those tags do *not* constitute tested extraction or render support. Model/animation decoding remains owned by existing viewer tools; do not build a second persistent cache before representative real-file tests and a measurable performance benefit.

## Decision / next bounded implementation slice

1. Reuse the existing item-icon cache and dialog/text indexes rather than flattening them into a single generic schema.
2. Validate parser availability against a local installed xi-tinkerer build and sample DATs. Capture parser outcomes and exact file provenance before enabling additional consumers.
3. Prioritize per-install client dialog/index health and on-demand icon discovery in DAT Inspector. Cache only durable, reusable extracted records; keep raw DAT bytes at the original installation.
4. Test multilingual text source identity across client builds and avoid silently treating translation or external reference terms as original DAT text.
5. Preserve source-file stat fingerprints, explicit client-root namespaces, fail-closed unknowns, read-only inspection and no packaged copyrighted game assets.

## Not established by this audit

This GitHub-only review does not enumerate dynamically exported symbols from a running local xi-tinkerer wheel, validate graphics decoders on real DATs, or measure cache performance on a complete installed FFXI client. Those require the actual installed bindings and sample client DATs.
