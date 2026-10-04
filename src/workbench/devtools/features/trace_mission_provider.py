"""Cross-framework mission/quest provider for Feature Trace.

LSB exact definitions and DSP/Topaz legacy handler scripts are normalized into the same
MissionStateMachine before projection.  The provider is read-only and returns relationship
candidates; it never mutates character or canonical graph state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from workbench.devtools.features.trace_expansion import mission_state_candidates
from workbench.devtools.missions.legacy_progression_extract import extract_legacy_progression
from workbench.devtools.missions.mission_source_catalog import LsbFeatureSourceCatalog


def _normalize_subject(kind: str, symbol: str) -> str:
    return f"{kind.strip().casefold()}:{symbol.strip().upper()}"


def resolve_lsb_machine(server_root: str | Path, *, kind: str, symbol: str):
    catalog = LsbFeatureSourceCatalog(server_root)
    subject = _normalize_subject(kind, symbol)
    # Catalog subjects preserve upper-case feature symbols.
    source = catalog.source_for(subject)
    if source is None:
        # Be tolerant of caller casing while still requiring an exact cataloged feature identity.
        wanted = subject.casefold()
        subject = next((candidate for candidate in catalog.subjects() if candidate.casefold() == wanted), subject)
    return catalog.resolve_machine(subject)


def resolve_legacy_machine(files: Iterable[str | Path], *, feature_id: str):
    paths = tuple(Path(path) for path in files)
    if not paths:
        return None
    return extract_legacy_progression(paths, feature_id=feature_id)


def mission_trace_candidates(
    server_root: str | Path,
    *,
    family: str,
    kind: str,
    symbol: str,
    feature_id: str | None = None,
    legacy_files: Iterable[str | Path] = (),
    root_node: str | None = None,
) -> dict:
    """Resolve one mission/quest into framework-neutral Feature Trace candidates."""
    family_norm = family.strip().casefold()
    machine = None
    source_mode = None
    if family_norm in {"lsb", "landsandboat"}:
        machine = resolve_lsb_machine(server_root, kind=kind, symbol=symbol)
        source_mode = "LSB_EXACT_DEFINITION"
    elif family_norm in {"dsp", "topaz"}:
        fid = feature_id or f"{kind}:{symbol}"
        machine = resolve_legacy_machine(legacy_files, feature_id=fid)
        source_mode = "LEGACY_HANDLER_SCOPE"
    else:
        raise ValueError(f"Unsupported server family: {family}")

    root = root_node or f"{kind.strip().casefold()}:{symbol.strip().casefold()}"
    if machine is None:
        return {
            "available": False,
            "family": family_norm,
            "kind": kind,
            "symbol": symbol,
            "root": root,
            "source_mode": source_mode,
            "machine": None,
            "relationships": [],
        }
    rows = mission_state_candidates(machine, root)
    return {
        "available": True,
        "family": family_norm,
        "kind": kind,
        "symbol": symbol,
        "root": root,
        "source_mode": source_mode,
        "machine_id": machine.machine_id,
        "feature_id": machine.feature_id,
        "relationship_count": len(rows),
        "relationships": [row.as_dict() for row in rows],
        "metadata": dict(getattr(machine, "metadata", {}) or {}),
    }
