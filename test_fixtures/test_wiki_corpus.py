"""Offline Wiki V2 regression runner over the sanitized real-source + synthetic corpus.

Deterministic: no network, no Ollama, no live databases. Reads only
``test_fixtures/wiki_corpus/*.json``. Real excerpts are minimal attributed structural
fragments; synthetic samples are independently authored and labelled as such.

Expectations come from the frozen label policy captured in the manifests (see
``scripts/wiki_corpus_extract.py``), never from the parser under test. Known deviations
between that policy and current behaviour live in ``known_gaps.json`` and are pinned so
that fixing them is a deliberate change, not a silent one.
"""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from workbench.devtools.reference.wiki_document import (
    html_blocks,
    legacy_text_blocks,
    mediawiki_blocks,
    presentation_groups,
)

CORPUS = Path(__file__).parent / "wiki_corpus"
# Keys a review hint may carry. Anything graph-like (relation/claim/mapping/edge) is a failure.
CANDIDATE_KEYS = {"field_type", "field", "value", "value_raw", "source_locator", "review_only", "source_links",
                  "row_index", "value_source_locator", "field_source_locator", "orientation", "column_index", "header_row_index"}
GRAPH_WORDS = ("relation", "claim", "mapping", "edge", "graph", "target_key", "resolved")
LINK_KEYS_FORBIDDEN = {"resolved", "target_key", "target_table", "mapping_status", "confidence"}


def _load():
    samples = []
    for name in ("real_manifest.json", "real_jp_manifest.json", "synthetic_manifest.json"):
        samples += json.loads((CORPUS / name).read_text(encoding="utf-8"))["samples"]
    gaps = json.loads((CORPUS / "known_gaps.json").read_text(encoding="utf-8"))
    return samples, gaps


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse(sample):
    text = sample["excerpt_wikitext"]
    if sample.get("source_format") == "legacy_text":
        blocks = legacy_text_blocks(sample["sample_id"], text)
    elif sample.get("source_format") == "html":
        blocks = html_blocks(sample["sample_id"], text)
    else:
        blocks = mediawiki_blocks(sample["sample_id"], text)
    return blocks, presentation_groups(blocks)


def _template_items(groups):
    """Ordered presentation items for template fields (one per template_field block)."""
    return [i for g in groups for i in g["content"] if i.get("type") == "definition" and "field_candidate" in i]


def _template_candidates(groups):
    return [(i, i["field_candidate"]) for i in _template_items(groups)]


def _table_candidates(groups):
    return [c for g in groups for item in g["content"] if item.get("type") == "table"
            for c in item["field_candidates"]]


def _assert_no_graph(sample, blocks, groups):
    sid = sample["sample_id"]
    for b in blocks:
        if b["block_type"] == "template_field":
            assert (b.get("metadata") or {}).get("review_only") is True, f"{sid}: template field not review_only"
    cands = [c for _, c in _template_candidates(groups) if c] + _table_candidates(groups)
    for c in cands:
        assert c.get("review_only") is True, f"{sid}: candidate not review_only"
        extra = set(c) - CANDIDATE_KEYS
        assert not extra, f"{sid}: unexpected candidate keys {extra}"
        assert not [k for k in c if any(w in k for w in GRAPH_WORDS)], f"{sid}: graph-like key on candidate"
        for link in c.get("source_links") or []:
            assert link.get("review_only") is True, f"{sid}: link not review_only"
            assert not (set(link) & LINK_KEYS_FORBIDDEN), f"{sid}: link carries resolution keys"


def test_manifest_integrity():
    samples, _ = _load()
    ids = [s["sample_id"] for s in samples]
    assert len(ids) == len(set(ids)), "duplicate sample ids"
    for s in samples:
        sid = s["sample_id"]
        assert _sha(s["excerpt_wikitext"]) == s["excerpt_sha256"], f"{sid}: excerpt hash drifted"
        assert s["evidence_type"] in {"real_excerpt", "synthetic"}
        if s["evidence_type"] == "real_excerpt":
            for key in ("source_url", "page_id", "page_title", "revision_id", "raw_source_sha256", "license_note"):
                assert s.get(key), f"{sid}: real sample missing {key}"
            assert len(s["raw_source_sha256"]) == 64
            assert s["raw_source_sha256_verified"] is True, f"{sid}: raw hash not verified at extraction"
            assert len(s["excerpt_wikitext"]) < 4000, f"{sid}: excerpt too large to be minimal"
        else:
            assert not s.get("source_url") and not s.get("raw_source_sha256"), f"{sid}: synthetic must not claim source evidence"
            assert s.get("modeled_on"), f"{sid}: synthetic sample must say what it models"


def test_template_fields_labels_values_locators_and_classification():
    samples, gaps = _load()
    for s in samples:
        if "fields" not in s or s.get("source_format") == "legacy_text":
            continue
        sid = s["sample_id"]
        blocks, groups = _parse(s)
        tf = [b for b in blocks if b["block_type"] == "template_field"]
        cands = _template_candidates(groups)
        assert len(cands) == len(tf)
        expected = s["fields"]
        if sid in gaps.get("parse_count", {}):
            assert len(tf) == gaps["parse_count"][sid]["observed"], sid
            continue
        assert len(tf) == len(expected), f"{sid}: parsed {len(tf)} fields, expected {len(expected)}"
        for b, exp, (_, cand) in zip(tf, expected, cands):
            md = b["metadata"]
            assert md["field"] == exp["label"], f"{sid}: label not preserved ({md['field']!r} != {exp['label']!r})"
            assert md["raw_value"] == exp["raw_value"], f"{sid}:{exp['label']}: raw value not preserved"
            assert b["source_locator"] == exp["locator"], f"{sid}:{exp['label']}: locator {b['source_locator']!r}"
            want = exp["expected_type"] if exp["raw_value"].strip() else None
            gap = gaps.get("field_type", {}).get(f"{sid}::{exp['label']}")
            got = cand["field_type"] if cand else None
            if gap:
                assert got == gap["observed"], f"{sid}:{exp['label']}: gap pin changed ({got!r} vs {gap['observed']!r})"
                assert got != want, f"{sid}:{exp['label']}: gap fixed - remove it from known_gaps.json"
            else:
                assert got == want, f"{sid}:{exp['label']}: classified {got!r}, expected {want!r}"
            if cand:
                assert cand["field"] == exp["label"] and cand["value_raw"] == exp["raw_value"]
                assert cand["source_locator"] == exp["locator"]
        _assert_no_graph(s, blocks, groups)


def test_japanese_labels_and_values_preserved():
    samples, _ = _load()
    jp = [s for s in samples if "japanese-label" in s["categories"] and s.get("fields")]
    assert jp, "corpus must contain Japanese-label samples"
    for s in jp:
        blocks, _ = _parse(s)
        tf = {b["metadata"]["field"]: b["metadata"]["raw_value"] for b in blocks if b["block_type"] == "template_field"}
        for exp in s["fields"]:
            assert tf[exp["label"]] == exp["raw_value"], f"{s['sample_id']}: {exp['label']}"
    labels = {f["label"] for s in jp for f in s["fields"]}
    assert {"出現条件", "戦利品", "報酬"} <= labels


def test_unsupported_and_near_miss_labels_rejected():
    samples, _ = _load()
    s = next(x for x in samples if x["sample_id"] == "syn-near-miss-labels")
    _, groups = _parse(s)
    got = [c for _, c in _template_candidates(groups)]
    assert got and all(c is None for c in got), "near-miss labels must not be classified"
    # Layout labels (Two Columns) and prose labels never classify either.
    for sid in ("bg-two-columns", "syn-ambiguous-prose"):
        s = next(x for x in samples if x["sample_id"] == sid)
        _, groups = _parse(s)
        for item in (i for g in groups for i in g["content"] if i.get("type") == "definition"):
            if item["term"].endswith(": Notes") or item["term"].endswith(": heading"):
                assert item["field_candidate"] is None, f"{sid}: {item['term']} classified"


def test_ambiguous_links_stay_review_only_and_unresolved():
    samples, _ = _load()
    s = next(x for x in samples if x["sample_id"] == "syn-ambiguous-prose")
    blocks, groups = _parse(s)
    drops = next(c for _, c in _template_candidates(groups) if c and c["field_type"] == "DROPS")
    targets = [l["target"] for l in drops["source_links"]]
    assert targets == ["Ice", "Fire"]
    for link in drops["source_links"]:
        assert link["review_only"] is True and not (set(link) & LINK_KEYS_FORBIDDEN)
        assert link["source_markup"].startswith("[[")
    # Free-prose spawn text may be a typed hint, but it must stay review-only and carry no resolved link state.
    spawn = next(c for _, c in _template_candidates(groups) if c and c["field_type"] == "SPAWN_CONDITIONS")
    assert spawn["review_only"] is True
    _assert_no_graph(s, blocks, groups)


def test_table_candidates_match_policy():
    samples, gaps = _load()
    for s in samples:
        if "table_expect" not in s:
            continue
        sid = s["sample_id"]
        blocks, groups = _parse(s)
        got = [(c["field"], c["value"]) for c in _table_candidates(groups)]
        for c in _table_candidates(groups):
            assert c["review_only"] is True and c["value_source_locator"] and c["field_source_locator"]
            if "field_type" in c:  # present once typed table hints land (PR #1092)
                assert c["field_type"] is not None
        if "table_expect" in s:
            want = [(e["label"], e["value"]) for e in s["table_expect"] if e["candidate"]]
            if sid in gaps.get("table", {}):
                assert got == [tuple(x) for x in gaps["table"][sid]["observed"]], f"{sid}: gap pin changed {got}"
            else:
                # Header-cell rows also yield hints; expectations list every label that must appear.
                for pair in want:
                    assert pair in got, f"{sid}: expected table candidate {pair} missing from {got}"
                rejected = [e["label"] for e in s["table_expect"] if not e["candidate"]]
                assert not [g for g in got if g[0] in rejected], f"{sid}: unsupported row classified"
        _assert_no_graph(s, blocks, groups)


def test_table_cell_attribute_prefix_gap_pinned():
    samples, gaps = _load()
    for s in samples:
        if "header_text_expect" not in s:
            continue
        blocks, _ = _parse(s)
        texts = [b["text"] for b in blocks if b["block_type"] in {"table_header_cell", "table_cell"}][:len(s["header_text_expect"]) + 1]
        pin = gaps["header_text"][s["sample_id"]]["observed"]
        assert texts[:len(pin)] == pin, f"{s['sample_id']}: cell text changed {texts}"
        assert texts[:len(s["header_text_expect"])] != s["header_text_expect"], "gap fixed - remove from known_gaps.json"


def test_real_tables_do_not_invent_candidates():
    samples, _ = _load()
    for s in samples:
        if s.get("excerpt_kind") != "table":
            continue
        _, groups = _parse(s)
        assert _table_candidates(groups) == [], f"{s['sample_id']}: real layout table produced a field candidate"


JP_EXPECTED_HITS = {
    "jp-vw-npc-table": [("エリア", "LOCATION", "南サンドリア"), ("エリア", "LOCATION", "(D-11)")],
    "jp-vw-route-table": [("エリア", "LOCATION", "西サルタバルタ")],
    "jp-bfnm-area-npc-table": [("エリア", "LOCATION", "北サンドリア"), ("エリア", "LOCATION", "バストゥーク港")],
    "jp-bfnm-location-monster-table": [("場所", "LOCATION", "ヨアトル大森林"), ("場所", "LOCATION", "ウガレピ寺院")],
}


def test_real_jp_html_tables_preserve_text_and_invent_nothing():
    """Real WikiWikiJP HTML table excerpts: every cell survives in order, no label/value hints appear."""
    samples, _ = _load()
    jp = [s for s in samples if s["source_wiki"] == "WikiWikiJP" and s["evidence_type"] == "real_excerpt"]
    assert len(jp) >= 3, "corpus must keep real WikiWikiJP excerpts"
    for s in jp:
        sid = s["sample_id"]
        assert s["retrieved_at"], f"{sid}: real JP sample needs retrieved_at"
        blocks, groups = _parse(s)
        if s["excerpt_kind"] == "html_list":
            got = [("li", " ".join(b["text"].split())) for b in blocks if b["block_type"] == "list_item"]
        else:
            got = [(("th" if b["block_type"] == "table_header_cell" else "td"), " ".join(b["text"].split()))
                   for b in blocks if b["block_type"] in {"table_header_cell", "table_cell"}]
        # Pinned behaviour: the parser emits no block for empty cells (e.g. blank spacer th), so compare non-empty cells.
        want = [tuple(c) for c in s["cells"] if c[1]]
        assert got == want, f"{sid}: cell text/order changed: {got} vs {want}"
        assert any(ord(ch) > 0x2E80 for _, t in want for ch in t), f"{sid}: no Japanese text in sample"
        assert _template_candidates(groups) == [], f"{sid}: unexpected template hint"
        cands = _table_candidates(groups)
        # Column-header semantics: a policy label in an all-header row types the cells beneath it
        # (review-only). Header cells never become the value. Rowspan tables are only positionally
        # indexed (known limitation: jp-vw-npc-table's second hit is a shifted column).
        got_hits = [(c["field"], c["field_type"], c["value"]) for c in cands]
        assert got_hits == JP_EXPECTED_HITS.get(sid, []), f"{sid}: column-header hits changed: {got_hits}"
        for c in cands:
            assert c["review_only"] is True and c["orientation"] == "column", f"{sid}: {c}"
            assert c["value"] not in {t for tag, t in want if tag == "th"}, f"{sid}: header used as value"
        _assert_no_graph(s, blocks, groups)


def test_legacy_flattened_text_is_degraded_and_untyped():
    samples, _ = _load()
    s = next(x for x in samples if x["sample_id"] == "syn-legacy-flattened-jp")
    blocks, groups = _parse(s)
    assert blocks and all(b["block_type"] == "legacy_text" and b["metadata"]["degraded"] for b in blocks)
    assert _template_candidates(groups) == [] and _table_candidates(groups) == []
    assert any("出現条件" in b["text"] for b in blocks), "original Japanese text lost"


def test_malformed_sources_do_not_raise():
    samples, _ = _load()
    for s in samples:
        if "malformed" in s["categories"]:
            blocks, groups = _parse(s)
            assert isinstance(blocks, list) and isinstance(groups, list)


def test_embedded_heading_quirk_pinned():
    samples, _ = _load()
    s = next(x for x in samples if x["sample_id"] == "syn-embedded-heading")
    blocks, _ = _parse(s)
    labels = [b["metadata"]["field"] for b in blocks if b["block_type"] == "template_field"]
    assert labels == ["Class", "Notes", "Location"]
    headings = [b["text"] for b in blocks if b["block_type"] == "heading"]
    assert headings == ["Getting There"], "heading-inside-template behaviour changed; update the audit"


def coverage_report():
    samples, _ = _load()
    rows = collections.OrderedDict()
    for s in samples:
        key = (s["source_wiki"], s["evidence_type"])
        r = rows.setdefault(key, collections.Counter())
        r["samples"] += 1
        blocks, groups = _parse(s)
        tf = [b for b in blocks if b["block_type"] == "template_field"]
        cands = _template_candidates(groups)
        r["template_fields"] += len(tf)
        r["typed"] += sum(1 for _, c in cands if c)
        r["table_candidates"] += len(_table_candidates(groups))
        r["japanese_labels"] += sum(1 for b in tf if any(ord(ch) > 0x2E80 for ch in b["metadata"]["field"]))
        r["japanese_values"] += sum(1 for b in tf if any(ord(ch) > 0x2E80 for ch in b["metadata"]["raw_value"]))
        r["legacy_blocks"] += sum(1 for b in blocks if b["block_type"] == "legacy_text")
    lines = ["wiki corpus coverage (source / evidence):"]
    for (src, ev), r in rows.items():
        lines.append(f"  {src:13s} {ev:12s} samples={r['samples']:2d} template_fields={r['template_fields']:3d} "
                     f"typed={r['typed']:2d} table_candidates={r['table_candidates']:2d} "
                     f"jp_labels={r['japanese_labels']:2d} jp_values={r['japanese_values']:2d} legacy_blocks={r['legacy_blocks']:2d}")
    return "\n".join(lines)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(coverage_report())
    print(f"OK ({len(tests)} wiki corpus checks)")


if __name__ == "__main__":
    main()
