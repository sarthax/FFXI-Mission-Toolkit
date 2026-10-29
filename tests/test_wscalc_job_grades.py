"""Job-grade coverage for the WS calculator profile code (gear.py).

Expected grades are server-derived: DSP-Valhalla src/map/grades.cpp (parsed when a checkout is
present) and LSB data/grades.yaml (letters a..g -> 1..7, none -> 0) for GEO/RUN.
"""
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workbench.server_admin.wscalc import gear  # noqa: E402

LSB_GEO_RUN = {21: (4, 3, 6, 4, 4, 5, 2, 2, 5), 22: (2, 6, 3, 4, 5, 2, 4, 4, 6)}
DSP_GRADES = Path(os.environ.get("DSP_GRADES_CPP", r"<local>/<DSP checkout>\src\map\grades.cpp"))


def test_all_22_jobs_have_nine_grades():
    assert sorted(gear.JOB_GRADES) == list(range(1, 23))
    for j, g in gear.JOB_GRADES.items():
        assert len(g) == 9 and all(0 <= x <= 7 for x in g), j
        assert g[0] >= 1, f"job {j} needs an HP grade"


@pytest.mark.parametrize("job", sorted(LSB_GEO_RUN))
def test_geo_run_match_lsb(job):
    assert gear.JOB_GRADES[job] == LSB_GEO_RUN[job]


@pytest.mark.skipif(not DSP_GRADES.exists(), reason="DSP checkout not available")
def test_all_jobs_match_dsp_grades_cpp():
    txt = DSP_GRADES.read_text(errors="replace")
    body = txt.split("JobGrades", 1)[1].split("RaceGrades", 1)[0]
    rows = [tuple(int(x) for x in m.split(",")) for m in re.findall(r"\{\s*(\d(?:\s*,\s*\d){8})\s*\}", body)]
    rows = [r for r in rows if len(r) == 9][-23:]  # index 0 is the padding row
    for j in range(1, 23):
        assert gear.JOB_GRADES[j] == rows[j], gear.JOBS[j]


@pytest.mark.parametrize("job", range(1, 23))
@pytest.mark.parametrize("level", [1, 50, 75, 99])
def test_base_stats_populated_for_every_job(job, level):
    st = gear.base_stats(job, level, 0, 0, 1)
    assert set(st) == set(gear._STATS)
    assert all(v > 0 for v in st.values())


@pytest.mark.parametrize("main", [21, 22])
@pytest.mark.parametrize("level", [1, 50, 75, 99])
def test_geo_run_as_main_and_sub_change_stats(main, level):
    base = gear.base_stats(main, level, 0, 0, 1)
    with_sub = gear.base_stats(1, level, main, max(1, level // 2), 1)
    without = gear.base_stats(1, level, 0, 0, 1)
    assert base and with_sub != without


def test_invalid_inputs_are_safe():
    assert gear.base_stats(99, 50, 0, 0, 1) == {}
    assert gear.base_stats(21, 0, 0, 0, 1) == {}
    assert gear.base_stats(21, 50, 99, 25, 1) == gear.base_stats(21, 50, 0, 0, 1)


def test_jobs_1_to_20_unchanged_hume_75():
    # regression pin: WAR 75/0 Hume STR from the pre-existing table
    assert gear.base_stats(1, 75, 0, 0, 1)["str"] > gear.base_stats(4, 75, 0, 0, 1)["str"]
