#!/usr/bin/env python3
"""Regression for capture ObservedTransition -> target identity resolution."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.core.services.identity_resolver import (
    IdentitySnapshot,
    ingest_dialog_records,
    register_snapshot,
)
from workbench.runtime.identity_bridge import resolve_transition_event
from workbench.runtime.observed_transition import normalize_transition


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        con = sqlite3.connect(Path(td) / "workbench.db")

        register_snapshot(
            con,
            IdentitySnapshot(
                snapshot_id="client:new",
                snapshot_type="CLIENT",
                family="RETAIL",
                version="new",
            ),
        )
        register_snapshot(
            con,
            IdentitySnapshot(
                snapshot_id="client:old",
                snapshot_type="CLIENT",
                family="RETAIL",
                version="old",
            ),
        )
        ingest_dialog_records(
            con,
            snapshot_id="client:new",
            zone_key="NORTH_GUSTABERG_S",
            entries={11: "You hand over the supplies."},
        )
        ingest_dialog_records(
            con,
            snapshot_id="client:old",
            zone_key="NORTH_GUSTABERG_S",
            entries={10: "You hand over the supplies."},
        )
        con.commit()

        typed = normalize_transition(
            transition_id="capture:27:transition:1",
            capture_id=27,
            client_snapshot_id="client:new",
            zone="NORTH_GUSTABERG_S",
            event_id=11,
            event_kind="CSID",
            evidence_ids=["capture:27:event:11"],
        )
        resolved = resolve_transition_event(
            con,
            typed,
            target_snapshot_id="client:old",
        )
        assert resolved.status == "TARGET_EQUIVALENT", resolved
        assert resolved.identity is not None, resolved
        assert resolved.identity.target_numeric_id == "10", resolved

        # Conservative rule: an untyped numeric observation is not translated as a CSID.
        untyped = normalize_transition(
            transition_id="capture:27:transition:2",
            capture_id=27,
            client_snapshot_id="client:new",
            zone="NORTH_GUSTABERG_S",
            event_id=11,
            event_kind="MESSAGE_OR_EVENT_ID",
            evidence_ids=["capture:27:raw:11"],
        )
        withheld = resolve_transition_event(
            con,
            untyped,
            target_snapshot_id="client:old",
        )
        assert withheld.status == "EVENT_KIND_UNRESOLVED", withheld
        assert withheld.identity is None, withheld

        missing_build = normalize_transition(
            transition_id="capture:27:transition:3",
            capture_id=27,
            zone="NORTH_GUSTABERG_S",
            event_id=11,
            event_kind="CSID",
        )
        unknown = resolve_transition_event(
            con,
            missing_build,
            target_snapshot_id="client:old",
        )
        assert unknown.status == "SOURCE_CLIENT_SNAPSHOT_UNKNOWN", unknown

        con.close()

    print("capture identity bridge self-test: PASS")


if __name__ == "__main__":
    main()
