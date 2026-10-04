from pathlib import Path


def test_validation_ui_exposes_read_only_preview_validation():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_admin.js").read_text(encoding="utf-8")
    gui = Path("src/workbench/server_admin/auction_house/gui.py").read_text(encoding="utf-8")

    assert 'id="ahValidatePreview"' in template
    assert 'id="ahValidationReport"' in template
    assert "Read-only preview validation" in template
    assert "EXECUTION DISABLED" in script
    assert "/auction-house/admin/validate/preview.json" in script
    assert '@router.post("/admin/validate/preview.json")' in gui
    assert "run_preview_validation" in gui
    assert 'payload["environment"] = identity' in gui


def test_preview_generation_attaches_lineage_specific_policy_binding():
    gui = Path("src/workbench/server_admin/auction_house/gui.py").read_text(encoding="utf-8")
    assert "preview_policy_binding" in gui
    assert "preview_lsb_policy_binding" in gui
    assert "load_lsb_policy" in gui
    assert 'payload["policy_binding"]' in gui


def test_validation_ui_renders_all_unified_report_stages():
    script = Path("gui/static/auction_house_admin.js").read_text(encoding="utf-8")
    for stage in (
        "environment",
        "lineage",
        "schema_readiness",
        "database_freshness",
        "policy",
        "policy_binding",
        "invariants",
    ):
        assert stage in script
    assert "read_only_validation_ready" in script
    assert "Blocking reasons" in script


def test_validation_surface_remains_non_executable():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_admin.js").read_text(encoding="utf-8")
    gui = Path("src/workbench/server_admin/auction_house/gui.py").read_text(encoding="utf-8")
    combined = "\n".join((template, script, gui)).lower()

    assert "no writes" in combined
    assert "/apply" not in script
    assert "/commit" not in script
    assert "executor_enabled = true" not in combined
    assert "write_enabled = true" not in combined


if __name__ == "__main__":
    test_validation_ui_exposes_read_only_preview_validation()
    test_preview_generation_attaches_lineage_specific_policy_binding()
    test_validation_ui_renders_all_unified_report_stages()
    test_validation_surface_remains_non_executable()
    print("Auction House validation UI regression: PASS")
