# DSP stock-MyISAM Auction House Test path

Status: backend executor implemented on the dedicated DSP Test branch.

This path exists only for historical DSP schemas where `char_inventory` is MyISAM and the normal rollback-safe player-listing executor correctly refuses to run.

## Safety boundary

Both feature flags are required:

```text
FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES=1
FFXI_MISSION_TOOLKIT_AH_DSP_MYISAM_TEST_WRITES=1
```

The active server profile must resolve as a named **DSP Test** environment and the request must still provide the exact active profile-name confirmation. Live, Topaz, LSB, custom, auto, and unclassified environments remain blocked from this fallback.

The seller must be offline.

## What it does

The executor mirrors stock Darkstar's player-listing order while adding safeguards around it:

1. validates seller/item/price/stack and active DSP AH policy;
2. verifies the seller is offline;
3. locks `auction_house` and `char_inventory` for the short mutation window;
4. captures the exact source item quantity and gil balance;
5. inserts the AH row;
6. removes the exact single item or full stack;
7. deducts the configured listing fee;
8. verifies the AH row, inventory, and gil post-state;
9. unlocks the tables;
10. on an ordinary statement/verification failure while the lock is held, attempts to delete the inserted AH row and restore item/gil pre-state before unlocking.

## Important limitation

This is **not crash-atomic**. MyISAM cannot roll back. If the toolkit process, database server, or host crashes between sequential writes, manual recovery may still be required. Use this only on a disposable DSP Test environment with a recent database backup.

The result contract intentionally reports:

```text
atomic = false
crash_window = true
execution_mode = dsp_myisam_compensating
```

## First test recommendation

Use a low-value ordinary auctionable item on an offline test character with enough gil for the listing fee. Record the character ID, inventory slot, item ID, quantity, and gil before the run so recovery can be verified independently.

The normal transactional player-listing path remains preferred whenever both `auction_house` and `char_inventory` use a transactional engine.

## Active policy note (`ah_list_limit`)

Stock DSP's map server has no `ah_list_limit` setting (it exists only in LSB/Topaz). For the DSP family the
policy loader therefore treats a missing `ah_list_limit` as `0` (no per-seller cap); every other key
(`ah_base_fee_*`, `ah_tax_rate_*`, `ah_max_fee`) is still required.

## First listing validated

Seller 21828 (Gwendy), slot 11, Hi-Potion (4116) x1 at 500 gil on the `DSP` profile (environment `test`):
slot emptied, 6 gil fee deducted (1 base + 1.0% of 500), AH row created at 500, and the Listing Manager
query returns the row with `preview_buy` / `return_to_seller` actions.

## Player purchase fallback

`scripts/auction_house_dsp_myisam_test.py --purchase --auction-id N --buyer-id C --price P --confirmation "<profile>"`
(`dsp_myisam_purchase.py`). On stock DSP only `char_inventory` is MyISAM, so the exact AH row is claimed inside a
real InnoDB transaction (the `auction_house_buy` / `delivery_box_insert` triggers queue seller settlement), the
buyer's gil debit and item grant are guarded writes, the post-state is verified, then the transaction commits.
Any ordinary failure rolls the transaction back and compensates the buyer writes. Still `atomic=false`: a crash
between the buyer writes and the commit can leave the buyer charged without the row claimed. The buyer must be
offline and different from the seller. `--readiness` now reports both listing and purchase readiness.
