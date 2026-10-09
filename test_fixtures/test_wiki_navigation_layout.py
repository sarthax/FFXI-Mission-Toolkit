"""Regression for Wiki review/recovery panels escaping the navigation toolbar."""
from pathlib import Path


def main():
    template = (Path(__file__).resolve().parents[1] / "gui/templates/wiki.html").read_text(encoding="utf-8")
    nav = '<div class="wiki-actions dense-toolbar" style="margin:6px 0">'
    browse = '<a class="chip {% if tab == \'browse\' %}active{% endif %}"'
    recovery = "{% if tab == 'recovery' %}"
    review = "{% if tab == 'review' %}"
    notice = "{% if review_result == 'approved' %}"

    assert template.count(nav) == 1
    assert template.count(recovery) == 1
    assert template.count(review) == 1
    assert template.index(notice) < template.index(nav)
    assert template.index(nav) < template.index(browse)
    nav_end = template.index("</div>", template.index(nav))
    assert template.index(recovery) > nav_end
    assert template.index(review) > nav_end
    assert template.index(recovery) < template.index(review)
    assert template.index("Local Wiki structure recovery") > nav_end
    assert template.index("Multilingual topic review queue") > nav_end


if __name__ == "__main__":
    main()
