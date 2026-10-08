"""Validated portable waypoint/path JSON for toolkit spatial workflows."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import PathSample, Position, Waypoint


def waypoint_document(waypoints: list[Waypoint]) -> dict:
    return {"schema_version": 1, "kind": "live_client_waypoints",
            "waypoints": [asdict(w) for w in waypoints]}


def parse_waypoints(document: dict) -> list[Waypoint]:
    if document.get("schema_version") != 1 or document.get("kind") != "live_client_waypoints":
        raise ValueError("unsupported waypoint document")
    rows = document.get("waypoints")
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError("invalid waypoint list")
    result = []
    for row in rows:
        name = row["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("invalid waypoint name")
        result.append(Waypoint(name=name, position=Position(**row["position"]),
                               source=row.get("source", "import")))
    return result


def path_document(samples: list[PathSample]) -> dict:
    return {"schema_version": 1, "kind": "live_client_path",
            "samples": [asdict(sample) for sample in samples]}


def export_waypoints(path: Path, waypoints: list[Waypoint]) -> None:
    """Write only to explicitly provided local paths; do not execute file content."""
    path.write_text(json.dumps(waypoint_document(waypoints), indent=2), encoding="utf-8")
