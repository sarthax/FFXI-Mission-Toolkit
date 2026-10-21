"""Synthetic offline Feature Trace URL breadcrumb and rendered route regressions.

Breadcrumbs are selection history only, never saved investigations, canonical
graph relationships, gameplay observations or evidence-verification results.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from workbench.devtools.features import trace_investigation as trail
from test_feature_trace_mode_navigation import _client


def test_invalid_url_trails_fail_closed_without_500():
    for bad in ("nonsense", "{}", '"root"', "[1]", '[""]',
                '["  "]', json.dumps(["x" * 241]),
                json.dumps(["alpha\nmalicious"]),
                "a" * 2700):
        assert trail.parse_trail(bad) == ()
    assert trail.parse_trail(None) == ()
    assert trail.parse_trail("") == ()


def test_bounded_navigation_retains_last_eight_exact_ids_and_safe_json():
    nodes = [f"synthetic:node-{n}" for n in range(13)]
    previous = trail.parse_trail(json.dumps(nodes))
    assert previous == tuple(nodes[-8:])
    outgoing = trail.trail_for_next_root(previous, "synthetic:next")
    assert json.loads(outgoing) == nodes[-7:] + ["synthetic:next"]
    # Clicking a link back to the already last-selected root must not
    # accidentally record a duplicate hop as if it were a new path.
    assert json.loads(trail.trail_for_next_root(previous, previous[-1])) == nodes[-8:]


def test_ancestry_links_are_prefix_history_not_the_whole_future():
    previous = ("synthetic:first", "synthetic:second", "synthetic:third")
    crumbs = trail.breadcrumb_links(previous)
    assert [item["node_id"] for item in crumbs] == list(previous)
    assert [json.loads(item["trail"]) for item in crumbs] == [
        [], ["synthetic:first"], ["synthetic:first", "synthetic:second"],
    ]
    assert trail.encode_trail(()) == "[]"


def test_empty_or_malformed_trail_does_not_interfere_with_feature_trace():
    client, traced, searched, _cleared, closed = _client()
    for raw in ("not-json", json.dumps([""])):
        response = client.get("/features/trace", params={
            "q": "synthetic-root", "mode": "implementation", "trail": raw,
        })
        assert response.status_code == 200
        assert 'id="trace-investigation-trail"' in response.text
        assert "not a validated evidence path" in response.text
        assert 'name="trail" value="[]"' in response.text
    assert len(traced) == 2
    assert all(item["kwargs"] == {"mode": "implementation"} for item in traced)
    assert closed == ["graph", "catalog"] * 2


def test_actual_rendered_links_preserve_mode_depth_direction_and_breadcrumbs():
    history = ["synthetic:origin", "synthetic:branch"]
    client, traced, searched, _cleared, closed = _client()
    response = client.get("/features/trace", params={
        "q": "synthetic-root", "mode": "mission", "depth": 2,
        "direction": "out", "trail": json.dumps(history),
    })
    assert response.status_code == 200
    rendered = response.text
    assert "synthetic:origin" in rendered and "synthetic:branch" in rendered
    assert 'aria-current="page">synthetic-root</strong>' in rendered
    assert 'name="trail"' in rendered
    assert "not a validated evidence path" in rendered
    assert 'id="trace-focused-mode"' in rendered
    assert traced[0]["root"] == "synthetic-root"
    assert traced[0]["kwargs"] == {"mode": "mission"}

    # Follow a semantic/provider link: selected ROOT joins the recorded
    # selections. Never mutate the trace edge list to manufacture a chain.
    href = re.search(r'href="(/features/trace\?q=synthetic-target[^"]+)"', rendered)
    assert href, "Test fixture has an actual relationship to synthetic-target"
    query = parse_qs(urlsplit(html.unescape(href.group(1))).query)
    assert query["q"] == ["synthetic-target"]
    assert query["mode"] == ["mission"]
    assert query["depth"] == ["2"]
    assert query["direction"] == ["out"]
    assert json.loads(query["trail"][0]) == history + ["synthetic-root"]

    # Backtracking to synthetic:branch prunes later history, preserving the
    # selected question/direction without claiming source-backed causality.
    crumb = re.search(r'href="(/features/trace\?q=synthetic%3Abranch[^"]+)"', rendered)
    assert crumb
    back = parse_qs(urlsplit(html.unescape(crumb.group(1))).query)
    assert back["mode"] == ["mission"]
    assert json.loads(back["trail"][0]) == ["synthetic:origin"]

    clear = re.search(r'href="(/features/trace\?q=synthetic-root[^"]+)"[^>]*>Clear trail for this root', rendered)
    assert clear
    assert "trail" not in parse_qs(urlsplit(html.unescape(clear.group(1))).query)
    assert closed == ["graph", "catalog"]


def test_untrusted_url_breadcrumbs_are_html_escaped_and_do_not_change_root():
    untrusted = '<img src=x onerror=alert("synthetic")>'
    client, traced, _searched, _cleared, _closed = _client()
    response = client.get("/features/trace", params={
        "q": "synthetic-root", "trail": json.dumps([untrusted]),
    })
    assert response.status_code == 200
    assert untrusted not in response.text
    assert "&lt;img src=x" in response.text
    assert traced[0]["root"] == "synthetic-root"
