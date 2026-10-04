import os, sqlite3, tempfile, time, zipfile
from pathlib import Path
from workbench.captures.ingestion import _build_index_impl as ib
from workbench.captures import bulk_ingest as bi
tmp = Path(tempfile.mkdtemp())
ib.DB_PATH = tmp / "t.db"; bi.JOB_DIR = tmp / "jobs"
con = sqlite3.connect(str(ib.DB_PATH)); ib.init_db(con)
src = tmp / "src"; src.mkdir()
with zipfile.ZipFile(src / "good.zip", "w") as z: z.writestr("cap/readme.txt", "hello")
(src / "bad.zip").write_bytes(b"not a zip")
(src / "old.rar").write_bytes(b"Rar!")
(src / "rawfolder").mkdir(); (src / "rawfolder" / "a.txt").write_text("x")
p = bi.scan(con, str(src), "archives")
acts = {e["name"]: e["action"] for e in p["entries"]}
assert acts == {"bad.zip": "ingest", "good.zip": "ingest", "old.rar": "unsupported"}, acts
praw = bi.scan(con, str(src), "raw")
assert [e["name"] for e in praw["entries"]] == ["rawfolder"], praw["entries"]
try: bi.scan(con, str(src / "nope"), "raw"); assert 0
except ValueError: pass
bi.MAX_PCT = 0.0001
p = bi.scan(con, str(src), "archives")
assert p["disk"]["over"]
try: bi.start(p["token"]); assert 0
except PermissionError: pass
job = bi.start(p["token"], override=True)
for _ in range(100):
    if job["state"] != "running": break
    time.sleep(0.2)
print(job["state"], [(i["name"], i["status"], i["error"][:60]) for i in job["items"]])
assert job["state"] == "done"
st = {i["name"]: i["status"] for i in job["items"]}
assert st["bad.zip"] == "FAILED" and st["old.rar"] == "unsupported", st
assert list(bi.JOB_DIR.glob("*.json"))
print("ok")
