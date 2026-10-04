# Auction House local audit / replay ledger

The Auction House administration module has a toolkit-local SQLite ledger foundation for preview validation evidence and future replay protection.

## Purpose

The ledger is **not** an FFXI server database and does not mutate Auction House server state. It exists to preserve an append-only local history of validation evidence and to provide a future executor with an atomic, one-time replay claim primitive.

Default database:

`data/auction_house_audit.db`

Generated `-wal` and `-shm` companions are runtime-only files.

## Append-only audit events

`ah_audit_events` stores immutable events. Current event type:

- `preview_validation`

Each validation event can preserve:

- preview ID
- audit ID
- replay ID
- environment family/name
- operation
- validation status
- normalized preview provenance
- flattened blocker evidence

The ledger API supports read-only filtering by preview ID, audit ID, or replay ID.

Existing audit-event rows are never updated or deleted by the ledger module.

## Replay consumption contract

`ah_replay_consumptions` uses `replay_id` as its primary key. `claim_replay_once()` opens a local `BEGIN IMMEDIATE` transaction and inserts the replay claim plus a matching `replay_consumed` audit event in the same transaction.

A second claim for the same replay ID raises `ReplayAlreadyConsumed` and rolls back without appending a second consumption event.

This gives a future executor an atomic toolkit-local consume-once primitive. It does **not** enable execution. A future executor must still:

1. revalidate preview lifetime/provenance,
2. reread live database/config state,
3. claim the replay ID exactly once,
4. execute only a lineage-verified server transaction,
5. append outcome evidence,
6. fail closed on any mismatch or rollback.

No Auction House mutation SQL, server commit path, Apply route, executor, or write feature flag is introduced by this ledger foundation.
