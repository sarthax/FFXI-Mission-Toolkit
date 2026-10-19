import pytest
from workbench.server_admin.feature_testing.observation_adapter import build_report


MANIFEST = {"run_id": "r1", "observed_at": "2026-10-18T21:00:00Z",
            "dsp_commit": "a"*40, "headless_commit": "b"*40, "toolkit_commit": "c"*40}
CATALOG = {"features": [{"id": "moghancement", "cases": [{"id": "MOG-01"}]}]}


def test_mog_modifier_observation_generates_structured_report():
    observations = [{"kind": "mog_modifier", "case_id": "MOG-01",
                     "baseline": {"GILFINDER": 2}, "active": {"GILFINDER": 12},
                     "removed": {"GILFINDER": 2}, "expected_delta": {"GILFINDER": 10}}]
    report = build_report(MANIFEST, observations, CATALOG)
    row = report["results"][0]
    assert row["verdict"] == "PASS"
    assert row["evidence"]["capture_provenance"] == "unverified_external_observation"
    assert row["stage"] == "modifier"


def test_wrong_modifier_results_in_fail():
    obs = [{"kind": "mog_modifier", "case_id": "MOG-01",
            "baseline": {"GILFINDER": 0}, "active": {"GILFINDER": 9},
            "removed": {"GILFINDER": 0}, "expected_delta": {"GILFINDER": 10}}]
    assert build_report(MANIFEST, obs, CATALOG)["results"][0]["verdict"] == "FAIL"


def test_duplicate_stage_and_case_is_rejected():
    obs = {"kind": "mog_modifier", "case_id": "MOG-01",
           "baseline": {"GILFINDER": 0}, "active": {"GILFINDER": 10},
           "removed": {"GILFINDER": 0}, "expected_delta": {"GILFINDER": 10}}
    with pytest.raises(ValueError, match="duplicate"):
        build_report(MANIFEST, [obs, obs], CATALOG)


def test_garden_reward_sql_observation(tmp_path):
    sql = tmp_path / "garden.sql"
    sql.write_text("INSERT INTO `gardening_results` VALUES (1, 1, 0, 0, 936, 12, 24, 30);")
    catalog = {"features": [{"id": "gardening", "cases": [{"id": "GARD-01"}]}]}
    obs = [{"kind": "garden_harvest", "case_id": "GARD-01",
            "inputs": {"seed": 1, "crystal1": 0, "crystal2": 0},
            "actual": {"item_id": 936, "quantity": 20}}]
    assert build_report(MANIFEST, obs, catalog, gardening_sql=sql)["results"][0]["verdict"] == "PASS"
