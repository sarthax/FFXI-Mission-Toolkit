from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "auction_house_dsp_myisam_test.py"


def test_dsp_myisam_cli_has_readiness_and_explicit_confirmation():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"--readiness"' in text
    assert '"--confirmation"' in text
    assert "get_active_server_identity" in text
    assert "get_active_server_root" in text
    assert "dsp_myisam_listing_readiness" in text


def test_dsp_myisam_cli_does_not_expose_network_service():
    text = SCRIPT.read_text(encoding="utf-8").lower()
    assert "fastapi" not in text
    assert "apirouter" not in text
    assert "uvicorn" not in text
