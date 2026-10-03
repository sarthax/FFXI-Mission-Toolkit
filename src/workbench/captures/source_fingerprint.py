"""Cheap content fingerprints for capture sources (zip or folder) so re-ingest/duplicates are
caught BEFORE any parsing. Zips: hash of the central directory's (name, CRC32, size) tuples --
read from the zip index only, no decompression, ~ms even for multi-GB archives. Folders: hash of
(relpath, size) tuples (mtime excluded so a re-copy still matches). Same fingerprint == same
content regardless of filename/location/zip-level re-compression.
"""
import hashlib
import os
import zipfile


def _digest(items):
    h = hashlib.sha256()
    for t in sorted(items):
        h.update(repr(t).encode("utf-8", "replace"))
    return h.hexdigest()


def fingerprint(path):
    """-> (fingerprint, file_count, total_bytes)."""
    if os.path.isdir(path):
        items = []
        for r, _, fs in os.walk(path):
            for f in fs:
                p = os.path.join(r, f)
                items.append((os.path.relpath(p, path).replace("\\", "/").lower(), os.path.getsize(p)))
        return _digest(items), len(items), sum(i[1] for i in items)
    with zipfile.ZipFile(path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        # strip a single common top-level folder so zip-of-folder == the folder itself
        names = [i.filename.replace("\\", "/") for i in infos]
        top = {n.split("/", 1)[0] for n in names}
        strip = len(top) == 1 and all("/" in n for n in names)
        items = [((n.split("/", 1)[1] if strip else n).lower(), i.file_size) for n, i in zip(names, infos)]
        return _digest(items), len(infos), sum(i.file_size for i in infos)


def ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS capture_source_fingerprint (
        fingerprint TEXT PRIMARY KEY, capture_id INTEGER, source_path TEXT, file_count INTEGER,
        total_bytes INTEGER, status TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP)""")


def precheck(con, path):
    """-> (fingerprint, existing_row_or_None). Existing row == duplicate content, skip it."""
    ensure_table(con)
    fp, n, b = fingerprint(path)
    return fp, con.execute("SELECT capture_id,source_path,status FROM capture_source_fingerprint WHERE fingerprint=?", (fp,)).fetchone()


def record(con, path, capture_id, status="ingested"):
    ensure_table(con)
    fp, n, b = fingerprint(path)
    con.execute("INSERT OR REPLACE INTO capture_source_fingerprint (fingerprint,capture_id,source_path,file_count,total_bytes,status) VALUES (?,?,?,?,?,?)",
                (fp, capture_id, path, n, b, status))
    con.commit()
