"""Deterministic translation QA, no Ollama calls."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from workbench.devtools.reference.wiki_ollama_translate import quality_warnings


def test_numbers_and_identifiers():
    issues=quality_warnings("HP 250、イベント 0x01AF と ITEM_123", "HP 200 and event")
    assert any("Numeric tokens missing" in s for s in issues)
    assert any("Identifiers missing" in s and "ITEM_123" in s for s in issues)


def test_terms_and_short_output():
    issues=quality_warnings("だいじなもの"+"詳細"*80, "item")
    assert any("key item" in s for s in issues)
    assert any("unusually short" in s for s in issues)


def test_valid_conservative():
    assert quality_warnings("だいじなもの HP 250", "key item HP 250") == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
