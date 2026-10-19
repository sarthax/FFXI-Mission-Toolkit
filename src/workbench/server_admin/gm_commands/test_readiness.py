"""Read-only join between planned feature tests and the selected DSP GM Lua catalog."""
from __future__ import annotations

import json
from pathlib import Path

from .catalog import catalog_commands


def resolve_test_utilities(server_root: str | Path, plan_path: str | Path) -> dict:
    """No execution: missing commands are reported rather than assumed available."""
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    commands = {item["name"]: item for item in catalog_commands(server_root)}
    features = []
    for feature in plan.get("features", []):
        resolved = []
        for name in feature.get("existing_gm_candidates", []):
            command = commands.get(name)
            resolved.append({
                "name": name,
                "availability": "found_unreviewed" if command else "not_found",
                "usage": command.get("usage") if command else None,
                "permission": command.get("permission") if command else None,
                "source_path": command.get("source_path") if command else None,
                "execution_enabled": False,
            })
        features.append({"id": feature["id"], "commands": resolved})
    return {"schema_version": 1, "server_root": str(Path(server_root).resolve()),
            "features": features, "execution_enabled": False}
