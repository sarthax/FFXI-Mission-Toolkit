"""Explicit local-operator entry point for the single validated XiHeadless observation.

Not exposed over HTTP or to LLM tools. Launches only MOG-09 with fixed script
and flags, then validates and imports the result. Does not run arbitrary commands.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import re
import subprocess
import sys
from typing import Callable
from urllib.parse import urlparse

from .execution_preflight import preflight
from .importer import import_report
from .router import _REPO
from .run_options import apply_to_env as apply_run_options, switches as run_option_switches


def execute_mog09(*, account: str, charid: int, out_dir: Path,
                  supervisor: str, approved: bool, timeout: int = 900,
                  progress: Callable[[str], None] | None = None,
                  run_options: dict | None = None) -> dict:
    if not approved:
        raise ValueError("explicit operator approval required")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,32}", account):
        raise ValueError("invalid account identifier")
    allowed = {int(item) for item in os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "").split(",")
               if item.strip().isdigit()}
    if not isinstance(charid, int) or charid <= 0 or charid not in allowed:
        raise ValueError("character is not approved for deterministic tests")
    url = urlparse(supervisor)
    if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1") or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment or url.port is None:
        raise ValueError("supervisor must be an explicit loopback HTTP URL with port")
    if not isinstance(timeout, int) or not 60 <= timeout <= 1800:
        raise ValueError("timeout must be 60..1800 seconds")
    readiness = preflight("moghancement", "MOG-09")
    if not readiness["ready_for_operator_review"]:
        raise ValueError("test preflight failed: " + ", ".join(x["id"] for x in readiness["checks"] if not x["ok"]))
    root = Path(os.environ["MISSION_TOOLKIT_TEST_HEADLESS_ROOT"]).resolve(strict=True)
    out = out_dir.expanduser()
    if not out.is_absolute() or out.is_symlink() or out.exists():
        raise ValueError("output directory must be a fresh absolute path (not a symlink)")
    # Prevent accidental writes into the source tree or a shared checkout.
    if out.resolve().is_relative_to(root) or out.resolve().is_relative_to(_REPO.resolve()):
        raise ValueError("output artifacts must be outside source checkouts")
    if not out.parent.is_dir() or out.parent.is_symlink():
        raise ValueError("output directory parent must exist and not be a symlink")
    script = root / "tools" / "observation_runner.py"
    env = dict(os.environ)
    env["TOOLKIT_SRC"] = str(_REPO / "src")
    chosen_options = apply_run_options(env, run_options)  # validated allowlist; also clears switches inherited from the operator shell
    args =[sys.executable, str(script), "--out-dir", str(out),
            "--account", account, "--charid", str(charid), "--supervisor", supervisor]
    # No shell, no user supplied script or passthrough command arguments.
    # XiHeadless checks dirty tracked files and refuses by default.
    out.mkdir(mode=0o700)
    try:
        result = subprocess.run(args, cwd=str(root), env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("observation runner timed out; check client cleanup and artifacts") from exc
    if result.returncode:
        raise RuntimeError(f"observation runner exited with status {result.returncode}; inspect local artifacts (no subprocess output returned)")
    if progress:
        progress("runner_finished")
    report = out / "report.json"
    if not report.is_file() or report.is_symlink():
        raise RuntimeError("runner did not produce a report")
    from .importer import validate_report
    import json
    contents = json.loads(report.read_text(encoding="utf-8"))
    catalog = json.loads((_REPO / "data/testing/feature_test_readiness.json").read_text(encoding="utf-8"))
    rows = validate_report(contents, catalog)
    if len(rows) != 1 or rows[0]["case_id"] != "MOG-09" or rows[0]["feature_id"] != "moghancement":
        raise ValueError("runner returned unexpected scenario identity")
    provenance = rows[0]["evidence"].get("observations", {}).get("provenance", {})
    if provenance.get("charid") != charid or provenance.get("account") != account:
        raise ValueError("runner identity does not match operator approval")
    if progress:
        progress("report_validated")
    count = import_report(os.environ["MISSION_TOOLKIT_TEST_RESULTS_DB"],
                          _REPO / "data/testing/feature_test_readiness.json", report)
    if progress:
        progress("evidence_imported")
    return {"run_id": rows[0]["run_id"], "verdict": rows[0]["verdict"],
            "imported_records": count, "artifacts": str(out), "run_options": chosen_options}


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicitly approve and execute the read-only MOG-09 local test")
    parser.add_argument("--case", choices=["MOG-09"], required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--charid", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--supervisor", required=True, help="Loopback Toolkit base URL with port")
    parser.add_argument("--approve-mog09", action="store_true",
                        help="Operator confirms disposable test account and read-only !moghancement info")
    parser.add_argument("--enable", action="append", default=[], metavar="ENV",
                        choices=[s["env"] for s in run_option_switches()],
                        help="Turn on one run option (repeatable). Default is the safe state: shortcuts off.")
    parser.add_argument("--disable", action="append", default=[], metavar="ENV",
                        choices=[s["env"] for s in run_option_switches()],
                        help="Turn off one run option (repeatable).")
    args = parser.parse_args()
    options = {**{name: True for name in args.enable}, **{name: False for name in args.disable}}
    try:
        result = execute_mog09(account=args.account, charid=args.charid,
                               out_dir=args.out_dir, supervisor=args.supervisor,
                               approved=args.approve_mog09, run_options=options)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Test did not complete: {exc}\n")
    print(f"Imported {result['imported_records']} record(s): {result['run_id']} {result['verdict']}")


if __name__ == "__main__":
    main()
