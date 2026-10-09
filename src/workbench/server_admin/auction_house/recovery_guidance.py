"""Read-only operator recovery guidance for DSP MyISAM AH execution.

These hints describe evidence to inspect, not a safe automatic rollback recipe.
MyISAM cannot provide crash atomicity across player inventory and AH writes.
"""
from __future__ import annotations

from typing import Any


def myisam_recovery_guidance(operation: str, *, auction_id: int | None = None,
                             character_id: int | None = None) -> dict[str, Any]:
    if operation not in {"player_listing", "player_purchase"}:
        raise ValueError("Unsupported DSP MyISAM recovery operation")
    if auction_id is not None and int(auction_id) <= 0:
        raise ValueError("auction_id must be positive")
    if character_id is not None and int(character_id) <= 0:
        raise ValueError("character_id must be positive")
    checks = [
        "Stop further AH administration for the affected character and retain a database backup.",
        "Compare the active/sold Auction House row against Activity/Audit evidence and the original preview.",
        "Inspect exact char_inventory item and gil rows before considering any manual correction.",
    ]
    if operation == "player_purchase":
        checks.extend([
            "Check the buyer item grant and gil debit together; verify seller delivery_box settlement.",
            "Determine whether the InnoDB AH transaction committed before assuming the purchase failed.",
        ])
    else:
        checks.extend([
            "Compare seller item quantity, listing fee, and active AH row to detect partial listing.",
            "Do not restore a removed item while the corresponding auction listing remains active.",
        ])
    checks.append("Escalate ambiguous or conflicting state for operator reconciliation; never auto-replay a non-atomic action.")
    return {
        "operation": operation,
        "execution_mode": "dsp_myisam_compensating",
        "test_only": True,
        "atomic": False,
        "crash_window": True,
        "automatic_recovery_safe": False,
        "auction_id": int(auction_id) if auction_id is not None else None,
        "character_id": int(character_id) if character_id is not None else None,
        "operator_checks": checks,
    }
