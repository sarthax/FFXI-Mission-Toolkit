"""Batch decompile every event in the dist dataset.

Reports OK / unknown-opcode / other-failure counts. Use ``--limit`` to bound
wall time. Uses ``--workers`` (default = cpu_count) to parallelize.
"""

from __future__ import annotations

import argparse
import collections
import multiprocessing
import os
import time
from pathlib import Path

from xi_events.dataset import Dataset
from xi_events.decompile import decompile


def _default_dist() -> Path:
    return Path(os.environ.get("XI_DIST") or Path.cwd() / "dist")


_WORKER_DS: Dataset | None = None


def _worker_init(dist_dir: str) -> None:
    global _WORKER_DS
    _WORKER_DS = Dataset.from_dist(dist_dir)


def _worker(work: tuple[int, int, int, int]) -> tuple[str, int | None, str | None]:
    zone, actor, block, idx = work
    try:
        decompile(_WORKER_DS.fixture(zone, actor, idx, block=block), comments=False)
        return ("ok", None, None)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("unknown opcode"):
            return ("miss", int(msg.split()[2], 16), None)
        return ("fail", None, msg)
    except Exception as e:
        return ("fail", None, f"{type(e).__name__}: {e}")


def run(dist_dir: Path, limit: int | None, workers: int, verbose: bool) -> None:
    ds = Dataset.from_dist(dist_dir)
    work = [
        (z, a, b, idx)
        for (z, a, b, idx), rec in ds.events.items()
        if rec["event_id"] >= 0 and rec["event_id"] != 65535
    ]
    if limit is not None:
        work = work[:limit]
    del ds  # free before spawning workers; each will load its own copy

    ok = 0
    missing: collections.Counter[int] = collections.Counter()
    failures: list[str] = []
    start = time.time()

    with multiprocessing.Pool(
        processes=workers,
        initializer=_worker_init,
        initargs=(str(dist_dir),),
    ) as pool:
        for kind, code, msg in pool.imap_unordered(_worker, work, chunksize=200):
            if kind == "ok":
                ok += 1
            elif kind == "miss":
                missing[code] += 1
            else:
                failures.append(msg)
                if verbose:
                    print(f"[FAIL] {msg[:120]}")

    elapsed = time.time() - start
    print(f"\n=== summary ({len(work)} events, {elapsed:.1f}s, {workers} workers) ===")
    print(f"OK: {ok}   missing-op: {sum(missing.values())}   other: {len(failures)}")
    if missing:
        print("\nmissing opcodes:")
        for code, n in missing.most_common():
            print(f"  0x{code:02X}  x{n}")
    if failures:
        kinds: collections.Counter[str] = collections.Counter()
        for msg in failures:
            kinds[msg.split(":")[0][:60]] += 1
        print("\nfailures by kind:")
        for k, n in kinds.most_common():
            print(f"  x{n}  {k}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dist", type=Path, default=_default_dist())
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    run(args.dist, args.limit, args.workers, args.verbose)


if __name__ == "__main__":
    main()
