# Auction House Economy Health

The Auction House administration module includes a read-only economy-health surface for server operators. It is intended to identify records worth reviewing, not to make claims about player intent or automatically alter the economy.

## Endpoint

`GET /auction-house/health.json`

Parameters:

- `days` — completed-sale review window, default 30 days.
- `stale_days` — age threshold for unsold active listings, default 30 days.
- `recent_days` — recent comparison window for price/volume movement, default 7 days.
- `baseline_days` — total lookback used to build the preceding baseline window, default 30 days and must exceed `recent_days`.

No mutation route is added by this feature.

## Signals

### Stale listings

Returns the oldest active listings whose listing timestamp is at least `stale_days` old. Results retain auction ID, item/category, lot type, seller identity when available, asking price, and age.

### Market movement

Compares each item and lot type separately. Recent average sale price and daily sales rate are compared with the preceding baseline period. Single-item and stack auctions are never combined.

Low-sample groups are suppressed by default so a single unusual sale does not become a market-movement alert.

### Participant concentration

Ranks sellers and, where the lineage exposes buyer identity, buyers by completed-sale gil during the review window. The result reports each participant's share of all transacted gil in that window.

Legacy DSP/Topaz-compatible schemas may expose buyer name without a numeric buyer ID. The diagnostic preserves that distinction instead of assuming the LSB buyer-ID shape.

### Transaction outliers

Completed sales are grouped by item and lot type. A transaction is flagged when its sale price is at least three times above or below the peer median and the peer group has enough samples.

This is intentionally a diagnostic signal. It is not labeled as fraud, abuse, manipulation, RMT, or any other conclusion.

## Safety and scope

- Queries are SELECT-only.
- No listing, purchase, delivery-box, inventory, or gil mutation is performed.
- No executor is enabled.
- No Apply or Commit endpoint is added.
- Existing Auction House lineage write guards remain unchanged.
- Results are intended for admin review and future dashboard visualization.
