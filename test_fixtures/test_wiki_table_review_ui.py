"""Wiki article template exposes only review-only labeled-table annotations."""
from pathlib import Path

def main():
    text=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert "{% if item.field_candidates %}" in text
    assert "{% for candidate in item.field_candidates %}" in text
    assert "{{ candidate.field }}" in text and "{{ candidate.value }}" in text
    assert "not verified gameplay facts" in text
    assert "<details class=\"wiki-table-review\">" in text
    print("Wiki V2 table review UI regression: PASS")

if __name__=="__main__":
    main()
