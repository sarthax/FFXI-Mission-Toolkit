"""#1408: every page extending base.html declares a viewport so narrow layouts apply on phones."""
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "gui" / "templates"


def test_base_template_declares_a_device_width_viewport():
    head = (TEMPLATES / "base.html").read_text(encoding="utf-8").split("</head>")[0]
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in head
