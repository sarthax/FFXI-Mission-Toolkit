"""TEST-only market-history seeding (history, scenarios, clear) for the AH Economy views.

Wraps the standalone seed_auction_house.py logic. Every row is written under the reserved fake-seller
range (990000..990024) so clear removes only seeded rows. Writes pass the same gate as other AH test writes.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate


def _seed_module():
    try:
        import seed_auction_house as m
    except ImportError:
        root = Path(__file__).resolve().parents[4]
        sys.path.insert(0, str(root))
        import seed_auction_house as m
    return m


def _columns(cur, m):
    cur.execute("DESCRIBE `auction_house`")
    a = m.column_map({r[0] for r in cur.fetchall()})
    if not (a["itemid"] and a["seller"] and a["date"] and a["price"] and a["sale"] and a["sell_date"]):
        raise ValueError("auction_house schema is missing expected columns")
    return a


def _seeded_count(cur, a, m) -> int:
    lo, hi = m.SELLER_BASE, m.SELLER_BASE + m.FAKE_PLAYERS - 1
    cur.execute(f"SELECT COUNT(*) FROM auction_house WHERE `{a['seller']}` BETWEEN %s AND %s", (lo, hi))
    return int(cur.fetchone()[0])


def _plan(cur, m, a, mode: str, items: int, days: int, seed: int) -> dict[str, Any]:
    if mode == "history":
        items, days = max(1, min(int(items), 300)), max(1, min(int(days), 365))
        players, picked, rows = m.plan(cur, a, argparse.Namespace(items=items, days=days, seed=seed))
        sold = sum(1 for r in rows if r["sell_date"])
        return {"players": players, "rows": rows, "notes": [], "summary": {
            "mode": mode, "items": len(picked), "rows": len(rows), "completed_sales": sold,
            "active_listings": len(rows) - sold, "days": days}}
    if mode == "scenarios":
        players, rows, notes = m.plan_scenarios(cur, random.Random(seed))
        return {"players": players, "rows": rows, "notes": notes, "summary": {
            "mode": mode, "rows": len(rows), "scenarios": len(notes)}}
    raise ValueError("mode must be history, scenarios or clear")


def preview_market_seed(service, *, mode: str, items: int = 60, days: int = 90, seed: int = 1234) -> dict[str, Any]:
    m = _seed_module()
    cur = service.connection.cursor()
    try:
        a = _columns(cur, m)
        existing = _seeded_count(cur, a, m)
        if mode == "clear":
            return {"summary": {"mode": mode, "rows_to_delete": existing}, "existing_seeded_rows": existing,
                    "notes": [], "seller_range": [m.SELLER_BASE, m.SELLER_BASE + m.FAKE_PLAYERS - 1]}
        plan = _plan(cur, m, a, mode, items, days, seed)
        blocked = mode == "history" and existing > 0
        return {"summary": plan["summary"], "notes": plan["notes"], "existing_seeded_rows": existing,
                "blocked_reason": "Seeded history already exists; clear it first." if blocked else None,
                "seller_range": [m.SELLER_BASE, m.SELLER_BASE + m.FAKE_PLAYERS - 1]}
    finally:
        cur.close()


def execute_market_seed(service, environment: dict[str, Any], *, mode: str, items: int = 60, days: int = 90,
                        seed: int = 1234, confirmation: str, feature_enabled: bool | None = None) -> dict[str, Any]:
    gate = evaluate_legacy_test_write_gate(environment=environment, schema_family_hint=service.schema.family_hint,
                                           confirmation=confirmation, feature_enabled=feature_enabled)
    if not gate.ready:
        codes = ", ".join(i.code for i in gate.issues if i.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")
    m = _seed_module()
    conn = service.connection
    cur = conn.cursor()
    try:
        a = _columns(cur, m)
        lo, hi = m.SELLER_BASE, m.SELLER_BASE + m.FAKE_PLAYERS - 1
        if mode == "clear":
            cur.execute(f"DELETE FROM auction_house WHERE `{a['seller']}` BETWEEN %s AND %s", (lo, hi))
            deleted = cur.rowcount
            conn.commit()
            return {"status": "completed", "mode": mode, "deleted": deleted}
        if mode == "history" and _seeded_count(cur, a, m):
            raise LegacyTestExecutionBlocked("Seeded history already exists; clear it first")
        plan = _plan(cur, m, a, mode, items, days, seed)
        m.insert(cur, a, plan["players"], plan["rows"])
        conn.commit()
        return {"status": "completed", "mode": mode, "inserted": len(plan["rows"]), "notes": plan["notes"],
                "summary": plan["summary"]}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        cur.close()
