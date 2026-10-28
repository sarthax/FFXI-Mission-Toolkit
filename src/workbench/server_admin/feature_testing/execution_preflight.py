"""Read-only preflight for explicitly supported local deterministic test runners."""
from __future__ import annotations

import os
from pathlib import Path

from .router import scenario_detail

SUPPORTED = {("moghancement", "MOG-09"): "xiheadless_observation_v1"}


def _safe_file(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
        return path.is_file() and not path.is_symlink() and resolved.is_relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False


def preflight(feature_id: str, case_id: str) -> dict:
    """Return capabilities and blockers; never start a process or modify state."""
    detail = scenario_detail(feature_id, case_id)
    runner = SUPPORTED.get((feature_id, case_id))
    checks = []
    from .test_execution_settings import sandbox_execution_check
    isolation = sandbox_execution_check()
    if isolation["isolated"]:
        checks.append({"id": "sandbox_isolation", "ok": isolation["ok"],
                       "detail": isolation["reason"]})
    if not runner:
        checks.append({"id": "runner_supported", "ok": False, "detail": "No verified deterministic runner is registered for this case"})
    else:
        checks.append({"id": "runner_supported", "ok": True, "detail": "XiHeadless observation_runner.py; read-only MOG-09"})
        root_text = os.environ.get("MISSION_TOOLKIT_TEST_HEADLESS_ROOT", "")
        root = Path(root_text) if root_text else None
        exists = bool(root and root.is_absolute() and root.is_dir() and not root.is_symlink()
                      and _safe_file(root / "tools" / "observation_runner.py", root))
        checks.append({"id": "runner_script", "ok": exists,
                       "detail": "Configured XiHeadless runner found" if exists else "Set MISSION_TOOLKIT_TEST_HEADLESS_ROOT to an approved local XiHeadless checkout containing tools/observation_runner.py"})
        dll = bool(exists and _safe_file(root / "bin" / "mcp" / "XiHeadless.dll", root))
        checks.append({"id": "headless_dll", "ok": dll, "detail": "DLL present" if dll else "Clean built XiHeadless DLL required"})
    results = bool(os.environ.get("MISSION_TOOLKIT_TEST_RESULTS_DB"))
    checks.append({"id": "results_db", "ok": results, "detail": "Import destination configured" if results else "MISSION_TOOLKIT_TEST_RESULTS_DB is not configured"})
    allowed = [x.strip() for x in os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "").split(",") if x.strip().isdigit()]
    checks.append({"id": "approved_characters", "ok": bool(allowed), "detail": "Disposable character allowlist configured" if allowed else "No approved test characters configured"})
    token = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "")
    checks.append({"id": "supervisor_auth", "ok": len(token) >= 32, "detail": "Supervisor authentication configured" if len(token) >= 32 else "Supervisor token not configured"})
    ready = all(x["ok"] for x in checks)
    return {"feature_id": feature_id, "case_id": case_id, "runner": runner,
            "checks": checks, "ready_for_operator_review": ready,
            "execution_enabled": False, "launch_implemented": False,
            "note": "Readiness does not authorize execution. Running the runner remains a separate local operator action."}
