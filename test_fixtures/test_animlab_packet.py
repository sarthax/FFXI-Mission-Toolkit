"""Standalone checks for workbench.client.animlab (packet codec, bridge, observations)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from workbench.client.animlab import observations, packet  # noqa: E402
from workbench.client.animlab.bridge import Bridge, MAX_SWEEP  # noqa: E402

MUMOR = 17093309
TEMPLATE = bytes.fromhex(packet.FINISH_TEMPLATE_HEX.replace(" ", ""))


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    p = packet.parse(TEMPLATE)
    check(p["actor"] == MUMOR, p)
    check(p["category"] == 11, p)
    check(p["param"] == 2900, p)
    check(p["anim"] == 2038, p)

    rebuilt = packet.build_finish(MUMOR, p["target"], 2038, 2900)
    check(rebuilt == TEMPLATE, "build_finish must round-trip the template")
    check(packet.parse(packet.build_finish(1, 2, 2037, 2899))["anim"] == 2037, "anim patch")

    r = packet.parse(packet.build_ready(MUMOR))
    check(r["category"] == 7 and r["param"] == 24931 and r["actor"] == MUMOR, r)

    with tempfile.TemporaryDirectory() as td:
        b = Bridge(td)
        b.find("Mumor")
        b.play(2037, 2899)
        b.sweep(2036, 2042, 8, 2899)
        lines = b.inbox.read_text(encoding="utf-8").splitlines()
        check(lines[1].split("\t")[1:] == ["play", "2037", "2899"], lines)
        try:
            b.sweep(0, MAX_SWEEP + 5, 8, 1)
            raise AssertionError("range cap not enforced")
        except ValueError:
            pass
        b.outbox.write_text("12:00:00.000\tfound\tMumor\t17093309\n", encoding="utf-8")
        check(b.results()[0].kind == "found", "outbox parse")

        store = Path(td) / "obs.json"
        observations.record("Mumor", 2037, 2899, "correct", path=store)
        observations.record("Mumor", 2037, 2899, "wrong", path=store)
        check(observations.confirmed(path=store) == [], "latest verdict wins")
    from workbench.client.animlab import panel  # noqa: E402
    sql = panel.export_sql([{"mob": "Mumor", "anim": 2037, "skill": 2899, "note": "x"}])
    check("2037" in sql and sql.startswith("--"), "export_sql")
    check(callable(panel.make_handler), "panel handler")
    print("animlab: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
