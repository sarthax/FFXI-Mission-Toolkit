"""Configuration manager for the Packetlyzer Analyzer.

Handles loading, saving, and validating user configuration with
safe defaults and value clamping for all settings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Config:
    """Analyzer configuration with validated defaults.

    All numeric values are clamped to their valid ranges on load.
    Missing or invalid values fall back to defaults silently.
    """

    window_width: int = 900       # 400–3840
    window_height: int = 600      # 300–2160
    port: int = 52985             # 1024–65535
    max_packets: int = 5000       # 100–100000
    filter_string: str = ""       # max 256 chars
    auto_scroll: bool = True
    ffxi_path: str = ""           # Path to FFXI install (auto-detect if empty)
    theme: str = "Dark"           # Color theme name (Dark, Light, FFXI)
    blocked_opcodes: list = None  # Opcode filter list (list of hex strings)
    passed_opcodes: list = None   # Passed-mode opcode list (list of hex strings)
    apply_filters_to_logging: bool = False  # Whether filters also apply to logging
    filter_mode: str = "blocked"  # "blocked" or "passed"
    last_zone_id: int = 0         # Last known zone ID (for resolver bootstrap)

    @classmethod
    def load(cls, path: str) -> "Config":
        """Load configuration from a JSON file.

        Returns a Config with defaults for any missing or invalid values.
        Values outside valid ranges are clamped to the nearest boundary.
        Returns default Config silently if the file is missing or corrupt.
        """
        config = cls()
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return config

        if not isinstance(data, dict):
            return config

        # window_width: int, 400–3840
        if isinstance(data.get("window_width"), (int, float)) and not isinstance(
            data.get("window_width"), bool
        ):
            config.window_width = _clamp(int(data["window_width"]), 400, 3840)

        # window_height: int, 300–2160
        if isinstance(data.get("window_height"), (int, float)) and not isinstance(
            data.get("window_height"), bool
        ):
            config.window_height = _clamp(int(data["window_height"]), 300, 2160)

        # port: int, 1024–65535
        if isinstance(data.get("port"), (int, float)) and not isinstance(
            data.get("port"), bool
        ):
            config.port = _clamp(int(data["port"]), 1024, 65535)

        # max_packets: int, 100–100000
        if isinstance(data.get("max_packets"), (int, float)) and not isinstance(
            data.get("max_packets"), bool
        ):
            config.max_packets = _clamp(int(data["max_packets"]), 100, 100000)

        # filter_string: str, max 256 chars
        if isinstance(data.get("filter_string"), str):
            config.filter_string = data["filter_string"][:256]

        # auto_scroll: bool
        if isinstance(data.get("auto_scroll"), bool):
            config.auto_scroll = data["auto_scroll"]

        # ffxi_path: str (filesystem path to FFXI install)
        if isinstance(data.get("ffxi_path"), str):
            config.ffxi_path = data["ffxi_path"]

        # theme: str
        if isinstance(data.get("theme"), str):
            config.theme = data["theme"]

        # blocked_opcodes: list of hex strings
        if isinstance(data.get("blocked_opcodes"), list):
            config.blocked_opcodes = [
                str(op) for op in data["blocked_opcodes"] if isinstance(op, str)
            ]

        # passed_opcodes: list of hex strings
        if isinstance(data.get("passed_opcodes"), list):
            config.passed_opcodes = [
                str(op) for op in data["passed_opcodes"] if isinstance(op, str)
            ]

        # apply_filters_to_logging: bool
        if isinstance(data.get("apply_filters_to_logging"), bool):
            config.apply_filters_to_logging = data["apply_filters_to_logging"]

        # filter_mode: str ("blocked" or "passed")
        if isinstance(data.get("filter_mode"), str):
            if data["filter_mode"] in ("blocked", "passed"):
                config.filter_mode = data["filter_mode"]

        # last_zone_id: int
        if isinstance(data.get("last_zone_id"), (int, float)) and not isinstance(
            data.get("last_zone_id"), bool
        ):
            config.last_zone_id = int(data["last_zone_id"])

        return config

    def save(self, path: str) -> None:
        """Write current configuration values to a JSON file with pretty formatting."""
        data = {
            "window_width": self.window_width,
            "window_height": self.window_height,
            "port": self.port,
            "max_packets": self.max_packets,
            "filter_string": self.filter_string,
            "auto_scroll": self.auto_scroll,
            "ffxi_path": self.ffxi_path,
            "theme": self.theme,
            "blocked_opcodes": self.blocked_opcodes if self.blocked_opcodes else [],
            "passed_opcodes": self.passed_opcodes if self.passed_opcodes else [],
            "apply_filters_to_logging": self.apply_filters_to_logging,
            "filter_mode": self.filter_mode,
            "last_zone_id": self.last_zone_id,
        }
        Path(path).write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )


def _clamp(value: int, minimum: int, maximum: int) -> int:
    """Clamp an integer value to [minimum, maximum]."""
    return max(minimum, min(maximum, value))
