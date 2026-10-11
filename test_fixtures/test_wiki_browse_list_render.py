"""Regression: Wiki browse list items must use dict key lookup, not dict.items method."""
from pathlib import Path
from jinja2 import Environment

ROOT=Path(__file__).resolve().parents[1]
template=(ROOT/"gui/templates/wiki.html").read_text(encoding="utf-8")
assert "{% for li in item['items'] %}" in template
assert "{% for li in item.items %}" not in template
snippet="{% for item in section.content %}{% if item.type == 'list' %}<ul>{% for li in item['items'] %}<li>{{ li.text }}</li>{% endfor %}</ul>{% endif %}{% endfor %}"
rendered=Environment(autoescape=True).from_string(snippet).render(section={
    "content":[{"type":"list","items":[{"text":"One"},{"text":"Two"}]}]})
assert "<li>One</li>" in rendered and "<li>Two</li>" in rendered
print("Wiki browse list dict-key rendering: PASS")
