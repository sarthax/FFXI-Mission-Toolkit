"""Read-only, zone-scoped client / DSP / LSB entity discrepancy report.

Consumes existing ffxi_zone_database.db indexes. Missing or empty source coverage
is UNKNOWN rather than proof of a missing game entity.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

SOURCES = ("dsp", "lsb")
KINDS = ("missing_client", "missing_server", "wrong_table", "name_mismatch",
         "server_name_disagreement", "position_disagreement", "model_disagreement", "zero_position",
         "client_index_unavailable", "server_index_unavailable")


def _exists(con, table):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _normal(name):
    return "".join(c for c in (name or "").casefold() if c.isalnum())


def _rows(con, sql, params=()):
    return [dict(r) for r in con.execute(sql, params)]


def build_report(db: Path, zone: int, *, sources=SOURCES, kind=None):
    """Return source-attributed mismatches; never assume empty index means absence."""
    if kind and kind not in KINDS:
        raise ValueError("Unknown mismatch type")
    if zone < 0 or zone > 65535:
        raise ValueError("Invalid zone")
    con = sqlite3.connect(f"file:{Path(db).resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        client = {}
        if _exists(con, "npc_names"):
            client = {r["npcid"]: r for r in _rows(con,
                "SELECT npcid,name,zoneid FROM npc_names WHERE zoneid=?", (zone,))}
        found = {}
        coverage = {"client": "indexed" if client else "unavailable_or_empty"}
        for source in sources:
            if source not in SOURCES:
                raise ValueError("Unknown source")
            npc_table, mob_table = source + "_npc_list", source + "_mob_spawn_points"
            if not _exists(con, npc_table) or not _exists(con, mob_table):
                found[source] = {}
                coverage[source] = "unavailable"
                continue
            npc = _rows(con, f"SELECT npcid AS id,name,pos_x,pos_y,pos_z FROM {npc_table} WHERE zoneid=?", (zone,))
            # FFXI runtime IDs are zoned; mob_spawn_points indexes may not store zoneid.
            mob = _rows(con, f"SELECT mobid AS id,mobname AS name,pos_x,pos_y,pos_z FROM {mob_table} WHERE (mobid >> 12) & 4095 = ?", (zone,))
            # Model provenance: spawn.groupid -> same-zone group.poolid -> pool.modelid.
            # A missing or ambiguous join remains unknown, not a discrepancy.
            group_table, pool_table = source + "_mob_groups", source + "_mob_pools"
            models = {}
            if _exists(con, group_table) and _exists(con, pool_table):
                for row in _rows(con, f"""
                    SELECT s.mobid AS id, p.modelid AS model
                    FROM {mob_table} s
                    JOIN {group_table} g ON s.groupid=g.groupid AND g.zoneid=?
                    JOIN {pool_table} p ON g.poolid=p.poolid
                    WHERE ((s.mobid >> 12) & 4095)=?
                """, (zone, zone)):
                    if row["id"] in models and models[row["id"]] != row["model"]:
                        models[row["id"]] = None
                    else:
                        models[row["id"]] = row["model"]
            for row in mob:
                row["model"] = models.get(row["id"])
            found[source] = {
                "npc": {r["id"]: r for r in npc},
                "mob": {r["id"]: r for r in mob},
            }
            coverage[source] = "indexed" if npc or mob else "unavailable_or_empty"
        issues = []
        def add(source, typ, entity_id, *, client_name="", server_name="", table="", detail="", confidence="review"):
            if kind and kind != typ:
                return
            issues.append(dict(zone=zone, source=source, type=typ, entity_id=entity_id,
                client_name=client_name, server_name=server_name, table=table,
                detail=detail, confidence=confidence))
        ids = set(client)
        for source, tables in found.items():
            if not tables:
                add(source, "server_index_unavailable", None, detail="NPC/mob index missing")
                continue
            present = set(tables["npc"]) | set(tables["mob"])
            if coverage[source] != "indexed":
                add(source, "server_index_unavailable", None, detail="No indexed server records for zone")
                continue
            if coverage["client"] != "indexed":
                add(source, "client_index_unavailable", None, detail="Client NPC/MobList index absent or empty")
            for entity_id in sorted(present | ids):
                memberships = [table for table in ("npc", "mob") if entity_id in tables[table]]
                server_row = tables[memberships[0]][entity_id] if memberships else None
                client_row = client.get(entity_id)
                c_name = client_row["name"] if client_row else ""
                s_name = server_row["name"] if server_row else ""
                if server_row and not client_row and coverage["client"] == "indexed":
                    add(source, "missing_client", entity_id, server_name=s_name,
                        table="/".join(memberships), detail="Present in server index; absent in client name index")
                if client_row and not server_row and coverage[source] == "indexed":
                    add(source, "missing_server", entity_id, client_name=c_name,
                        detail="Present in client index; absent in both server NPC and mob tables")
                if not server_row:
                    continue
                if len(memberships) > 1:
                    add(source, "wrong_table", entity_id, client_name=c_name,
                        server_name=s_name, table="npc/mob",
                        detail="ID occurs in both server tables; review classification")
                if client_row and _normal(c_name) != _normal(s_name):
                    add(source, "name_mismatch", entity_id, client_name=c_name,
                        server_name=s_name, table="/".join(memberships),
                        detail="Normalized client (POLUtils) and server names differ")
                coords = tuple(server_row[f"pos_{axis}"] for axis in "xyz")
                if all(c is not None and abs(float(c)) < 0.00001 for c in coords):
                    add(source, "zero_position", entity_id, client_name=c_name,
                        server_name=s_name, table="/".join(memberships),
                        detail="Server XYZ all zero; may be moved by Lua")
        if all(coverage.get(s) == "indexed" for s in ("dsp", "lsb")):
            for entity_id in sorted((set(found["dsp"]["npc"]) | set(found["dsp"]["mob"])) &
                                    (set(found["lsb"]["npc"]) | set(found["lsb"]["mob"]))):
                for source in ("dsp", "lsb"):
                    # Exact ID may occupy different table types in the two server versions.
                    other = "lsb" if source == "dsp" else "dsp"
                    tables = found[source]
                    table = "npc" if entity_id in tables["npc"] else "mob"
                    other_table = "npc" if entity_id in found[other]["npc"] else "mob"
                    if table != other_table and source == "dsp":
                        add("dsp/lsb", "wrong_table", entity_id,
                            table=f"DSP:{table} / LSB:{other_table}",
                            detail="DSP and LSB classify the same ID differently")
                d = found["dsp"]["npc"].get(entity_id) or found["dsp"]["mob"].get(entity_id)
                l = found["lsb"]["npc"].get(entity_id) or found["lsb"]["mob"].get(entity_id)
                # Do not equate an NPC with a mob or compare unresolved model IDs.
                if (entity_id in found["dsp"]["mob"] and entity_id in found["lsb"]["mob"]
                        and d.get("model") not in (None, "") and l.get("model") not in (None, "")
                        and str(d["model"]) != str(l["model"])):
                    add("dsp/lsb", "model_disagreement", entity_id,
                        detail=f"DSP mob pool model {d['model']} vs LSB mob pool model {l['model']}")
                if _normal(d["name"]) != _normal(l["name"]):
                    add("dsp/lsb", "server_name_disagreement", entity_id,
                        client_name=d["name"], server_name=l["name"],
                        detail="DSP name vs LSB name (client comparison separate)")
                if all(d[f"pos_{a}"] is not None and l[f"pos_{a}"] is not None for a in "xyz"):
                    delta = sum((float(d[f"pos_{a}"]) - float(l[f"pos_{a}"])) ** 2 for a in "xyz") ** .5
                    if delta > 1.0:
                        add("dsp/lsb", "position_disagreement", entity_id,
                            client_name=d["name"], server_name=l["name"],
                            detail=f"DSP vs LSB XYZ differ by {delta:.2f} world units")
        # Attach the exact side-by-side source records, not just a textual diagnosis.
        # Absent source values remain None (never displayed as an invented zero).
        for issue in issues:
            entity_id = issue["entity_id"]
            if entity_id is None:
                issue["values"] = {"client": None, "dsp": None, "lsb": None}
                continue
            def snapshot(source):
                tables = found.get(source) or {}
                if not tables:
                    return None
                matches = [(table, tables[table][entity_id])
                           for table in ("npc", "mob") if entity_id in tables[table]]
                if not matches:
                    return None
                table, row = matches[0]
                return {"table": "/".join(t for t, _ in matches),
                        "name": row["name"], "model": row.get("model"), "position": [
                            row["pos_x"], row["pos_y"], row["pos_z"]]}
            issue["values"] = {
                "client": {"name": client[entity_id]["name"], "table": "client MobList"}
                          if entity_id in client else None,
                "dsp": snapshot("dsp"),
                "lsb": snapshot("lsb"),
            }
        # Precisely flag the affected fields. Comparisons are scoped to the
        # source pairs that actually produced the finding.
        for issue in issues:
            typ, source = issue["type"], issue["source"]
            fields = {"client": [], "dsp": [], "lsb": []}
            if typ == "name_mismatch":
                fields["client"].append("name")
                fields[source].append("name")
            elif typ == "server_name_disagreement":
                fields["dsp"].append("name")
                fields["lsb"].append("name")
            elif typ == "model_disagreement":
                fields["dsp"].append("model")
                fields["lsb"].append("model")
            elif typ == "position_disagreement":
                d, l = issue["values"]["dsp"], issue["values"]["lsb"]
                if d and l:
                    for i, axis in enumerate("xyz"):
                        if d["position"][i] is not None and l["position"][i] is not None and abs(float(d["position"][i]) - float(l["position"][i])) > 0.00001:
                            fields["dsp"].append("pos_" + axis)
                            fields["lsb"].append("pos_" + axis)
            elif typ == "zero_position" and source in fields:
                fields[source].extend(("pos_x", "pos_y", "pos_z"))
            elif typ == "wrong_table":
                for name in (("dsp", "lsb") if source == "dsp/lsb" else (source,)):
                    fields[name].append("table")
            elif typ == "missing_client":
                fields["client"].append("presence")
            elif typ == "missing_server" and source in fields:
                fields[source].append("presence")
            issue["field_flags"] = fields
        issues.sort(key=lambda x: (x["type"], x["source"], x["entity_id"] if x["entity_id"] is not None else -1))
        return {"zone": zone, "coverage": coverage, "counts": dict(Counter(r["type"] for r in issues)),
                "rows": issues, "limitations": [
                    "No client positions or models are present in npc_names; do not infer client model or position mismatches.",
                    "Mob models are compared only when both group/pool joins resolve; NPC model comparisons are not yet supported.",
                    "Wrong-table inference only flags duplicate IDs or DSP/LSB classification disagreement.",
                    "Absent records are only reported when both corresponding indexes contain zone data.",
                    "This is a review report: runtime spawns, instance entities and intentional Lua moves can explain gaps.",
                ]}
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only zone NPC/mob discrepancy report")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--zone", type=int, required=True)
    parser.add_argument("--type", choices=KINDS)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(args.db, args.zone, kind=args.type)
    if args.format == "json":
        data = json.dumps(report, indent=2, ensure_ascii=False)
    else:
        import io
        stream = io.StringIO()
        fields = ("zone","source","type","entity_id","client_name","server_name","table","detail","confidence")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report["rows"])
        data = stream.getvalue()
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data)


if __name__ == "__main__":
    main()
