"""Admin-impact overlay: toolkit-driven AH actions (seed, restock, Admin Buy, return, rewards) lined up
against market activity, with a per-item before/after price check where the action names an item."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .activity import unified_activity
from .economy_intelligence import _load_records, _median, _now_epoch

_EFFECTIVE = {"committed", "completed", "partial", "delivered"}
_LABELS = {
    "admin_buy": "Admin Buy", "restock": "Restock", "return_to_seller": "Return to seller", "list_item": "Admin listing",
    "purchase_item": "Purchase", "player_purchase": "Player purchase", "player_listing": "Player-backed listing",
    "synthetic_category_seed": "Category seed", "market_seed": "Market seed", "reward_delivery": "Reward delivery",
}
_WINDOW = 7 * 86400


def _epoch(iso: str) -> int | None:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp())
    except ValueError:
        return None


def impact_from(records: list[dict[str, Any]], rows: list[dict[str, Any]], now: int) -> list[dict[str, Any]]:
    """Pure. rows are unified_activity rows. Keeps effective actions only; adds before/after medians per item."""
    sales: dict[int, list[tuple[int, int]]] = {}
    for r in records:
        if r["sold_at"]:
            sales.setdefault(r["item_id"], []).append((r["sold_at"], r["sale_price"]))
    names = {r["item_id"]: r["item_name"] for r in records}
    out = []
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status not in _EFFECTIVE:
            continue
        ts = _epoch(row.get("occurred_at_utc"))
        if ts is None:
            continue
        op = str(row.get("operation") or "")
        item_id = row.get("item_id")
        ev = {"ts": ts, "day": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"), "operation": op,
              "label": _LABELS.get(op, op.replace("_", " ")), "status": status, "item_id": item_id,
              "item_name": names.get(item_id) if item_id else None, "before_median": None, "after_median": None,
              "change_pct": None, "sales_before": None, "sales_after": None}
        if item_id and item_id in sales:
            before = [p for t, p in sales[item_id] if ts - _WINDOW <= t < ts]
            after = [p for t, p in sales[item_id] if ts <= t < ts + _WINDOW]
            ev.update(sales_before=len(before), sales_after=len(after),
                      before_median=_median(before), after_median=_median(after))
            if before and after and ev["before_median"]:
                ev["change_pct"] = round((ev["after_median"] - ev["before_median"]) / ev["before_median"] * 100, 1)
            ev["settled"] = ts + _WINDOW <= now
        out.append(ev)
    out.sort(key=lambda e: e["ts"], reverse=True)
    return out


def admin_impact(service, env: str, days: int = 30) -> dict[str, Any]:
    now = _now_epoch()
    since = datetime.fromtimestamp(now - days * 86400, timezone.utc).isoformat()
    act = unified_activity(environment_name=env, since_utc=since, include_evidence=False, limit=500)
    records, _ = _load_records(service, days=days + 14)
    events = impact_from(records, act["rows"], now)
    return {"env": env, "days": days, "events": events,
            "note": "Before/after compare the item's median sale price in the 7 days either side of the action. "
                    "Other things change at the same time, so treat this as a pointer, not proof."}
