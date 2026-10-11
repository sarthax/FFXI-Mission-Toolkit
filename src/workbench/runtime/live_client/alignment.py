"""Validate exported two-point Live Client 3D alignment evidence offline.

No bridge connection, persistent capture, inferred axis correction, or game writes.
"""
from __future__ import annotations

from math import isfinite, sqrt


def _vec(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("invalid coordinate object")
    out = {}
    for key in ("x", "y", "z"):
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not isfinite(number):
            raise ValueError("non-finite or missing coordinate: " + key)
        out[key] = float(number)
    return out


def evaluate_alignment(export: dict) -> dict:
    """Check a viewer's two-point clipboard export without trusting its delta.

    Report translation-free movement distances and axis candidates, not proof of
    correctness. An independent known-direction Windows observation is required.
    """
    if not isinstance(export, dict) or not isinstance(export.get("points"), list) or len(export["points"]) != 2:
        raise ValueError("exactly two alignment points required")
    points = export["points"]
    if not all(isinstance(p, dict) for p in points):
        raise ValueError("invalid alignment point")
    first, second = points
    client = first.get("client_id")
    zone = first.get("zone_id")
    if not isinstance(client, str) or not client or type(zone) is not int or not 1 <= zone <= 65535:
        raise ValueError("invalid client or zone")
    if export.get("client_id") != client or export.get("zone_id") != zone:
        raise ValueError("export identity mismatch")
    for point in points:
        if point.get("client_id") != client or point.get("zone_id") != zone:
            raise ValueError("mixed client or zone")
        if point.get("character") != first.get("character") or point.get("adapter") != first.get("adapter"):
            raise ValueError("character or adapter changed")
        if point.get("axis_preview") != export.get("axis_preview"):
            raise ValueError("mixed axis preview")
        if point.get("heading_preview_degrees") != export.get("heading_preview_degrees"):
            raise ValueError("mixed heading preview")
        t = point.get("observed_at")
        if isinstance(t, bool) or not isinstance(t, (float, int)) or not isfinite(t):
            raise ValueError("invalid observation time")
    if second["observed_at"] <= first["observed_at"]:
        raise ValueError("observations are not strictly increasing")
    if export.get("axis_preview") not in ("legacy", "xyz", "xzy", "x-z-y"):
        raise ValueError("unknown axis preview")
    heading = export.get("heading_preview_degrees")
    if type(heading) is not int or heading not in (0, 90, 180, 270):
        raise ValueError("invalid heading preview")
    a, b = (_vec(p["raw_position"]) for p in points)
    va, vb = (_vec(p["viewer_position"]) for p in points)
    raw = {k: b[k] - a[k] for k in a}
    viewer = {k: vb[k] - va[k] for k in va}
    magnitude = lambda vector: sqrt(sum(v*v for v in vector.values()))
    raw_distance, viewer_distance = magnitude(raw), magnitude(viewer)
    return {
        "client_id": client, "zone_id": zone,
        "axis_preview": export["axis_preview"], "heading_preview_degrees": heading,
        "elapsed_seconds": second["observed_at"] - first["observed_at"],
        "delta_raw": raw, "delta_viewer": viewer,
        "raw_distance": raw_distance, "viewer_distance": viewer_distance,
        "distance_preserved": abs(raw_distance - viewer_distance) <= max(1e-6, raw_distance * 1e-6),
        "movement_detected": raw_distance > 1e-6,
        "calibrated": False, "write_safe": False,
        "qualification": "Requires independent in-game direction/position comparison; two points cannot establish absolute alignment or write safety.",
    }
