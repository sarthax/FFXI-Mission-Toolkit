"""Reference-source adapters and evidence handling."""

from __future__ import annotations

from typing import Any


def seed_runtime_reference_graphs(con) -> list[dict[str, Any]]:
    """Load registered reference graph bundles into a canonical graph connection.

    Add future reference scenarios here; GUI consumers deliberately invoke this registry
    rather than naming any individual game feature or scenario.
    """
    from .absolute_virtue_demo import seed_reference_graph

    return [seed_reference_graph(con)]
