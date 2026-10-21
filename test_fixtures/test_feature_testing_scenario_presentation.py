"""Read-only presentation contracts for #1260; all evidence here is synthetic."""
from __future__ import annotations

import copy
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from workbench.server_admin.feature_testing.scenario_presentation import scenario_presentation
from workbench.server_admin.feature_testing.test_specifications import specification
from workbench.server_admin.feature_testing.normalized_evidence import evaluate_imported_mog09


ROOT = Path(__file__).resolve().parents[1]


def synthetic_bdd():
    """Presentation-only fixture mirroring #1263's optional field names.

    Do not persist this fixture into the canonical test specifications.
    """
    spec = copy.deepcopy(specification("moghancement", "MOG-09"))
    spec["purpose"] = "Synthetic: stored furnishings must not activate an aura"
    spec["rationale"] = "Synthetic presentation example only"
    spec["behavior"] = {
        "given": ["Synthetic disposable test fixture", "Installed layout unobserved"],
        "when": ["Imported assertion values are inspected"],
        "then": ["Six assertions can be recalculated; no live verification"],
    }
    spec["steps"] = [{
        "id": "SYNTH-MOG09-" + str(i + 1),
        "title": "Synthetic step " + str(i + 1),
        "intent": "synthetic_read_only_display",
        "expected": "Synthetic: compare the linked assertion contract",
        "assertion_ids": [a["id"]],
        "evidence_refs": [a["observed"]] + (
            [a["expected"]] if isinstance(a.get("expected"), str) and
            a["expected"] in ("db_bag", "db_safe") else []
        ),
        "confidence_note": "Synthetic fixture; not independently authenticated",
    } for i, a in enumerate(spec["assertions"])]
    spec["authoring"] = {
        "state": "synthetic_fixture",
        "execution_policy": "read_only",
        "evidence_provenance": "synthetic_not_live",
        "review_required": True,
        "blocking_gaps": ["Installed layout readback UNKNOWN"],
    }
    return spec


def synthetic_imported_result():
    from test_feature_testing_normalized_evidence import sample
    return sample()


def test_six_ordered_bdd_steps_and_dual_verdict_do_not_authenticate_import():
    record = synthetic_imported_result()
    view = scenario_presentation(synthetic_bdd(), evaluate_imported_mog09(record))
    assert view["purpose"].startswith("Synthetic:")
    assert view["behavior"]["given"]
    assert view["legacy"] is False
    assert len(view["steps"]) == 6
    assert [step["number"] for step in view["steps"]] == list(range(1, 7))
    assert view["mapped_assertion_count"] == view["assertion_count"] == 6
    assert view["unmapped_assertions"] == []
    assert all(step["status"] == "PASS" for step in view["steps"])
    assert view["recorded_verdict"] == "PASS"
    assert view["recalculated_verdict"] == "PASS"
    assert view["independent_verification"] == "NOT_ESTABLISHED"
    assert view["blocking_gaps"] == ["Installed layout readback UNKNOWN"]
    assert view["steps"][4]["provenance"][0]["source"].startswith("evidence.assertions[")


def test_mismatch_retains_recorded_pass_and_recalculated_failure():
    record = synthetic_imported_result()
    record["evidence"]["assertions"][2]["observed"] = 387
    view = scenario_presentation(synthetic_bdd(), evaluate_imported_mog09(record))
    assert view["recorded_verdict"] == "PASS"
    assert view["recalculated_verdict"] == "FAIL"
    assert view["steps"][2]["status"] == "FAIL"
    assert view["independent_verification"] == "NOT_ESTABLISHED"


def test_missing_observation_is_blocked_and_original_source_not_invented():
    record = synthetic_imported_result()
    record["evidence"]["assertions"].pop()
    view = scenario_presentation(synthetic_bdd(), evaluate_imported_mog09(record))
    assert view["steps"][5]["status"] == "BLOCKED"
    assert view["steps"][5]["provenance"][0]["available"] is False
    assert view["steps"][5]["provenance"][0]["source"] is None
    assert "db_safe" in view["missing_fields"]


def test_legacy_spec_has_no_fabricated_bdd_or_observed_pass():
    spec = copy.deepcopy(specification("moghancement", "MOG-09"))
    for field in ("steps", "behavior", "purpose", "rationale", "authoring"):
        spec.pop(field, None)
    view = scenario_presentation(spec)
    assert view["legacy"] is True
    assert view["behavior"] == {"given": [], "when": [], "then": []}
    assert len(view["steps"]) == 6
    assert all(step["status"] == "UNKNOWN" for step in view["steps"])
    assert view["recorded_verdict"] is None
    assert view["recalculated_verdict"] is None
    assert view["independent_verification"] == "NOT_ESTABLISHED"
    assert scenario_presentation(None)["available"] is False


def test_optional_bdd_and_html_escape_in_shared_template():
    fixture = synthetic_bdd()
    fixture["steps"][0]["title"] = "<script>alert('not evidence')</script>"
    view = scenario_presentation(fixture)
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "gui" / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("feature_testing_steps.html").render(scenario_view=view)
    assert "&lt;script&gt;" in html
    assert "<script>alert('not evidence')</script>" not in html
    assert "Given / When / Then" in html
    assert "UNKNOWN" in html
    assert "NOT_ESTABLISHED" in html
    assert "Assertion contracts and provenance" in html


def test_scenario_and_run_views_wire_read_only_presentation(monkeypatch):
    from workbench.server_admin.feature_testing import router, results

    detail = router.scenario_detail("moghancement", "MOG-09")
    assert detail["execution_enabled"] is False
    assert detail["presentation"]["assertion_count"] == 6

    record = synthetic_imported_result()
    record.update(run_id="synthetic-run", stage="key_item",
                  observed_at="2026-10-20T00:00:00Z",
                  dsp_commit="a" * 40, headless_commit="b" * 40,
                  toolkit_commit="c" * 40)
    monkeypatch.setattr(router, "_results_db", lambda: "/unused/synthetic.sqlite")
    monkeypatch.setattr(results, "results_for_run", lambda path, run_id: [record])
    class Templates:
        def TemplateResponse(self, **kwargs):
            return kwargs["context"]
    monkeypatch.setattr(router, "templates", Templates())
    context = router.run_page(None, "synthetic-run")
    view = context["scenario_views"][0]
    assert len(view["steps"]) == 6
    assert view["recorded_verdict"] == "PASS"
    assert view["recalculated_verdict"] == "PASS"
    assert view["independent_verification"] == "NOT_ESTABLISHED"


def test_unmapped_claims_and_unrecognized_status_never_turn_into_pass():
    spec = synthetic_bdd()
    spec["steps"].pop()
    view = scenario_presentation(spec, {
        "recorded_verdict": "PASS",
        "evaluation": {"assertions": [
            {"id": "expected_character", "status": "SKIPPED", "reason": "Synthetic unsupported status"},
        ]},
    })
    assert view["unmapped_assertions"] == ["safe_matches_persisted"]
    assert view["mapped_assertion_count"] == 5
    assert view["steps"][0]["status"] == "UNKNOWN"
    assert view["steps"][1]["status"] == "UNKNOWN"
    assert view["independent_verification"] == "NOT_ESTABLISHED"


def test_source_kind_labels_are_prefix_labels_not_authentication():
    from workbench.server_admin.feature_testing.scenario_presentation import source_kind
    assert source_kind("client_x") == "Client-observed"
    assert source_kind("db_x") == "Server database"
    assert source_kind("gm_x") == "GM diagnostic"
    assert source_kind("session") == "Runner session report"
    assert source_kind("whatever") == "Runner-reported (source unspecified)"


def test_design_view_has_no_selected_run_and_unknown_outcomes():
    view = scenario_presentation(specification("moghancement", "MOG-09"))
    assert view["selected_run_id"] is None
    assert not any(s["has_failed_assertion"] for s in view["steps"])
    stages = list(view["lifecycle"])
    assert len(stages) == 5
    for step in view["steps"]:
        for assertion in step["assertions"]:
            assert assertion["outcome_kind"] != "FAILED_ASSERTION"


def test_selected_run_id_is_carried_and_templates_link_runs():
    view = scenario_presentation(specification("moghancement", "MOG-09"), {"recorded_verdict": "PASS"}, "run-1")
    assert view["selected_run_id"] == "run-1"
    root = Path(__file__).resolve().parents[1]
    scen = (root / "gui/templates/feature_testing_scenario.html").read_text(encoding="utf-8")
    assert "?run=" in scen and "No run (design view)" in scen
    run = (root / "gui/templates/feature_testing_run.html").read_text(encoding="utf-8")
    assert "?run=" in run
