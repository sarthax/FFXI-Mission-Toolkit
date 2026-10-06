"""Inventory of Discord channels scraped for capture links (link-first intake groundwork).

Tables live in the same SQLite DB as the canonical capture index (captures table):
  discord_channels  one row per channel: category, last scrape time, post count, oldest/newest post
  discord_posts     one row per message: author, date, title, text, urls (json), optional capture_id link

Usage:
  py -3 discord_inventory.py load <posts.json> --channel-id ID --name NAME --category CAT
  py -3 discord_inventory.py list
  py -3 discord_inventory.py link          # attach discord_posts.capture_id by matching video_url / data urls

posts.json is a list of {id, t (ISO), a (author line), x (text), l (urls)} as produced by the browser scrape.
"""
import argparse, json, re, sqlite3, time
from workbench.captures.ingestion import build_index as b

GUILD = "443544205206355968"


def init(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS discord_channels (
        channel_id TEXT PRIMARY KEY, guild_id TEXT, name TEXT, category TEXT,
        last_scraped_at INTEGER, post_count INTEGER, oldest_post TEXT, newest_post TEXT, notes TEXT);
    CREATE TABLE IF NOT EXISTS discord_posts (
        message_id TEXT PRIMARY KEY, channel_id TEXT, posted_at TEXT, author TEXT, title TEXT,
        text TEXT, urls TEXT, capture_id INTEGER, ingest_status TEXT DEFAULT 'indexed');
    CREATE INDEX IF NOT EXISTS idx_dp_channel ON discord_posts(channel_id);
    """)


def clean_author(a):
    return re.sub(r"\s*\[.*$", "", (a or "").split(",")[0]).strip()


def title_of(x):
    ls = [s.strip() for s in (x or "").split("\n") if s.strip()]
    for i, s in enumerate(ls):
        if re.match(r"^\w+day, \w+ \d+, \d{4}", s):
            return ls[i + 1][:200] if i + 1 < len(ls) else ""
    return ls[1][:200] if len(ls) > 1 else ""


def load(con, path, cid, name, cat):
    posts = json.load(open(path, encoding="utf-8"))
    if isinstance(posts, dict):
        posts = [dict(v, id=k) for k, v in posts.items()]
    ts = sorted(p["t"] for p in posts if p.get("t"))
    for p in posts:
        con.execute("INSERT OR REPLACE INTO discord_posts(message_id,channel_id,posted_at,author,title,text,urls) VALUES(?,?,?,?,?,?,?)",
                    (p["id"], cid, p.get("t"), clean_author(p.get("a")), title_of(p.get("x")), p.get("x"), json.dumps(p.get("l", []))))
    con.execute("INSERT OR REPLACE INTO discord_channels VALUES(?,?,?,?,?,?,?,?,?)",
                (cid, GUILD, name, cat, int(time.time()), len(posts), ts[0] if ts else None, ts[-1] if ts else None, None))
    con.commit()
    print(f"{name}: {len(posts)} posts {ts[0] if ts else ''}..{ts[-1] if ts else ''}")


def link(con):
    n = 0
    for cid, vurl in con.execute("SELECT capture_id, video_url FROM captures WHERE video_url IS NOT NULL").fetchall():
        key = vurl.rsplit("/", 1)[-1].replace("watch?v=", "")
        for (mid,) in con.execute("SELECT message_id FROM discord_posts WHERE urls LIKE ?", (f"%{key}%",)).fetchall():
            con.execute("UPDATE discord_posts SET capture_id=?, ingest_status='ingested' WHERE message_id=?", (cid, mid))
            n += 1
    con.commit()
    print(f"linked {n} posts")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    l = sp.add_parser("load"); l.add_argument("path"); l.add_argument("--channel-id", required=True)
    l.add_argument("--name", required=True); l.add_argument("--category", required=True)
    sp.add_parser("list"); sp.add_parser("link")
    a = ap.parse_args()
    con = sqlite3.connect(str(b.DB_PATH)); init(con)
    if a.cmd == "load": load(con, a.path, a.channel_id, a.name, a.category)
    elif a.cmd == "link": link(con)
    else:
        for r in con.execute("SELECT category,name,channel_id,post_count,oldest_post,newest_post,datetime(last_scraped_at,'unixepoch') FROM discord_channels ORDER BY category,name"):
            print(" | ".join(str(x) for x in r))
    con.close()


if __name__ == "__main__":
    main()
