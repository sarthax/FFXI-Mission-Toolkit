"""File bridge between the toolkit and the animprobe Ashita addon.

The toolkit appends tab-separated command lines to ``inbox.txt``; the addon polls it by byte
offset and appends result lines to ``outbox.txt``. Plain text on both sides so the Lua addon
needs no JSON parser. Directory: ``<ashita>/addons/animprobe/bridge`` (or any override).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ASHITA_ROOT = Path("C:/ValhallaXI/Ashitav4-Beta")
MAX_SWEEP = 64          # refuse wild ranges that could feed the client junk ids
MAX_ANIM = 4095         # 12-bit field


def bridge_dir(ashita_root: Path | str = DEFAULT_ASHITA_ROOT) -> Path:
    return Path(ashita_root) / "addons" / "animprobe" / "bridge"


@dataclass
class Result:
    stamp: str
    kind: str
    args: list[str]


class Bridge:
    def __init__(self, directory: Path | str | None = None):
        self.dir = Path(directory) if directory else bridge_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.inbox = self.dir / "inbox.txt"
        self.outbox = self.dir / "outbox.txt"
        self._seq = 0

    def _send(self, *fields) -> int:
        self._seq += 1
        with self.inbox.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("\t".join(str(x) for x in (self._seq, *fields)) + "\n")
        return self._seq

    def find(self, name: str) -> int:
        return self._send("find", name)

    def play(self, anim: int, skill: int) -> int:
        if not 0 <= anim <= MAX_ANIM:
            raise ValueError("anim must be 0..4095")
        return self._send("play", anim, skill)

    def sweep(self, lo: int, hi: int, gap: float, skill: int) -> int:
        if not (0 <= lo <= hi <= MAX_ANIM) or hi - lo + 1 > MAX_SWEEP:
            raise ValueError(f"sweep must be within 0..{MAX_ANIM} and at most {MAX_SWEEP} ids")
        return self._send("sweep", lo, hi, gap, skill)

    def stop(self) -> int:
        return self._send("stop")

    def results(self) -> list[Result]:
        if not self.outbox.exists():
            return []
        out = []
        for line in self.outbox.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                out.append(Result(parts[0], parts[1], parts[2:]))
        return out

    def wait_for(self, kind: str, timeout: float = 30.0) -> Result | None:
        end = time.time() + timeout
        start = len(self.results())
        while time.time() < end:
            for r in self.results()[start:]:
                if r.kind == kind:
                    return r
            time.sleep(0.25)
        return None
