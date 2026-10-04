from pathlib import Path

from src.workbench.server_admin.auction_house.config_policy import load_active_legacy_policy
from src.workbench.server_admin.auction_house.policy_binding import (
    preview_policy_binding,
    validate_preview_policy_binding,
)


POLICY = """
ah_base_fee_single: 1
ah_base_fee_stacks: 4
ah_tax_rate_single: 1.0
ah_tax_rate_stacks: 0.5
ah_max_fee: 10000
ah_list_limit: 7
"""


def _active(tmp_path: Path, text: str = POLICY):
    path = tmp_path / "conf" / "map.conf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return load_active_legacy_policy(server_root=tmp_path, family="topaz")


def test_preview_binding_carries_policy_provenance(tmp_path):
    active = _active(tmp_path)
    binding = preview_policy_binding(active)
    assert binding["family"] == "topaz"
    assert binding["source_kind"] == "active"
    assert binding["source_path"].endswith("conf/map.conf")
    assert binding["policy_fingerprint"] == active.policy_fingerprint
    assert binding["policy_ready"] is True
    assert binding["executor_enabled"] is False
    assert binding["executable"] is False


def test_unchanged_policy_binding_is_ready(tmp_path):
    active = _active(tmp_path)
    preview = {"policy_binding": preview_policy_binding(active)}
    check = validate_preview_policy_binding(preview, _active(tmp_path))
    assert check.binding_ready is True
    assert check.issues == []
    assert check.executor_enabled is False
    assert check.executable is False


def test_policy_value_change_invalidates_preview(tmp_path):
    original = _active(tmp_path)
    preview = {"policy_binding": preview_policy_binding(original)}
    changed = _active(tmp_path, POLICY.replace("ah_list_limit: 7", "ah_list_limit: 9"))
    check = validate_preview_policy_binding(preview, changed)
    assert check.binding_ready is False
    assert "auction_policy_drift" in {issue.code for issue in check.issues}


def test_missing_preview_binding_is_rejected(tmp_path):
    check = validate_preview_policy_binding({}, _active(tmp_path))
    assert check.binding_ready is False
    assert "preview_policy_binding_missing" in {issue.code for issue in check.issues}


def test_unavailable_active_policy_is_rejected(tmp_path):
    active = _active(tmp_path)
    preview = {"policy_binding": preview_policy_binding(active)}
    (tmp_path / "conf" / "map.conf").unlink()
    unavailable = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    check = validate_preview_policy_binding(preview, unavailable)
    assert check.binding_ready is False
    assert "active_policy_unavailable" in {issue.code for issue in check.issues}


def test_family_change_is_rejected(tmp_path):
    active = _active(tmp_path)
    binding = preview_policy_binding(active)
    binding["family"] = "dsp"
    check = validate_preview_policy_binding({"policy_binding": binding}, active)
    assert check.binding_ready is False
    assert "auction_policy_family_changed" in {issue.code for issue in check.issues}


def test_gui_previews_attach_policy_binding_and_no_apply_route():
    source = Path("src/workbench/server_admin/auction_house/gui.py").read_text(encoding="utf-8")
    assert "_preview_payload_with_policy(preview)" in source
    assert "preview_policy_binding" in source
    assert 'router.post("/admin/list/preview.json")' in source
    assert 'router.post("/admin/purchase/preview.json")' in source
    assert 'router.post("/apply' not in source
    assert 'router.post("/commit' not in source


def test_binding_module_contains_no_mutation_primitive():
    source = Path("src/workbench/server_admin/auction_house/policy_binding.py").read_text(encoding="utf-8")
    upper = source.upper()
    assert "UPDATE AUCTION_HOUSE" not in upper
    assert "INSERT INTO AUCTION_HOUSE" not in upper
    assert "DELETE FROM AUCTION_HOUSE" not in upper
    assert ".COMMIT(" not in upper
