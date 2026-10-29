"""R6 WP4 (#1211, #1199): compare stored results across two DSP revisions without over-claiming.

Design: docs/workbench/R6_REGRESSION_IMPACT_DESIGN_1199_1210.md section 5. A pure, offline function over result
records already in the append-only store (``results.recent_results`` shape). It never reads a database, runs git,
launches a test or attributes a verdict change to a DSP change: it reports what changed between two recorded
results and whether the comparison is even meaningful.

A transition is only named (REGRESSION_CANDIDATE, FIXED_CANDIDATE, ...) when the pair passes the comparability
gate. Everything the gate needs that the result store does not carry yet (test-definition digest, environment
fingerprint, fixture context, evidence schema version) is an explicit input, so until those exist the honest answer
is NOT_COMPARABLE with the failing conditions listed, never a guess.
"""
from __future__ import annotations

import re

from .results import VERDICTS, reason_class, UNCLASSIFIED

_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REQUIRED = ("run_id", "case_id", "feature_id", "stage", "verdict", "observed_at", "dsp_commit",
             "headless_commit", "toolkit_commit", "evidence")
_CONTEXT_KEYS = {"definition_sha256", "environment_fingerprint", "fixture_context", "schema_version"}
_BLOCK_NAMES = {"ENVIRONMENT": "ENVIRONMENT_BLOCKED", "FIXTURE_ABSENT": "FIXTURE_ABSENT",
                "ORACLE_UNKNOWN": "ORACLE_UNKNOWN", "OTHER": "BLOCKED_OTHER"}


def _clean_context(context: object, label: str) -> dict:
    if context is None:
        return {}
    if not isinstance(context, dict) or not set(context) <= _CONTEXT_KEYS:
        raise ValueError(f"{label} context must be an object with only {sorted(_CONTEXT_KEYS)}")
    out = dict(context)
    digests = out.get("definition_sha256", {})
    if not isinstance(digests, dict) or not all(
            isinstance(k, str) and "/" in k and isinstance(v, str) and _SHA256.fullmatch(v)
            for k, v in digests.items()):
        raise ValueError(f"{label} definition_sha256 must map 'feature_id/case_id' to a lowercase 64-hex digest")
    for key in ("environment_fingerprint", "fixture_context"):
        if key in out and (not isinstance(out[key], str) or not out[key].strip() or len(out[key]) > 256):
            raise ValueError(f"{label} {key} must be a non-empty string of at most 256 characters")
    if "schema_version" in out and (type(out["schema_version"]) is not int or out["schema_version"] < 1):
        raise ValueError(f"{label} schema_version must be a positive integer")
    return out


def _latest_per_key(records: object, label: str) -> dict[tuple[str, str, str], dict]:
    if not isinstance(records, list):
        raise ValueError(f"{label} records must be a list")
    chosen: dict[tuple[str, str, str], dict] = {}
    for record in records:
        if not isinstance(record, dict) or not all(k in record for k in _REQUIRED):
            raise ValueError(f"{label} record is missing required fields")
        if record["verdict"] not in VERDICTS:
            raise ValueError(f"{label} record has unknown verdict {record['verdict']!r}")
        key = (record["feature_id"], record["case_id"], record["stage"])
        rank = (str(record["observed_at"]), str(record["run_id"]))
        if key not in chosen or rank > (str(chosen[key]["observed_at"]), str(chosen[key]["run_id"])):
            chosen[key] = record
    return chosen


def _side(record: dict | None) -> dict | None:
    if record is None:
        return None
    provenance = record["evidence"].get("capture_provenance") if isinstance(record["evidence"], dict) else None
    return {"run_id": record["run_id"], "verdict": record["verdict"], "observed_at": record["observed_at"],
            "dsp_commit": record["dsp_commit"], "headless_commit": record["headless_commit"],
            "toolkit_commit": record["toolkit_commit"], "reason_class": reason_class(record),
            "capture_provenance": provenance if isinstance(provenance, str) else None}


def _gate(key, left, right, lctx, rctx) -> list[str]:
    """Every failing comparability condition, sorted; empty means comparable."""
    failures = []
    for tag, record in (("LEFT", left), ("RIGHT", right)):
        if not _SHA40.fullmatch(str(record["dsp_commit"])):
            failures.append(f"DSP_COMMIT_INVALID_{tag}")
        if record["verdict"] == "BLOCKED" and reason_class(record) == UNCLASSIFIED:
            failures.append(f"UNCLASSIFIED_BLOCK_{tag}")
    if not failures and left["dsp_commit"] == right["dsp_commit"]:
        failures.append("SAME_DSP_REVISION")
    name = f"{key[0]}/{key[1]}"
    ldig, rdig = lctx.get("definition_sha256", {}).get(name), rctx.get("definition_sha256", {}).get(name)
    if ldig is None or rdig is None:
        failures.append("DEFINITION_DIGEST_MISSING")
    elif ldig != rdig:
        failures.append("DEFINITION_CHANGED")
    for field, missing, mismatch in (
            ("environment_fingerprint", "ENVIRONMENT_FINGERPRINT_MISSING", "ENVIRONMENT_MISMATCH"),
            ("fixture_context", "FIXTURE_CONTEXT_MISSING", "FIXTURE_CONTEXT_MISMATCH"),
            ("schema_version", "SCHEMA_VERSION_MISSING", "SCHEMA_DRIFT")):
        if field not in lctx or field not in rctx:
            failures.append(missing)
        elif lctx[field] != rctx[field]:
            failures.append(mismatch)
    return sorted(set(failures))


def _transition(left: dict, right: dict) -> str:
    lv, rv = left["verdict"], right["verdict"]
    if "SKIPPED" in (lv, rv):
        return "SKIPPED"
    if rv == "BLOCKED":
        return "STILL_BLOCKED" if lv == "BLOCKED" else _BLOCK_NAMES[reason_class(right)]
    if lv == "BLOCKED":
        return "UNBLOCKED"
    if lv == rv:
        return "STILL_UNKNOWN" if lv == "UNKNOWN" else "UNCHANGED"
    if rv == "UNKNOWN":
        return "NOT_ESTABLISHED"
    if lv == "UNKNOWN":
        return "NOW_ESTABLISHED"
    return "REGRESSION_CANDIDATE" if (lv, rv) == ("PASS", "FAIL") else "FIXED_CANDIDATE"


def compare_revisions(left_records: list[dict], right_records: list[dict],
                      left_context: dict | None = None, right_context: dict | None = None) -> dict:
    """Compare the latest result per (feature, case, stage) on each side.

    ``left`` is the earlier revision, ``right`` the later one. Contexts (all optional, all required for a pair
    to be comparable): ``definition_sha256`` mapping ``"feature_id/case_id"`` to a digest of the test definition,
    ``environment_fingerprint``, ``fixture_context`` and ``schema_version``. Equality is the only compatibility
    rule applied; nothing is judged "close enough".
    """
    lctx, rctx = _clean_context(left_context, "left"), _clean_context(right_context, "right")
    left, right = _latest_per_key(left_records, "left"), _latest_per_key(right_records, "right")
    rows = []
    for key in sorted(set(left) | set(right)):
        l_rec, r_rec = left.get(key), right.get(key)
        row = {"feature_id": key[0], "case_id": key[1], "stage": key[2],
               "left": _side(l_rec), "right": _side(r_rec), "comparable": False, "reasons": []}
        if l_rec is None:
            row["transition"], row["reasons"] = "NO_BASELINE", ["NO_RECORD_LEFT"]
        elif r_rec is None:
            # An earlier determination with nothing recorded later is not a pass, fail or regression.
            row["transition"], row["reasons"] = "NOT_ESTABLISHED", ["NO_RECORD_RIGHT"]
        else:
            failures = _gate(key, l_rec, r_rec, lctx, rctx)
            if failures:
                row["transition"], row["reasons"] = "NOT_COMPARABLE", failures
            else:
                row["comparable"], row["transition"] = True, _transition(l_rec, r_rec)
        rows.append(row)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["transition"]] = counts.get(row["transition"], 0) + 1
    return {
        "schema_version": 1, "comparisons": rows, "transition_counts": dict(sorted(counts.items())),
        "attribution": "NOT_ATTRIBUTED",
        "note": "A transition describes two recorded results. It is not evidence that a DSP change caused it, "
                "and nothing was launched, fixed, merged or closed. Imported results are unauthenticated.",
    }
