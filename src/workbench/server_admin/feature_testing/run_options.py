"""#1484: typed, allow-listed run options for the headless bot's opt-in switches.

Names map 1:1 to xiheadless-dsp environment variables (PR #531). Values are booleans only and rendered as
``"1"``/``"0"``; unknown names or non-boolean values are rejected so nothing else reaches the subprocess env.
Defaults are the safe state: every shortcut off, position trace on.
"""
from __future__ import annotations

import json

RUN_OPTIONS: dict[str, dict] = {
    "XIBOT_QUICK_TRAVEL": {"default": False, "shortcut": True,
                           "label": "Quick travel: send zone-line request after a short walk, from anywhere"},
    "XIBOT_ALLOW_GM_WARP": {"default": False, "shortcut": True, "label": "Allow GM !zone / !pos teleports"},
    "XIBOT_GRIND_HERE": {"default": False, "shortcut": True,
                         "label": "Grind-only: fight where standing, no travel/shopping"},
    "XI_POS_TRACE": {"default": True, "shortcut": False, "label": "Log position/zone-in trace"},
    "XI_RDM_SHADOW_TRACE": {"default": False, "shortcut": False, "label": "RDM shadow policy trace"},
    "XIBOT_VERBOSE": {"default": False, "shortcut": False, "label": "Verbose logging"},
    "XI_TELEMETRY": {"default": False, "shortcut": False, "label": "Per-run telemetry JSONL (written to the run artifacts folder)", "path_valued": True},
}


def defaults() -> dict[str, bool]:
    return {name: spec["default"] for name, spec in RUN_OPTIONS.items()}


def resolve_run_options(options: object = None) -> dict[str, bool]:
    """Defaults overlaid with ``options``. Raises ValueError on unknown keys or non-bool values."""
    if options is None:
        return defaults()
    if not isinstance(options, dict):
        raise ValueError("run options must be an object of boolean values")
    unknown = sorted(str(k) for k in options if k not in RUN_OPTIONS)
    if unknown:
        raise ValueError("unknown run option(s): " + ", ".join(unknown))
    bad = sorted(k for k, v in options.items() if not isinstance(v, bool))
    if bad:
        raise ValueError("run option values must be true or false: " + ", ".join(bad))
    return {**defaults(), **options}


def env_for(options: dict[str, bool], telemetry_path: str | None = None) -> dict[str, str]:
    """Environment entries for an already-resolved option set.

    XI_TELEMETRY is a file path in xiheadless (any non-empty value enables it), so it is set to ``telemetry_path``
    when on and omitted when off; callers must also drop any ambient value.
    """
    env = {}
    for name, spec in RUN_OPTIONS.items():
        if spec.get("path_valued"):
            if options[name] and telemetry_path:
                env[name] = telemetry_path
        else:
            env[name] = "1" if options[name] else "0"
    return env


def shortcuts_enabled(options: dict[str, bool]) -> list[str]:
    return [name for name, spec in RUN_OPTIONS.items() if spec["shortcut"] and options.get(name)]


def to_json(options: dict[str, bool]) -> str:
    return json.dumps(options, sort_keys=True)


def from_json(text: str | None) -> dict[str, bool] | None:
    """Stored options, or None when the run predates #1484 or the stored value is unusable."""
    if not text:
        return None
    try:
        return resolve_run_options(json.loads(text))
    except (ValueError, TypeError):
        return None
