"""Load the four ndjson.gz files into in-memory indexes.

Schema v2: per-event ``byte_code``, keyed by ``(zone_id, actor_id, block, idx)``.

A few zones (e.g. Aht Urhgan Whitegate phases) ship two event DATs that share
an ``actor_id``; ``block`` (default 0) disambiguates them. ``event_id`` is
not unique within a block — fragments share ``-1``.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator


@dataclass
class Fixture:
    zone_id: int
    actor_id: int
    block: int
    idx: int
    event_id: int
    bytecode: bytes
    imed_data: list[int]
    strings: dict[int, str]
    entities: dict[int, str]
    items: dict[int, str] = field(default_factory=dict)
    entrypoint: int = 0  # original byte offset within the actor-block frame
    # Block-wide bytecode (all events in this actor-block stitched at their
    # absolute offsets). Set by ``Dataset.fixture()``. Required for events that
    # JUMP_TO_POSITION into subroutines living in sibling events. When None,
    # decompile falls back to ``bytecode`` zero-padded to ``entrypoint``.
    block_bytecode: bytes | None = None


@dataclass
class Dataset:
    actors: dict[tuple[int, int, int], dict] = field(default_factory=dict)
    events: dict[tuple[int, int, int, int], dict] = field(default_factory=dict)
    strings: dict[int, dict[int, str]] = field(default_factory=dict)
    entities: dict[int, dict[int, str]] = field(default_factory=dict)
    items: dict[int, str] = field(default_factory=dict)
    _block_bytecode_cache: dict[tuple[int, int, int], bytes] = field(
        default_factory=dict, repr=False
    )

    @classmethod
    def from_dist(cls, dist_dir: Path | str) -> "Dataset":
        dist_dir = Path(dist_dir)
        ds = cls()

        for rec in _stream(dist_dir / "events_actors.ndjson.gz"):
            ds.actors[(rec["zone_id"], rec["actor_id"], rec["block"])] = rec

        for rec in _stream(dist_dir / "events.ndjson.gz"):
            ds.events[(rec["zone_id"], rec["actor_id"], rec["block"], rec["idx"])] = rec

        for rec in _stream(dist_dir / "strings.ndjson.gz"):
            ds.strings.setdefault(rec["zone_id"], {})[rec["string_id"]] = rec["content"]

        for rec in _stream(dist_dir / "entities.ndjson.gz"):
            ds.entities.setdefault(rec["zone_id"], {})[rec["entity_id"]] = rec["name"]

        for rec in _stream_optional(dist_dir / "items.ndjson.gz"):
            name = rec.get("name")
            if isinstance(name, dict):
                name = name.get("english") or name.get("english_log_single")
            if name:
                ds.items[rec["id"]] = name

        return ds

    def event(self, zone_id: int, actor_id: int, idx: int, *, block: int = 0) -> dict:
        try:
            return self.events[(zone_id, actor_id, block, idx)]
        except KeyError:
            raise KeyError(
                f"event idx={idx} not found on actor {actor_id} block {block} "
                f"(zone {zone_id})"
            ) from None

    def actor(self, zone_id: int, actor_id: int, *, block: int = 0) -> dict:
        try:
            return self.actors[(zone_id, actor_id, block)]
        except KeyError:
            raise KeyError(
                f"actor {actor_id} block {block} not found in zone {zone_id}"
            ) from None

    def events_for(self, zone_id: int, actor_id: int, event_id: int) -> list[dict]:
        """All events on ``(zone, actor)`` matching ``event_id``, across all
        blocks. Returned ordered by ``(block, idx)``."""
        return sorted(
            (
                rec
                for (z, a, _b, _i), rec in self.events.items()
                if z == zone_id and a == actor_id and rec["event_id"] == event_id
            ),
            key=lambda r: (r["block"], r["idx"]),
        )

    def fixture(
        self, zone_id: int, actor_id: int, idx: int, *, block: int = 0
    ) -> Fixture:
        ev = self.event(zone_id, actor_id, idx, block=block)
        ac = self.actor(zone_id, actor_id, block=block)
        return Fixture(
            zone_id=zone_id,
            actor_id=actor_id,
            block=block,
            idx=idx,
            event_id=ev["event_id"],
            bytecode=bytes.fromhex(ev["byte_code"]),
            entrypoint=ev["entrypoint"],
            imed_data=ac["imed_data"],
            strings=self.strings.get(zone_id, {}),
            entities=self.entities.get(zone_id, {}),
            items=self.items,
            block_bytecode=self._block_bytecode(zone_id, actor_id, block),
        )

    def _block_bytecode(self, zone_id: int, actor_id: int, block: int) -> bytes:
        """Stitch all events in ``(zone, actor, block)`` into one buffer where
        each event's bytes live at their absolute offset. Cached per block."""
        key = (zone_id, actor_id, block)
        cached = self._block_bytecode_cache.get(key)
        if cached is not None:
            return cached

        siblings = [
            rec
            for (z, a, b, _i), rec in self.events.items()
            if z == zone_id and a == actor_id and b == block
        ]
        total = max(
            (rec["entrypoint"] + len(rec["byte_code"]) // 2 for rec in siblings),
            default=0,
        )
        buf = bytearray(total)
        for rec in siblings:
            ep = rec["entrypoint"]
            bc = bytes.fromhex(rec["byte_code"])
            buf[ep : ep + len(bc)] = bc

        out = bytes(buf)
        self._block_bytecode_cache[key] = out
        return out

    def iter_events(self) -> Iterator[tuple[int, int, int, int, int, str]]:
        """Yield ``(zone_id, actor_id, block, idx, event_id, zone_name)``."""
        for (z, a, b, idx), rec in self.events.items():
            yield z, a, b, idx, rec["event_id"], rec.get("zone_name", "?")


def _stream(path: Path) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                yield json.loads(line)


def _stream_optional(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    yield from _stream(path)
