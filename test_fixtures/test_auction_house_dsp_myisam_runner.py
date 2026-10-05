from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "dsp_myisam_runner.py"


def test_dsp_myisam_runner_forces_and_restores_autocommit():
    text = RUNNER.read_text(encoding="utf-8")
    assert 'hasattr(connection, "autocommit")' in text
    assert "previous = bool(connection.autocommit)" in text
    assert "connection.autocommit = True" in text
    assert "connection.autocommit = previous" in text
