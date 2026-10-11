"""Compare manually captured native Ashita XYZ with a matching live snapshot.

No game process access; mismatched zones and stale samples never pass.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite, dist


@dataclass(frozen=True)
class PositionSample:
    zone_id: int
    x: float
    y: float
    z: float
    observed_at: float

    def __post_init__(self):
        if type(self.zone_id) is not int or not 1 <= self.zone_id <= 65535:
            raise ValueError("invalid zone")
        if any(type(v) not in (int, float) or not isfinite(v) for v in
               (self.x, self.y, self.z, self.observed_at)):
            raise ValueError("nonfinite or invalid position sample")


def compare_native_live(native: PositionSample, live: PositionSample, *,
                        tolerance: float = 1.5, max_age_seconds: float = 2.0) -> dict:
    if not 0 < tolerance <= 10 or not 0 < max_age_seconds <= 10:
        raise ValueError("invalid comparison limits")
    if native.zone_id != live.zone_id:
        return {"matched": False, "reason": "zone_mismatch", "distance": None}
    age = abs(native.observed_at - live.observed_at)
    if age > max_age_seconds:
        return {"matched": False, "reason": "samples_not_synchronized",
                "age_seconds": age, "distance": None}
    distance = dist((native.x, native.y, native.z), (live.x, live.y, live.z))
    return {"matched": distance <= tolerance,
            "reason": "within_tolerance" if distance <= tolerance else "position_mismatch",
            "distance": round(distance, 4), "age_seconds": round(age, 4)}
