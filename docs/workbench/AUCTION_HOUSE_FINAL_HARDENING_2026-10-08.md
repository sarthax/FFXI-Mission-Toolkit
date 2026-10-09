# Auction House final hardening — recovery, campaigns, augments (2026-10-08)

## Scope and operator status

This is the last planned AH reliability package before maintenance. It does not
change the user-confirmed stable DSP core operations.

1. **MyISAM interruption journal** (auction_house_recovery.db): DSP Test listing and purchase executors record evidence before their first game DB mutation. Success and review-required states are retained across restarts; an abrupt crash leaves a possibly_interrupted case. Compensation is best effort, never crash-atomic, and no automatic rollback or replay occurs.
2. **Inbox reward attempt journal** (auction_house_reward_attempts.db): each recipient progresses pending -> in_flight -> committed/failed, with durable transitions. An unknown pending/in-flight result after interruption requires inspecting game delivery_box. Never automatically retry recipients with unknown outcomes.
3. **One-time Test scheduling** (auction_house_reward_schedules.db): the operator chooses a future time and confirms the named Test profile. Recipients are resolved and frozen at approval. The running toolkit claims a due schedule only once, rechecks the same DSP/Topaz Test environment and write gates, generates a fresh preview, and uses the guarded reward executor. Jobs overdue more than 24 hours require review. An interrupted send is not automatically retried. The toolkit must stay running, and there is no recurring schedule or Live write support.
4. **Augmented-item inspection foundation**: uses the existing Character Editor item-extra codec (24 bytes) and active server augments.sql to preview one to four supported augment IDs and values. Ordinary reward execution rejects extra/augments fields rather than silently sending a plain item. Actual custom augmented Mog delivery is blocked pending verified end-to-end mailbox pickup behavior on the relevant server lineage. Arbitrary new effects still require server augment definitions.

## Operator surfaces

- Server -> Auction House -> Inbox: one-time schedule approvals and custom augment preview.
- Auction House -> More tools -> Reward history: interrupted reward journals and unresolved MyISAM cases.
- Read-only diagnostics and guarded scheduling endpoints under /auction-house/rewards/.

## Required Windows/DSP acceptance

- On disposable DSP Test, compare MyISAM journal cases against inventory/gil and auction rows after success, ordinary failure, and a controlled interruption.
- Send ordinary rewards to two characters, induce a recipient rollback and controlled interruption, then verify the attempt journal distinguishes failed from unknown; do not retry unknown without independent evidence.
- Schedule a small delivery, confirm it sends only under the original named Test profile with enabled write gates, and exercise cancellation, downtime, alternate profile and interruption.
- Preview a known augment from augments.sql; verify encoding and later test in-game mail pickup before enabling any augmented write route.

## Safety boundaries

- MyISAM and toolkit SQLite case records are not one atomic transaction.
- Delivery-box writes and SQLite attempt records are not one atomic transaction; in_flight is unknown after a crash.
- Schedules are claimed once, with no automatic retry after uncertain outcomes.
- Augmented Mog delivery, recurring campaigns, production authorization and broad LSB writes are not complete.
