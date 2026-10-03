from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "gui" / "static" / "server_environment_selector.js"


def test_top_level_workspace_clicks_open_section_menus_without_default_navigation():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "#app-shell .shell-workspaces a.workspace-link" in text
    assert "event.preventDefault()" in text
    assert "openCategoryMenu(link)" in text
    assert "Open ${link.textContent.trim()} overview" in text
    assert "DOMParser" in text
    assert "details.section-menu .shell-popover" in text


def test_sections_toggle_uses_secondary_bar_and_persists_session_state():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "shellSectionBar" in text
    assert "shell-section-strip" in text
    assert "aria-controls', 'shellSectionBar" in text
    assert "shellSectionsExpanded" in text
    assert "sessionStorage.setItem" in text


def test_server_environment_management_links_stay_in_settings():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "/settings#server-environments" in text
    assert "link.href = '/character-editor'" not in text
