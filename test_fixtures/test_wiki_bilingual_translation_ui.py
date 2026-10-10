"""Static smoke guard for aligned Wiki JP translation interface."""
from pathlib import Path

template = (Path(__file__).resolve().parents[2] / "gui/templates/wiki.html").read_text(encoding="utf-8")
assert 'id="tr-bilingual"' in template
assert 'id="tr-aligned"' in template
assert 'b.original||' in template
assert 'translated.textContent=b.text||' in template
assert "row.append(jp,en)" in template
assert "Array.isArray(d.blocks)" in template
assert ".catch(function(e)" in template
assert "wiki-bilingual-row" in template
print("ok: aligned Wiki translation UI contract")
