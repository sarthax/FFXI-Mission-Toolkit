"""Audit: match Discord capture posts to ingested captures by NAME (filename vs post title/URL filename).

Read-only. Writes a CSV of possible matches; never updates capture IDs or ingestion state.
  py -3 scripts/import/discord_match_audit.py [--out exports/discord_match_audit.csv]
Tiers: exact (normalized names equal), high (>=0.88), possible (>=0.72). Everything is a candidate, never auto-linked.
"""
import argparse, csv, json, os, re, sqlite3, sys
from difflib import SequenceMatcher
from urllib.parse import unquote

DB = os.path.join(os.path.dirname(__file__), "..", "..", "ffxi_zone_database.db")
HOST = re.compile(r"dropbox|1drv|drive\.google|mega\.nz|onedrive|youtu")
STOP = {"zip", "rar", "7z", "log", "txt", "dl", "the", "a", "of", "and", "win", "loss", "capture", "captures", "run", "x1", "x2"}


def norm(s):
    s = unquote(s or "").lower()
    s = re.sub(r"\.(zip|rar|7z|log|txt)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(t for t in s.split() if t not in STOP)


def toks(s): return set(norm(s).split())


def score(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb: return 0.0
    if na == nb: return 1.0
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0
    return max(SequenceMatcher(None, na, nb).ratio(), jac, 0.95 * len(ta & tb) / min(len(ta), len(tb)) if min(len(ta), len(tb)) >= 3 else 0)


def url_names(urls):
    out = []
    for u in urls:
        m = re.search(r"dropbox\.com/s/\w+/([^?]+)", u)
        if m: out.append(unquote(m.group(1)))
    return out


def body_title(text):
    ls = [l.strip() for l in (text or "").split("\n") if l.strip()]
    for i, l in enumerate(ls):
        if re.match(r"^\w+day, \w+ \d+, \d{4}", l): ls = ls[i + 1:]; break
    ls = [l for l in ls if not re.match(r"^https?://", l)]
    return ls[0] if ls else ""


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="exports/discord_match_audit.csv")
    # No --apply action: even a high string similarity is not evidence of ingestion.
    a = ap.parse_args()
    con = sqlite3.connect(DB)
    caps = []
    for cid, label, mission, sp in con.execute("SELECT capture_id,capture_label,mission_name,source_path FROM captures"):
        base = os.path.basename((sp or "").split("::")[0].replace("\\", "/"))
        names = {n for n in (label, mission, base) if n}
        caps.append((cid, label or base, base, names))
    posts = []
    for mid, ch, dt, au, text, urls, st in con.execute(
            "SELECT p.message_id,c.name,p.posted_at,p.author,p.text,p.urls,p.ingest_status FROM discord_posts p "
            "LEFT JOIN discord_channels c USING(channel_id) WHERE p.ingest_status='indexed'"):
        try: ul = json.loads(urls or "[]")
        except (TypeError, ValueError): continue
        if not isinstance(ul, list): continue
        ul = [u for u in ul if isinstance(u, str)]
        if not any(HOST.search(u) for u in ul): continue
        names = url_names(ul) + [body_title(text)]
        posts.append((mid, ch, dt, au, [n for n in names if n], ul))
    rows, tier_n = [], {"exact": 0, "high": 0, "possible": 0, "none": 0}
    for mid, ch, dt, au, names, ul in posts:
        best = (0, None, "", "")
        for cid, label, base, cn in caps:
            for pn in names:
                for c in cn:
                    sc = score(pn, c)
                    if sc > best[0]: best = (sc, cid, label, pn)
        sc = best[0]
        tier = "exact" if sc >= 0.999 else "high" if sc >= 0.88 else "possible" if sc >= 0.72 else "none"
        tier_n[tier] += 1
        rows.append({"tier": tier, "score": round(sc, 3), "message_id": mid, "channel": ch, "posted": (dt or "")[:10], "author": au,
                     "post_name": best[3] or (names[0] if names else ""), "capture_id": best[1] if tier != "none" else "",
                     "capture_label": best[2] if tier != "none" else "", "url": ul[0] if ul else ""})
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["tier", "score", "message_id", "channel",
                                          "posted", "author", "post_name", "capture_id",
                                          "capture_label", "url"])
        w.writeheader()
        for row in sorted(rows, key=lambda row: -row["score"]):
            w.writerow({k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
                        for k, v in row.items()})
    print("posts with file/video links:", len(posts), "captures:", len(caps)); print(tier_n); print("wrote", a.out)


if __name__ == "__main__":
    main()
