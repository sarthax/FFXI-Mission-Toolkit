from pathlib import Path

from workbench.editors.character.merit_catalog import merit_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_lsb_merit_catalog_parses_categories_costs_effects_and_jobs(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "merits.yaml").write_text(
        """
merits:
  upgrade_costs:
    hp_mp: [1, 2, 3]
    job_group_1: [1, 2, 3, 4, 5]
  categories:
    hp_mp:
      id: 0x0040
      max_upgrades: 75
      merits:
        max_hp:
          id: 0x0040
          value: 10
          upgrade_cost: hp_mp
    warrior_group_1:
      id: 0x0200
      max_upgrades: 10
      merits:
        berserk_recast:
          id: 0x0200
          value: -10
          upgrade_cost: job_group_1
          jobs: [war]
""".strip(),
        encoding="utf-8",
    )

    catalog = merit_catalog(tmp_path, "lsb")
    assert catalog["source"]["available"] is True
    assert [row["label"] for row in catalog["categories"]] == ["HP MP", "Warrior Group 1"]
    hp = catalog["items"][str(0x0040)]
    assert hp["label"] == "Max HP"
    assert hp["value_per_upgrade"] == 10
    assert hp["costs"] == [1, 2, 3]
    assert hp["max_upgrades"] == 3
    warrior = catalog["items"][str(0x0200)]
    assert warrior["jobs"] == ["war"]
    assert warrior["value_per_upgrade"] == -10


def test_legacy_checkout_without_structured_catalog_does_not_guess_current_lsb_ids(tmp_path):
    catalog = merit_catalog(tmp_path, "dsp")
    assert catalog["source"]["available"] is False
    assert catalog["categories"] == []
    assert catalog["items"] == {}
    assert "does not expose" in catalog["note"]


def test_merit_catalog_is_attached_only_as_checkout_catalog_and_ui_renders_all_definitions():
    category_data = (ROOT / "src" / "workbench" / "editors" / "character" / "category_data.py").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_merits.js").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")

    assert "from .merit_catalog import merit_catalog" in category_data
    assert 'if tab.key == "merits-jobpoints"' in category_data
    assert 'catalogs["merits"] = merit_catalog' in category_data
    assert "activeCategoryData?.catalogs?.merits" in script
    # Current UI groups checkout catalog definitions through each category's `merits` list
    # rather than the older `category.merits || []` local variable shape.
    assert "c.merits || []" in script
    assert "cat.merits || []" in script
    assert "Rank" in script and "Next cost" in script and "value_per_upgrade" in script
    assert "Apply merit changes" in script
    assert "const base = `/character-editor/characters/${selectedChar}/fields`" in script
    assert "`${base}/preview`" in script and "`${base}/apply`" in script
    assert "/static/character_editor_merits.js" in template
    assert template.index('/static/character_editor_merits.js') < template.index('/static/character_editor_dense_modes.js')
