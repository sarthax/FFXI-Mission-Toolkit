"""Thin CLI for Anim Lab: python -m workbench.client.cli.anim_lab <command>."""
from __future__ import annotations

import argparse

from workbench.client.animlab import observations
from workbench.client.animlab.bridge import Bridge


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bridge-dir")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("find").add_argument("name")
    p = sub.add_parser("play")
    p.add_argument("anim", type=int)
    p.add_argument("--skill", type=int, default=2899)
    s = sub.add_parser("sweep")
    s.add_argument("lo", type=int)
    s.add_argument("hi", type=int)
    s.add_argument("--gap", type=float, default=8.0)
    s.add_argument("--skill", type=int, default=2899)
    sub.add_parser("stop")
    o = sub.add_parser("note")
    o.add_argument("mob")
    o.add_argument("anim", type=int)
    o.add_argument("skill", type=int)
    o.add_argument("verdict", choices=observations.VERDICTS)
    o.add_argument("text", nargs="?", default="")
    sub.add_parser("results")
    a = ap.parse_args(argv)
    if a.cmd == "note":
        print(observations.record(a.mob, a.anim, a.skill, a.verdict, a.text))
        return 0
    b = Bridge(a.bridge_dir)
    if a.cmd == "find":
        b.find(a.name)
    elif a.cmd == "play":
        b.play(a.anim, a.skill)
    elif a.cmd == "sweep":
        b.sweep(a.lo, a.hi, a.gap, a.skill)
    elif a.cmd == "stop":
        b.stop()
    elif a.cmd == "results":
        for r in b.results():
            print(r.stamp, r.kind, *r.args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
