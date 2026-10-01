"""Compare two cpp_api_index JSON files; optionally persist canonical findings."""
import argparse
import json
from pathlib import Path

from workbench.analyzers.server.binding_compatibility import compare_bindings
from workbench.core.graph import init_db, insert_record
from workbench.core.services.capability_producers import persist_binding_compatibility_capabilities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--graph-db", type=Path)
    args = parser.parse_args()
    try:
        result = compare_bindings(json.loads(args.source.read_text(encoding="utf-8")),
                                  json.loads(args.target.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.graph_db:
        con = init_db(args.graph_db)
        try:
            with con:
                insert_record(con, result["analysis"], "AnalysisResult")
                for finding in result["findings"]:
                    insert_record(con, finding, "Finding")
                persist_binding_compatibility_capabilities(con, result)
        finally:
            con.close()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
