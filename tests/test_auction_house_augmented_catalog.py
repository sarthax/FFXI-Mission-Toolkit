"""The augmented reward catalog stores definitions, never delivery authority."""
import pytest
from workbench.server_admin.auction_house.augmented_catalog import (
    save_config,list_configs,delete_config
)
from workbench.server_admin.auction_house.reward_templates import RewardTemplateError


def test_catalog_roundtrip_and_edit(tmp_path):
    db=tmp_path/"augments.db"
    first=save_config(name="Sword reward", item_id=100, family="dsp",
                      augments=[{"id":45,"value":3}],path=db)
    assert first["augments"]==[{"id":45,"value":3}]
    second=save_config(name="Sword reward II", item_id=101, family="dsp",
                       augments=[{"id":46,"value":1}], config_id=first["id"],path=db)
    assert second["id"]==first["id"]
    assert second["created_utc"]==first["created_utc"]
    assert len(list_configs(path=db))==1
    assert delete_config(first["id"],path=db)["deleted"]
    assert list_configs(path=db)==[]


@pytest.mark.parametrize("augments", [[],[{"id":0,"value":1}],
    [{"id":2048,"value":1}], [{"id":5,"value":32}],
    [{"id":5,"value":1}]*5])
def test_catalog_rejects_invalid_augments(tmp_path, augments):
    with pytest.raises(RewardTemplateError):
        save_config(name="Invalid", item_id=100, family="dsp",augments=augments,path=tmp_path/"db.sqlite")
