"""Wiki scrape jobs remain observable after a browser refresh."""
from pathlib import Path


def main():
    text=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert "if(box && box.querySelector('.job-row')) poll();" in text
    assert "summary.textContent='Job log (" in text
    assert "pre.textContent=j.log.join(" in text
    assert "if(j.state==='done')" in text
    assert "link.textContent='Open cached page'" in text
    assert "node.appendChild(details)" in text
    print("Wiki scrape trace UI: PASS")


if __name__ == "__main__":
    main()
