import sqlite3, sys
from workbench.captures import review_queue as rq, source_info as si
con = sqlite3.connect(":memory:")
con.executescript("""CREATE TABLE captures(capture_id INTEGER PRIMARY KEY, capture_label TEXT, source_path TEXT, video_url TEXT);
CREATE TABLE capture_tags(capture_id INT, tag TEXT, UNIQUE(capture_id,tag));
INSERT INTO captures VALUES (1,'Campaign - A','D:/x/A.zip',NULL),(2,'Campaign - B','D:/x/B.zip',NULL);""")
rq.ensure(con)
rq.raise_item(con, "manifest_link", "D:/x/A.zip", 1)
t = si.template_csv(con, "pending")
assert "capture_id,capture_file" in t, t
sheet = si.template_csv(con, "blank") + '\n1,,Bob,2026-01-02,,https://youtu.be/x,campaign-battle,,,,\n,B.zip,Al,2026-13-40,,,,,,,\n,Nope.zip,Al,,,,,,,,\n2,,,,,,,,,,\n'
r = si.import_csv(con, sheet, dry_run=True)
print(r)
assert len(r["applied"]) == 1 and len(r["errors"]) == 3, r
assert not con.execute("SELECT COUNT(*) FROM capture_post_meta").fetchone()[0]
r = si.import_csv(con, sheet, dry_run=False)
assert con.execute("SELECT uploader FROM capture_post_meta WHERE capture_id=1").fetchone()[0] == "Bob"
print("ok")
