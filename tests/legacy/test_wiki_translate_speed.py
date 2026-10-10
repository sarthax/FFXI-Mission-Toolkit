from workbench.devtools.reference import wiki_ollama_translate as e


def test_auto_num_ctx_scales_and_clamps():
    assert e.auto_num_ctx("x" * 100, 50) == 2048
    assert e.auto_num_ctx("x" * 600, 1500) == 3072
    assert e.auto_num_ctx("x" * 9000, 5000) == 8192


def test_has_japanese():
    assert e.has_japanese("ミッション")
    assert e.has_japanese("Lv75 魔法")
    assert not e.has_japanese("20:Cloud Orb / 30")
