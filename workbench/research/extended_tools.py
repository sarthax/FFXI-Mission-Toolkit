"""Typed read-only capture, reference, and client/DAT research tools."""
from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path
from typing import Any

import capture_backtrace
import item_dat_tools
import scrape_bg_wiki


class CaptureResearchReader:
    def __init__(self, capture_db: Path, graph_db: Path | None = None):
        self.capture_db=Path(capture_db)
        self.graph_db=Path(graph_db) if graph_db else None

    def _connect(self):
        con=sqlite3.connect(f"file:{self.capture_db}?mode=ro",uri=True)
        con.row_factory=sqlite3.Row
        return con

    def search(
        self,
        query: str = "",
        *,
        zone: str | None = None,
        mission: str | None = None,
        limit: int = 50,
    ) -> dict[str,Any]:
        con=self._connect()
        try:
            where=["1=1"]
            params=[]
            if query:
                where.append("(COALESCE(capture_label,'') LIKE ? OR COALESCE(capturer,'') LIKE ? OR COALESCE(source_path,'') LIKE ?)")
                term=f"%{query}%"; params.extend([term,term,term])
            if zone:
                where.append("COALESCE(zones,'') LIKE ?"); params.append(f"%{zone}%")
            if mission:
                where.append("COALESCE(mission_name,'') LIKE ?"); params.append(f"%{mission}%")
            rows=con.execute(
                "SELECT capture_id,source_path,capturer,capture_label,content_type,zones,mission_name,"
                "addons,client_build,is_retail,start_time,ingested_at FROM captures "
                f"WHERE {' AND '.join(where)} ORDER BY capture_id DESC LIMIT ?",
                (*params,limit),
            ).fetchall()
            return {
                "status":"OK",
                "authority":"CAPTURE_RUNTIME_OBSERVATION",
                "matches":[dict(row) for row in rows],
                "truncated":len(rows)>=limit,
                "notes":["Capture presence is runtime observation, not proof of server/client implementation."],
            }
        finally:
            con.close()

    def backtrace(self, capture_id: int) -> dict[str,Any]:
        try:
            result=capture_backtrace.backtrace(self.capture_db,capture_id,self.graph_db)
        except SystemExit as exc:
            return {"status":"ERROR","error":str(exc)}
        result["status"]="OK"
        result["authority"]="CAPTURE_RUNTIME_OBSERVATION"
        evidence_ids=set()
        for check in result.get("checks",[]):
            for rel in check.get("graph_relationships",[]) or []:
                if rel.get("evidence_id"):
                    evidence_ids.add(rel["evidence_id"])
            for rel in check.get("implementation_path",[]) or []:
                if rel.get("evidence_id"):
                    evidence_ids.add(rel["evidence_id"])
        result["evidence_ids"]=sorted(evidence_ids)
        return result


class ReferenceResearchReader:
    def __init__(self, dump_path: Path | None = None):
        self.dump_path=Path(dump_path) if dump_path else Path(scrape_bg_wiki.DUMP_PATH)

    def _rows(self):
        if not self.dump_path.exists():
            return []
        rows=[]
        with gzip.open(self.dump_path,"rt",encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 20,
        include_wikitext: bool = False,
    ) -> dict[str,Any]:
        if not query:
            return {"status":"ERROR","error":"query is required"}
        needle=query.lower()
        matches=[]
        for row in self._rows():
            cats=row.get("categories") or []
            if category and not any(category.lower() in str(cat).lower() for cat in cats):
                continue
            title=str(row.get("title") or "")
            text=str(row.get("wikitext") or "")
            if needle not in title.lower() and needle not in text.lower():
                continue
            item={
                "title":title,
                "pageid":row.get("pageid"),
                "revid":row.get("revid"),
                "timestamp":row.get("timestamp"),
                "url":row.get("url"),
                "categories":cats,
                "authority":"REFERENCE",
                "confidence":"INFERRED",
            }
            if include_wikitext:
                item["wikitext"]=text[:12000]
                item["truncated"]=len(text)>12000
            matches.append(item)
            if len(matches)>=limit:
                break
        return {
            "status":"OK",
            "query":query,
            "matches":matches,
            "truncated":len(matches)>=limit,
            "notes":["Reference/wiki evidence must not be promoted to server/client truth without independent verification."],
        }

    def compare(self, titles: list[str]) -> dict[str,Any]:
        wanted={str(title).lower():str(title) for title in titles}
        found={}
        for row in self._rows():
            key=str(row.get("title") or "").lower()
            if key in wanted:
                found[wanted[key]]={
                    "title":row.get("title"),
                    "pageid":row.get("pageid"),
                    "revid":row.get("revid"),
                    "timestamp":row.get("timestamp"),
                    "url":row.get("url"),
                    "categories":row.get("categories") or [],
                    "authority":"REFERENCE",
                    "confidence":"INFERRED",
                }
        return {
            "status":"OK",
            "requested":titles,
            "found":[found[t] for t in titles if t in found],
            "missing":[t for t in titles if t not in found],
            "notes":["Missing reference pages do not prove missing game/server/client functionality."],
        }


class ClientResearchReader:
    def __init__(self, graph_db: Path | None = None):
        self.graph_db=Path(graph_db) if graph_db else None

    def capability(
        self,
        name: str,
        *,
        subject_id: str | None = None,
        limit: int = 50,
    ) -> dict[str,Any]:
        if self.graph_db is None or not self.graph_db.exists():
            return {"status":"ERROR","error":"canonical graph DB is not configured"}
        con=sqlite3.connect(f"file:{self.graph_db}?mode=ro",uri=True)
        con.row_factory=sqlite3.Row
        try:
            where=["(name LIKE ? OR capability_id LIKE ?)"]
            params=[f"%{name}%",f"%{name}%"]
            if subject_id:
                where.append("subject_id=?"); params.append(subject_id)
            rows=con.execute(
                "SELECT capability_id,name,capability_type,subject_id,source_snapshot_id,status,"
                "value_json,evidence_id,notes_json FROM capabilities "
                f"WHERE {' AND '.join(where)} ORDER BY capability_id LIMIT ?",
                (*params,limit),
            ).fetchall()
            matches=[]
            evidence_ids=set()
            for row in rows:
                item=dict(row)
                item["value"]=json.loads(item.pop("value_json")) if item["value_json"] else None
                item["notes"]=json.loads(item.pop("notes_json") or "[]")
                item["authority"]="CLIENT_CAPABILITY_EVIDENCE"
                if item.get("evidence_id"):
                    evidence_ids.add(item["evidence_id"])
                observations=[]
                for obs in con.execute(
                    "SELECT observation_id,source_snapshot_id,status,value_json,evidence_id,notes_json "
                    "FROM capability_observations WHERE capability_id=? ORDER BY source_snapshot_id,observation_id",
                    (item["capability_id"],),
                ).fetchall():
                    rec=dict(obs)
                    rec["value"]=json.loads(rec.pop("value_json")) if rec["value_json"] else None
                    rec["notes"]=json.loads(rec.pop("notes_json") or "[]")
                    if rec.get("evidence_id"):
                        evidence_ids.add(rec["evidence_id"])
                    observations.append(rec)
                item["observations"]=observations
                matches.append(item)
            return {
                "status":"OK",
                "query":name,
                "matches":matches,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(matches)>=limit,
            }
        finally:
            con.close()

    def dat_lookup(self, item_id: int) -> dict[str,Any]:
        try:
            record=item_dat_tools.read_client_item(int(item_id))
        except Exception as exc:
            return {"status":"ERROR","error":f"{type(exc).__name__}: {exc}"}
        if record is None:
            return {
                "status":"NOT_FOUND",
                "item_id":int(item_id),
                "authority":"CLIENT_DAT",
                "notes":["No readable client item record was found; this does not prove the item is absent from every client DAT/build."],
            }
        item=item_dat_tools.item_to_dict(record)
        item["authority"]="CLIENT_DAT"
        item["dat_layout"]=item_dat_tools.describe(
            item_dat_tools.detect_stride_path(Path(record.dat))
        ) if record.dat else record.format
        return {
            "status":"OK",
            "item_id":int(item_id),
            "item":item,
            "source_path":record.dat,
            "dat_ui":record.dat_ui,
            "format":record.format,
            "record_index":record.record_index,
            "authority":"CLIENT_DAT",
            "notes":["Client DAT evidence is independent of server SQL and should be compared, not conflated."],
        }
