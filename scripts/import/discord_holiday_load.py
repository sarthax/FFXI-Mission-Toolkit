"""Load Discord 'holiday events' + 'temporary events' posts into the captures table (link-first).

One captures row per post (source_path = discord://<message_id>, so re-runs are idempotent):
  capturer    poster (blank authors on grouped Discord messages are filled from the previous post in the channel)
  video_url   first video link in the post (youtube/rumble/twitch)
  mission_name event name (from the title's 'Holiday Events - X' / 'Temp Events - X' segment, else the channel)
  tags        'Events - Holiday' or 'Events - Temporary' (+ 'Events')
Also backfills discord_posts.author and sets capture_id / ingest_status='link_logged'.

Usage: py -3 scripts/import/discord_holiday_load.py [--apply]
"""
import argparse, json, re, sqlite3, datetime as dt
from workbench.captures.ingestion import build_index as b

CATS = {"holiday events": "Events - Holiday", "temporary events": "Events - Temporary"}
VIDEO = re.compile(r"(youtu\.be|youtube\.com|rumble\.com|twitch\.tv)")
SEG = re.compile(r"^(?:Holiday Events|Temp(?:orary)? Events)\s*[-:]\s*(.+?)\s*(?:[-\[(]|$)", re.I)


CANON = {"sunbreeze-festival": "Sunbreeze Festival", "egg-hunt-egg-stravaganza": "Egg Hunt / Eggstravaganza",
         "feast-of-swords": "Feast of Swords", "valentiones-day": "Valentione's Day", "happy-new-year": "Happy New Year",
         "starlight-celebration": "Starlight Celebration", "harvest-festival": "Harvest Festival",
         "doll-festival": "Doll Festival", "celestial-nights": "Celestial Nights", "green-festival": "Green Festival",
         "blazing-buffaloes": "Blazing Buffaloes", "sunshine-seeker": "Sunshine Seekers",
         "adventurer-appreciation": "Adventurer Appreciation", "adventurer-gratitude": "Adventurer Gratitude",
         "dragon-quest-x": "Dragon Quest X Crossover", "ffxiv-crossover": "FFXIV Crossover", "mog-bonanza": "Mog Bonanza"}
OVERRIDE = ("Vanaversary", "Mog Bonanza")


def event_name(title, channel):
    # canonical per channel, unless the post's own title names a different known event (cross-posts)
    for o in OVERRIDE:
        if o.lower() in (title or "").lower():
            return o
    return CANON.get(channel, channel.replace("-", " ").title())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    con = sqlite3.connect(str(b.DB_PATH)); b.init_db(con)
    rows = con.execute("""SELECT p.message_id,p.posted_at,p.author,p.title,p.urls,ch.name,ch.category
        FROM discord_posts p JOIN discord_channels ch USING(channel_id)
        WHERE ch.category IN ('holiday events','temporary events') ORDER BY ch.channel_id,p.posted_at""").fetchall()
    last, made, skipped = {}, 0, 0
    for mid, t, author, title, urls, chan, cat in rows:
        key = (chan, cat)
        author = author or last.get(key, "")
        last[key] = author
        urls = json.loads(urls or "[]")
        video = next((u for u in urls if VIDEO.search(u)), None)
        src = f"discord://{mid}"
        label = re.sub(r"\s+", " ", title or chan).strip()[:200]
        ev = event_name(title, chan)
        print(f"{cat[:4]} {chan:26} {author or '?':10} {ev[:30]:30} {'V' if video else '-'} {label[:60]}")
        if not a.apply:
            continue
        if con.execute("SELECT 1 FROM captures WHERE source_path=?", (src,)).fetchone():
            skipped += 1; continue
        st = dt.datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp() if t else None
        cur = con.execute("""INSERT INTO captures (source_path,capturer,capture_label,content_type,mission_name,
            addons,zones,start_time,video_url) VALUES (?,?,?,?,?,?,?,?,?)""",
            (src, author or None, label, "unclassified", ev, "[]", "[]", st, video))
        b.set_capture_tags(con, cur.lastrowid, ["Events", CATS[cat]])
        con.execute("UPDATE discord_posts SET author=?, capture_id=?, ingest_status='link_logged' WHERE message_id=?",
                    (author, cur.lastrowid, mid))
        made += 1
    con.commit()
    print(f"{len(rows)} posts; created {made}, already present {skipped}" if a.apply else f"{len(rows)} posts (dry run)")


if __name__ == "__main__":
    main()
