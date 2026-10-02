from __future__ import annotations

import pytest

from workbench.editors.character.scalar_transactions import _coerce, editable_columns
from workbench.editors.character.schema import CharacterSchema, ColumnInfo, TableInfo


def column(name: str, sql_type: str, *, key: str = "", nullable: bool = False) -> ColumnInfo:
    return ColumnInfo(name=name, sql_type=sql_type, nullable=nullable, key=key, default=None, extra="")


def schema_for(table: TableInfo) -> CharacterSchema:
    return CharacterSchema(tables={table.name: table}, capabilities={}, packed_profile_fields={})


def test_scalar_editors_exclude_keys_blobs_and_unapproved_chars_fields():
    table = TableInfo(
        name="chars",
        character_key="charid",
        columns=[
            column("charid", "int(10) unsigned", key="PRI"),
            column("accid", "int(10) unsigned"),
            column("nation", "tinyint(1) unsigned"),
            column("pos_x", "float(7,3)"),
            column("missions", "blob"),
        ],
    )
    fields = {row["name"] for row in editable_columns(schema_for(table), "chars")}
    assert fields == {"nation", "pos_x"}


def test_profile_and_jobs_are_schema_driven_scalar_editors():
    profile = TableInfo(
        name="char_profile",
        character_key="charid",
        columns=[column("charid", "int unsigned", key="PRI"), column("rank_points", "int unsigned"), column("fame_norg", "smallint unsigned")],
    )
    jobs = TableInfo(
        name="char_jobs",
        character_key="charid",
        columns=[column("charid", "int unsigned", key="PRI"), column("genkai", "tinyint unsigned"), column("war", "tinyint unsigned")],
    )
    assert {row["name"] for row in editable_columns(schema_for(profile), "char_profile")} == {"rank_points", "fame_norg"}
    assert {row["name"] for row in editable_columns(schema_for(jobs), "char_jobs")} == {"genkai", "war"}


def test_skill_identity_is_read_only_but_value_and_rank_are_editable():
    table = TableInfo(
        name="char_skills",
        character_key="charid",
        columns=[
            column("charid", "int unsigned", key="PRI"),
            column("skillid", "tinyint unsigned", key="PRI"),
            column("value", "smallint unsigned"),
            column("rank", "tinyint unsigned"),
        ],
    )
    assert {row["name"] for row in editable_columns(schema_for(table), "char_skills")} == {"value", "rank"}


def test_currency_row_is_schema_driven_but_character_key_is_read_only():
    table = TableInfo(
        name="char_points",
        character_key="charid",
        columns=[
            column("charid", "int unsigned", key="PRI"),
            column("cruor", "int unsigned"),
            column("imperial_standing", "int unsigned"),
            column("daily_tally", "int signed"),
        ],
    )
    assert {row["name"] for row in editable_columns(schema_for(table), "char_points")} == {
        "cruor", "imperial_standing", "daily_tally"
    }


def test_merit_identity_is_read_only_and_only_upgrade_count_is_editable():
    table = TableInfo(
        name="char_merit",
        character_key="charid",
        columns=[
            column("charid", "int unsigned"),
            column("meritid", "smallint unsigned"),
            column("upgrades", "smallint unsigned"),
        ],
    )
    assert {row["name"] for row in editable_columns(schema_for(table), "char_merit")} == {"upgrades"}


def test_job_point_identity_is_read_only_and_progression_fields_are_editable():
    table = TableInfo(
        name="char_job_points",
        character_key="charid",
        columns=[
            column("charid", "int unsigned"),
            column("jobid", "tinyint unsigned"),
            column("capacity_points", "smallint unsigned"),
            column("job_points", "smallint unsigned"),
            column("job_points_spent", "smallint unsigned"),
            column("jptype0", "tinyint unsigned"),
        ],
    )
    assert {row["name"] for row in editable_columns(schema_for(table), "char_job_points")} == {
        "capacity_points", "job_points", "job_points_spent", "jptype0"
    }


def test_integer_coercion_honors_sql_unsigned_bounds():
    tiny = column("war", "tinyint(2) unsigned")
    assert _coerce(tiny, "99") == 99
    with pytest.raises(ValueError):
        _coerce(tiny, -1)
    with pytest.raises(ValueError):
        _coerce(tiny, 256)


def test_float_and_nullable_scalar_coercion():
    pos = column("pos_x", "float(7,3)")
    note = column("note", "varchar(4)", nullable=True)
    assert _coerce(pos, "12.5") == 12.5
    assert _coerce(note, None) is None
    with pytest.raises(ValueError):
        _coerce(note, "abcde")
