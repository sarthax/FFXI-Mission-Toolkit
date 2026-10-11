"""Offline alignment evidence is never a write-capability certificate."""
import pytest
from workbench.runtime.live_client.alignment import evaluate_alignment


def sample():
    return {"client_id":"ashita-a","zone_id":235,"axis_preview":"xyz",
            "heading_preview_degrees":0,"points":[
                {"client_id":"ashita-a","zone_id":235,"character":"Hero","adapter":"ashita",
                 "axis_preview":"xyz","heading_preview_degrees":0,"observed_at":10,
                 "raw_position":{"x":1,"y":2,"z":3},"viewer_position":{"x":1,"y":2,"z":3}},
                {"client_id":"ashita-a","zone_id":235,"character":"Hero","adapter":"ashita",
                 "axis_preview":"xyz","heading_preview_degrees":0,"observed_at":11,
                 "raw_position":{"x":4,"y":6,"z":3},"viewer_position":{"x":4,"y":6,"z":3}}]}


def test_valid_movement_never_authorizes_writes():
    result = evaluate_alignment(sample())
    assert result["raw_distance"] == 5
    assert result["distance_preserved"]
    assert result["movement_detected"]
    assert result["calibrated"] is False and result["write_safe"] is False


@pytest.mark.parametrize("change", [
    lambda s: s["points"][1].update(zone_id=236),
    lambda s: s["points"][1].update(client_id="ashita-b"),
    lambda s: s["points"][1].update(character="Other"),
    lambda s: s["points"][1].update(observed_at=10),
    lambda s: s["points"][1]["raw_position"].update(x=float("nan")),
    lambda s: s.update(axis_preview="unverified"),
    lambda s: s["points"][1].update(axis_preview="xzy"),
    lambda s: s.update(heading_preview_degrees=45),
    lambda s: s.update(zone_id=236),
])
def test_rejects_incompatible_or_corrupted_samples(change):
    payload = sample()
    change(payload)
    with pytest.raises(ValueError):
        evaluate_alignment(payload)


def test_reports_distorted_viewer_distance_without_claiming_calibration():
    payload = sample()
    payload["points"][1]["viewer_position"]["x"] = 40
    result = evaluate_alignment(payload)
    assert result["distance_preserved"] is False
    assert result["write_safe"] is False
