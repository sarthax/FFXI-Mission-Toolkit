"""Source-backed animation metadata shared by zone viewers/editors.

Persistent npc_list.render fields and transient FOURCC visual animations are different client
mechanisms. This module keeps them separate and reads the configured LandSandBoat checkout at runtime:

- data/enums/animation.yaml -> xi.animation byte values used by Render.animation
- literal setAnimationSub(N) calls -> observed sub-animation evidence
- scripts/enum/animation_string.lua -> named FOURCC entityAnimationPacket effects

Sub-animation labels are evidence summaries, not universal semantics: the same byte can mean
different things on different models.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import re

import yaml

from workbench.devtools.indexing import build_lsb_index

LSB_ROOT = build_lsb_index.LSB_ROOT
ANIMATION_YAML = LSB_ROOT / "data" / "enums" / "animation.yaml"
ANIMATION_STRING_LUA = LSB_ROOT / "scripts" / "enum" / "animation_string.lua"

FALLBACK_ANIMATIONS = {
    0: "none", 1: "attack", 2: "despawn", 3: "death", 4: "event", 5: "chocobo",
    6: "fishing", 8: "open_door", 9: "close_door", 10: "elevator_up",
    11: "elevator_down", 32: "fishing_npc", 33: "healing", 44: "synth",
    47: "sit", 48: "ranged", 85: "mount", 90: "trust",
}

SUB_RE = re.compile(r":setAnimationSub\(\s*(\d+)\s*\)")
MODEL_RE = re.compile(r":setModelId\(\s*(\d+)\s*\)")
ANIM_STRING_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*['\"](.{4})['\"]")


def _label(name: str) -> str:
    return str(name).replace("_", " ").strip()


def animation_values() -> list[dict]:
    values = dict(FALLBACK_ANIMATIONS)
    source = "fallback"
    if ANIMATION_YAML.is_file():
        try:
            raw = yaml.safe_load(ANIMATION_YAML.read_text(encoding="utf-8")) or {}
            parsed = raw.get("values") or {}
            values = {int(v): str(k) for k, v in parsed.items()}
            source = str(ANIMATION_YAML.relative_to(LSB_ROOT)).replace("\\", "/")
        except Exception:
            pass
    return [
        {"value": value, "name": name, "label": _label(name), "source": source}
        for value, name in sorted(values.items())
    ]


def animation_strings() -> list[dict]:
    out = []
    if not ANIMATION_STRING_LUA.is_file():
        return out
    for lineno, line in enumerate(
        ANIMATION_STRING_LUA.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
    ):
        m = ANIM_STRING_RE.match(line)
        if not m:
            continue
        out.append({
            "name": m.group(1),
            "fourcc": m.group(2),
            "line": lineno,
            "source": str(ANIMATION_STRING_LUA.relative_to(LSB_ROOT)).replace("\\", "/"),
        })
    return out


def subanimation_evidence(max_samples_per_value: int = 12) -> list[dict]:
    found = defaultdict(list)
    scripts = LSB_ROOT / "scripts"
    if not scripts.is_dir():
        return []
    for path in scripts.rglob("*.lua"):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        rel = str(path.relative_to(LSB_ROOT)).replace("\\", "/")
        for idx, line in enumerate(lines):
            m = SUB_RE.search(line)
            if not m:
                continue
            value = int(m.group(1))
            before = lines[max(0, idx - 5):idx + 1]
            model_id = None
            for context_line in reversed(before):
                mm = MODEL_RE.search(context_line)
                if mm:
                    model_id = int(mm.group(1))
                    break
            sample = {
                "source": rel,
                "line": idx + 1,
                "text": line.strip()[:300],
                "model_id_nearby": model_id,
            }
            found[value].append(sample)

    out = []
    for value in sorted(found):
        samples = found[value]
        models = sorted({s["model_id_nearby"] for s in samples if s["model_id_nearby"] is not None})
        out.append({
            "value": value,
            "uses": len(samples),
            "nearby_model_ids": models,
            "samples": samples[:max_samples_per_value],
            "warning": "observed LSB script use; meaning remains model-dependent",
        })
    return out


@lru_cache(maxsize=1)
def metadata() -> dict:
    return {
        "animations": animation_values(),
        "subanimations": subanimation_evidence(),
        "animation_strings": animation_strings(),
        "notes": [
            "animation is the persistent Render.animation byte / xi.animation enum",
            "animation_sub is a raw model-dependent selector; observed values are evidence, not universal names",
            "entityAnimationPacket FOURCC strings are transient visual actions and are separate from npc_list.animation/animationsub",
        ],
        "lsb_root": str(LSB_ROOT),
    }
