"""Preview a fixed, operator-reviewed MOG-09 test plan; never runs anything."""
from __future__ import annotations

import os
import re
from .execution_preflight import preflight


def build_plan(account: str, charid: int, supervisor_port: int = 8420) -> dict:
    if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", account):
        raise ValueError("account must be 1..32 letters, digits, underscores or dashes")
    if not isinstance(charid, int) or charid <= 0:
        raise ValueError("positive character ID required")
    if not isinstance(supervisor_port, int) or not 1 <= supervisor_port <= 65535:
        raise ValueError("invalid supervisor port")
    checks = preflight("moghancement", "MOG-09")
    approved = {int(s) for s in os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "").split(",") if s.strip().isdigit()}
    allowed = charid in approved
    return {"feature_id": "moghancement", "case_id": "MOG-09",
            "runner": "xiheadless_observation_v1", "account": account, "charid": charid,
            "supervisor": f"http://127.0.0.1:{supervisor_port}",
            "character_approved": allowed, "preflight": checks,
            "ready_for_operator_review": bool(checks["ready_for_operator_review"] and allowed),
            "steps": ["Inspect approved disposable test account and server profile",
                      "Verify clean XiHeadless DLL and commit provenance",
                      "Collect client and server inventory and Moghancement observations",
                      "Validate importer report and append evidence to configured database",
                      "Review six recorded assertions; do not infer installed-layout state"],
            "required_operator_confirmation": "--approve-mog09",
            "launch_mode": "local_cli_only",
            "browser_execution_enabled": False,
            "model_execution_enabled": False,
            "note": "This is a plan preview, not an execution request; choose a fresh absolute artifact directory when launching locally."}
