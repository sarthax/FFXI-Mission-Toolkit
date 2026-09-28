"""Conservative cross-source packet correlation for capture evidence.

Correlations never merge or replace observations. They record bounded pairwise candidate identity
between independently-ingested runtime sources while preserving ambiguity.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from workbench.core.services import timeline_alignment as ta
from workbench.core.services.packet_identity import canonical_opcode

RAW = "RAW_PACKET"
EVENTVIEW = "EVENTVIEW_DECODE"
IDVIEW = "IDVIEW_EVENT"
VIDEO = "VIDEO_OCR"

STATUS_MATCHED = "MATCHED"
STATUS_AMBIGUOUS = "AMBIGUOUS"


def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS capture_packet_correlations (
            capture_id INTEGER NOT NULL,
            correlation_id TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_ref TEXT NOT NULL,
            target_kind TEXT NOT NULL,
            target_ref TEXT NOT NULL,
            opcode TEXT,
            direction TEXT,
            time_delta_seconds REAL,
            basis TEXT NOT NULL,
            status TEXT NOT NULL,
            score REAL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(capture_id,correlation_id)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_packet_corr_source
            ON capture_packet_correlations(capture_id,source_kind,source_ref);
        CREATE INDEX IF NOT EXISTS idx_capture_packet_corr_target
            ON capture_packet_correlations(capture_id,target_kind,target_ref);
        CREATE INDEX IF NOT EXISTS idx_capture_packet_corr_opcode
            ON capture_packet_correlations(capture_id,opcode,status);
    """)
    con.commit()


def _table_exists(con, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _opcode(value) -> str | None:
    return canonical_opcode(value)


def _direction(value) -> str:
    raw=str(value or "").strip().lower()
    if raw in {"incoming","in","s2c","<<","<","incoming <"}:
        return "incoming"
    if raw in {"outgoing","out","c2s",">>",">","outgoing >"}:
        return "outgoing"
    return raw or "unknown"


def _absolute_ts(value) -> float | None:
    if value is None:
        return None
    raw=str(value).strip()
    if not raw:
        return None
    normalized=raw.replace("T"," ").rstrip("Z")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f","%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(normalized,fmt).timestamp()
        except ValueError:
            pass
    return None


def _rows(con: sqlite3.Connection, capture_id: int) -> dict[str,list[dict]]:
    con.row_factory=sqlite3.Row
    out={RAW:[],EVENTVIEW:[],IDVIEW:[],VIDEO:[]}
    if _table_exists(con,"capture_raw_packets"):
        for row in con.execute(
            """SELECT seq,ts,direction,opcode,raw_hex FROM capture_raw_packets
               WHERE capture_id=? ORDER BY seq""",(capture_id,)
        ):
            item=dict(row)
            item.update({
                "kind":RAW,
                "ref":f"raw-packet:{row['seq']}",
                "opcode_norm":_opcode(row["opcode"]),
                "direction_norm":_direction(row["direction"]),
                "absolute_ts":_absolute_ts(row["ts"]),
            })
            out[RAW].append(item)
    if _table_exists(con,"capture_eventview"):
        for row in con.execute(
            """SELECT zone_db,seq,ts,direction,opcode,packet_class,gp_command,
                      entity_id,mes_num,message_number,fields_json
               FROM capture_eventview WHERE capture_id=? ORDER BY zone_db,seq""",(capture_id,)
        ):
            item=dict(row)
            try:
                item["fields"]=json.loads(item.pop("fields_json") or "{}")
            except json.JSONDecodeError:
                item["fields"]={}
            item.update({
                "kind":EVENTVIEW,
                "ref":f"eventview:{row['zone_db']}:{row['seq']}",
                "opcode_norm":_opcode(row["opcode"]),
                "direction_norm":_direction(row["direction"]),
                "absolute_ts":_absolute_ts(row["ts"]),
            })
            out[EVENTVIEW].append(item)
    if _table_exists(con,"capture_events"):
        for row in con.execute(
            """SELECT zone_db,seq,direction,opcode,opcode_name,entity_id,entity_name,
                      event_hex,option,message_id,params_raw
               FROM capture_events WHERE capture_id=? ORDER BY zone_db,seq""",(capture_id,)
        ):
            item=dict(row)
            item.update({
                "kind":IDVIEW,
                "ref":f"idview:{row['zone_db']}:{row['seq']}",
                "opcode_norm":_opcode(row["opcode"]),
                "direction_norm":_direction(row["direction"]),
            })
            out[IDVIEW].append(item)
    if _table_exists(con,"capture_video_observations"):
        for row in con.execute(
            """SELECT observation_id,video_ts,direction,opcode,gp_command,packet_class,
                      fields_json,ocr_confidence,provenance_json
               FROM capture_video_observations WHERE capture_id=? AND opcode IS NOT NULL
               ORDER BY video_ts,observation_id""",(capture_id,)
        ):
            item=dict(row)
            try:
                item["fields"]=json.loads(item.pop("fields_json") or "{}")
            except json.JSONDecodeError:
                item["fields"]={}
            item.update({
                "kind":VIDEO,
                "ref":f"video-ocr:{row['observation_id']}",
                "opcode_norm":_opcode(row["opcode"]),
                "direction_norm":_direction(row["direction"]),
            })
            out[VIDEO].append(item)
    return out


def _pair_id(a_kind,a_ref,b_kind,b_ref):
    return f"packet-corr:{a_kind}:{a_ref}->{b_kind}:{b_ref}"


def _insert(con,capture_id,a,b,*,basis,status,delta=None,score=None,details=None):
    cid=_pair_id(a["kind"],a["ref"],b["kind"],b["ref"])
    con.execute(
        """INSERT OR REPLACE INTO capture_packet_correlations
           (capture_id,correlation_id,source_kind,source_ref,target_kind,target_ref,
            opcode,direction,time_delta_seconds,basis,status,score,details_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            capture_id,cid,a["kind"],a["ref"],b["kind"],b["ref"],
            a.get("opcode_norm") or b.get("opcode_norm"),
            a.get("direction_norm") if a.get("direction_norm")==b.get("direction_norm") else None,
            delta,basis,status,score,json.dumps(details or {},sort_keys=True),
        ),
    )


def _same_packet_dims(a,b):
    if not a.get("opcode_norm") or a.get("opcode_norm")!=b.get("opcode_norm"):
        return False
    ad=a.get("direction_norm"); bd=b.get("direction_norm")
    return ad=="unknown" or bd=="unknown" or ad==bd


def _raw_eventview(con,capture_id,rows,tolerance=1.0):
    raw=rows[RAW]; ev=rows[EVENTVIEW]
    candidates={}
    for a in raw:
        if a.get("absolute_ts") is None:
            continue
        matches=[]
        for b in ev:
            if b.get("absolute_ts") is None or not _same_packet_dims(a,b):
                continue
            delta=b["absolute_ts"]-a["absolute_ts"]
            if abs(delta)<=tolerance:
                matches.append((abs(delta),delta,b))
        matches.sort(key=lambda x:(x[0],x[2]["ref"]))
        candidates[a["ref"]]=matches
    reverse={}
    for a_ref,matches in candidates.items():
        for _absd,_delta,b in matches:
            reverse.setdefault(b["ref"],[]).append(a_ref)

    for a in raw:
        matches=candidates.get(a["ref"],[])
        if not matches:
            continue
        unique=len(matches)==1 and len(reverse.get(matches[0][2]["ref"],[]))==1
        for absd,delta,b in matches:
            _insert(
                con,capture_id,a,b,
                basis="opcode+direction+absolute_timestamp",
                status=STATUS_MATCHED if unique else STATUS_AMBIGUOUS,
                delta=round(delta,6),
                score=max(0.0,1.0-(absd/max(tolerance,0.001))*0.25),
                details={"candidate_count_for_source":len(matches),
                         "candidate_count_for_target":len(reverse.get(b["ref"],[])),
                         "tolerance_seconds":tolerance},
            )


def _idview_eventview(con,capture_id,rows):
    ids=rows[IDVIEW]; evs=rows[EVENTVIEW]
    candidates={}
    for a in ids:
        matches=[]
        for b in evs:
            if not _same_packet_dims(a,b):
                continue
            shared=[]
            if a.get("entity_id") is not None and b.get("entity_id") is not None and int(a["entity_id"])==int(b["entity_id"]):
                shared.append("entity_id")
            mid=a.get("message_id")
            if mid is not None and mid in (b.get("mes_num"),b.get("message_number")):
                shared.append("message_id")
            if not shared:
                continue
            matches.append((b,shared))
        candidates[a["ref"]]=matches
    reverse={}
    for a_ref,matches in candidates.items():
        for b,_shared in matches:
            reverse.setdefault(b["ref"],[]).append(a_ref)

    for a in ids:
        matches=candidates.get(a["ref"],[])
        if not matches:
            continue
        unique=len(matches)==1 and len(reverse.get(matches[0][0]["ref"],[]))==1
        for b,shared in matches:
            score=0.75+0.1*min(len(shared),2)
            _insert(
                con,capture_id,a,b,
                basis="opcode+direction+shared_decoded_fields",
                status=STATUS_MATCHED if unique else STATUS_AMBIGUOUS,
                score=score,
                details={"shared_fields":shared,
                         "candidate_count_for_source":len(matches),
                         "candidate_count_for_target":len(reverse.get(b["ref"],[]))},
            )


def _video_to_clock_candidates(con,capture_id,rows,target_kind,clock_kind,tolerance=1.5):
    video=rows[VIDEO]; target=rows[target_kind]
    model=ta.fit_alignment(con,capture_id,clock_kind)
    if model is None:
        return
    timeline=ta.capture_timeline_candidates(con,capture_id,limit=100000)
    capture_time_by_ref={row["source_ref"]:row["capture_ts"] for row in timeline if (
        (target_kind==RAW and row["source_type"]=="RAW_PACKET") or
        (target_kind==EVENTVIEW and row["source_type"]=="EVENTVIEW")
    )}

    candidates={}
    for a in video:
        if a.get("video_ts") is None:
            continue
        projected=model.video_to_capture(float(a["video_ts"]))
        matches=[]
        for b in target:
            if not _same_packet_dims(a,b):
                continue
            ref=b["ref"]
            target_ts=capture_time_by_ref.get(ref)
            if target_ts is None:
                continue
            delta=target_ts-projected
            if abs(delta)<=tolerance:
                matches.append((abs(delta),delta,b,projected,target_ts))
        matches.sort(key=lambda x:(x[0],x[2]["ref"]))
        candidates[a["ref"]]=matches
    reverse={}
    for a_ref,matches in candidates.items():
        for _absd,_delta,b,_p,_t in matches:
            reverse.setdefault(b["ref"],[]).append(a_ref)

    for a in video:
        matches=candidates.get(a["ref"],[])
        if not matches:
            continue
        unique=len(matches)==1 and len(reverse.get(matches[0][2]["ref"],[]))==1
        for absd,delta,b,projected,target_ts in matches:
            _insert(
                con,capture_id,a,b,
                basis=f"opcode+direction+aligned_{clock_kind.lower()}",
                status=STATUS_MATCHED if unique else STATUS_AMBIGUOUS,
                delta=round(delta,6),
                score=max(0.0,0.9-(absd/max(tolerance,0.001))*0.25),
                details={
                    "candidate_count_for_source":len(matches),
                    "candidate_count_for_target":len(reverse.get(b["ref"],[])),
                    "tolerance_seconds":tolerance,
                    "alignment":model.as_dict(),
                    "projected_capture_ts":round(projected,6),
                    "target_capture_ts":round(target_ts,6),
                },
            )


def correlate_capture(con: sqlite3.Connection, capture_id: int) -> dict:
    """Rebuild conservative pairwise correlations for one capture."""
    init_db(con)
    con.execute("DELETE FROM capture_packet_correlations WHERE capture_id=?",(int(capture_id),))
    rows=_rows(con,int(capture_id))
    _raw_eventview(con,int(capture_id),rows)
    _idview_eventview(con,int(capture_id),rows)
    _video_to_clock_candidates(
        con,int(capture_id),rows,RAW,ta.CLOCK_RAW_PACKET_RELATIVE
    )
    _video_to_clock_candidates(
        con,int(capture_id),rows,EVENTVIEW,ta.CLOCK_EVENTVIEW_RELATIVE
    )
    con.commit()
    counts={status:con.execute(
        "SELECT COUNT(*) FROM capture_packet_correlations WHERE capture_id=? AND status=?",
        (int(capture_id),status)
    ).fetchone()[0] for status in (STATUS_MATCHED,STATUS_AMBIGUOUS)}
    by_basis={
        basis:count for basis,count in con.execute(
            """SELECT basis,COUNT(*) FROM capture_packet_correlations
               WHERE capture_id=? GROUP BY basis ORDER BY basis""",(int(capture_id),)
        ).fetchall()
    }
    return {
        "capture_id":int(capture_id),
        "source_counts":{kind:len(items) for kind,items in rows.items()},
        "matched":counts[STATUS_MATCHED],
        "ambiguous":counts[STATUS_AMBIGUOUS],
        "by_basis":by_basis,
    }


def list_correlations(con: sqlite3.Connection,capture_id:int,status:str|None=None) -> list[dict]:
    init_db(con)
    con.row_factory=sqlite3.Row
    sql="SELECT * FROM capture_packet_correlations WHERE capture_id=?"
    params=[int(capture_id)]
    if status:
        sql+=" AND status=?"; params.append(status)
    sql+=" ORDER BY status,basis,source_kind,source_ref,target_kind,target_ref"
    out=[]
    for row in con.execute(sql,params):
        item=dict(row)
        try:
            item["details"]=json.loads(item.pop("details_json") or "{}")
        except json.JSONDecodeError:
            item["details"]={}
        out.append(item)
    return out
