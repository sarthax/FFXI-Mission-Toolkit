import copy
import json
from pathlib import Path

import pytest

from workbench.server_admin.gm_commands.garden_campaign import generate_campaign


def plan():
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "data/testing/gardening_batch_plan.json").read_text(encoding="utf-8"))


def test_campaign_deterministic_bounded_and_nonexecuting():
    p = plan()
    a = generate_campaign(p)
    assert a == generate_campaign(p)
    assert a["cases"] and len(a["cases"]) <= 300
    assert all(c["execution_status"] == "NOT_RUN" and not c["evidence"] for c in a["cases"])
    assert a["pairwise_covered"] > 0


def test_non_tree_cases_never_have_second_crystal():
    result = generate_campaign(plan())
    assert all(c["inputs"]["plant_type"] in (6, 7) or c["inputs"]["crystal2"] == 0
               for c in result["cases"])


def test_selected_filter_limits_cases():
    p = plan()
    p["sampling"]["filter"] = {"pot_type": 216, "plant_type": 6, "crystal1": 1, "crystal2": 2}
    cases = generate_campaign(p)["cases"]
    assert len(cases) == 1
    assert cases[0]["inputs"] == p["sampling"]["filter"]


def test_empty_or_invalid_cases_rejected():
    p = plan()
    p["sampling"]["filter"]["crystal2"] = 3
    p["sampling"]["filter"]["plant_type"] = 1
    with pytest.raises(ValueError, match="no valid cases"):
        generate_campaign(p)
    p = plan()
    p["execution_enabled"] = True
    with pytest.raises(ValueError):
        generate_campaign(p)


def test_cartesian_requires_opt_in_and_repetitions_bounded():
    p = plan()
    p["sampling"]["strategy"] = "full_cartesian"
    with pytest.raises(ValueError, match="opt-in"):
        generate_campaign(p)
    p["sampling"]["allow_full_cartesian"] = True
    p["sampling"]["max_runs"] = 6
    p["sampling"]["repeat_per_case"] = 2
    out = generate_campaign(p)
    assert len(out["cases"]) == 6
