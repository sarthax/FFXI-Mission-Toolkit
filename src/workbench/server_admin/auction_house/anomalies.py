"""Rule-based anomaly detection over Auction House records (no model, every flag is explained).

Each finding compares something recent against that same thing's own history, so a cheap item is never
judged against an expensive one. Spread is measured with the median absolute deviation (MAD), which one
wild sale cannot distort the way a standard deviation would.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

MIN_HISTORY_SALES = 5      # earlier sales an item needs before its price is judged
MIN_RECENT_SALES = 2
PRICE_FLOOR_PCT = 25.0     # never flag a move smaller than this, however tight the history is
LISTING_HIGH, LISTING_LOW = 3.0, 0.4
VOLUME_RATIO, VOLUME_MIN = 3.0, 5
FLOOD_RATIO, FLOOD_MIN = 3.0, 10

_DAY = 86400


def _mad(vals: list[float], mid: float) -> float:
    return median(abs(v - mid) for v in vals)


def _sev(score: float, lo: float, hi: float) -> int:
    return 3 if score >= hi else 2 if score >= lo else 1


def anomalies_from(records: list[dict[str, Any]], now: int, days: int = 7, history_days: int = 60) -> dict[str, Any]:
    recent_from, hist_from = now - days * _DAY, now - history_days * _DAY
    sold = [r for r in records if r["sold_at"] and r["sale_price"]]
    active = [r for r in records if not r["sold_at"]]
    by_item_sales: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in sold:
        if r["sold_at"] >= hist_from:
            by_item_sales[r["item_id"]].append(r)
    out: list[dict[str, Any]] = []

    for iid, rows in by_item_sales.items():
        recent = [r for r in rows if r["sold_at"] >= recent_from]
        earlier = [int(r["sale_price"]) for r in rows if r["sold_at"] < recent_from]
        name = rows[0]["item_name"]
        if len(recent) >= MIN_RECENT_SALES and len(earlier) >= MIN_HISTORY_SALES:
            base = median(earlier)
            now_med = median(int(r["sale_price"]) for r in recent)
            spread = max(1.4826 * _mad(earlier, base), base * PRICE_FLOOR_PCT / 100)
            if base and abs(now_med - base) > 3 * spread:
                pct = (now_med - base) / base * 100
                out.append({"kind": "price_shift", "severity": _sev(abs(now_med - base) / spread, 5, 8), "item_id": iid, "item_name": name,
                            "value": now_med, "baseline": base, "change_pct": round(pct, 1),
                            "detail": f"Median sale {now_med:,.0f}g in the last {days}d vs {base:,.0f}g usual ({pct:+.0f}%), from {len(recent)} sales against {len(earlier)} earlier."})
        if len(recent) >= VOLUME_MIN and len(earlier):
            span = max(1.0, history_days - days)
            expected = len(earlier) / span * days
            if expected and len(recent) >= VOLUME_RATIO * expected:
                out.append({"kind": "volume_spike", "severity": _sev(len(recent) / expected, 5, 10), "item_id": iid, "item_name": name,
                            "value": len(recent), "baseline": round(expected, 1), "change_pct": None,
                            "detail": f"{len(recent)} sales in {days}d where about {expected:.1f} would be typical."})

    for r in active:
        hist = [int(x["sale_price"]) for x in by_item_sales.get(r["item_id"], [])]
        if len(hist) < MIN_HISTORY_SALES:
            continue
        base = median(hist)
        if not base:
            continue
        ratio = int(r["asking_price"]) / base
        if ratio >= LISTING_HIGH or ratio <= LISTING_LOW:
            high = ratio >= LISTING_HIGH
            out.append({"kind": "listing_overpriced" if high else "listing_underpriced",
                        "severity": _sev(ratio if high else 1 / max(ratio, 0.01), 5 if high else 4, 10 if high else 8),
                        "item_id": r["item_id"], "item_name": r["item_name"], "seller_id": r["seller_id"], "seller_name": r["seller_name"],
                        "auction_id": r["auction_id"], "value": int(r["asking_price"]), "baseline": base, "change_pct": round((ratio - 1) * 100, 1),
                        "detail": f"Listed at {int(r['asking_price']):,}g, {ratio:.1f}x the {base:,.0f}g median sale."})

    # a seller listing far more than they usually do
    listed: dict[int, list[int]] = defaultdict(list)
    names: dict[int, str] = {}
    for r in records:
        if r["listed_at"] and r["listed_at"] >= hist_from:
            listed[r["seller_id"]].append(r["listed_at"])
            names[r["seller_id"]] = r["seller_name"]
    for sid, ts in listed.items():
        recent_n = sum(1 for t in ts if t >= recent_from)
        earlier_n = len(ts) - recent_n
        expected = earlier_n / max(1.0, history_days - days) * days
        if recent_n >= FLOOD_MIN and expected and recent_n >= FLOOD_RATIO * expected:
            out.append({"kind": "seller_flood", "severity": _sev(recent_n / expected, 5, 10), "seller_id": sid, "seller_name": names[sid],
                        "value": recent_n, "baseline": round(expected, 1), "change_pct": None,
                        "detail": f"Posted {recent_n} listings in {days}d where about {expected:.1f} is usual for them."})

    out.sort(key=lambda a: (-a["severity"], -abs(a["change_pct"] or 0)))
    counts: dict[str, int] = defaultdict(int)
    for a in out:
        counts[a["kind"]] += 1
    return {"days": days, "history_days": history_days, "count": len(out), "by_kind": dict(counts), "findings": out[:100],
            "rules": {"min_history_sales": MIN_HISTORY_SALES, "price_floor_pct": PRICE_FLOOR_PCT, "listing_high_x": LISTING_HIGH,
                      "listing_low_x": LISTING_LOW, "volume_ratio": VOLUME_RATIO, "flood_ratio": FLOOD_RATIO}}


def economy_anomalies(service, days: int = 7, history_days: int = 60) -> dict[str, Any]:
    from .economy_intelligence import _load_records, _now_epoch
    records, _ = _load_records(service, days=history_days)
    return anomalies_from(records, _now_epoch(), days, history_days)
