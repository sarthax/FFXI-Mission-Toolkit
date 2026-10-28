# Test Catalog — versioned design-only scenario revisions (#1410)

**Status:** first slice implemented (store, review states, search, local API). No page, no Scenario Developer
integration and no importer yet. Nothing here makes a scenario runnable.

## What it is
A catalog of scenario **revisions**, distinct from the global Feature Catalog (Toolkit capabilities, `/feature-catalog`)
and from the built-in published specifications behind `/feature-testing?tab=catalog`. An entry is a
`(feature_id, case_id)` identity. Its content only changes by adding a new immutable revision; a revert is a new revision
with the old content. A revision's review state moves forward through append-only events.

## Decisions taken (the recommended options; change them here if the owner prefers otherwise)
1. **Storage:** the local authoring SQLite file that already holds spec drafts (`MISSION_TOOLKIT_TEST_DRAFTS_DB`); two tables
   are created on first catalog use. This is the local Toolkit store, not a DSP/production database, and existing drafts are
   untouched. Triggers abort UPDATE and DELETE on both tables, so history is append-only.
2. **States:** `DRAFT` → `VALIDATED_DESIGN` → `PUBLISHED` → `ARCHIVED`, forward only (`ARCHIVED` is reachable from any earlier
   state). A stored revision is re-validated against today's rules before it advances. **Publishing records a reviewer
   decision and needs a note.** The current published revision of an entry is its latest `PUBLISHED` one; an unreviewed new
   revision never displaces it.
3. **Nothing is runnable:** every revision must stay `execution_status: design_only` with `runner: unassigned`, and every
   response carries `execution_enabled: false` and `run_availability: UNAVAILABLE`. Publishing is not an execution grant;
   running stays the separate, gated path in #1412.
4. **Search and categories:** the feature is the category; free tags (lowercase, at most 10) and text search over name,
   purpose, case id and tags; filter by feature, tag and the latest revision's state.
5. **Concurrency:** adding a revision needs the latest revision number the caller saw (compare-and-swap), like drafts.
6. **Access:** reads are local-only and same-origin and expose only design-only specifications; writes need the operator
   token, like draft saves.
7. **Provenance:** each revision keeps its `source` (`draft:…`, `import:…` or `manual…`), the SHA-256 of its stored content and
   its `base_spec_sha256` (the same fingerprint run comparison uses), and when it was created.

## API (local; not in the OpenAPI schema)
`GET /feature-testing/test-catalog?q=&feature_id=&tag=&state=&limit=&offset=` · `GET /feature-testing/test-catalog/{feature}/{case}`
· `POST /feature-testing/test-catalog/revisions` (operator) · `POST /feature-testing/test-catalog/state` (operator).

## Slices
1. **This one:** `test_catalog.py`, the routes, and tests (immutability, forward-only states, conflict, design-only guard,
   search, auth).
2. Browse page: a searchable list and entry detail with revision and state history, inside the existing Test catalog tab.
3. "Add to catalog" from Scenario Developer (a saved draft becomes revision N+1; `source = draft:…`).
4. Import of native XIHeadless scenario JSON into draft revisions. The earlier offline prototype (#1424) predates the typed
   action library and is not reused as is; the importer should call `typed_action_library.review_native_steps`.
5. Hand-off to supervised run (#1412): only a `PUBLISHED` revision with a reviewed execution contract may ever be offered,
   after separate owner approval. Out of scope here.

## Not established
This is storage and review bookkeeping. It does not show a scenario is correct, supported by the runner, or safe to run, and
"published" means only "a reviewer recorded a decision". Existing built-in specifications are not copied in. The store has no
backup, export or multi-user story beyond the SQLite file.
