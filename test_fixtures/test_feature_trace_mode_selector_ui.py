from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_feature_trace_mode_selector_is_injected_by_shared_shell_script():
    script = (ROOT / "gui" / "static" / "server_environment_selector.js").read_text(encoding="utf-8")
    assert "installFeatureTraceModes" in script
    assert "location.pathname !== '/features/trace'" in script
    assert "featureTraceMode" in script
    assert "How is this implemented?" in script
    assert "Mission progression" in script
    assert "Runtime evidence" in script
    assert "Client ↔ server identity" in script
    assert "Why is this broken?" in script
    assert "input.value = `@${select.value} ${query}`" in script
    assert "Generated provider relationships remain read-only evidence" in script
