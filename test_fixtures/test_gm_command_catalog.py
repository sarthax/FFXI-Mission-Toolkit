from pathlib import Path
import pytest
from workbench.server_admin.gm_commands.catalog import catalog_commands, command_preview


def test_catalog_is_read_only_and_parses_dsp_metadata(tmp_path: Path):
    folder = tmp_path / "scripts" / "commands"
    folder.mkdir(parents=True)
    (folder / "getmobaction.lua").write_text('''-- func: getmobaction
-- desc: Prints mob current action
cmdprops = { permission = 1, parameters = "i" }
function onTrigger(player, id) end
''')
    (folder / "additem.lua").write_text('cmdprops={permission=1, parameters="ii"}')
    result = catalog_commands(tmp_path)
    assert len(result) == 2
    read = next(x for x in result if x["name"] == "getmobaction")
    assert read["classification"] == "diagnostic_candidate"
    assert read["permission"] == 1 and read["parameters"] == "i"
    assert read["execution_enabled"] is False
    assert next(x for x in result if x["name"] == "additem")["classification"] == "unreviewed"
    assert command_preview(read, ["17215539"]) == "!getmobaction 17215539"


def test_rejects_injected_line_breaks_and_bad_names():
    with pytest.raises(ValueError):
        command_preview({"name":"getmobaction"}, ["123\n!additem 1"])
    with pytest.raises(ValueError):
        command_preview({"name":"a;bad"}, [])
