"""Bridge observed Retail transitions into snapshot-aware identity resolution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import sqlite3
from typing import Any

from workbench.core.services.identity_resolver import IdentityResolution, resolve_identity
from workbench.runtime.observed_transition import ObservedTransition


EVENT_KINDS = {"EVENT", "EVENT_ID", "CSID", "EVENT_RESOURCE_ID"}


@dataclass(frozen=True)
class TransitionIdentityResolution:
    transition_id: str
    capture_id: str
    source_client_snapshot_id: str | None
    target_snapshot_id: str
    raw_event_id: str | None
    event_kind: str
    status: str
    identity: IdentityResolution | None = None
    reason: str | None = None


def resolve_transition_event(
    con: sqlite3.Connection,
    transition: ObservedTransition,
    *,
    target_snapshot_id: str,
    namespace: str = "EVENT",
) -> TransitionIdentityResolution:
    """Resolve a typed captured event from its originating client into a target snapshot.

    MESSAGE_OR_EVENT_ID is deliberately not auto-promoted to EVENT. Upstream packet/correlation
    evidence must first narrow the semantic kind.
    """
    raw_event_id = None if transition.event_id is None else str(transition.event_id)
    kind = str(transition.event_kind or "MESSAGE_OR_EVENT_ID").strip().upper()

    base = dict(
        transition_id=transition.transition_id,
        capture_id=transition.capture_id,
        source_client_snapshot_id=transition.client_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        raw_event_id=raw_event_id,
        event_kind=kind,
    )

    if not transition.client_snapshot_id:
        return TransitionIdentityResolution(
            status="SOURCE_CLIENT_SNAPSHOT_UNKNOWN",
            reason="Captured transition is not bound to the client snapshot that produced it.",
            **base,
        )
    if raw_event_id is None:
        return TransitionIdentityResolution(
            status="NO_EVENT_ID",
            reason="Observed transition has no event identifier to resolve.",
            **base,
        )
    if kind not in EVENT_KINDS:
        return TransitionIdentityResolution(
            status="EVENT_KIND_UNRESOLVED",
            reason=(
                "Raw capture identifier is not deterministically typed as an event/CSID; "
                "identity translation is withheld."
            ),
            **base,
        )

    identity = resolve_identity(
        con,
        source_snapshot_id=transition.client_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        namespace=namespace,
        source_numeric_id=raw_event_id,
        zone_key=transition.zone,
    )
    return TransitionIdentityResolution(
        status=identity.status,
        identity=identity,
        reason=identity.reason,
        **base,
    )


def resolution_dict(value: TransitionIdentityResolution) -> dict[str, Any]:
    data = asdict(value)
    return data
