# Auction House admin presets

Auction House admin presets are toolkit-local reusable configurations for the DSP/Topaz administration workflows.

## Supported preset types

### Cleanup rule

A cleanup preset can store seller, category, item, price, age/listed-before, result-limit, and default action criteria. The supported default actions are `return_to_seller` and `admin_buy`.

### Synthetic category seed

A seed preset can store seller ID, category ID, fixed asking price, stack mode, copies per item, and item limit.

## Safety model

Presets are configuration only. They never store:

- Test profile confirmation text
- write authorization or feature-flag state
- preview/replay tokens
- credentials
- active environment identity

Opening or using a preset does not authorize a write.

`Preview live` resolves the saved configuration against the currently active server and returns the exact current target evidence. The API creates a preset preview fingerprint over the saved preset version plus stable target evidence. Cleanup fingerprints bind the exact cleanup criteria and exact cleanup preview token. Synthetic seed fingerprints bind the exact category expansion, price/stack parameters, and item set.

Execution re-runs that live preview. If the saved preset changed or the live target evidence no longer matches, execution fails closed as stale before invoking a write executor.

After a write attempt, the UI discards its preview so the operator must preview again before another execution.

## Persistence

Presets are stored in toolkit-local SQLite at:

`data/auction_house_presets.db`

The store is separate from the FFXI server database and does not alter server schema.

## UI

Use **Server -> AH Presets** or `/auction-house/presets`.

The page supports creating, listing, live-previewing, executing, and deleting saved presets. Actual mutations continue to use the existing guarded cleanup and synthetic-seeding executors, including named Test environment, feature flag, exact profile confirmation, and DSP/Topaz lineage requirements.
