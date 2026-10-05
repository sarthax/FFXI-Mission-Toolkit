# Auction House Activity / Audit

`Server -> AH Activity` is the unified read-only administrative timeline for Auction House operations.

## Sources

The view merges three toolkit-local evidence sources:

1. **Execution outcomes** in `data/auction_house_audit.db` (`ah_execution_events`).
   - price changes
   - synthetic single listings
   - synthetic category seeding
   - player-backed listings
   - player purchases
   - admin buys
   - returns
   - multi-select batch actions
   - rule-driven cleanup
2. **Preview/replay evidence** already stored in the append-only AH audit ledger.
3. **Reward campaigns** from `data/auction_house_reward_campaigns.db`.

The activity layer never connects to or mutates the FFXI server database.

## Execution audit semantics

Executor outcome rows are appended **after** the server executor returns.  The audit SQLite write is deliberately outside the FFXI server transaction.  If local audit persistence fails after a server commit, the toolkit must not claim that the server transaction rolled back.

Execution events retain normalized indexed fields for:

- UTC timestamp;
- environment family/name;
- operation;
- status;
- auction row ID when applicable;
- character ID when applicable;
- item ID when applicable;
- preview/replay IDs when available;
- full executor result plus a sanitized request snapshot.

Confirmation strings, passwords, secrets, and generic token fields are excluded from the stored request snapshot.

## Filters

`GET /auction-house/activity.json` supports:

- environment name;
- operation;
- status;
- character ID;
- item ID;
- UTC start/end;
- evidence inclusion;
- reward campaign inclusion;
- bounded result limit (maximum 1,000 rows).

`GET /auction-house/activity` provides the operator UI.

## Historical boundary

Execution outcome auditing begins when this feature is installed.  Older AH mutations that predate execution-event recording cannot be reconstructed unless they are represented by older preview/replay evidence, reward campaign history, or native server data.

This is intentional: the Activity view does not fabricate historical executor events from current database state.
