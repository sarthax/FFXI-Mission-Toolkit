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
