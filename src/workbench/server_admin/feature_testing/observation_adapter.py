"""Offline adapter from captured measurements to importable feature test reports.

Input observations must be captured by a trusted independent runner. This module
neither communicates with a client/server nor claims measurements are authentic.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from workbench.server_admin.gm_commands.garden_rewards import load_results, validate_harvest
from workbench.server_admin.gm_commands.moghancement_effects import (
    evaluate_modifiers, evaluate_replacement,
)
from .importer import validate_report


def evaluate_observation(observation: dict, sql_path: str | Path | None = None) -> dict:
    kind = observation.get("kind")
    if kind == "garden_harvest":
        if sql_path is None:
            raise ValueError("gardening SQL path required")
        inputs = observation["inputs"]
        actual = observation["actual"]
        return validate_harvest(load_results(sql_path), inputs["seed"],
                                inputs["crystal1"], inputs["crystal2"],
                                actual["item_id"], actual["quantity"])
    if kind == "mog_modifier":
        return evaluate_modifiers(observation["baseline"], observation["active"],
                                  observation["removed"], observation["expected_delta"])
    if kind == "mog_replacement":
        return evaluate_replacement(observation["baseline"], observation["old_active"],
                                    observation["new_active"], observation["old_effect"],
                                    observation["new_effect"])
    raise ValueError("unknown observation type")


def build_report(manifest: dict, observations: list[dict], catalog: dict,
                 *, gardening_sql: str | Path | None = None) -> dict:
    if not isinstance(observations, list) or not observations or len(observations) > 1000:
        raise ValueError("1..1000 observations required")
    if not isinstance(manifest, dict):
        raise ValueError("manifest required")
    required = ("run_id", "observed_at", "dsp_commit", "headless_commit", "toolkit_commit")
    if any(x not in manifest for x in required):
        raise ValueError("manifest missing provenance")
    rows = []
    for o in observations:
        verdict = evaluate_observation(o, gardening_sql)
        if verdict["verdict"] not in ("PASS", "FAIL", "BLOCKED"):
            raise ValueError("unexpected evaluator verdict")
        feature = "gardening" if o["kind"] == "garden_harvest" else "moghancement"
        stage = "mechanics" if feature == "gardening" else "modifier"
        evidence = {"assertions": [{"oracle": o["kind"], "verdict": verdict["verdict"]}],
                    "observations": o, "evaluation": verdict,
                    "capture_provenance": "unverified_external_observation"}
        rows.append({**{k: manifest[k] for k in required},
                     "feature_id": feature, "case_id": o["case_id"], "stage": stage,
                     "verdict": verdict["verdict"], "evidence": evidence})
    report = {"schema_version": 1, "results": rows}
    validate_report(report, catalog)
    return report


def build_report_file(manifest_path: str | Path, observations_path: str | Path,
                      catalog_path: str | Path, output_path: str | Path,
                      *, gardening_sql: str | Path | None = None) -> int:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    observations = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    report = build_report(manifest, observations, catalog, gardening_sql=gardening_sql)
    Path(output_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return len(report["results"])
