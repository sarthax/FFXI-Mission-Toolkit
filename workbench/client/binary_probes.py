"""Feature-presence probes for client binaries, persisted as snapshot-scoped capability observations.

A probe is a named string or byte-pattern check against one client binary. A hit is exact evidence the
bytes exist in that build (VERIFIED). A miss stays UNKNOWN, never absent: FFXiMain.dll is packed, so
"not found on disk" does not prove the client lacks the feature. Feature Checker then reads these like
any other observation via USES_CLIENT_CAPABILITY.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from workbench.client.binary_deep import byte_search
from workbench.client.binary_index import index_binary
from workbench.core import graph
from workbench.core.schema import Capability, CapabilityObservation, CapabilityRequirement, Evidence


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def run_probe(path: Path, idx: dict, probe: dict) -> dict:
    kind, needle = probe["kind"], probe["needle"]
    if kind == "string":
        n = needle.lower()
        hits = [s for s in idx["strings"] if n in s["text"].lower()]
        return {"found": bool(hits), "count": len(hits), "sample": [h["text"] for h in hits[:5]]}
    if kind == "bytes":
        r = byte_search(path, needle, executable_only=False, max_matches=20)
        return {"found": bool(r["matches"]), "count": len(r["matches"]), "sample": [str(m) for m in r["matches"][:5]]}
    raise ValueError(f"unknown probe kind: {kind}")


def persist_probes(con, binary_path: str, snapshot_id: str, probes: list[dict]) -> list[dict]:
    """probes: [{"name","kind":"string"|"bytes","needle", optional "feature" (feature_id; adds a
    CapabilityRequirement so Feature Checker sees it) and "required" (default True)}]. Returns per-probe results."""
    path = Path(binary_path)
    idx = index_binary(path, max_strings=25000)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    out = []
    for p in probes:
        res = run_probe(path, idx, p)
        base = f"{snapshot_id}:{path.name}:{_slug(p['name'])}"
        cap_id = f"capability:client-binary-probe:{path.name}:{_slug(p['name'])}"
        ev_id = f"evidence:client-binary-probe:{base}"
        graph.insert_record(con, Evidence(
            evidence_id=ev_id, evidence_type="CLIENT_SOURCE", source="binary_probes",
            location=str(path), snapshot=snapshot_id,
            notes=f"{p['kind']} probe {p['needle']!r}; sha256={sha}"))
        graph.insert_record(con, Capability(
            capability_id=cap_id, name=f"client_binary_probe:{p['name']}",
            capability_type="CLIENT_BINARY_PROBE", subject_id=p.get("feature"),
            value={"snapshot_scoped": True},
            notes=["Presence of a probe in a client binary; a miss is UNKNOWN, not absent."]))
        graph.insert_record(con, CapabilityObservation(
            observation_id=f"capability-observation:{base}", capability_id=cap_id,
            source_snapshot_id=snapshot_id, status="VERIFIED" if res["found"] else "UNKNOWN",
            value={**res, "binary": path.name, "sha256": sha, "kind": p["kind"], "needle": p["needle"]},
            evidence_id=ev_id))
        if p.get("feature"):
            # Tie the probe to the feature so Feature Checker reports it as a client requirement.
            graph.insert_record(con, CapabilityRequirement(
                requirement_id=f"requirement:{p['feature']}:{cap_id}", feature_id=p["feature"],
                capability_id=cap_id, required=p.get("required", True), status="DISCOVERED",
                evidence_id=ev_id, notes=["Client binary probe requirement."]))
        out.append({"name": p["name"], **res})
    return out
