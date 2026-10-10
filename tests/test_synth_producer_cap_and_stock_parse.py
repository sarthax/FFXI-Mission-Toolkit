from workbench.server_admin.auction_house.arbitrage import _dsp_stock_offers
from workbench.server_admin.synth import recipes as R


def test_stock_parse_survives_nested_braces():
    text = "local stock = { 0x1000, 50, {x=1}, 0x1001, 70 }\nshowShop(player, stock)"
    assert _dsp_stock_offers(text)[0] == (0x1000, 50)


def test_stock_parse_plain_pairs():
    assert _dsp_stock_offers("stock = {0x10, 5, 0x11, 6}\nshowShop(p, stock)") == [(0x10, 5), (0x11, 6)]


def test_obtainable_explores_producers_beyond_sixth():
    av = R.Availability.__new__(R.Availability)
    av._memo, av._soft = {}, {}
    av.src = {"vendors": {7: {"price": 1, "vendor": "v", "zone": ""}}, "drops": {}, "orphan_drops": set(), "bcnm": set(), "ah": {}, "scripts": {},
              "crafted": {1: list(range(100, 110))}}
    av.recipes = {rid: {"crystal": 0, "ingredients": [99 if rid < 109 else 7]} for rid in range(100, 110)}
    assert av.obtainable(1) is True  # only the 10th producer is viable
