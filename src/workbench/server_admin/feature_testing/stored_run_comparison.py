"""#1408: compare two stored runs using what the importer recorded about them.

Read-only glue between the result store and ``revision_comparison.compare_revisions``. It builds each side's comparison
context only from facts that are actually on the stored rows: the importer's ``import_context`` (definition
fingerprint and report schema version) and the optional runner-supplied ``environment_fingerprint`` and
``fixture_context``. Anything missing or inconsistent across a run's rows is left out, so the comparison reports it as
missing rather than guessing. It never runs, imports or attributes anything.
"""
from __future__ import annotations

from .importer import IMPORT_CONTEXT_KEY
from .results import results_for_run
from .revision_comparison import compare_revisions


def _agreed(values: list) -> object | None:
    """The one value every row agrees on, else None (absent or conflicting facts are not carried forward)."""
    present = [v for v in values if v is not None]
    return present[0] if present and len(present) == len(values) and all(v == present[0] for v in present) else None


def comparison_context(records: list[dict]) -> dict:
    """The comparison context one run's stored rows can honestly support."""
    contexts = [(r.get("evidence") or {}).get(IMPORT_CONTEXT_KEY) for r in records]
    contexts = [c if isinstance(c, dict) else {} for c in contexts]
    context: dict = {}
    digests = {f"{r['feature_id']}/{r['case_id']}": c.get("definition_sha256")
               for r, c in zip(records, contexts) if isinstance(c.get("definition_sha256"), str)}
    if digests:
        context["definition_sha256"] = digests
    version = _agreed([c.get("report_schema_version") for c in contexts])
    if type(version) is int and version >= 1:
        context["schema_version"] = version
    for key in ("environment_fingerprint", "fixture_context"):
        value = _agreed([(r.get("evidence") or {}).get(key) for r in records])
        if isinstance(value, str) and value.strip() and len(value) <= 256:
            context[key] = value
    return context


def compare_stored_runs(db_path: str, left_run: str, right_run: str) -> dict:
    """Compare two stored runs. ``left_run`` is the earlier revision, ``right_run`` the later one."""
    left, right = results_for_run(db_path, left_run), results_for_run(db_path, right_run)
    if not left or not right:
        raise ValueError("both runs must exist in the result store")
    return compare_revisions(left, right, comparison_context(left), comparison_context(right))
