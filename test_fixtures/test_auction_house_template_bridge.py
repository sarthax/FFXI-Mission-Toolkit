from types import SimpleNamespace
import sys

from workbench.server_admin.auction_house import gui


def test_auction_house_syncs_host_template_globals():
    original = sys.modules.get("workbench.app.host")
    sentinel_theme = lambda: "dark"
    sentinel_shell = lambda request: {"request": request}
    fake_env = SimpleNamespace(globals={
        "current_theme": sentinel_theme,
        "shell_context": sentinel_shell,
        "backport_enabled": lambda: False,
    })
    sys.modules["workbench.app.host"] = SimpleNamespace(templates=SimpleNamespace(env=fake_env))
    try:
        gui.templates.env.globals.pop("current_theme", None)
        gui.templates.env.globals.pop("shell_context", None)
        gui._sync_host_template_globals()
        assert gui.templates.env.globals["current_theme"] is sentinel_theme
        assert gui.templates.env.globals["shell_context"] is sentinel_shell
    finally:
        if original is None:
            sys.modules.pop("workbench.app.host", None)
        else:
            sys.modules["workbench.app.host"] = original


def test_auction_house_page_syncs_before_template_render():
    source = gui.auction_house_page.__wrapped__ if hasattr(gui.auction_house_page, "__wrapped__") else gui.auction_house_page
    names = source.__code__.co_names
    assert "_sync_host_template_globals" in names


if __name__ == "__main__":
    test_auction_house_syncs_host_template_globals()
    test_auction_house_page_syncs_before_template_render()
    print("Auction House template bridge regression: PASS")
