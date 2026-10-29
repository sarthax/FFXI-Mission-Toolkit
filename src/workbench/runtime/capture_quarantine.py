"""Read-side filter that keeps quarantined (blocking, pending) captures out of cross-capture aggregates.

Core copy of ``captures.review_queue.exclude_sql`` so Core graph connectors need not import Captures.
Read-only: it never creates or migrates the review_queue table.
"""


def exclude_sql(con, col="capture_id"):
    """' AND <col> NOT IN (<quarantined captures>)', or '' when the queue is absent/unmigrated. Never raises."""
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_queue'").fetchone():
            return ""
        if "blocking" not in {row[1] for row in con.execute("PRAGMA table_info(review_queue)")}:
            return ""
        return (" AND %s NOT IN (SELECT capture_id FROM review_queue WHERE status='pending' "
                "AND capture_id IS NOT NULL AND blocking=1)" % col)
    except Exception:
        return ""
