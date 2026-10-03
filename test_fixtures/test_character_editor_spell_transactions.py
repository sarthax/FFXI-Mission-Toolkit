from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    tx = (ROOT / "src" / "workbench" / "editors" / "character" / "spell_transactions.py").read_text(encoding="utf-8")
    service = (ROOT / "src" / "workbench" / "editors" / "character" / "service.py").read_text(encoding="utf-8")

    assert '_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}' in tx
    assert 'action not in {"learn", "unlearn"}' in tx
    assert 'Character is online; spell writes are blocked.' in tx
    assert 'online_state_unknown' in tx
    assert 'spell_list' in tx and 'char_spells' in tx
    assert 'learned_now != plan.learned_before' in tx
    assert 'INSERT INTO `char_spells`' in tx
    assert 'DELETE FROM `char_spells`' in tx
    assert 'connection.commit()' in tx and 'connection.rollback()' in tx
    assert 'search_spells' in service
    assert 'preview_spell_edit' in service
    assert 'apply_spell_edit_request' in service
    assert '"spells_offline"' in service


if __name__ == "__main__":
    main()
