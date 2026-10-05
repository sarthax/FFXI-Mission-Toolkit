# Auction House player-backed listing

Status: guarded DSP/Topaz Test executor implemented.

This path creates a real Auction House listing from one exact offline character Inventory slot. It mirrors the source-backed legacy listing semantics instead of injecting synthetic supply.

## Contract

The executor requires:

- active named Test environment;
- explicit DSP or Topaz lineage;
- `FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES=1`;
- exact Test profile-name confirmation;
- legacy-compatible AH schema;
- active lineage configuration from `conf/map.conf` (Topaz) or the supported DSP active config path;
- transactional `auction_house` and `char_inventory` tables;
- offline seller;
- exact seller Inventory slot and expected item ID;
- auctionable item metadata;
- for a stack listing, the selected Inventory row must contain exactly one full stack;
- enough seller gil for the active-config listing fee;
- seller active-listing count below the active-config limit.

Execution locks the selected Inventory item row and gil row, calculates the fee from the active server policy, verifies the active listing count, inserts the AH row, removes the exact item/stack quantity, deducts the fee, verifies all post-state, and commits. Any mismatch rolls the transaction back.

## Legacy storage-engine boundary

Historical Topaz/DSP schemas may use MyISAM for `char_inventory`. That engine cannot participate in rollback with the InnoDB Auction House table. The toolkit therefore blocks direct player-backed listing when either `auction_house` or `char_inventory` is non-transactional or unknown.

This is intentional. The toolkit does not claim transaction safety that the server schema cannot provide.

The existing synthetic/admin listing path remains available for Test economy seeding because it mutates only the Auction House row and does not remove player inventory or charge a fee.

## API

- `GET /auction-house/test-write/player-listing-readiness.json`
- `POST /auction-house/test-write/player-listing.json`

Required write payload fields are `seller_id`, `inventory_slot`, `item_id`, `price`, `stack`, and `confirmation`.

## Next legacy option

For stock MyISAM servers, a future server-native bridge can call the map-server listing machinery (or a purpose-built server admin handler) so player state is mutated through the same runtime path as the game client. Until that exists, direct database player listing remains fail-closed on MyISAM.
