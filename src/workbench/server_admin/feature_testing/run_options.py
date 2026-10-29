"""#1484: per-run opt-in switches for the headless bot, passed as environment variables and recorded with the run.

Source of truth for the variables is xiheadless-dsp docs/ENV_FLAGS.md. Boolean switches there match exactly "1", so an
"off" switch is *removed* from the child environment (an operator shell that already exports one must not turn a
shortcut on by accident). XIBOT_VERBOSE is the exception: unset means verbose, so off is sent as "0".
XI_TELEMETRY is a file path rather than a boolean and is deliberately not offered here.

Pure functions only; nothing here launches anything or widens what the launcher may run.
"""
from __future__ import annotations

from typing import Mapping, MutableMapping

# env var -> (label, default, shortcut, value sent when off: None = remove the variable)
_SWITCHES: dict[str, dict] = {
    "XIBOT_QUICK_TRAVEL": {"label": "Quick travel", "default": False, "shortcut": True, "off": None,
                           "help": "Send the zone-line request after a short walk, from anywhere."},
    "XIBOT_ALLOW_GM_WARP": {"label": "Allow GM warps", "default": False, "shortcut": True, "off": None,
                            "help": "Allow GM !zone / !pos teleports."},
    "XIBOT_GRIND_HERE": {"label": "Grind here only", "default": False, "shortcut": True, "off": None,
                         "help": "Fight where standing; skip travel and shopping."},
    "XI_POS_TRACE": {"label": "Position trace", "default": True, "shortcut": False, "off": None,
                     "help": "Log position and zone-in trace for diagnosis."},
    "XI_RDM_SHADOW_TRACE": {"label": "RDM shadow trace", "default": False, "shortcut": False, "off": None,
                            "help": "Log the RDM shadow policy trace (diagnostic only)."},
    "XIBOT_VERBOSE": {"label": "Verbose logging", "default": False, "shortcut": False, "off": "0",
                      "help": "Verbose bot logging."},
}


def switches() -> list[dict]:
    """The offered switches in display order, for the launcher panel."""
    return [{"env": env, "label": s["label"], "default": s["default"], "shortcut": s["shortcut"], "help": s["help"]}
            for env, s in _SWITCHES.items()]


def defaults() -> dict[str, bool]:
    return {env: s["default"] for env, s in _SWITCHES.items()}


def normalize(options: object = None) -> dict[str, bool]:
    """Full {ENV: bool} map: defaults overlaid with the requested choices. Unknown names or non-booleans are refused."""
    if options is None:
        return defaults()
    if not isinstance(options, Mapping):
        raise ValueError("run options must be an object of switch names to true/false")
    unknown = sorted(str(k) for k in options if k not in _SWITCHES)
    if unknown:
        raise ValueError("unknown run option: " + ", ".join(unknown))
    bad = sorted(k for k, v in options.items() if not isinstance(v, bool))
    if bad:
        raise ValueError("run option values must be true or false: " + ", ".join(bad))
    return {**defaults(), **dict(options)}


def apply_to_env(env: MutableMapping[str, str], options: object = None) -> dict[str, bool]:
    """Set or clear every offered switch in ``env`` and return the normalized choices that were applied."""
    chosen = normalize(options)
    for name, on in chosen.items():
        if on:
            env[name] = "1"
        elif _SWITCHES[name]["off"] is None:
            env.pop(name, None)
        else:
            env[name] = _SWITCHES[name]["off"]
    return chosen


def shortcuts_enabled(options: object) -> list[str]:
    """Labels of the shortcut switches that were on, so a result can say "this run used shortcuts"."""
    chosen = normalize(options)
    return [s["label"] for env, s in _SWITCHES.items() if s["shortcut"] and chosen[env]]
