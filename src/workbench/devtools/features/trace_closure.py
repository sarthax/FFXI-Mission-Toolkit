"""Feature Trace adapter for canonical obtainability/access closure projections."""
from __future__ import annotations

import sqlite3

from workbench.devtools.dependencies.obtainability import (
    build_obtainability_closure,
    closure_projection,
    resolve_obtainability_root,
)
from workbench.reference import seed_runtime_reference_graphs
from workbench.devtools.dependencies.presentation import initial_presentation


def build_feature_trace_closure(con: sqlite3.Connection, selection: str = "") -> dict:
    """Load registered reference data, resolve a GUI selection, and project its closure.

    This is deliberately the boundary between user-facing labels and canonical graph IDs.
    Registered reference bundles are normal canonical records with reference provenance,
    allowing a fresh GUI database to demonstrate the map without a fixture-only path.
    """
    bundles = seed_runtime_reference_graphs(con)
    requested = selection.strip() or bundles[0]["root"]
    canonical_root = resolve_obtainability_root(con, requested)
    bundle = next((entry for entry in bundles if entry["root"] == canonical_root), None)
    relationships = bundle["relationships"] if bundle else None
    projection = closure_projection(
        build_obtainability_closure(con, canonical_root, relationships=relationships)
    )
    projection["resolved_root"] = canonical_root
    projection["presentation"] = initial_presentation(projection)
    if bundle:
        projection["reference_name"] = bundle["name"]
        projection["source"] = "Reference graph bundle; not a claim about live server state."
    return projection
