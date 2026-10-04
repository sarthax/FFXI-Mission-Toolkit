"""Bulk capture ingest: point at any directory (local, other drive, NAS/UNC), review a plan, then run it as one
background job. Two modes keep archives and loose data apart:

  archives -- only .zip/.7z/.rar/... files. (.zip and .7z ingest; .rar and friends are listed as unsupported.)
  raw      -- only folders and loose files (never archives).

Guardrails: scan is read-only; a drive-capacity check (default 90%) refuses to run unless explicitly overridden;
one job at a time (single DB writer); cancel between captures; every file's outcome is reported, failures with
their error. Blocking review-queue items are raised by ingest() itself, exactly as for the CLI.
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

MAX_PCT = float(os.environ.get("BULK_INGEST_MAX_DRIVE_PCT", "90"))
DB_GROWTH_FACTOR = 1.0            # estimated DB growth per byte of uncompressed capture (conservative guess)
INGESTABLE_ARCHIVES = {".zip", ".7z"}
UNSUPPORTED_ARCHIVES = {".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
ARCHIVE_EXTS = INGESTABLE_ARCHIVES | UNSUPPORTED_ARCHIVES
JOB_DIR = Path(os.environ.get("BULK_INGEST_JOB_DIR", "D:/Claude/mission_toolkit/bulk_ingest_jobs"))

_lock = threading.Lock()          # held for the whole of a running job
_jobs = {}                        # job_id -> job dict
_plans = {}                       # token -> plan dict


# ---------------------------------------------------------------- scan
def _dir_bytes(p):
    n = c = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            try:
                n += os.path.getsize(os.path.join(r, f))
                c += 1
            except OSError:
                pass
    return n, c


def _archive_uncompressed(p):
    """Best-effort uncompressed size (drives the temp-space estimate for .7z)."""
    ext = p.suffix.lower()
    try:
        if ext == ".zip":
            import zipfile
            with zipfile.ZipFile(p) as z:
                return sum(i.file_size for i in z.infolist())
        if ext == ".7z":
            import py7zr
            with py7zr.SevenZipFile(p, mode="r") as z:
                return sum(getattr(f, "uncompressed", 0) or 0 for f in z.list())
    except Exception:
        pass
    return p.stat().st_size


def _units(root, mode, recursive):
    root = Path(root)
    if mode == "archives":
        it = root.rglob("*") if recursive else root.iterdir()
        for p in sorted(it):
            try:
                if p.is_file() and p.suffix.lower() in ARCHIVE_EXTS:
                    yield p
            except OSError:
                continue
    else:
        for p in sorted(root.iterdir()):
            try:
                if p.is_dir():
                    yield p
                elif p.is_file() and p.suffix.lower() not in ARCHIVE_EXTS:
                    yield p
            except OSError:
                continue


def scan(con, root, mode="archives", content_type="instances", recursive=False):
    """Read-only. -> plan dict (also cached under plan['token'])."""
    from workbench.captures import source_fingerprint as sf
    if mode not in ("archives", "raw"):
        raise ValueError("mode must be 'archives' or 'raw'")
    root = str(root).strip().strip('"')
    if not root:
        raise ValueError("enter a directory")
    if not os.path.isdir(root):
        raise ValueError("%r is not a directory this server can read" % root)
    known = {r[0] for r in con.execute("SELECT source_path FROM captures")}
    sf.ensure_table(con)
    entries = []
    for p in _units(root, mode, recursive):
        e = {"path": str(p), "name": p.name, "kind": "folder" if p.is_dir() else p.suffix.lower() or "file",
             "bytes": 0, "uncompressed": 0, "action": "ingest", "reason": ""}
        try:
            if p.is_dir():
                e["bytes"], nfiles = _dir_bytes(p)
                e["uncompressed"] = e["bytes"]
                if nfiles == 0:
                    e.update(action="skip", reason="folder is empty")
            else:
                e["bytes"] = p.stat().st_size
                e["uncompressed"] = _archive_uncompressed(p) if p.suffix.lower() in INGESTABLE_ARCHIVES else e["bytes"]
        except OSError as ex:
            e.update(action="skip", reason="cannot read: %s" % ex)
        if e["action"] == "ingest":
            ext = p.suffix.lower()
            if ext in UNSUPPORTED_ARCHIVES:
                e.update(action="unsupported", reason="%s archives can't be ingested - re-compress as .zip or .7z" % ext)
            elif str(p) in known:
                e.update(action="skip", reason="already ingested")
            elif p.is_dir() or ext in INGESTABLE_ARCHIVES:
                try:
                    _, dup = sf.precheck(con, str(p))
                    if dup:
                        e.update(action="skip", reason="same content as capture #%s" % dup[0])
                except Exception as ex:
                    e["reason"] = "looks unreadable (%s) - will be tried and queued for review if it fails" % ex
        entries.append(e)
    plan = {"token": uuid.uuid4().hex[:12], "root": root, "mode": mode, "content_type": content_type,
            "recursive": recursive, "entries": entries, "made": time.time()}
    plan["disk"] = disk_check(plan)
    _plans.clear() if len(_plans) > 20 else None
    _plans[plan["token"]] = plan
    return plan


# ---------------------------------------------------------------- disk guardrail
def _drive_key(path):
    p = os.path.abspath(path)
    d = os.path.splitdrive(p)[0]
    return d.upper() if d else "/"


def _usage(path):
    probe = path
    while probe and not os.path.exists(probe):
        nxt = os.path.dirname(probe)
        if nxt == probe:
            break
        probe = nxt
    u = shutil.disk_usage(probe)
    return u.total, u.used


def disk_check(plan, max_pct=None):
    """Projected % full for each drive the job writes to. Needs: DB drive = sum of uncompressed sizes x growth
    factor; temp drive = largest .7z (extracted to temp while parsing). Source drive is read-only so only
    reported. -> {'max_pct', 'drives':[...], 'over': bool}"""
    from workbench.captures.ingestion import _build_index_impl as bi
    max_pct = MAX_PCT if max_pct is None else max_pct
    todo = [e for e in plan["entries"] if e["action"] == "ingest"]
    need = {}
    db_dir = os.path.dirname(os.path.abspath(str(bi.DB_PATH)))
    need[db_dir] = ("database", int(sum(e["uncompressed"] for e in todo) * DB_GROWTH_FACTOR))
    sev = [e["uncompressed"] for e in todo if e["name"].lower().endswith(".7z")]
    if sev:
        tmp = tempfile.gettempdir()
        tk = _drive_key(tmp)
        add = max(sev)
        if _drive_key(db_dir) == tk:
            need[db_dir] = ("database + temp", need[db_dir][1] + add)
        else:
            need[tmp] = ("temp (.7z extraction)", add)
    drives = []
    for path, (role, add) in need.items():
        total, used = _usage(path)
        now, after = used * 100.0 / total, (used + add) * 100.0 / total
        drives.append({"path": path, "role": role, "need_bytes": add, "free_bytes": total - used,
                       "now_pct": round(now, 1), "after_pct": round(after, 1), "over": after > max_pct or now > max_pct})
    return {"max_pct": max_pct, "drives": drives, "over": any(d["over"] for d in drives)}


# ---------------------------------------------------------------- run
def current_job():
    live = [j for j in _jobs.values() if j["state"] == "running"]
    return live[0] if live else None


def start(token, override=False, sheet_text=None, overwrite_sheet=False):
    plan = _plans.get(token)
    if not plan:
        raise ValueError("this plan expired - scan again")
    plan["disk"] = disk_check(plan)                       # re-check at run time; disk may have changed
    if plan["disk"]["over"] and not override:
        raise PermissionError("a drive would pass %.0f%% full - tick the override box to run anyway" % plan["disk"]["max_pct"])
    if not any(e["action"] == "ingest" for e in plan["entries"]):
        raise ValueError("nothing to ingest in this plan")
    if not _lock.acquire(blocking=False):
        raise RuntimeError("another bulk ingest is already running")
    job = {"id": uuid.uuid4().hex[:10], "state": "running", "root": plan["root"], "mode": plan["mode"],
           "content_type": plan["content_type"], "started": time.time(), "finished": None, "cancel": False,
           "override": bool(override), "disk": plan["disk"], "sheet": None,
           "items": [dict(e, status="pending", error="", capture_id=None, secs=None) for e in plan["entries"]]}
    _jobs[job["id"]] = job
    threading.Thread(target=_run, args=(job, sheet_text, overwrite_sheet), daemon=True).start()
    return job


def cancel(job_id):
    j = _jobs.get(job_id)
    if j and j["state"] == "running":
        j["cancel"] = True
    return j


def _run(job, sheet_text, overwrite_sheet):
    import sqlite3
    from workbench.captures.ingestion import _build_index_impl as bi
    con = None
    try:
        con = sqlite3.connect(str(bi.DB_PATH), timeout=60)
        con.row_factory = None
        bi.init_db(con)
        for it in job["items"]:
            if it["action"] != "ingest":
                it["status"] = "skipped" if it["action"] == "skip" else "unsupported"
                continue
            if job["cancel"]:
                it["status"] = "not run (cancelled)"
                continue
            it["status"] = "running"
            t0, buf = time.time(), io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    cid = bi.ingest(con, it["path"], content_type=job["content_type"])
                it["capture_id"] = cid if isinstance(cid, int) else None
                row = con.execute("SELECT capture_id FROM captures WHERE source_path=?", (it["path"],)).fetchone()
                if it["capture_id"] is None and row:
                    it["capture_id"] = row[0]
                it["status"] = "ok" if it["capture_id"] else "no capture created"
                if not it["capture_id"]:
                    it["error"] = buf.getvalue()[-400:].strip()
            except (Exception, SystemExit) as ex:
                it["status"] = "FAILED"
                it["error"] = ("%s: %s" % (type(ex).__name__, ex))[:600]
                try:
                    con.rollback()
                except Exception:
                    pass
            it["secs"] = round(time.time() - t0, 1)
        if sheet_text and not job["cancel"]:
            from workbench.captures import source_info as si
            rep = si.import_csv(con, sheet_text, dry_run=False, overwrite=overwrite_sheet)
            job["sheet"] = {"applied": len(rep["applied"]), "errors": rep["errors"], "skipped": rep["skipped"]}
        try:
            from workbench.core.services import campaign_manifest
            if campaign_manifest.MANIFEST_PATH.exists():
                campaign_manifest.apply(con)
        except Exception as ex:
            job["manifest_error"] = str(ex)
        job["state"] = "cancelled" if job["cancel"] else "done"
    except Exception as ex:
        job["state"] = "failed"
        job["fatal"] = "%s: %s" % (type(ex).__name__, ex)
    finally:
        if con is not None:
            con.close()
        job["finished"] = time.time()
        _save(job)
        _lock.release()


def summary(job):
    c = {}
    for it in job["items"]:
        k = it["status"].split(" ")[0]
        c[k] = c.get(k, 0) + 1
    return c


def _save(job):
    try:
        JOB_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.fromtimestamp(job["started"]).strftime("%Y%m%d_%H%M%S")
        (JOB_DIR / ("bulk_%s_%s.json" % (stamp, job["id"]))).write_text(json.dumps(job, indent=1, default=str), encoding="utf-8")
    except OSError:
        pass


def get_job(job_id):
    return _jobs.get(job_id)


def recent_jobs(n=10):
    return sorted(_jobs.values(), key=lambda j: j["started"], reverse=True)[:n]
