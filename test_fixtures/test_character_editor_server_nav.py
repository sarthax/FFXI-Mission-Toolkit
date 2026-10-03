from workbench.gui_shell import WORKSPACES, build_shell_context, route_owner


def _context(path: str) -> dict:
    return build_shell_context(
        path=path,
        method="GET",
        settings={},
        default_topaz_root="C:/missing-topaz",
        default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )


def test_character_editor_is_server_navigation_entry():
    server = next(workspace for workspace in WORKSPACES if workspace["name"] == "Server")
    entry = next(section for section in server["sections"] if section["label"] == "Character Editor")
    assert entry["href"] == "/character-editor"
    assert entry["mutation"] is True


def test_character_editor_route_is_owned_by_server_workspace():
    owner = route_owner("/character-editor")
    assert owner["home"] == "Server"
    assert owner["section"] == "Character Editor"

    nested = route_owner("/character-editor/history.json")
    assert nested["home"] == "Server"
    assert nested["section"] == "Character Editor"


def test_character_editor_shell_marks_server_and_section_active():
    shell = _context("/character-editor")
    assert shell["active_home"] == "Server"
    active = next(section for section in shell["sections"] if section["active"])
    assert active["label"] == "Character Editor"


if __name__ == "__main__":
    test_character_editor_is_server_navigation_entry()
    test_character_editor_route_is_owned_by_server_workspace()
    test_character_editor_shell_marks_server_and_section_active()
