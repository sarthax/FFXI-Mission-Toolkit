from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "dsp_myisam_purchase.py"
SCRIPT = ROOT / "scripts" / "auction_house_dsp_myisam_test.py"


def test_dsp_myisam_purchase_is_test_only_flagged_and_non_atomic():
    text = MODULE.read_text(encoding="utf-8")
    assert "FFXI_MISSION_TOOLKIT_AH_DSP_MYISAM_TEST_WRITES" in text or "_MYISAM_FLAG" in text
    assert "DSP MyISAM purchase fallback is DSP Test-only" in text
    assert '"atomic": False' in text
    assert '"crash_window": True' in text
    assert "Buyer must be offline" in text


def test_dsp_myisam_purchase_claims_row_in_transaction_and_compensates():
    text = MODULE.read_text(encoding="utf-8")
    assert "START TRANSACTION" in text and "FOR UPDATE" in text
    assert "connection.commit()" in text and "connection.rollback()" in text
    assert "Seller settlement was not queued exactly once" in text
    assert "DELETE FROM `char_inventory`" in text  # compensation of the granted item
    assert "Buyer gil post-state verification failed" in text


def test_dsp_myisam_purchase_only_allows_char_inventory_non_transactional():
    text = MODULE.read_text(encoding="utf-8")
    assert 'set(engine_probe.blocking_tables) != {"char_inventory"}' in text
    assert "Transactional tables are available; use the normal player-purchase executor" in text


def test_cli_exposes_purchase_without_a_network_route():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"--purchase"' in text and '"--auction-id"' in text and '"--buyer-id"' in text
    assert "dsp_myisam_purchase_readiness" in text
