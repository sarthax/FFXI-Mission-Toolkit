"""Wiki candidate review panel shows escaped original source and provenance."""
from pathlib import Path

def main():
    template=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    for expected in ("class=\"wiki-candidate-source\"", "{{ candidate.value_raw }}",
                     "{{ candidate.value_source_locator }}", "{{ candidate.field_source_locator }}"):
        assert expected in template,expected
    assert "Source cell" in template
    print("Wiki V2 review source cell UI regression: PASS")

if __name__=="__main__":
    main()
