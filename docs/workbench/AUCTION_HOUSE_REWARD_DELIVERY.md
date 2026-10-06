# Auction House Reward Delivery

## Status

DSP/Topaz Test-only guarded reward/mail administration surface under **Server -> Auction House -> Inbox**.

This feature is intentionally separate from Auction House sale settlement. It uses the already-verified legacy `delivery_box` contract to queue administrator-supplied items into character Mog delivery boxes.

## Supported workflows

- create and save reusable item-bundle templates;
- build an ad-hoc bundle without saving it;
- preview delivery to one or more selected character IDs;
- preview delivery to all characters in the active server database;
- execute the exact previewed target set;
- report success/failure per recipient when a large delivery partially succeeds.

## Template storage

Templates are toolkit-local and stored in:

`data/auction_house_reward_templates.db`

A template contains only:

- template name;
- item IDs;
- quantities.

Templates never store server credentials, Test confirmation text, preview authorization, replay IDs, environment identity, or feature-flag state.

## Delivery contract

The executor uses the verified DSP/Topaz delivery shape:

- `box = 1`;
- `slot = 0` before the trigger assigns the queue slot;
- `itemsubid = 0`;
- `extra = NULL`;
- `senderid = 0`;
- `sender = 'AH-Admin Reward'`;
- `received = 0`;
- `sent = 0`.

`delivery_box_insert` must exist and `delivery_box` must use a transactional storage engine. The executor refuses to proceed if either requirement is not proven.

This first version delivers ordinary item rows only. Augmented/custom `extra` payloads are deliberately out of scope until their lineage-specific serialization is verified.

## Preview binding

Every preview resolves:

- the exact character IDs and names;
- the exact item IDs;
- current item stack sizes;
- requested quantities.

It returns a SHA-256 preview fingerprint plus unique `preview_id` and `replay_id` values.

Execution resolves the live state again and requires an exact fingerprint match. Character creation/deletion/renaming in an `all` preview, changes to a selected recipient set, deleted/changed item metadata, or changed quantities therefore invalidate the preview.

The replay ID is claimed once in the toolkit-local AH audit ledger before server mutation begins. Reusing the same preview is rejected.

## Transaction boundary

Each recipient is processed as one database transaction containing the entire bundle.

This means:

- a recipient gets all rows in the bundle or none of them;
- a full/invalid delivery box can fail one character without rolling back previously completed characters;
- large fan-out operations can therefore return `partial` with per-character results.

A failed or interrupted fan-out does not automatically replay the same preview because the replay ID has already been consumed. Create a new preview for any recipients that still require delivery. This favors duplicate prevention over automatic retry.

## Bounds

- maximum 20 distinct item rows per bundle;
- quantity must be positive and cannot exceed the current `item_basic` stack size;
- maximum 5,000 resolved recipient characters per preview;
- maximum 50,000 generated delivery rows per operation.

If an `all` operation exceeds these limits, use selected-character batches.

## Write guard

Actual delivery uses the existing legacy Auction House Test-write gate:

- active named environment required;
- environment kind must be `Test`;
- family must be DSP or Topaz;
- compatible legacy AH schema must be detected;
- `FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES` must be enabled;
- operator must type the exact active Test profile name.

Live, LSB, custom/unclassified and legacy fallback environments remain blocked by this executor.

## Future extensions

Potential additive work after real-server validation:

- recipient selection by account, character-name search, job/level or other proven character metadata;
- scheduling/announcements around reward campaigns;
- augmented item delivery after `extra` serialization is source-verified;
- delivery history/reporting from toolkit audit evidence;
- production authorization as an independently reviewed policy, not a relaxation of the Test gate.
