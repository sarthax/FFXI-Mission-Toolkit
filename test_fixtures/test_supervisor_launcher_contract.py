"""Static Windows launcher contract; execution requires an owner's local Windows test."""
from pathlib import Path

START = Path(__file__).resolve().parents[1] / "start.bat"


def test_supervisor_environment_is_explicit_and_local_only():
    text = START.read_text(encoding="utf-8")
    assert "if not defined MISSION_TOOLKIT_ENV_PS1 goto standard_start" in text
    assert 'if not exist "%MISSION_TOOLKIT_ENV_PS1%" (' in text
    assert 'MISSION_TOOLKIT_PYTHON=%PY%' in text
    assert "& $env:MISSION_TOOLKIT_PYTHON -m workbench.app.host" in text
    assert '%MISSION_TOOLKIT_ENV_PS1%\';' not in text
    assert 'D:\\MissionToolkitData' not in text
    assert '.env.ps1' not in text
    assert ":standard_start" in text
    assert '"%PY%" -m workbench.app.host' in text
    assert "set PY=%~dp0.venv\\Scripts\\python.exe" in text
