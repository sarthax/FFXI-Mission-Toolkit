"""Live FFXI client development bridge contracts.

This package deliberately contains no process-memory offsets or writes.
An adapter must establish version compatibility before reporting live state.
"""
from .models import ClientSnapshot, Position, Waypoint, PathSample, DevelopmentAction, validate_action

__all__ = ["ClientSnapshot", "Position", "Waypoint", "PathSample", "DevelopmentAction", "validate_action"]
