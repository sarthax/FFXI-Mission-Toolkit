# Test Catalog — versioned design-only scenario revisions (#1410)

**Status:** slices 1 and 2 implemented (store, review states, search, local API, and a read-only browse page). No Scenario
Developer integration and no importer yet. Nothing here makes a scenario runnable.

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
2. **Done:** browse page. The Test catalog tab (`/feature-testing?tab=catalog`) starts with a "Saved scenario revisions" section (search by
   text, feature, tag and state; latest revision and state; current published revision; empty and not-configured states;
   local readers only). Each row opens `/feature-testing/catalog-entry/{feature}/{case}`, a read-only page with the revision table
   (state history with reviewer notes, source, content hash), a readable view of one revision (default: the current published
   one, else the latest; `?revision=N` picks another) including the saved typed steps as When / Then, and the full JSON. The
   page says plainly that it is design-only and that publishing does not make anything runnable. The existing built-in
   definitions follow below it, unchanged.
3. **Done:** "Add to catalog" from Scenario Developer. Under the saved-drafts controls, *Add selected saved draft to the Test catalog*
   (optional tags, operator token) calls `POST /feature-testing/test-catalog/from-draft`. The server reads the stored draft, so only
   what was **saved** is added (never unsaved edits or client-sent content); it becomes the next catalog revision in the DRAFT
   state with `source = draft:<feature>/<case>@r<draft revision>`. If the draft moved on since the list was read, or its content
   already equals the latest catalog revision, nothing is added and the message says why. Review and publishing are not in the
   UI yet (the operator API only).
4. Import of native XIHeadless scenario JSON into draft revisions. The earlier offline prototype (#1424) predates the typed
   action library and is not reused as is; the importer should call `typed_action_library.review_native_steps`.
5. Hand-off to supervised run (#1412): only a `PUBLISHED` revision with a reviewed execution contract may ever be offered,
   after separate owner approval. Out of scope here.

## Not established
This is storage and review bookkeeping. It does not show a scenario is correct, supported by the runner, or safe to run, and
"published" means only "a reviewer recorded a decision". Existing built-in specifications are not copied in. The store has no
backup, export or multi-user story beyond the SQLite file.
