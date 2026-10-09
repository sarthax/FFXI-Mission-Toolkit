import json

from workbench.server_admin.voidwatch import warps as W


def test_warps_data_integrity():
    rows = json.loads(W.WARPS.read_text(encoding="utf-8"))
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) and len(rows) >= 60
    opts = [r["option"] for r in rows if r["option"] is not None]
    assert len(opts) == len(set(opts))
    assert all(o % 65536 == 2 for o in opts)  # teleport action


def test_render_lua_skips_unvalidated(monkeypatch):
    monkeypatch.setattr(W, "overview", lambda conn: {"warps": [
        {"era": "present", "stone": "Hyacinth", "set": "Tavnazia", "tier": 1, "menu": "Lufaise_Meadows", "landing_note": "", "complete": True, "validation": "untested",
         "option": 3670018, "zone_id": 24, "x": 1.0, "y": 2.0, "z": 3.0, "rot": 4}]})
    assert "SKIPPED" in W.render_lua(None) and "] = {" not in W.render_lua(None)


def test_officer_zone_validation_rollup(tmp_path, monkeypatch):
    from workbench.server_admin.voidwatch import officers as O
    monkeypatch.setattr(O, "VALIDATION", tmp_path / "v.json")
    z = O.OFFICERS[0]["zones"]
    assert O.validation_status({}, z) == "unvalidated"
    all_ok = {k: "ok" for k, _ in O.ZONE_AREAS}
    O.save_zone_validation(O.OFFICERS[0]["id"], z[0], all_ok, "")
    rec = O.load_validation()[O.OFFICERS[0]["id"]]
    assert O.validation_status(rec, z) == "partial"
    O.save_zone_validation(O.OFFICERS[0]["id"], z[1], all_ok, "")
    assert O.validation_status(O.load_validation()[O.OFFICERS[0]["id"]], z) == "validated"
    O.save_zone_validation(O.OFFICERS[0]["id"], z[1], {**all_ok, "position": "issue"}, "off")
    assert O.validation_status(O.load_validation()[O.OFFICERS[0]["id"]], z) == "issue"


def test_parse_option_lines_keep_only_teleports_and_dedupe():
    from workbench.server_admin.voidwatch import warps as W
    txt = ("[08/Oct] [16:04:41][LUA Script] [VWO refiner] unhandled option=3670018 (0x380002) char=Gwendy zone=235\n"
           "[16:05:00][LUA Script] [VWO refiner] unhandled option=3670018 (0x380002) char=Gwendy zone=235\n"
           "[16:06:00][LUA Script] [VWO refiner] unhandled option=7 (0x7) char=Gwendy zone=235\n")
    recs = W.parse_options(txt)
    assert [r["option"] for r in recs] == [3670018] and recs[0]["dest_id"] == 56


def test_parse_logpos():
    from workbench.server_admin.voidwatch import warps as W
    r = W.parse_logpos("12:00 LOGPOS,gate,235,10.5,-2.0,33.25,64\n")
    assert r == [{"label": "gate", "zone_id": 235, "x": 10.5, "y": -2.0, "z": 33.25, "rot": 64}]
