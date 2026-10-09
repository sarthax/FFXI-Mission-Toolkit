from workbench.server_admin.voidwatch import drops as Dr


def test_render_parse_roundtrip():
    o = {"pool": [4096, 4097], "poolRemove": [4100], "nm": {"Cottus": {"add": {11667: 12.5, 4096: 100.0}, "remove": [123]}, "Empty": {"add": {}, "remove": []}}}
    text = Dr.render(o)
    assert "Empty" not in text
    back = Dr.parse(text)
    assert back["pool"] == [4096, 4097]
    assert back["poolRemove"] == [4100]
    assert back["nm"]["Cottus"] == {"add": {11667: 12.5, 4096: 100.0}, "remove": [123]}


def test_parse_empty_default():
    text = Dr.render({"pool": [], "poolRemove": [], "nm": {}})
    assert Dr.parse(text) == {"pool": [], "poolRemove": [], "nm": {}}
