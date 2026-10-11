#!/usr/bin/env python3
"""Static UI/route contract for manual capture review workflow."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    detail=(ROOT/"gui/templates/capture_detail.html").read_text(encoding="utf-8")
    review=(ROOT/"gui/templates/capture_review.html").read_text(encoding="utf-8")
    host=(ROOT/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    help_text=(ROOT/"gui/templates/capture_help.html").read_text(encoding="utf-8")

    assert "Review / missing data" in detail
    assert 'action="/captures/{{ detail.capture_id }}/review-flags"' in detail
    assert 'name="blocking"' in detail
    assert "/review-flags/{{ item.review_id }}" in detail
    assert "item.detail.summary" in detail

    assert "r.detail.summary" in review
    assert "{% if r.blocking %}" in review

    assert '@app.post("/captures/{capture_id}/review-flags")' in host
    assert '@app.post("/captures/{capture_id}/review-flags/{review_id}")' in host
    assert "rq.create_manual(" in host

    assert "Review flags, missing data, and follow-up requests" in help_text
    assert "non-blocking by default" in help_text

    print("capture manual review UI self-test: PASS")


if __name__=="__main__":
    main()
