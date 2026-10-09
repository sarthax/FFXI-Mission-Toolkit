"""Displayed observation consistency, separate from authorization and verification."""
from dataclasses import asdict
import hashlib
import json

from fastapi import HTTPException


def observation_token(registry, session_id, frame):
    generation = registry._generations.get(session_id)
    source = registry._clients.get(session_id) or registry._feeds.get(session_id)
    if generation is None or generation[0] is not source or registry.frame(session_id) is not frame:
        raise ValueError('observation changed; refresh before capturing')
    payload = json.dumps(asdict(frame), sort_keys=True, separators=(',', ':'), allow_nan=False)
    token = hashlib.sha256((generation[1] + payload).encode('utf-8')).hexdigest()
    if registry._generations.get(session_id) is not generation or registry.frame(session_id) is not frame:
        raise ValueError('observation changed; refresh before capturing')
    return token


def require_observation(registry, session_id, frame, expected_token):
    # Optional for compatibility with existing API clients. The console supplies it.
    if expected_token is None:
        return
    try:
        if observation_token(registry, session_id, frame) != expected_token:
            raise ValueError('observation changed; refresh before capturing')
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
