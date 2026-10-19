"""Before/after reparse validation of Wiki V2 over a WORKING COPY of the Wiki database.

Never point this at the production database. Use --apply only on a copy.
Reuses wiki_document.build_blocks / store_document (no second import system); no network.

  py -3.11 scripts/wiki_full_corpus_validate.py --db WORKING.db --out report.json            # measure only
  py -3.11 scripts/wiki_full_corpus_validate.py --db WORKING.db --out report.json --apply    # reparse + store
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workbench.devtools.reference import wiki_document as wd  # noqa: E402

EXAMPLE_CAP = 12


def measure(blocks):
    m = collections.Counter()
    typed_labels = collections.Counter()
    unrec = collections.Counter()
    groups = wd.presentation_groups(blocks)
    for b in blocks:
        m["blocks"] += 1
        bt = b["block_type"]
        m["bt:" + bt] += 1
        if bt == "template_field":
            m["template_fields"] += 1
            field = str((b.get("metadata") or {}).get("field") or "")
            ft = wd.review_field_type(field)
            if ft:
                m["typed_fields"] += 1
                typed_labels[ft] += 1
                if not (b.get("text") or "").strip():
                    m["typed_empty"] += 1
            else:
                unrec[field] += 1
        elif bt in {"table_cell", "table_header_cell"}:
            m["table_cells"] += 1
        if (b.get("metadata") or {}).get("cell_attributes"):
            m["cells_with_attrs"] += 1
    tcand = collections.Counter()
    tcand_rows = []
    for g in groups:
        for item in g["content"]:
            if item.get("type") == "table":
                for c in item["field_candidates"]:
                    m["table_candidates"] += 1
                    tcand[c.get("field_type") or "UNTYPED"] += 1
                    tcand_rows.append(c)
            elif item.get("type") == "definition" and item.get("field_candidate"):
                m["template_candidates"] += 1
    return m, typed_labels, unrec, tcand, tcand_rows


def locator_set(blocks):
    return {(b["block_type"], b.get("source_locator")) for b in blocks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--source", default=None)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if "ffxi_zone_database.db" in Path(a.db).name and a.apply:
        raise SystemExit("refusing --apply on the production database name; use a working copy")
    con = sqlite3.connect(a.db, timeout=60)
    con.execute("PRAGMA busy_timeout=60000")
    wd.init_db(con)
    q = ("SELECT source_id,page_id,source_format,raw_source,raw_hash,parser_version,retrieved_at,source_revision "
         "FROM reference_wiki_documents WHERE raw_source IS NOT NULL AND trim(raw_source)!='' "
         "AND source_format IN ('mediawiki','html')")
    args = []
    if a.source:
        q += " AND source_id=?"
        args.append(a.source)
    keys = [r[:2] for r in con.execute("SELECT source_id,page_id FROM reference_wiki_documents WHERE raw_source IS NOT NULL "
                                        "AND trim(raw_source)!='' AND source_format IN ('mediawiki','html')"
                                        + (" AND source_id=?" if a.source else "") + " ORDER BY source_id,page_id", args)]
    if a.limit:
        keys = keys[:a.limit]
    R = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "parser_version": wd.PARSER_VERSION,
         "apply": a.apply, "sources": {}, "failures": [], "examples": collections.defaultdict(list)}
    t0 = time.time()
    for n, (sid, pid) in enumerate(keys, 1):
        S = R["sources"].setdefault(sid, {"docs": 0, "before": collections.Counter(), "after": collections.Counter(),
                                          "typed_before": collections.Counter(), "typed_after": collections.Counter(),
                                          "tcand_before": collections.Counter(), "tcand_after": collections.Counter(),
                                          "unrec_after": collections.Counter(), "locator_changed_pages": 0,
                                          "pages_changed": 0, "parser_versions_before": collections.Counter()})
        try:
            row = con.execute("SELECT source_format,raw_source,raw_hash,parser_version,retrieved_at,source_revision "
                              "FROM reference_wiki_documents WHERE source_id=? AND page_id=?", (sid, pid)).fetchone()
            fmt, raw, rhash, pver, rat, rrev = row
            old = wd.stored_blocks(con, sid, pid)
            _, _, new = wd.build_blocks({"page_id": pid}, source_format=fmt, raw_source=raw)
            mo, to, _, co, _ = measure(old)
            mn, tn, un, cn, rows_new = measure(new)
            S["docs"] += 1
            S["parser_versions_before"][pver] += 1
            S["before"].update(mo); S["after"].update(mn)
            S["typed_before"].update(to); S["typed_after"].update(tn)
            S["tcand_before"].update(co); S["tcand_after"].update(cn)
            S["unrec_after"].update(un)
            if mn != mo:
                S["pages_changed"] += 1
            lo, ln = locator_set(old), locator_set(new)
            if lo and not (lo <= ln):
                S["locator_changed_pages"] += 1
                if len(R["examples"]["locator_changed:" + sid]) < EXAMPLE_CAP:
                    R["examples"]["locator_changed:" + sid].append(
                        {"page": pid, "lost": sorted(map(str, lo - ln))[:3], "gained": sorted(map(str, ln - lo))[:3]})
            if mn["typed_empty"] < mo["typed_empty"] and len(R["examples"]["empty_recovered:" + sid]) < EXAMPLE_CAP:
                R["examples"]["empty_recovered:" + sid].append({"page": pid, "before": mo["typed_empty"], "after": mn["typed_empty"]})
            if mn["table_candidates"] != mo["table_candidates"] and len(R["examples"]["tcand_changed:" + sid]) < EXAMPLE_CAP:
                R["examples"]["tcand_changed:" + sid].append(
                    {"page": pid, "before": mo["table_candidates"], "after": mn["table_candidates"],
                     "sample": [{k: c.get(k) for k in ("field", "field_type", "value", "orientation")} for c in rows_new[:3]]})
            if a.apply:
                wd.store_document(con, source_id=sid, page_id=pid, source_format=fmt, raw_source=raw, blocks=new,
                                  retrieved_at=rat, source_revision=rrev)
        except Exception as exc:  # logged, retryable
            R["failures"].append({"source": sid, "page": pid, "error": f"{type(exc).__name__}: {exc}"[:300]})
        if n % 2000 == 0:
            print(f"{n}/{len(keys)} {time.time()-t0:.0f}s fail={len(R['failures'])}", flush=True)
    R["elapsed_s"] = round(time.time() - t0, 1)
    for S in R["sources"].values():
        S["unrec_after"] = dict(S["unrec_after"].most_common(40))
        for k in list(S):
            if isinstance(S[k], collections.Counter):
                S[k] = dict(S[k])
    R["examples"] = dict(R["examples"])
    Path(a.out).write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print("done", R["elapsed_s"], "s; failures", len(R["failures"]))


if __name__ == "__main__":
    main()
