# Auction House Economy Intelligence

Status: read-only DSP/Topaz administration surface.

## Purpose

`Server -> AH Economy` summarizes seller and category health from the live `auction_house` and `item_basic` tables without mutating server state.

## Seller metrics

- active listing count and aggregate asking value
- sales and realized gil in the selected lookback window
- average and median asking price
- average and median realized sale price
- oldest active listing age
- aging buckets: `<7d`, `7-30d`, `30-90d`, `90d+`
- stale active listing count
- sell-through percentage: sold / (active + sold in the bounded sample)
- top items by active exposure and realized volume

## Category metrics

Seller metrics are aggregated by AH category and supplemented with:

- distinct item count
- distinct seller count
- transparent supply-health signal

Current signal heuristics are intentionally simple and visible:

- `undersupplied`: 2 or fewer active listings and at least 5 recent sales
- `stale_or_oversupplied`: at least 10 active listings, at least half stale, and weak recent sales
- otherwise `balanced_or_insufficient_evidence`

These labels are review signals, not conclusions about players or market manipulation.

## Query bounds

The service performs one bounded active/recent-sale read using discovered schema columns only. Default sample limit is 20,000 rows and the hard API limit is 50,000. The response reports `sample_truncated` if the bound is reached.

This is deliberate: the page is intended for responsive administration and health inspection, not an unbounded warehouse query.

## Filters

- lookback days
- stale threshold days
- seller ID
- category ID
- result row limit
- sample limit

## Safety

The module is read-only. It does not use the Test-write feature flag and is safe to query on configured DSP/Topaz environments subject to normal database read permissions.
