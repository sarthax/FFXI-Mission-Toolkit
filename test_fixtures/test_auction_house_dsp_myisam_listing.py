from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "dsp_myisam_listing.py"


def test_dsp_myisam_listing_is_explicitly_test_only_and_non_atomic():
    text = MODULE.read_text(encoding="utf-8")
    assert "FFXI_MISSION_TOOLKIT_AH_DSP_MYISAM_TEST_WRITES" in text
    assert 'family != "dsp"' in text
    assert '"atomic": False' in text
    assert '"crash_window": True' in text
    assert "Seller must be offline" in text


def test_dsp_myisam_listing_uses_table_locks_and_compensation():
    text = MODULE.read_text(encoding="utf-8")
    assert "LOCK TABLES `auction_house` WRITE, `char_inventory` WRITE" in text
    assert "UNLOCK TABLES" in text
    assert "compensation_attempted" in text
    assert "DELETE FROM `auction_house`" in text
    assert "INSERT INTO `char_inventory`" in text
    assert "seller gil post-state" in text.lower()


def test_dsp_myisam_listing_keeps_transactional_path_separate():
    text = MODULE.read_text(encoding="utf-8")
    assert "Transactional tables are available; use the normal player-listing executor" in text
    assert "char_inventory" in text
