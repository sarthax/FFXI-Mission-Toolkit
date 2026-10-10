"""Bilingual (EN/JA) client text database.

Pairs every English client text table with its Japanese twin from the same
install and stores them in one SQLite DB so other modules/services can look up
``(table, id) -> en/ja`` without re-parsing DATs.

Sources (pairing comes from the vendored FFXI-Resources configs):
  * zone dialog   strings_na <-> strings_jp  (scripts/events/dats.yaml)
  * auto-translate ROM/168/25.DAT <-> ROM/168/24.DAT (JA is Shift-JIS, layout
    ``02 01 cat id len str [len str2(kana)]``; xi_tinkerer cannot parse it)
  * items: names/descriptions decoded with FFXI-Resources/parsers/items.py
    (needs the ``construct`` package); pairs also recorded in ``dat_pairs``

Build:  python -m workbench.client.dat.text_db build [--ffxi PATH] [--db PATH]
Query:  from workbench.client.dat.text_db import TextDB
        db = TextDB(); db.dialog(zone_id=230, msg_id=1); db.search("Home Point")
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
from pathlib import Path

from workbench.runtime.paths import DATA_ROOT, VENDOR_ROOT

DB_PATH = DATA_ROOT / "ja_en_text.db"
_RES = VENDOR_ROOT / "FFXI-Resources" / "scripts"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dat_pairs(
  kind TEXT, ident TEXT, name TEXT, en_dat TEXT, ja_dat TEXT,
  en_exists INT, ja_exists INT, en_bytes INT, ja_bytes INT,
  en_sha1 TEXT, ja_sha1 TEXT, entries INT, index_aligned INT, note TEXT,
  PRIMARY KEY(kind, ident));
CREATE TABLE IF NOT EXISTS zone_dialog(
  zone_id INT, msg_id INT, en TEXT, ja TEXT, PRIMARY KEY(zone_id, msg_id));
CREATE TABLE IF NOT EXISTS auto_translate(
  cat_id INT, entry_id INT, key TEXT, category_en TEXT, category_ja TEXT,
  en TEXT, ja TEXT, ja_kana TEXT, PRIMARY KEY(cat_id, entry_id));
CREATE TABLE IF NOT EXISTS items(
  item_id INT PRIMARY KEY, category TEXT, name_en TEXT, name_ja TEXT,
  log_single_en TEXT, log_plural_en TEXT, desc_en TEXT, desc_ja TEXT);
CREATE TABLE IF NOT EXISTS zones(zone_id INT PRIMARY KEY, name TEXT);
CREATE INDEX IF NOT EXISTS ix_dialog_en ON zone_dialog(en);
"""


def _sha1(p: str) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _walk_auto_translate(path: str):
    """Return ({(cat, id): [strings]}, {cat: name}) for an auto-translate DAT."""
    b = open(path, "rb").read()
    pos, ents, cats = 0, {}, {}
    while pos < len(b) - 5:
        if b[pos] != 2:
            pos += 1
            continue
        cat, eid = b[pos + 2], b[pos + 3]
        if eid == 0:  # category header, fixed 0x4c bytes
            nm = b[pos + 4:pos + 0x24].split(b"\0")[0].decode("cp932", "replace")
            cats[cat] = nm.strip("【】")
            pos += 0x4C
            continue
        ln = b[pos + 4]
        strs = [b[pos + 5:pos + 4 + ln].decode("cp932", "replace")]
        pos += 5 + ln
        if pos < len(b) and b[pos] != 2:  # JA carries a 2nd (kana) string
            ln2 = b[pos]
            strs.append(b[pos + 1:pos + ln2].decode("cp932", "replace"))
            pos += 1 + ln2
        ents[(cat, eid)] = strs
    return ents, cats


def _load_items(con, root: str) -> int:
    import sys
    import yaml
    res = str(VENDOR_ROOT / "FFXI-Resources")
    if res not in sys.path:
        sys.path.insert(0, res)
    from parsers.items import parse_all_items

    spec = yaml.safe_load(open(_RES / "items" / "dats.yaml"))
    items = parse_all_items(root.rstrip("/"), spec)
    con.executemany(
        "INSERT OR REPLACE INTO items VALUES(?,?,?,?,?,?,?,?)",
        [(i.id, i.category, i.name.english, i.name.japanese, i.name.english_log_single,
          i.name.english_log_plural, i.description.english, i.description.japanese) for i in items])
    return len(items)


def build(ffxi_path: str | None = None, db_path: Path | str = DB_PATH) -> dict:
    import xi_tinkerer as x
    import yaml

    if ffxi_path is None:
        from workbench.runtime import settings_store
        ffxi_path = settings_store.get_ffxi_install()
    if not ffxi_path:
        raise RuntimeError("FFXI install path not configured; pass --ffxi")
    root = str(ffxi_path).replace("\\", "/").rstrip("/") + "/"

    tmp = Path(str(db_path) + ".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)

    def pair(kind, ident, name, en, ja, note=""):
        row = dict(kind=kind, ident=str(ident), name=name, en_dat=en, ja_dat=ja, note=note,
                   entries=None, index_aligned=None)
        for k, p in (("en", en), ("ja", ja)):
            fp = root + p
            ok = os.path.exists(fp)
            row[k + "_exists"], row[k + "_bytes"] = int(ok), os.path.getsize(fp) if ok else 0
            row[k + "_sha1"] = _sha1(fp) if ok else ""
        return row

    def save(row):
        cols = list(row)
        con.execute(f"INSERT OR REPLACE INTO dat_pairs({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                    [row[c] for c in cols])

    stats = {"zones": 0, "dialog_rows": 0, "missing_zones": [], "auto_translate": 0}
    for z in yaml.safe_load(open(_RES / "events" / "dats.yaml"))["zones"]:
        f = z["files"]
        row = pair("zone_dialog", z["id"], z["name"], f["strings_na"], f["strings_jp"])
        con.execute("INSERT OR REPLACE INTO zones VALUES(?,?)", (z["id"], z["name"]))
        if not (row["en_exists"] and row["ja_exists"]):
            row["note"] = "MISSING in this client install"
            stats["missing_zones"].append(z["id"])
            save(row)
            continue
        try:
            en = x.parse_dialog(root + f["strings_na"])["entries"]
            ja = x.parse_dialog(root + f["strings_jp"])["entries"]
        except Exception as ex:  # e.g. empty dialog DAT
            row["note"] = f"parse error: {str(ex)[:80]}"
            save(row)
            continue
        keys = sorted(set(en) | set(ja), key=int)
        con.executemany("INSERT OR REPLACE INTO zone_dialog VALUES(?,?,?,?)",
                        [(z["id"], int(k), en.get(k), ja.get(k)) for k in keys])
        row["entries"], row["index_aligned"] = len(keys), int(set(en) == set(ja))
        stats["zones"] += 1
        stats["dialog_rows"] += len(keys)
        save(row)

    en_e, en_c = _walk_auto_translate(root + "ROM/168/25.DAT")
    ja_e, ja_c = _walk_auto_translate(root + "ROM/168/24.DAT")
    row = pair("auto_translate", "168", "Auto-translate phrases", "ROM/168/25.DAT", "ROM/168/24.DAT",
               "JA layout: 02 01 cat id len str [len kana]; EN lang byte=02")
    row["entries"], row["index_aligned"] = len(en_e), int(set(en_e) == set(ja_e))
    save(row)
    for k in sorted(set(en_e) | set(ja_e)):
        j = ja_e.get(k) or []
        con.execute("INSERT OR REPLACE INTO auto_translate VALUES(?,?,?,?,?,?,?,?)",
                    (k[0], k[1], "0202%02x%02x" % k, en_c.get(k[0]), ja_c.get(k[0]),
                     (en_e.get(k) or [None])[0], j[0] if j else None, j[1] if len(j) > 1 else None))
    stats["auto_translate"] = len(en_e)

    for e in yaml.safe_load(open(_RES / "items" / "dats.yaml"))["item_dats"]:
        save(pair("items", e["base_id"], f"item block base_id={e['base_id']} max={e['max_count']}",
                  e["en"], e["ja"], "decoded into `items` table"))

    stats["items"] = _load_items(con, root)
    con.commit()
    con.close()
    os.replace(tmp, db_path)
    return stats


class TextDB:
    """Read-only access to the bilingual text DB."""

    def __init__(self, path: Path | str = DB_PATH):
        if not Path(path).exists():
            raise FileNotFoundError(f"{path} missing; run `python -m workbench.client.dat.text_db build`")
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row

    def dialog(self, zone_id: int, msg_id: int | None = None):
        if msg_id is not None:
            r = self.con.execute("SELECT en, ja FROM zone_dialog WHERE zone_id=? AND msg_id=?",
                                 (zone_id, msg_id)).fetchone()
            return dict(r) if r else None
        return [dict(r) for r in self.con.execute(
            "SELECT msg_id, en, ja FROM zone_dialog WHERE zone_id=? ORDER BY msg_id", (zone_id,))]

    def auto_translate(self, cat_id: int | None = None):
        q, a = "SELECT * FROM auto_translate", ()
        if cat_id is not None:
            q, a = q + " WHERE cat_id=?", (cat_id,)
        return [dict(r) for r in self.con.execute(q + " ORDER BY cat_id, entry_id", a)]

    def search(self, text: str, limit: int = 50):
        """Substring search over EN or JA across dialog and auto-translate."""
        like = f"%{text}%"
        d = [dict(r, table="zone_dialog") for r in self.con.execute(
            "SELECT zone_id, msg_id, en, ja FROM zone_dialog WHERE en LIKE ? OR ja LIKE ? LIMIT ?",
            (like, like, limit))]
        a = [dict(r, table="auto_translate") for r in self.con.execute(
            "SELECT cat_id, entry_id, en, ja FROM auto_translate WHERE en LIKE ? OR ja LIKE ? LIMIT ?",
            (like, like, limit))]
        it = [dict(r, table="items") for r in self.con.execute(
            "SELECT item_id, name_en, name_ja FROM items WHERE name_en LIKE ? OR name_ja LIKE ? LIMIT ?",
            (like, like, limit))]
        return d + a + it

    def item(self, item_id: int):
        r = self.con.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone()
        return dict(r) if r else None

    def pairs(self, kind: str | None = None):
        q, a = "SELECT * FROM dat_pairs", ()
        if kind:
            q, a = q + " WHERE kind=?", (kind,)
        return [dict(r) for r in self.con.execute(q, a)]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="text_db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--ffxi")
    b.add_argument("--db", default=str(DB_PATH))
    s = sub.add_parser("search")
    s.add_argument("text")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(build(a.ffxi, a.db))
    else:
        for r in TextDB().search(a.text):
            print(r)


if __name__ == "__main__":
    main()
