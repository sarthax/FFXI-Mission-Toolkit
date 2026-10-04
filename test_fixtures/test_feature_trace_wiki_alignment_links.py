import sqlite3

from workbench.devtools.features.trace_catalog import provider_relationships


def _db(*, duplicate_bg_claim: bool = False) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE reference_wiki_claims (claim_id TEXT, subject_text TEXT)")
    con.execute("CREATE TABLE reference_wiki_page_alignments (alignment_id TEXT, norm_title TEXT)")
    con.execute(
        "CREATE TABLE reference_wiki_claim_alignments ("
        "pair_id TEXT, status TEXT, alignment_id TEXT, bg_claim_id TEXT, ffxiclopedia_claim_id TEXT)"
    )
    con.execute(
        "INSERT INTO reference_wiki_page_alignments VALUES (?, ?)",
        ("align-1", "cait sith"),
    )
    con.execute(
        "INSERT INTO reference_wiki_claims VALUES (?, ?)",
        ("bg-claim-1", "BG claim"),
    )
    if duplicate_bg_claim:
        con.execute(
            "INSERT INTO reference_wiki_claims VALUES (?, ?)",
            ("bg-claim-1", "Ambiguous duplicate BG claim"),
        )
    con.execute(
        "INSERT INTO reference_wiki_claims VALUES (?, ?)",
        ("ffxi-claim-1", "FFXIclopedia claim"),
    )
    con.execute(
        "INSERT INTO reference_wiki_claim_alignments VALUES (?, ?, ?, ?, ?)",
        ("pair-1", "ALIGNED", "align-1", "bg-claim-1", "ffxi-claim-1"),
    )
    return con


def test_claim_alignment_exposes_exact_provider_native_links():
    con = _db()
    links = provider_relationships(con, "catalog:reference_wiki_claim_alignments:pair-1")
    by_rel = {row["relationship"]: row for row in links}

    assert by_rel["IN_REFERENCE_PAGE_ALIGNMENT"]["target_node"] == "catalog:reference_wiki_page_alignments:align-1"
    assert by_rel["ALIGNS_BG_REFERENCE_CLAIM"]["target_node"] == "catalog:reference_wiki_claims:bg-claim-1"
    assert by_rel["ALIGNS_FFXICLOPEDIA_REFERENCE_CLAIM"]["target_node"] == "catalog:reference_wiki_claims:ffxi-claim-1"
    assert all(row["provider_native"] is True for row in links)


def test_claim_alignment_does_not_guess_ambiguous_claim_identity():
    con = _db(duplicate_bg_claim=True)
    links = provider_relationships(con, "catalog:reference_wiki_claim_alignments:pair-1")
    relationships = {row["relationship"] for row in links}

    assert "IN_REFERENCE_PAGE_ALIGNMENT" in relationships
    assert "ALIGNS_FFXICLOPEDIA_REFERENCE_CLAIM" in relationships
    assert "ALIGNS_BG_REFERENCE_CLAIM" not in relationships
