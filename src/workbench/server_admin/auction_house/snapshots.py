"""Daily Auction House snapshots kept in the toolkit's own SQLite DB.

The game server only stores current listings and past sales, not how supply looked on a given day, so
supply history can only be built by recording it going forward. One row per environment per UTC day
(plus per-category and per-item active counts) is written by a background loop and on demand.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .economy_intelligence import _load_records, _now_epoch

_LOCK = threading.Lock()
_SCHEMA = """
CREATE TABLE IF NOT EXISTS ah_snapshot (
  env TEXT NOT NULL, day TEXT NOT NULL, taken_at INTEGER NOT NULL,
  active_listings INTEGER, active_gil INTEGER, active_items INTEGER,
  sales_7d INTEGER, gil_7d INTEGER, listed_7d INTEGER, sell_through_7d REAL,
  PRIMARY KEY (env, day));
CREATE TABLE IF NOT EXISTS ah_snapshot_category (
  env TEXT NOT NULL, day TEXT NOT NULL, category_id INTEGER NOT NULL,
  active INTEGER, active_gil INTEGER, sales_7d INTEGER, PRIMARY KEY (env, day, category_id));
CREATE TABLE IF NOT EXISTS ah_snapshot_item (
  env TEXT NOT NULL, day TEXT NOT NULL, item_id INTEGER NOT NULL, item_name TEXT,
  active INTEGER, sales_7d INTEGER, PRIMARY KEY (env, day, item_id));
"""


def _db() -> sqlite3.Connection:
    import settings
    con = sqlite3.connect(settings.DB_PATH, timeout=10)
    con.executescript(_SCHEMA)
    return con


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def summarize(records: list[dict[str, Any]], now: int) -> dict[str, Any]:
    """Pure: supply and sell-through figures from loaded AH records."""
    week = now - 7 * 86400
    active = [r for r in records if not r["sold_at"]]
    sold = [r for r in records if r["sold_at"] and r["sold_at"] >= week]
    listed = [r for r in records if r["listed_at"] >= week]
    cats: dict[int, dict[str, int]] = defaultdict(lambda: {"active": 0, "active_gil": 0, "sales_7d": 0})
    items: dict[int, dict[str, Any]] = {}
    for r in active:
        c = cats[r["category_id"]]
        c["active"] += 1
        c["active_gil"] += int(r["asking_price"])
        it = items.setdefault(r["item_id"], {"name": r["item_name"], "active": 0, "sales_7d": 0})
        it["active"] += 1
    for r in sold:
        cats[r["category_id"]]["sales_7d"] += 1
        items.setdefault(r["item_id"], {"name": r["item_name"], "active": 0, "sales_7d": 0})["sales_7d"] += 1
    return {
        "active_listings": len(active), "active_gil": sum(int(r["asking_price"]) for r in active),
        "active_items": len({r["item_id"] for r in active}),
        "sales_7d": len(sold), "gil_7d": sum(int(r["sale_price"]) for r in sold), "listed_7d": len(listed),
        # of everything offered in the last 7 days (still listed or sold), the share that sold
        "sell_through_7d": round(len(sold) / (len(sold) + len(active)) * 100, 1) if (sold or active) else None,
        "categories": cats, "items": items,
    }


def take_snapshot(service, env: str, *, force: bool = False) -> dict[str, Any]:
    """Record today's snapshot for env. Returns {taken: bool, day}. One per UTC day unless force."""
    now = _now_epoch()
    day = _day(now)
    with _LOCK:
        con = _db()
        try:
            if not force and con.execute("SELECT 1 FROM ah_snapshot WHERE env=? AND day=?", (env, day)).fetchone():
                return {"taken": False, "day": day, "reason": "already recorded today"}
            records, _ = _load_records(service, days=7)
            s = summarize(records, now)
            con.execute("DELETE FROM ah_snapshot WHERE env=? AND day=?", (env, day))
            con.execute("DELETE FROM ah_snapshot_category WHERE env=? AND day=?", (env, day))
            con.execute("DELETE FROM ah_snapshot_item WHERE env=? AND day=?", (env, day))
            con.execute("INSERT INTO ah_snapshot VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (env, day, now, s["active_listings"], s["active_gil"], s["active_items"],
                         s["sales_7d"], s["gil_7d"], s["listed_7d"], s["sell_through_7d"]))
            con.executemany("INSERT INTO ah_snapshot_category VALUES (?,?,?,?,?,?)",
                            [(env, day, k, v["active"], v["active_gil"], v["sales_7d"]) for k, v in s["categories"].items()])
            con.executemany("INSERT INTO ah_snapshot_item VALUES (?,?,?,?,?,?)",
                            [(env, day, k, v["name"], v["active"], v["sales_7d"]) for k, v in s["items"].items()])
            con.commit()
            return {"taken": True, "day": day, "active_listings": s["active_listings"]}
        finally:
            con.close()


BASELINE_MIN_POINTS = 7
_BASELINE_METRICS = ("active_listings", "active_gil", "sales_7d", "sell_through_7d")


def baselines_from_series(series: list[dict[str, Any]], window: int = 28) -> dict[str, Any]:
    """Pure. Baseline = median of up to `window` snapshots before the latest; typical range = median +/- 2 MAD.

    Reported per metric as {latest, baseline, low, high, deviation_pct, status}. status: normal, high, low.
    Until BASELINE_MIN_POINTS earlier snapshots exist the status is "building" and no judgement is made.
    """
    out: dict[str, Any] = {"min_points": BASELINE_MIN_POINTS, "points": max(0, len(series) - 1), "metrics": {}}
    if not series:
        return out
    latest, prior = series[-1], series[-1 - window:-1] if len(series) > 1 else []
    for k in _BASELINE_METRICS:
        vals = [r[k] for r in prior if r.get(k) is not None]
        cur = latest.get(k)
        m: dict[str, Any] = {"latest": cur, "baseline": None, "low": None, "high": None, "deviation_pct": None, "status": "building"}
        if len(vals) >= BASELINE_MIN_POINTS and cur is not None:
            from statistics import median
            base = median(vals)
            mad = median(abs(v - base) for v in vals)
            spread = max(mad * 2, abs(base) * 0.05)  # floor so a perfectly flat history is not hair-trigger
            m.update(baseline=round(base, 1), low=round(base - spread, 1), high=round(base + spread, 1),
                     deviation_pct=round((cur - base) / base * 100, 1) if base else None,
                     status="high" if cur > base + spread else "low" if cur < base - spread else "normal")
        out["metrics"][k] = m
    return out


def snapshot_history(env: str, days: int = 90) -> dict[str, Any]:
    con = _db()
    try:
        cutoff = _day(_now_epoch() - days * 86400)
        rows = con.execute("SELECT day,active_listings,active_gil,active_items,sales_7d,gil_7d,listed_7d,sell_through_7d "
                           "FROM ah_snapshot WHERE env=? AND day>=? ORDER BY day", (env, cutoff)).fetchall()
        keys = ("day", "active_listings", "active_gil", "active_items", "sales_7d", "gil_7d", "listed_7d", "sell_through_7d")
        series = [dict(zip(keys, r)) for r in rows]
        return {"env": env, "days": days, "series": series, "baselines": baselines_from_series(series)}
    finally:
        con.close()


_loop_started = False


def start_daily_loop(open_context, env_name, interval: int = 3600) -> None:
    """Background thread: once an hour, record today's snapshot if it is missing. Safe to call repeatedly."""
    global _loop_started
    if _loop_started:
        return
    _loop_started = True

    def run():
        while True:
            try:
                env = env_name()
                if env:
                    with open_context() as ctx:
                        take_snapshot(ctx.service, env)
            except Exception:
                pass  # server down or no active environment: try again next hour
            time.sleep(interval)

    threading.Thread(target=run, name="ah-snapshot-loop", daemon=True).start()
