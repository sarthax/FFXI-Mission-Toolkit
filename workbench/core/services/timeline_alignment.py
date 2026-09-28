"""Timeline alignment between gameplay video and runtime capture clocks.

Anchors are explicit observations supplied by a user or later correlation logic.  The model never
assumes that independent capture tables share a clock.  Anchors are grouped by clock_kind, and a
fit is produced only within one clock basis.

With one anchor, the model is offset-only (slope=1).  With two or more anchors it uses ordinary
least squares for capture_time = intercept + slope * video_time and reports residual/drift
diagnostics so callers can judge whether clocks actually stay aligned.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3
import uuid


CLOCK_VIDEO_RELATIVE = "VIDEO_RELATIVE_SECONDS"
CLOCK_CAPTURE_RELATIVE = "CAPTURE_RELATIVE_SECONDS"
CLOCK_EPOCH_SECONDS = "EPOCH_SECONDS"
CLOCK_LOGGER_SECONDS = "LOGGER_SECONDS"
CLOCK_KINDS = {
    CLOCK_CAPTURE_RELATIVE,
    CLOCK_EPOCH_SECONDS,
    CLOCK_LOGGER_SECONDS,
}


@dataclass(frozen=True)
class AlignmentModel:
    capture_id: int
    clock_kind: str
    anchor_count: int
    slope: float
    intercept: float
    drift_ppm: float
    rms_error_seconds: float
    max_error_seconds: float
    video_min: float | None
    video_max: float | None

    def video_to_capture(self, video_seconds: float) -> float:
        return self.intercept + self.slope * float(video_seconds)

    def capture_to_video(self, capture_seconds: float) -> float | None:
        if self.slope == 0:
            return None
        return (float(capture_seconds) - self.intercept) / self.slope

    def as_dict(self) -> dict:
        return {
            "capture_id": self.capture_id,
            "clock_kind": self.clock_kind,
            "anchor_count": self.anchor_count,
            "slope": self.slope,
            "intercept": self.intercept,
            "drift_ppm": self.drift_ppm,
            "rms_error_seconds": self.rms_error_seconds,
            "max_error_seconds": self.max_error_seconds,
            "video_min": self.video_min,
            "video_max": self.video_max,
        }


def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS capture_alignment_anchors (
            capture_id INTEGER NOT NULL,
            anchor_id TEXT NOT NULL,
            video_ts REAL NOT NULL,
            capture_ts REAL NOT NULL,
            clock_kind TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'MANUAL',
            video_ref TEXT,
            capture_ref TEXT,
            label TEXT,
            confidence TEXT NOT NULL DEFAULT 'USER_CONFIRMED',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (capture_id, anchor_id)
        );
        CREATE INDEX IF NOT EXISTS idx_capture_alignment_clock
            ON capture_alignment_anchors(capture_id, clock_kind, video_ts);
    """)
    con.commit()


def add_anchor(
    con: sqlite3.Connection,
    capture_id: int,
    *,
    video_ts: float,
    capture_ts: float,
    clock_kind: str,
    source_type: str = "MANUAL",
    video_ref: str | None = None,
    capture_ref: str | None = None,
    label: str | None = None,
    confidence: str = "USER_CONFIRMED",
    notes: str | None = None,
    anchor_id: str | None = None,
) -> str:
    if clock_kind not in CLOCK_KINDS:
        raise ValueError(f"unsupported clock_kind {clock_kind!r}")
    video_ts = float(video_ts)
    capture_ts = float(capture_ts)
    if not math.isfinite(video_ts) or not math.isfinite(capture_ts):
        raise ValueError("alignment timestamps must be finite numbers")
    if video_ts < 0:
        raise ValueError("video_ts must be >= 0")
    init_db(con)
    aid = anchor_id or f"align-{uuid.uuid4().hex[:16]}"
    con.execute(
        """INSERT OR REPLACE INTO capture_alignment_anchors
           (capture_id,anchor_id,video_ts,capture_ts,clock_kind,source_type,
            video_ref,capture_ref,label,confidence,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            int(capture_id), aid, video_ts, capture_ts, clock_kind,
            source_type or "MANUAL", video_ref, capture_ref, label,
            confidence or "USER_CONFIRMED", notes,
        ),
    )
    con.commit()
    return aid


def delete_anchor(con: sqlite3.Connection, capture_id: int, anchor_id: str) -> bool:
    init_db(con)
    cur = con.execute(
        "DELETE FROM capture_alignment_anchors WHERE capture_id=? AND anchor_id=?",
        (int(capture_id), anchor_id),
    )
    con.commit()
    return cur.rowcount > 0


def list_anchors(con: sqlite3.Connection, capture_id: int) -> list[dict]:
    init_db(con)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT * FROM capture_alignment_anchors
           WHERE capture_id=? ORDER BY clock_kind,video_ts,created_at,anchor_id""",
        (int(capture_id),),
    ).fetchall()
    return [dict(row) for row in rows]


def fit_alignment(
    con: sqlite3.Connection,
    capture_id: int,
    clock_kind: str,
) -> AlignmentModel | None:
    init_db(con)
    rows = con.execute(
        """SELECT video_ts,capture_ts FROM capture_alignment_anchors
           WHERE capture_id=? AND clock_kind=? ORDER BY video_ts,anchor_id""",
        (int(capture_id), clock_kind),
    ).fetchall()
    if not rows:
        return None

    xs = [float(r[0]) for r in rows]
    ys = [float(r[1]) for r in rows]
    n = len(xs)

    if n == 1:
        slope = 1.0
        intercept = ys[0] - xs[0]
    else:
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        denom = sum((x - mean_x) ** 2 for x in xs)
        if denom == 0:
            slope = 1.0
            intercept = sum(y - x for x, y in zip(xs, ys)) / n
        else:
            slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
            intercept = mean_y - slope * mean_x

    errors = [(intercept + slope * x) - y for x, y in zip(xs, ys)]
    rms = math.sqrt(sum(e * e for e in errors) / n)
    max_error = max(abs(e) for e in errors)

    return AlignmentModel(
        capture_id=int(capture_id),
        clock_kind=clock_kind,
        anchor_count=n,
        slope=slope,
        intercept=intercept,
        drift_ppm=(slope - 1.0) * 1_000_000.0,
        rms_error_seconds=rms,
        max_error_seconds=max_error,
        video_min=min(xs),
        video_max=max(xs),
    )


def alignment_summary(con: sqlite3.Connection, capture_id: int) -> dict:
    anchors = list_anchors(con, capture_id)
    kinds = sorted({a["clock_kind"] for a in anchors})
    models = {}
    for kind in kinds:
        model = fit_alignment(con, capture_id, kind)
        if model is not None:
            models[kind] = model.as_dict()
    return {
        "capture_id": int(capture_id),
        "anchors": anchors,
        "models": models,
    }
