"""Decompile a single event from the dist dataset."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .dataset import Dataset
from .decompile import decompile


def _default_dist() -> Path:
    return Path(os.environ.get("XI_DIST") or Path.cwd() / "dist")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("zone_id", type=int)
    p.add_argument("actor_id", type=int)
    p.add_argument("event_id", type=int)
    p.add_argument(
        "--idx",
        type=int,
        help="disambiguate when multiple events share event_id",
    )
    p.add_argument(
        "--block",
        type=int,
        default=None,
        help="block ordinal (default 0; some zones have multiple)",
    )
    p.add_argument("--dist", type=Path, default=_default_dist())
    p.add_argument("-o", "--out", type=Path)
    args = p.parse_args(argv)

    ds = Dataset.from_dist(args.dist)

    if args.idx is not None:
        block = args.block if args.block is not None else 0
        idx = args.idx
    else:
        matches = ds.events_for(args.zone_id, args.actor_id, args.event_id)
        if args.block is not None:
            matches = [m for m in matches if m["block"] == args.block]
        if not matches:
            print(
                f"no event matching event_id={args.event_id} on actor {args.actor_id} "
                f"in zone {args.zone_id}"
                + (f" block {args.block}" if args.block is not None else ""),
                file=sys.stderr,
            )
            return 1
        if len(matches) > 1:
            keys = [(m["block"], m["idx"]) for m in matches]
            print(
                f"warning: event_id={args.event_id} has {len(matches)} matches "
                f"(block,idx)={keys}; using {keys[0]}. "
                f"Pass --block / --idx to choose.",
                file=sys.stderr,
            )
        block = matches[0]["block"]
        idx = matches[0]["idx"]

    src = decompile(ds.fixture(args.zone_id, args.actor_id, idx, block=block))

    if args.out:
        args.out.write_text(src, encoding="utf-8")
    else:
        sys.stdout.write(src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
