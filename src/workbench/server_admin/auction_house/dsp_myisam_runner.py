"""Connection-state wrapper for the DSP MyISAM Test listing executor."""
from __future__ import annotations

from typing import Any

from .dsp_myisam_listing import execute_dsp_myisam_test_player_listing
from .legacy_test_executor import LegacyTestExecutionBlocked


def execute_dsp_myisam_test_player_listing_with_connection_guard(
    *, service, server_root, environment: dict[str, Any], **kwargs
) -> dict[str, Any]:
    """Run the compensating MyISAM path with deterministic autocommit semantics.

    `LOCK TABLES` plus mixed InnoDB/MyISAM behavior is easiest to reason about with
    autocommit enabled: every sequential write is durable immediately, so the core
    executor's compensating writes describe the actual recovery behavior instead of
    depending on the connector's default transaction state.
    """
    connection = service.connection
    if not hasattr(connection, "autocommit"):
        raise LegacyTestExecutionBlocked("DSP MyISAM Test path requires a connector with explicit autocommit control")

    previous = bool(connection.autocommit)
    try:
        connection.autocommit = True
        return execute_dsp_myisam_test_player_listing(
            service=service,
            server_root=server_root,
            environment=environment,
            **kwargs,
        )
    finally:
        try:
            connection.autocommit = previous
        except Exception:
            pass
