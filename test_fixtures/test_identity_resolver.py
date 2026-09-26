#!/usr/bin/env python3
"""Regression for snapshot-aware ID drift / identity resolution."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.core.services.identity_resolver import (
    IdentityRecord,
    IdentitySnapshot,
    compare_snapshots,
    ingest_dialog_records,
    register_snapshot,
    resolve_identity,
    persist_mapping,
    assess_identity_closure,
    upsert_record,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "workbench.db"
        con = sqlite3.connect(db)

        register_snapshot(
            con,
            IdentitySnapshot(
                snapshot_id="client:2019-12-04",
                snapshot_type="CLIENT",
                family="RETAIL",
                version="30191204_1",
            ),
        )
        register_snapshot(
            con,
            IdentitySnapshot(
                snapshot_id="client:2022-test",
                snapshot_type="CLIENT",
                family="RETAIL",
                version="2022-test",
            ),
        )

        old_rows = {
            10: "The seal bears the crest of the Republic.",
            11: "You hand over the supplies.",
            12: "Return when the preparations are complete.",
        }
        new_rows = {
            11: "The seal bears the crest of the Republic.",
            12: "You hand over the supplies.",
            13: "Return when the preparations are complete.",
        }

        ingest_dialog_records(
            con,
            snapshot_id="client:2019-12-04",
            zone_key="NORTH_GUSTABERG_S",
            entries=old_rows,
        )
        ingest_dialog_records(
            con,
            snapshot_id="client:2022-test",
            zone_key="NORTH_GUSTABERG_S",
            entries=new_rows,
        )
        con.commit()

        comparison = compare_snapshots(
            con,
            "client:2022-test",
            "client:2019-12-04",
            "EVENT",
            zone_key="NORTH_GUSTABERG_S",
        )
        assert len(comparison["drifted"]) == 3, comparison
        assert comparison["stable"] == [], comparison
        assert comparison["ambiguous"] == [], comparison

        resolution = resolve_identity(
            con,
            source_snapshot_id="client:2022-test",
            target_snapshot_id="client:2019-12-04",
            namespace="EVENT",
            source_numeric_id=11,
            zone_key="NORTH_GUSTABERG_S",
        )
        assert resolution.status == "TARGET_EQUIVALENT", resolution
        assert resolution.target_numeric_id == "10", resolution
        assert resolution.confidence == "INFERRED", resolution

        mapping = persist_mapping(
            con,
            resolution,
            evidence_ids=["evidence:capture:27:event:11", "evidence:client:2019:dialog:10"],
        )
        con.commit()
        row = con.execute(
            "SELECT target_numeric_id,status,confidence FROM identity_mappings WHERE mapping_id=?",
            (mapping.mapping_id,),
        ).fetchone()
        assert row == ("10", "TARGET_EQUIVALENT", "INFERRED"), row

        # Same numeric ID in another zone must not be treated as the same event.
        upsert_record(
            con,
            IdentityRecord(
                record_id="identity:client:2022-test:EVENT:OTHER_ZONE:11",
                snapshot_id="client:2022-test",
                namespace="EVENT",
                semantic_key="EVENT|OTHER_ZONE|*|*|different",
                numeric_id=11,
                zone_key="OTHER_ZONE",
                confidence="VERIFIED",
            ),
        )
        con.commit()

        scoped = resolve_identity(
            con,
            source_snapshot_id="client:2022-test",
            target_snapshot_id="client:2019-12-04",
            namespace="EVENT",
            source_numeric_id=11,
            zone_key="NORTH_GUSTABERG_S",
        )
        assert scoped.status == "TARGET_EQUIVALENT", scoped

        unscoped = resolve_identity(
            con,
            source_snapshot_id="client:2022-test",
            target_snapshot_id="client:2019-12-04",
            namespace="EVENT",
            source_numeric_id=11,
        )
        assert unscoped.status == "SOURCE_ID_AMBIGUOUS", unscoped

        closure = assess_identity_closure([scoped])
        assert closure.status == "READY", closure
        assert closure.target_equivalent == 1, closure

        manual = assess_identity_closure([scoped, unscoped])
        assert manual.status == "MANUAL_REQUIRED", manual
        assert manual.ambiguous == 1, manual

        blocked = assess_identity_closure([unscoped], unresolved_blocks=True)
        assert blocked.status == "BLOCKED", blocked

        con.close()

    print("snapshot identity resolver self-test: PASS")


if __name__ == "__main__":
    main()
