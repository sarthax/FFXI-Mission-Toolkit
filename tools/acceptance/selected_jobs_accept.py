import os, sys, json, time
sys.path[:0] = [os.path.join(os.environ.get("TOOLKIT_CHECKOUT", "."), "src")]
import pymysql
pw = open(os.environ.get("SYNTH_PW_FILE", ".synth_pw")).read().strip()
root = pymysql.connect(host="127.0.0.1", port=3398, user="root", password="", database="synth_acc", autocommit=True)
rc = root.cursor()
rc.execute("SET GLOBAL log_output='TABLE'"); rc.execute("TRUNCATE mysql.general_log"); rc.execute("SET GLOBAL general_log=ON")


def snap():
    rc.execute("SELECT (SELECT COUNT(*) FROM chars),(SELECT SUM(mjob+sjob+mlvl+slvl) FROM char_stats),(SELECT COUNT(*) FROM char_stats)")
    return rc.fetchone()


def threads():
    rc.execute("SELECT COUNT(*) FROM information_schema.processlist WHERE user='ro_synth'")
    return rc.fetchone()[0]


base = snap()
os.environ.update({"MISSION_TOOLKIT_SUPERVISOR_TOKEN": "z" * 40,
                   "MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS": "900001,900002,900003,900004,900005",
                   "MISSION_TOOLKIT_SUPERVISOR_DB_USER": "ro_synth", "MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD": pw,
                   "MISSION_TOOLKIT_SUPERVISOR_DB_NAME": "synth_acc", "MISSION_TOOLKIT_SUPERVISOR_DB_PORT": "3398"})
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workbench.server_admin.feature_testing import supervisor
from workbench.server_admin.feature_testing import database_diagnostics as dd, bounded_selected_jobs as bj

app = FastAPI(); app.include_router(supervisor.router); cl = TestClient(app)
P = "/api/supervisor/test-character-selected-jobs"
H = {"Authorization": "Bearer " + "z" * 40}
res = []


def rec(name, ok, detail):
    res.append((name, ok, detail)); print(("PASS " if ok else "FAIL ") + name + " :: " + detail)


def get(cid, h=H):
    return cl.get(P, params={"charid": cid}, headers=h)


x = get(900001); j = x.json()
rec("real DB valid read", x.status_code == 200 and j["status"] == "PERSISTED_FIELDS_OBSERVED" and j["selected_jobs"] == {"main_job_id": 1, "support_job_id": 2, "main_level": 75, "support_level": 37} and j["execution_enabled"] is False, f"{x.status_code} {j['status']}")
x = get(900002).json(); rec("zeros preserved", x["status"] == "PERSISTED_FIELDS_OBSERVED" and x["selected_jobs"]["main_level"] == 0, x["status"])
x = get(900003).json(); rec("missing char_stats", x["status"] == "INCOMPLETE_MISSING_CHAR_STATS", x["status"])
x = get(900004).json(); rec("ambiguous char_stats", x["status"] == "INCOMPLETE_AMBIGUOUS_CHAR_STATS", x["status"])
x = get(900005).json(); rec("allowlisted but unknown character", x["status"] == "UNKNOWN_CHARACTER", x["status"])
for h, n in ((None, "no auth"), ({"Authorization": "Bearer bad"}, "bad token")):
    x = cl.get(P, params={"charid": 900001}, headers=h or {}); rec("authz " + n, x.status_code == 403, str(x.status_code))
for cid in (1, 0, -5, 900099):
    x = get(cid); rec(f"allowlist rejects charid {cid}", x.status_code == 400, f"{x.status_code} {x.json().get('detail')}")
x = cl.get(P, params={"charid": "abc"}, headers=H); rec("non-int charid", x.status_code == 422, str(x.status_code))


def with_env(k, v, cid=900001):
    old = os.environ.get(k); os.environ[k] = v
    try:
        return get(cid)
    finally:
        os.environ[k] = old


for v in ("abc", "0", "70000", "-1", " "):
    x = with_env("MISSION_TOOLKIT_SUPERVISOR_DB_PORT", v)
    rec(f"invalid DB_PORT {v!r}", x.status_code == 503 and "unavailable" in x.json()["detail"], f"{x.status_code} {x.json()['detail']}")
x = with_env("MISSION_TOOLKIT_SUPERVISOR_DB_PORT", "3397")
rec("closed port connect error sanitized", x.status_code == 503 and "3397" not in x.text and "127.0.0.1" not in x.text and "Errno" not in x.text, f"{x.status_code} {x.json()['detail']}")
x = with_env("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD", "wrong-synthetic-pw")
rec("bad password sanitized", x.status_code == 503 and "wrong-synthetic-pw" not in x.text and "ro_synth" not in x.text and "Access denied" not in x.text, f"{x.status_code} {x.json()['detail']}")
x = with_env("MISSION_TOOLKIT_SUPERVISOR_DB_NAME", "no_such_db")
rec("bad database name sanitized", x.status_code == 503 and "no_such_db" not in x.text, f"{x.status_code} {x.json()['detail']}")
old = os.environ.pop("MISSION_TOOLKIT_SUPERVISOR_DB_USER"); x = get(900001); os.environ["MISSION_TOOLKIT_SUPERVISOR_DB_USER"] = old
rec("unconfigured -> UNAVAILABLE", x.status_code == 200 and x.json()["status"] == "UNAVAILABLE", f"{x.status_code} {x.json()['status']}")

real_open = dd._open


class Cur:
    def __init__(s, c, close_fail=False, sel_fail=False): s.c = c; s.cf = close_fail; s.sf = sel_fail
    def __getattr__(s, n): return getattr(s.c, n)
    def execute(s, q, a=None):
        if s.sf and q.startswith("SELECT charid"): raise RuntimeError("boom SECRET")
        return s.c.execute(q) if a is None else s.c.execute(q, a)
    def close(s):
        try: s.c.close()
        finally:
            if s.cf: raise RuntimeError("synthetic cursor.close failure SECRET")


class Con:
    def __init__(s, c, mode): s.c = c; s.mode = mode
    def __getattr__(s, n): return getattr(s.c, n)
    def rollback(s):
        if s.mode == "rb": raise RuntimeError("synthetic rollback failure SECRET")
        return s.c.rollback()
    def close(s):
        s.c.close()
        if s.mode == "conn": raise RuntimeError("synthetic conn.close failure SECRET")


for mode, desc in (("cur", "cursor.close raises"), ("conn", "connection.close raises"), ("rb", "rollback raises"), ("sel", "SELECT raises")):
    def fo(u, p, d, port, mode=mode):
        c, cu = real_open(u, p, d, port)
        return Con(c, mode), Cur(cu, close_fail=(mode == "cur"), sel_fail=(mode == "sel"))
    dd._open = fo
    try: bj.selected_jobs_snapshot(900001); exc = None
    except Exception as e: exc = e
    dd._open = real_open
    time.sleep(0.5); after = threads()
    rec(f"cleanup when {desc}: sanitized RuntimeError, server-side connection released",
        isinstance(exc, RuntimeError) and "SECRET" not in str(exc) and after == 0, f"exc={exc!s}; ro_synth server threads after={after}")

c = pymysql.connect(host="127.0.0.1", port=3398, user="ro_synth", password=pw, database="synth_acc"); cu = c.cursor()
tamper = ("INSERT INTO chars VALUES (1,'x')", "UPDATE char_stats SET mlvl=1", "DELETE FROM chars", "DROP TABLE chars")
for sql in tamper:
    try: cu.execute(sql); ok = False; d = "EXECUTED"
    except Exception as e: ok = True; d = type(e).__name__ + " " + str(e.args[0])
    rec("ro_synth (service DB account) cannot " + sql.split()[0], ok, d)
c.close()
rec("synthetic data unchanged after all runs", snap() == base, f"{base} -> {snap()}")

rc.execute("SELECT argument FROM mysql.general_log WHERE user_host LIKE '%ro_synth%' AND command_type='Query'")
stmts = [(a[0].decode() if isinstance(a[0], bytes) else a[0]) for a in rc.fetchall()]
mine = tuple(t.upper() for t in tamper)
service = [s for s in stmts if s.upper() not in mine]
ok_prefix = ("SELECT CHARID FROM CHARS WHERE CHARID = ", "SELECT MJOB, SJOB, MLVL, SLVL FROM CHAR_STATS WHERE CHARID = ", "SET TRANSACTION READ ONLY", "START TRANSACTION", "ROLLBACK", "SET NAMES UTF8MB4", "SET AUTOCOMMIT = 0")
kinds = {}
for s in service:
    k = s.upper().split("WHERE")[0].strip()[:60]; kinds[k] = kinds.get(k, 0) + 1
rec("server general_log: every service statement is fixed read-only form", len(service) > 0 and all(s.upper().startswith(ok_prefix) for s in service), f"{len(service)} service stmts; {json.dumps(kinds)}")
rc.execute("SET GLOBAL general_log=OFF")
json.dump([{"name": n, "pass": o, "detail": d} for n, o, d in res], open(os.environ.get("RESULTS_JSON", "RESULTS.json"), "w"), indent=1)
print(sum(1 for _, o, _ in res if o), "/", len(res), "pass")
