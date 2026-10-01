#!/usr/bin/env python3
"""Regression for fail-closed acquisition ITEM / KEY_ITEM reconciliation."""
from __future__ import annotations

import sqlite3

from workbench.core import graph
from workbench.core.services.acquisition_identity import (
    reconcile_acquisition_catalog,
    verified_canonical_item_ids,
)
from workbench.core.services.identity_resolver import (
    IdentityRecord,
    IdentitySnapshot,
    ensure_schema,
    register_snapshot,
    upsert_record,
)


def _enum(con, enum_id, enum_name, value, symbol):
    con.execute(
        "INSERT INTO enum_definitions VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            enum_id,
            enum_name,
            "lsb-canonical",
            "scripts/globals/items.lua" if enum_name == "xi.item" else "scripts/globals/keyitems.lua",
            1,
            "LUA_TABLE",
            str(value),
            symbol,
            f"evidence:{enum_id}",
            "[]",
        ),
    )


def _subject(kind, literal, family):
    return {
        "subject_kind": kind,
        "subject_id": str(literal),
        "acquisition_types": ["TEST"],
        "paths": [{
            "path_id": f"path:{kind}:{literal}:{family}",
            "subject_kind": kind,
            "subject_id": str(literal),
            "source_family": family,
            "source_table": "test",
            "confidence": "VERIFIED",
        }],
    }


def main():
    con = sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    ensure_schema(con)

    # Same number in different namespaces is deliberately legal and must never cross-resolve.
    _enum(con, "enum:item:test", "xi.item", 100, "TEST_ITEM")
    _enum(con, "enum:ki:test", "xi.keyItem", 100, "TEST_KI")

    register_snapshot(con, IdentitySnapshot("lsb-canonical", "SERVER", family="LSB"))
    register_snapshot(con, IdentitySnapshot("topaz-source", "SERVER", family="TOPAZ"))
    upsert_record(con, IdentityRecord(
        "identity:topaz:item:9000",
        "topaz-source",
        "ITEM",
        "ITEM|TEST_ITEM",
        "9000",
        confidence="VERIFIED",
    ))
    upsert_record(con, IdentityRecord(
        "identity:lsb:item:100",
        "lsb-canonical",
        "ITEM",
        "ITEM|TEST_ITEM",
        "100",
        confidence="VERIFIED",
    ))

    catalog = {
        "schema_version": "acquisition-catalog/v1",
        "subjects": [
            _subject("ITEM", "xi.item.TEST_ITEM", "LSB_LUA_SHOP"),
            _subject("KEY_ITEM", "xi.keyItem.TEST_KI", "LSB"),
            _subject("ITEM", "xi.keyItem.TEST_KI", "LSB"),  # wrong namespace
            _subject("ITEM", "Potion", "LSB"),             # name-only
            _subject("ITEM", "9000", "TOPAZ"),             # explicit provider bridge
            _subject("ITEM", "7000", "DSP"),               # no provider mapping
        ],
    }
    reconciled = reconcile_acquisition_catalog(
        con,
        catalog,
        canonical_snapshot_id="lsb-canonical",
        provider_snapshots={"TOPAZ": "topaz-source"},
    )

    rows = {(row["subject_kind"], row["subject_id"]): row for row in reconciled["subjects"]}
    item = rows[("ITEM", "xi.item.TEST_ITEM")]["canonical_identity"]
    key_item = rows[("KEY_ITEM", "xi.keyItem.TEST_KI")]["canonical_identity"]
    assert item["status"] == "VERIFIED" and item["canonical_id"] == "100", item
    assert item["canonical_symbol"] == "xi.item.TEST_ITEM", item
    assert key_item["status"] == "VERIFIED" and key_item["canonical_id"] == "100", key_item
    assert key_item["canonical_symbol"] == "xi.keyItem.TEST_KI", key_item

    assert rows[("ITEM", "xi.keyItem.TEST_KI")]["canonical_identity"]["status"] == "UNRESOLVED"
    assert rows[("ITEM", "Potion")]["canonical_identity"]["status"] == "UNRESOLVED"
    assert rows[("ITEM", "7000")]["canonical_identity"]["status"] == "UNRESOLVED"

    bridged = rows[("ITEM", "9000")]["canonical_identity"]
    assert bridged["status"] == "VERIFIED", bridged
    assert bridged["canonical_id"] == "100", bridged
    assert bridged["basis"] == "VERIFIED_SNAPSHOT_IDENTITY_BRIDGE", bridged

    # The graph-projection gate exports only reconciled canonical ITEM IDs, never raw literals.
    assert verified_canonical_item_ids(reconciled) == {100}
    assert reconciled["identity_reconciliation"]["fail_closed"] is True
    assert reconciled["identity_reconciliation"]["names_are_identity_evidence"] is False

    # Conflicting authoritative symbols for one numeric ID must remain ambiguous.
    _enum(con, "enum:item:test-conflict", "xi.item", 100, "TEST_ITEM_ALIAS")
    conflict = reconcile_acquisition_catalog(
        con,
        {"subjects": [_subject("ITEM", "100", "LSB")]},
        canonical_snapshot_id="lsb-canonical",
    )
    identity = conflict["subjects"][0]["canonical_identity"]
    assert identity["status"] == "AMBIGUOUS", identity
    assert conflict["canonical_subjects"] == [], conflict

    print("acquisition identity self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
