"""Zone-wide Assault dependencies require explicit evidence and do not create mission links."""
import pytest
from workbench.domains.assault_shared_reviews import read, set_zone


def test_zone_scope_separate_from_mission_links(tmp_path):
    db=tmp_path/"assault.db"
    args={"topics":{"System-wide"}, "zones":{"Periqia","Ilrusi Atoll"}, "path":db}
    with pytest.raises(ValueError, match="evidence"):
        set_zone("System-wide","Periqia",**args)
    set_zone("System-wide","Periqia","Zone.lua timeout handler",**args)
    rows=read(db)
    assert rows["zones"][0]["zone"]=="Periqia"
    assert rows["links"]==[]
    set_zone("System-wide","Periqia",unlink=True,**args)
    assert read(db)["zones"]==[]


def test_zone_scope_rejects_unknown_zone(tmp_path):
    with pytest.raises(ValueError, match="zone"):
        set_zone("System-wide","Whitegate","reference",
                 topics={"System-wide"},zones={"Periqia"},path=tmp_path/"s.db")
