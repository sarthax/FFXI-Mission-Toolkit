"""Resolve persisted Live Client replay preferences with opt-in environment overrides."""
from __future__ import annotations

from collections.abc import Mapping


def effective_replay_configuration(settings: Mapping[str, str],
                                   environment: Mapping[str, str]) -> dict[str, str]:
    """Generate bootstrap variables; disabled or non-autoconnect sources stay off."""
    env_file = str(environment.get("FFXI_LIVE_REPLAY_FILE", "")).strip()
    env_client = str(environment.get("FFXI_LIVE_REPLAY_CLIENT", "")).strip()
    if env_file or env_client:
        return {"FFXI_LIVE_REPLAY_FILE": env_file,
                "FFXI_LIVE_REPLAY_CLIENT": env_client}
    if settings.get("live_client_source") != "replay" or settings.get("live_client_auto_connect") != "1":
        return {}
    return {"FFXI_LIVE_REPLAY_FILE": str(settings.get("live_client_replay_file", "")).strip(),
            "FFXI_LIVE_REPLAY_CLIENT": str(settings.get("live_client_replay_client", "")).strip()}
