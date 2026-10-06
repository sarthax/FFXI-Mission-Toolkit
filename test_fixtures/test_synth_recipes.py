from workbench.server_admin.synth import recipes as R

DSP_COLS = ["ID", "Type", "KeyItem", *R.CRAFTS, "Crystal", "HQCrystal", *R.INGREDIENTS, *R.RESULTS, *R.QTYS]


def _row(**kw):
    base = {c: 0 for c in DSP_COLS}
    base.update(kw)
    return base


def _rec(**kw):
    rec = {"id": 7, "desynth": False, "key_item": 0, "skills": {c: 0 for c in R.CRAFTS}, "crystal": 4096, "hq_crystal": 4096,
           "ingredients": [662, 100], "results": [{"item_id": 128, "qty": 1}] * 4, "result_name": "Console", "content_tag": None}
    rec.update(kw)
    rec["skills"] = {**{c: 0 for c in R.CRAFTS}, "Smith": 5}
    return rec


def test_flavor_detection_and_desynth_semantics():
    assert R.detect_flavor(["ID", "Type", "KeyItem"]) == "dsp"
    assert R.detect_flavor(["ID", "Desynth", "ResultName"]) == "topaz"
    assert R.detect_flavor(["ID", "Desynth", "ResultName", "content_tag"]) == "lsb"
    assert R._is_desynth({"Type": 0}) and not R._is_desynth({"Type": 1})
    assert R._is_desynth({"Desynth": 1}) and not R._is_desynth({"Desynth": 0})


def test_canon_drops_empty_ingredient_slots():
    c = R._canon(_row(ID=3, Smith=9, Ingredient1=5, Ingredient2=6, Result=8, ResultQty=2))
    assert c["ingredients"] == [5, 6] and c["results"][0] == {"item_id": 8, "qty": 2}


def test_build_sql_per_flavor():
    rec = _rec()
    dsp, topaz, lsb = (R.build_sql(rec, f) for f in R.FLAVORS)
    assert "`Type`" in dsp and "`Desynth`" not in dsp and "ResultName" not in dsp
    assert "`Desynth`" in topaz and "'Console'" in topaz and "content_tag" not in topaz
    assert "`content_tag`" in lsb and lsb.rstrip(";").endswith("NULL)")
    assert "WHERE `ID`=7" in R.build_sql(rec, "dsp", "update") and R.build_sql(rec, "lsb", "delete") == "DELETE FROM `synth_recipes` WHERE `ID`=7;"


def test_desynth_flag_maps_inverted_for_dsp():
    rec = _rec(desynth=True)
    assert "VALUES (7,0," in R.build_sql(rec, "dsp") and "VALUES (7,1," in R.build_sql(rec, "topaz")


def test_sql_literals_escape_quotes():
    bs = chr(92)
    assert R._lit("O'B" + bs) == "'O''B" + bs + bs + "'" and R._lit(None) == "NULL"


def test_dsp_stock_parser_pairs_and_triples():
    from workbench.server_admin.auction_house.arbitrage import _dsp_stock_offers
    nation = "stock = {\n 0x4100, 284,3, --Axe\n 0x4101, 1435,3\n}\nshowNationShop(player, NATION_BASTOK, stock);"
    assert _dsp_stock_offers(nation) == [(0x4100, 284), (0x4101, 1435)]
    plain = "stock = {0x0279, 14, 0x0280, 20}\nshowShop(player, STATIC, stock)"
    assert _dsp_stock_offers(plain) == [(0x279, 14), (0x280, 20)]
