# Auction House Preview Safety Checklist

- Preview listing uses SELECT-only item and seller snapshots.
- Preview purchase/cleanup uses the exact active auction row.
- Admin cleanup reports seller compensation and gil injection.
- Normal purchase requires a valid buyer snapshot.
- Every preview returns `apply_supported: false`.
- Every preview carries a blocking `preview_only` warning.
- No apply/commit/delete endpoint exists in this phase.
- Regression coverage enforces preview-only POST routes.
