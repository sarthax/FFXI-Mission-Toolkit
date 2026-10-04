from pathlib import Path

from src.workbench.server_admin.auction_house.config_policy import load_active_legacy_policy


POLICY = """
ah_base_fee_single: 2
ah_base_fee_stacks: 5
ah_tax_rate_single: 1.25
ah_tax_rate_stacks: 0.75
ah_max_fee: 12345
ah_list_limit: 9
"""


def _write(root: Path, relative: str, text: str = POLICY) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_topaz_active_map_conf_is_loaded(tmp_path):
    path = _write(tmp_path, "conf/map.conf")
    result = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    assert result.policy_ready is True
    assert result.source_path == str(path)
    assert result.source_kind == "active"
    assert result.policy.base_fee_single == 2
    assert result.policy.base_fee_stacks == 5
    assert result.policy.tax_rate_single == 1.25
    assert result.policy.tax_rate_stacks == 0.75
    assert result.policy.max_fee == 12345
    assert result.policy.list_limit == 9
    assert result.policy_fingerprint
    assert result.executor_enabled is False
    assert result.executable is False


def test_dsp_darkstar_config_is_loaded(tmp_path):
    path = _write(tmp_path, "conf/map_darkstar.conf")
    result = load_active_legacy_policy(server_root=tmp_path / "conf", family="dsp")
    assert result.policy_ready is True
    assert result.source_path == str(path)
    assert result.policy.list_limit == 9


def test_topaz_template_is_reported_but_never_promoted_to_active(tmp_path):
    template = _write(tmp_path, "conf/default/map.conf")
    result = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    assert result.policy_ready is False
    assert result.policy is None
    assert result.template_paths == (str(template),)
    assert "active_ah_config_missing" in {issue.code for issue in result.issues}


def test_incomplete_active_policy_fails_closed(tmp_path):
    _write(tmp_path, "conf/map.conf", "ah_base_fee_single: 1\nah_max_fee: 10000\n")
    result = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    assert result.policy_ready is False
    assert result.policy is None
    assert "ah_policy_incomplete" in {issue.code for issue in result.issues}


def test_invalid_active_policy_fails_closed(tmp_path):
    _write(tmp_path, "conf/map.conf", POLICY.replace("ah_list_limit: 9", "ah_list_limit: -1"))
    result = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    assert result.policy_ready is False
    assert result.policy is None
    assert "ah_policy_invalid" in {issue.code for issue in result.issues}


def test_dsp_conflict_between_active_looking_configs_is_blocked(tmp_path):
    _write(tmp_path, "conf/map_darkstar.conf", POLICY)
    _write(tmp_path, "conf/map.conf", POLICY.replace("ah_list_limit: 9", "ah_list_limit: 12"))
    result = load_active_legacy_policy(server_root=tmp_path, family="dsp")
    assert result.policy_ready is False
    assert result.policy is None
    assert "active_ah_config_ambiguous" in {issue.code for issue in result.issues}


def test_dsp_duplicate_equivalent_config_is_not_ambiguous(tmp_path):
    preferred = _write(tmp_path, "conf/map_darkstar.conf", POLICY)
    _write(tmp_path, "conf/map.conf", POLICY)
    result = load_active_legacy_policy(server_root=tmp_path, family="dsp")
    assert result.policy_ready is True
    assert result.source_path == str(preferred)


def test_legacy_equals_syntax_and_inline_comments_are_supported(tmp_path):
    text = """
ah_base_fee_single = 1 # retail
ah_base_fee_stacks = 4
ah_tax_rate_single = 1.0
ah_tax_rate_stacks = 0.5
ah_max_fee = 10000
ah_list_limit = 0 ; unlimited
"""
    _write(tmp_path, "conf/map.conf", text)
    result = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    assert result.policy_ready is True
    assert result.policy.list_limit == 0


def test_unknown_family_never_uses_legacy_defaults(tmp_path):
    _write(tmp_path, "conf/map.conf")
    result = load_active_legacy_policy(server_root=tmp_path, family="auto")
    assert result.policy_ready is False
    assert result.policy is None
    assert "config_family_unsupported" in {issue.code for issue in result.issues}


def test_policy_fingerprint_only_tracks_required_values(tmp_path):
    path = _write(tmp_path, "conf/map.conf", "# first\n" + POLICY)
    first = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    path.write_text("# changed comment\n" + POLICY, encoding="utf-8")
    second = load_active_legacy_policy(server_root=tmp_path, family="topaz")
    assert first.policy_fingerprint == second.policy_fingerprint


def test_module_contains_no_database_or_mutation_primitive():
    source = Path("src/workbench/server_admin/auction_house/config_policy.py").read_text(encoding="utf-8")
    upper = source.upper()
    assert "UPDATE AUCTION_HOUSE" not in upper
    assert "INSERT INTO AUCTION_HOUSE" not in upper
    assert "DELETE FROM AUCTION_HOUSE" not in upper
    assert ".COMMIT(" not in upper
