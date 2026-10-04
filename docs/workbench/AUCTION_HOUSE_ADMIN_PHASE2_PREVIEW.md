# Auction House Administration — Phase 2 Preview Milestone

This milestone adds preview-only administrative listing and purchase/cleanup flows on top of the merged read-only Auction House foundation.

No Auction House write endpoint exists in this milestone. All database access remains SELECT-only.

Key safety properties:

- exact active-auction snapshot before a purchase/cleanup preview;
- item and character identity validation before a listing preview;
- explicit single-vs-stack quantity and price-per-item calculation;
- explicit seller compensation, buyer charge, and admin gil-injection reporting;
- `apply_supported: false` on every preview;
- blocking `preview_only` warning on every preview;
- no `/apply`, `/commit`, `/delete`, purchase execution, or listing insertion route;
- regression tests enforce that POST routes are preview-only.

The next phase should implement write adapters behind tests first, then require stale-state revalidation, explicit environment confirmation, transactions, and audit logging before any GUI apply action is exposed.
