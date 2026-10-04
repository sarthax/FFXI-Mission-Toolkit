from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scenario_trace_route_is_registered_and_mode_aware():
    init = (ROOT / "src/workbench/editors/character/__init__.py").read_text(encoding="utf-8")
    route = (ROOT / "src/workbench/editors/character/feature_trace_scenario_gui.py").read_text(encoding="utf-8")
    template = (ROOT / "gui/templates/feature_trace_scenario.html").read_text(encoding="utf-8")
    character = (ROOT / "gui/templates/character_editor_progression.html").read_text(encoding="utf-8")

    assert "feature_trace_scenario_gui" in init
    assert '@router.get("/scenario-trace"' in route
    assert "feature_trace.resolve_query" in route
    assert "mode=selected.mode_id" in route
    assert "normalize_mode(mode)" in route
    assert "Scenario Feature Trace" in template
    assert 'name="mode"' in template
    assert "Generated provider relationships" in template
    assert "Multiple plausible roots remain" in template
    assert "/features/trace" in template
    assert "/character-editor/scenario-trace" in character


def test_scenario_trace_exposes_all_question_modes():
    template = (ROOT / "gui/templates/feature_trace_scenario.html").read_text(encoding="utf-8")
    modes = (ROOT / "src/workbench/devtools/features/trace_modes.py").read_text(encoding="utf-8")
    for mode_id in (
        "implementation", "triggers", "effects", "dependencies", "mission",
        "runtime", "identity", "diagnose", "all",
    ):
        assert f'TraceMode("{mode_id}"' in modes
    assert "mode_options" in template
    assert "Technical Trace" in template
