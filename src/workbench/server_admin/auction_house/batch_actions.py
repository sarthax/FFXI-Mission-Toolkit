"""Bounded DSP/Topaz Test batch actions built on proven single-row AH executors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .admin_buy import execute_legacy_test_admin_buy
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .safe_return import execute_legacy_test_safe_return

_MAX_BATCH = 100
_SUPPORTED_ACTIONS = {"admin_buy", "return_to_seller"}


@dataclass(frozen=True)
class BatchTarget:
    auction_id: int
    expected_price: int | None = None


def _normalize_targets(values: list[dict[str, Any]]) -> list[BatchTarget]:
    if not isinstance(values, list) or not values:
        raise LegacyTestExecutionBlocked("Batch requires at least one listing")
    if len(values) > _MAX_BATCH:
        raise LegacyTestExecutionBlocked(f"Batch is limited to {_MAX_BATCH} listings")
    seen: set[int] = set()
    targets: list[BatchTarget] = []
    for raw in values:
        if not isinstance(raw, dict):
            raise LegacyTestExecutionBlocked("Every batch target must be an object")
        auction_id = int(raw.get("auction_id") or 0)
        if auction_id <= 0:
            raise LegacyTestExecutionBlocked("Every batch target requires a positive auction_id")
        if auction_id in seen:
            raise LegacyTestExecutionBlocked(f"Duplicate auction_id in batch: {auction_id}")
        seen.add(auction_id)
        expected = raw.get("expected_price")
        targets.append(BatchTarget(
            auction_id=auction_id,
            expected_price=None if expected in (None, "") else int(expected),
        ))
    return targets


def execute_legacy_test_batch(
    *,
    service,
    environment: dict[str, Any],
    action: str,
    targets: list[dict[str, Any]],
    confirmation: str,
    feature_enabled: bool | None = None,
) -> dict[str, Any]:
    """Run selected listings independently and report partial success explicitly.

    Each selected row uses the established single-row executor and therefore its own transaction.
    A failure never causes the function to pretend earlier committed rows were rolled back.
    """
    action = str(action or "").strip().lower()
    if action not in _SUPPORTED_ACTIONS:
        raise LegacyTestExecutionBlocked(f"Unsupported batch action: {action or 'unknown'}")
    normalized = _normalize_targets(targets)

    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")

    results: list[dict[str, Any]] = []
    committed = 0
    failed = 0
    for target in normalized:
        try:
            if action == "admin_buy":
                if target.expected_price is None or target.expected_price <= 0:
                    raise LegacyTestExecutionBlocked("Admin Buy targets require expected_price")
                result = execute_legacy_test_admin_buy(
                    service=service,
                    environment=environment,
                    auction_id=target.auction_id,
                    expected_price=target.expected_price,
                    confirmation=confirmation,
                    feature_enabled=feature_enabled,
                )
            else:
                result = execute_legacy_test_safe_return(
                    service=service,
                    environment=environment,
                    auction_id=target.auction_id,
                    confirmation=confirmation,
                    feature_enabled=feature_enabled,
                )
            committed += 1
            results.append({"auction_id": target.auction_id, "status": "committed", "result": result})
        except Exception as exc:
            failed += 1
            results.append({"auction_id": target.auction_id, "status": "failed", "error": str(exc)})

    return {
        "status": "completed" if failed == 0 else ("failed" if committed == 0 else "partial"),
        "operation": "batch_listing_action",
        "action": action,
        "test_only": True,
        "attempted": len(normalized),
        "committed": committed,
        "failed": failed,
        "partial_success_possible": True,
        "max_batch": _MAX_BATCH,
        "results": results,
        "note": "Each listing is committed or rolled back independently using the corresponding single-row executor.",
    }
