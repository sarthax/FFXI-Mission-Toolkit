"""Preview-bound rule-driven cleanup for DSP/Topaz Auction House administration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import time
from typing import Any

from .batch_actions import execute_legacy_test_batch
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate

_MAX_TARGETS = 100


@dataclass(frozen=True)
class CleanupCriteria:
    seller_id: int | None = None
    seller_name: str | None = None
    category_id: int | None = None
    item_id: int | None = None
    min_price: int | None = None
    max_price: int | None = None
    listed_before: int | None = None
    limit: int = 100

    def normalized(self) -> "CleanupCriteria":
        limit = max(1, min(int(self.limit), _MAX_TARGETS))
        min_price = None if self.min_price is None else max(0, int(self.min_price))
        max_price = None if self.max_price is None else max(0, int(self.max_price))
        if min_price is not None and max_price is not None and min_price > max_price:
            raise LegacyTestExecutionBlocked("min_price cannot exceed max_price")
        return CleanupCriteria(
            seller_id=None if self.seller_id is None else int(self.seller_id),
            seller_name=(str(self.seller_name).strip() or None) if self.seller_name is not None else None,
            category_id=None if self.category_id is None else int(self.category_id),
            item_id=None if self.item_id is None else int(self.item_id),
            min_price=min_price,
            max_price=max_price,
            listed_before=None if self.listed_before is None else int(self.listed_before),
            limit=limit,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())


def criteria_from_payload(payload: dict[str, Any], *, now: int | None = None) -> CleanupCriteria:
    now = int(time.time() if now is None else now)
    age_days = payload.get("min_age_days")
    listed_before = payload.get("listed_before")
    if listed_before in (None, "") and age_days not in (None, ""):
        age_days = float(age_days)
        if age_days < 0:
            raise LegacyTestExecutionBlocked("min_age_days cannot be negative")
        listed_before = now - int(age_days * 86400)
    return CleanupCriteria(
        seller_id=None if payload.get("seller_id") in (None, "") else int(payload["seller_id"]),
        seller_name=payload.get("seller_name"),
        category_id=None if payload.get("category_id") in (None, "") else int(payload["category_id"]),
        item_id=None if payload.get("item_id") in (None, "") else int(payload["item_id"]),
        min_price=None if payload.get("min_price") in (None, "") else int(payload["min_price"]),
        max_price=None if payload.get("max_price") in (None, "") else int(payload["max_price"]),
        listed_before=None if listed_before in (None, "") else int(listed_before),
        limit=int(payload.get("limit") or _MAX_TARGETS),
    ).normalized()


def _select(service, criteria: CleanupCriteria) -> list[dict[str, Any]]:
    c = criteria.normalized()
    a = service.schema.auction_columns
    i = service.schema.item_columns
    required_a = ("id", "item_id", "seller_id", "listed_at", "asking_price", "sale_price", "sold_at")
    required_i = ("item_id", "name", "ah_category")
    if any(not a.get(k) for k in required_a) or any(not i.get(k) for k in required_i):
        raise LegacyTestExecutionBlocked("Auction House schema is missing cleanup selector columns")

    clauses = [f"ah.`{a['sale_price']}`=0", f"ah.`{a['sold_at']}`=0"]
    params: list[Any] = []
    if c.seller_id is not None:
        clauses.append(f"ah.`{a['seller_id']}`=%s")
        params.append(c.seller_id)
    if c.seller_name:
        if not a.get("seller_name"):
            raise LegacyTestExecutionBlocked("seller_name filtering is unavailable in this schema")
        clauses.append(f"ah.`{a['seller_name']}` LIKE %s")
        params.append(f"%{c.seller_name}%")
    if c.category_id is not None:
        clauses.append(f"ib.`{i['ah_category']}`=%s")
        params.append(c.category_id)
    if c.item_id is not None:
        clauses.append(f"ah.`{a['item_id']}`=%s")
        params.append(c.item_id)
    if c.min_price is not None:
        clauses.append(f"ah.`{a['asking_price']}`>=%s")
        params.append(c.min_price)
    if c.max_price is not None:
        clauses.append(f"ah.`{a['asking_price']}`<=%s")
        params.append(c.max_price)
    if c.listed_before is not None:
        clauses.append(f"ah.`{a['listed_at']}`<=%s")
        params.append(c.listed_before)

    seller_name_expr = f"ah.`{a['seller_name']}`" if a.get("seller_name") else "NULL"
    sql = (
        "SELECT "
        f"ah.`{a['id']}`,ah.`{a['item_id']}`,ib.`{i['name']}`,ib.`{i['ah_category']}`,"
        f"ah.`{a['seller_id']}`,{seller_name_expr},ah.`{a['listed_at']}`,ah.`{a['asking_price']}` "
        "FROM `auction_house` ah JOIN `item_basic` ib "
        f"ON ib.`{i['item_id']}`=ah.`{a['item_id']}` WHERE " + " AND ".join(clauses) +
        f" ORDER BY ah.`{a['listed_at']}` ASC,ah.`{a['id']}` ASC LIMIT %s"
    )
    params.append(c.limit)
    cursor = service.connection.cursor()
    try:
        cursor.execute(sql, tuple(params))
        return [{
            "auction_id": int(r[0]), "item_id": int(r[1]), "item_name": str(r[2] or ""),
            "category_id": int(r[3] or 0), "seller_id": int(r[4] or 0), "seller_name": r[5],
            "listed_at": int(r[6] or 0), "asking_price": int(r[7] or 0),
        } for r in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def _token(criteria: CleanupCriteria, rows: list[dict[str, Any]]) -> str:
    material = {
        "criteria": criteria.as_dict(),
        "targets": [{
            "auction_id": r["auction_id"], "asking_price": r["asking_price"],
            "listed_at": r["listed_at"], "seller_id": r["seller_id"], "item_id": r["item_id"],
        } for r in rows],
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def preview_cleanup(service, criteria: CleanupCriteria, *, now: int | None = None) -> dict[str, Any]:
    now = int(time.time() if now is None else now)
    criteria = criteria.normalized()
    rows = _select(service, criteria)
    ages = [max(0, now - int(row["listed_at"])) for row in rows if row["listed_at"]]
    return {
        "status": "preview",
        "operation": "rule_cleanup",
        "criteria": criteria.as_dict(),
        "count": len(rows),
        "aggregate_asking_value": sum(int(r["asking_price"]) for r in rows),
        "oldest_age_days": (max(ages) / 86400.0) if ages else None,
        "newest_age_days": (min(ages) / 86400.0) if ages else None,
        "targets": rows,
        "preview_token": _token(criteria, rows),
        "max_targets": _MAX_TARGETS,
        "generated_at": now,
    }


def execute_cleanup(
    *, service, environment: dict[str, Any], criteria: CleanupCriteria, preview_token: str,
    action: str, confirmation: str, feature_enabled: bool | None = None,
) -> dict[str, Any]:
    criteria = criteria.normalized()
    gate = evaluate_legacy_test_write_gate(
        environment=environment, schema_family_hint=service.schema.family_hint,
        confirmation=confirmation, feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")
    rows = _select(service, criteria)
    live_token = _token(criteria, rows)
    if not preview_token or str(preview_token) != live_token:
        raise LegacyTestExecutionBlocked("Cleanup preview is stale; refresh the exact target set before executing")
    if not rows:
        raise LegacyTestExecutionBlocked("Cleanup preview contains no active listings")
    targets = [{"auction_id": r["auction_id"], "expected_price": r["asking_price"]} for r in rows]
    result = execute_legacy_test_batch(
        service=service, environment=environment, action=action, targets=targets,
        confirmation=confirmation, feature_enabled=feature_enabled,
    )
    result["cleanup_criteria"] = criteria.as_dict()
    result["preview_token"] = live_token
    return result
