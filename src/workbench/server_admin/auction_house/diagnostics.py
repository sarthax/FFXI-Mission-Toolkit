"""Read-only Auction House smoke diagnostics for live server testing.

Each probe is isolated so one schema/query failure does not hide the status of the
remaining Auction House administration surface.
"""
from __future__ import annotations

from typing import Any, Callable

from .analytics import economy_summary, search_items
from .health import market_movement, participant_concentration, stale_listings, transaction_outliers
from .service import AuctionHouseService
from .write_probe import probe_write_readiness


def _run_check(
    checks: list[dict[str, Any]],
    name: str,
    *,
    critical: bool,
    probe: Callable[[], Any],
) -> None:
    try:
        detail = probe()
        checks.append({"name": name, "ok": True, "critical": critical, "detail": detail})
    except Exception as exc:
        checks.append({
            "name": name,
            "ok": False,
            "critical": critical,
            "error": f"{type(exc).__name__}: {exc}",
        })


def run_read_only_diagnostics(service: AuctionHouseService) -> dict[str, Any]:
    """Run bounded SELECT/metadata probes across the AH read surface.

    The function intentionally catches failures per capability. The resulting payload is
    suitable for first-pass testing against DSP, Topaz, LSB, and custom forks without
    enabling or exercising any Auction House mutation path.
    """
    checks: list[dict[str, Any]] = []

    _run_check(
        checks,
        "schema",
        critical=True,
        probe=lambda: {
            "family_hint": service.status().get("family_hint"),
            "capabilities": service.status().get("capabilities", []),
        },
    )
    _run_check(
        checks,
        "categories",
        critical=True,
        probe=lambda: {"category_count": len(service.categories())},
    )
    _run_check(
        checks,
        "item_search",
        critical=True,
        probe=lambda: {
            "sample": [
                {"item_id": row.get("item_id"), "name": row.get("name")}
                for row in search_items(service, "", limit=3)
            ]
        },
    )
    _run_check(
        checks,
        "economy_summary",
        critical=True,
        probe=lambda: economy_summary(service, days=30),
    )

    # Economy-health probes are intentionally bounded for smoke testing. They validate
    # the query shape without turning diagnostics into a full analytical scan.
    _run_check(
        checks,
        "stale_listings",
        critical=False,
        probe=lambda: {"sample_count": len(stale_listings(service, days=30, limit=3))},
    )
    _run_check(
        checks,
        "market_movement",
        critical=False,
        probe=lambda: {"sample_count": len(market_movement(service, recent_days=7, baseline_days=30, limit=3))},
    )
    _run_check(
        checks,
        "participant_concentration",
        critical=False,
        probe=lambda: participant_concentration(service, days=30, limit=3),
    )
    _run_check(
        checks,
        "transaction_outliers",
        critical=False,
        probe=lambda: {
            "sample_count": len(
                transaction_outliers(service, days=30, sample_limit=500, result_limit=3)
            )
        },
    )
    _run_check(
        checks,
        "write_readiness_metadata",
        critical=False,
        probe=lambda: {
            **probe_write_readiness(service.connection).as_dict(),
            "executor_enabled": False,
            "write_enabled": False,
        },
    )

    failed = [check["name"] for check in checks if not check["ok"]]
    critical_failed = [check["name"] for check in checks if not check["ok"] and check["critical"]]
    return {
        "status": "degraded" if critical_failed else ("ok_with_warnings" if failed else "ok"),
        "read_only": True,
        "write_enabled": False,
        "executor_enabled": False,
        "checks": checks,
        "failed_checks": failed,
        "critical_failed_checks": critical_failed,
    }
