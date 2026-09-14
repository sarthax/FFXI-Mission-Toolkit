# Design: LSB-Primary Core + Optional Backport Module (Topaz / DSP)

Status: **design only, not scoped into implementation yet** -- written 2026-09-08, revised
2026-09-08 same day after two real decisions from the user. Nothing in this doc has been built.

**Revision note:** the original version of this doc scoped a symmetric three-way "pick any of
Topaz/DSP/LSB as primary" architecture. The user made two decisions that change the shape of the
work (kept below, not just appended):

1. **LSB is the default/primary target**, not a three-way choice. LSB is the only actively
   developed/distributed core and what most users are actually running; Topaz and DSP are both
   deprecated, and most servers that started on either have since moved to LSB.
2. **Split into modules.** This toolkit was originally built around Topaz (and DSP only to support
   the user's own backporting work) -- most users would never need that functionality at all. The
   real dividing line isn't "which core," it's "browsing/research tooling" (captures, dialog
   search, entity lookup, wiki compiler, packet decoder) vs. "cross-reference/backport tooling"
   (ID Drift, DSP indexing, Topaz-vs-LSB diffing). The former should default to LSB with zero
   cross-reference complexity for a typical user; the latter becomes an optional module serving
   the user's own Topaz/DSP backporting workflow specifically.

**Second revision note (same day):** the module split isn't "one codebase, backport module off by
default for everyone" -- it's **two aligned variants**, each with a real, distinct owner:
- **Public/main toolkit**: LSB-primary, research + capture intake only. This is what most users
  run. No Topaz/DSP awareness needed at all.
- **The user's own variant**: Topaz-primary, with capture intake *and* LSB as a reference/cross-
  check source (the backport module from above, but scoped specifically to "Topaz primary, LSB
  secondary" rather than "no core preference, DSP/Topaz both optional add-ons").

Both variants need to **stay aligned** -- i.e. share code/updates rather than drift into two
unrelated forks. That's a real vote for Open Question #1 below: a config-driven single codebase
(which schema profile is "primary" is a setting, not a fork point) fits "stay aligned" far better
than a literal package split would, since a real fork requires manually porting every future
change to both instead of one shared codebase serving both configurations.

## Goal

Two goals now, not one:

- **Core module** ("browsing/research tooling"): captures, dialog search, entity lookup, browse by
  zone, wiki compiler, packet decoder, key items, item browser. Targets **LSB by default**. A
  typical user installs this, points it at their LSB checkout, and never sees Topaz or DSP
  mentioned anywhere.
- **Backport module** (optional, off by default): ID Drift, DSP indexing, Topaz-vs-LSB
  cross-referencing. Targets the user's own Topaz/DSP-vs-LSB backporting workflow. Not installed/
  enabled for a user who only wants the core module.

## What's already there (real, confirmed -- not being rebuilt)

Still true, and it turns out to matter more for the backport module than the core module now:

1. **All three sources already load into a consistent `<prefix>_<realtablename>` naming scheme.**
   Topaz's own tables are `sql_*` (`build_sql_index.py`), DSP's are `dsp_*` (`build_dsp_index.py`),
   LSB's are `lsb_*` (`build_lsb_index.py`). None of the three write into bare, unprefixed table
   names.

2. **Each source already has its own configurable root path**, resolved independently at read
   time: `settings.get_topaz_root()` / `topaz_server_path`, `settings.get_dsp_root()` /
   `dsp_server_path`, and LSB's own equivalent. DSP's is explicitly optional today (`dsp_server_path`
   empty = "DSP cross-reference disabled") -- the same "optional" treatment DSP already gets is
   the right model for the whole backport module now, not just DSP within it.

3. **Real, confirmed schema differences between the three are already documented in code**, not
   guessed -- found via direct `CREATE TABLE` comparison, per `build_lsb_index.py`'s own comments:
   - LSB has extra columns Topaz's tables don't: `mob_skill_aoe_radius`, a `radius` column on
     several tables, `tertiary_sc`/`knockback`, `damageType`.
   - LSB uses `@ELEMENT_*`/`@SKILL_*` named SQL variables in some columns where Topaz stores raw
     integers.
   - DSP calls `item_equipment.sql` `item_armor.sql` instead (same 10-column shape, different
     filename) -- and per `build_dsp_index.py`'s own header, this was **the exception**: most of
     DSP's schema is confirmed the same shape as Topaz's/LSB's, not a different family of quirks.
   - Status effects are registered differently per source: LSB generates both its C++ enum and its
     Lua `xi.effect` table from `data/status_effects.yaml`; Topaz's is a hand-maintained C++ enum
     (`status_effect.h`) with no equivalent generation step.

## What changes in each module

### Core module (LSB-primary)

Being Topaz-primary today isn't one flag, it's baked into several places -- these all move to
LSB, not to a configurable three-way choice:

- **`settings.py`**: `get_topaz_root()`'s hardcoded fallback (`DEFAULT_TOPAZ_ROOT = "C:/topaz"`)
  becomes LSB's real default checkout shape/location instead.
- **`build_sql_index.py`**: becomes the LSB indexer (LSB's real schema, not Topaz's) -- still the
  one whose output tables drive the homepage's primary stat counts and the base every core-module
  page's queries are written against, just pointed at a different real schema.
- **Zone/dialog/entity indexing** (`build_database.py`, `build_npc_index.py`,
  `build_dialog_index.py`, `mission_toolkit.py`): unchanged -- these already read the FFXI
  *client*, not a server checkout, so they were already core-agnostic in practice.
- **Homepage/nav labels**: "Your Topaz server's own SQL" becomes "Your LSB server's own SQL" (or
  similar), and the backport module's own pages (ID Drift, DSP) move out of the default nav
  entirely -- see module boundary below.

### Backport module (optional, Topaz/DSP-vs-LSB)

This is where the real three-way schema-profile work from the original version of this doc still
applies -- it just now has a fixed shape (Topaz and DSP diffed **against LSB as the baseline**,
not an arbitrary pick) instead of needing to support any-vs-any:

- **`build_lsb_index.py`** effectively inverts role: instead of "LSB cross-referenced against
  Topaz," it becomes the *baseline* the backport module's Topaz/DSP indexers diff against.
- **`build_dsp_index.py`**: unchanged in spirit (DSP was already the optional, user-has-a-real-
  checkout-or-doesn't source) -- stays exactly that, just now diffing against LSB instead of Topaz.
- **A "Topaz indexer" is a new addition inside this module** -- today Topaz's own SQL indexing
  (`build_sql_index.py`) *is* the core module's primary loader; once LSB takes that role, Topaz
  needs its own indexer inside the backport module, structurally parallel to `build_dsp_index.py`
  (own root-path setting, own `topaz_*`-prefixed tables, optional/off by default).
- **ID Drift page**: moves into this module, diff direction fixed to "Topaz/DSP vs LSB baseline."

## Module boundary -- what actually separates them

Given the "split into modules" decision, the practical boundary is:

- **Enablement**: the core module (LSB + client-derived data) is always on. The backport module is
  gated by whether `topaz_server_path`/`dsp_server_path` are set at all -- same "optional, tell us
  if you have it" pattern DSP already uses today, just extended to cover the whole module rather
  than one indexer.
- **Navigation**: backport-module pages (ID Drift, and whatever a "Topaz/DSP browse" page would be)
  only appear in the nav when the module is enabled, instead of always-present links that error or
  show empty state for a user with no Topaz/DSP checkout.
- **Setup flow**: `setup.bat` asks for the FFXI client path and LSB path unconditionally (core
  module); Topaz/DSP paths become a distinctly optional prompt ("skip if you don't do backport
  work"), not bundled into the same required flow as today.
- **Whether this is a literal code split** (separate installable package) **or a feature-flagged
  single codebase** is still open -- see Open Questions below. Nothing above requires deciding that
  yet; the enablement/nav/setup boundary is the same either way.

## Explicitly out of scope for this pass

- Client-side indexing (`build_database.py`, `build_npc_index.py`, `build_dialog_index.py`,
  `mission_toolkit.py`) -- already source-agnostic, no module-split impact.
- Any *new* schema knowledge beyond what's already documented in `build_lsb_index.py`/
  `build_dsp_index.py`'s own comments. Validating LSB-as-primary for real (not just diffed-against)
  may surface a real schema gap nobody's hit yet -- that's a follow-up investigation, not assumed
  solved by this doc.
- Auto-detecting which core a given checkout is -- the user explicitly sets each root path, same
  as today.
- Deciding the literal packaging mechanism for the module split (see Open Questions).

## Open questions (need a decision before implementation starts)

1. **Literal module split, or a feature flag in one codebase?** A true package split (e.g. a
   `mission_toolkit_backport` add-on) vs. one codebase where the backport module's pages/indexers
   just don't register themselves when Topaz/DSP paths aren't set. The latter is far less work and
   matches the "optional, tell us if you have it" pattern DSP already uses -- worth confirming
   that's acceptable before assuming a real package boundary is wanted.
2. **What happens to a page/feature that's genuinely Topaz-specific in a way that isn't just SQL
   naming** -- e.g. a future page that reads Topaz's real C++ source directly. Does an LSB
   equivalent get built, or does that stay backport-module-only permanently (likely correct, given
   it's about Topaz specifically)?
3. **Does the *existing* Topaz-primary install (the user's own, right now) need a migration path**,
   or is it acceptable to treat this as a fresh setup once LSB-primary lands -- i.e. does the
   user's own current database/config need to carry forward, or is a rebuild-from-scratch fine
   given the toolkit is early enough that this is expected?

## Suggested phasing (once the open questions above are answered)

1. Build the real LSB indexer (parallel to today's `build_sql_index.py`, LSB's real schema) and
   make it the core module's primary -- verify the core-module pages (captures, entity lookup,
   dialog search, etc.) work correctly against a real LSB checkout before touching anything else.
2. Move Topaz's current indexing into its own backport-module indexer (structurally parallel to
   `build_dsp_index.py`), gated the same optional way DSP already is.
3. Flip `build_lsb_index.py`'s diff direction so Topaz/DSP diff *against* LSB as baseline; move ID
   Drift into the backport module's nav/enablement boundary.
4. Un-hardcode setup.bat's flow and the homepage/nav labels last, once the module boundary itself
   is proven correct.
