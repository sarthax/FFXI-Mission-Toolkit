from __future__ import annotations

import pytest

from workbench.editors.character.scalar_transactions import _coerce, editable_columns
from workbench.editors.character.schema import CharacterSchema, ColumnInfo, TableInfo


def column(name: str, sql_type: str, *, key: str = "", nullable: bool = False) -> ColumnInfo:
    return ColumnInfo(name=name, sql_type=sql_type, nullable=nullable, key=key, default=None, extra="")


def schema_for(table: TableInfo) -> CharacterSchema:
    return CharacterSchema(tables={table.name: table}, capabilities={}, packed_profile_fields={})


def names(table: TableInfo) -> set[str]:
    return {row["name"] for row in editable_columns(schema_for(table), table.name)}


def test_scalar_editors_exclude_keys_blobs_and_unapproved_chars_fields():
    table = TableInfo(name="chars", character_key="charid", columns=[
        column("charid", "int(10) unsigned", key="PRI"), column("accid", "int(10) unsigned"),
        column("nation", "tinyint(1) unsigned"), column("pos_x", "float(7,3)"), column("missions", "blob"),
    ])
    assert names(table) == {"nation", "pos_x"}


def test_profile_and_jobs_are_schema_driven_scalar_editors():
    profile = TableInfo(name="char_profile", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("rank_points", "int unsigned"), column("fame_norg", "smallint unsigned")])
    jobs = TableInfo(name="char_jobs", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("genkai", "tinyint unsigned"), column("war", "tinyint unsigned")])
    assert names(profile) == {"rank_points", "fame_norg"}
    assert names(jobs) == {"genkai", "war"}


def test_appearance_and_style_rows_are_scalar_editable_except_character_key():
    look = TableInfo(name="char_look", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("face", "tinyint unsigned"),
        column("race", "tinyint unsigned"), column("size", "tinyint unsigned"), column("head", "smallint unsigned")])
    style = TableInfo(name="char_style", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("head", "smallint unsigned"), column("body", "smallint unsigned")])
    assert names(look) == {"face", "race", "size", "head"}
    assert names(style) == {"head", "body"}


def test_skill_identity_is_read_only_but_value_and_rank_are_editable():
    table = TableInfo(name="char_skills", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("skillid", "tinyint unsigned", key="PRI"),
        column("value", "smallint unsigned"), column("rank", "tinyint unsigned")])
    assert names(table) == {"value", "rank"}


def test_currency_row_is_schema_driven_but_character_key_is_read_only():
    table = TableInfo(name="char_points", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("cruor", "int unsigned"),
        column("imperial_standing", "int unsigned"), column("daily_tally", "int signed")])
    assert names(table) == {"cruor", "imperial_standing", "daily_tally"}


def test_merit_identity_is_read_only_and_only_upgrade_count_is_editable():
    table = TableInfo(name="char_merit", character_key="charid", columns=[
        column("charid", "int unsigned"), column("meritid", "smallint unsigned"), column("upgrades", "smallint unsigned")])
    assert names(table) == {"upgrades"}


def test_job_point_identity_is_read_only_and_progression_fields_are_editable():
    table = TableInfo(name="char_job_points", character_key="charid", columns=[
        column("charid", "int unsigned"), column("jobid", "tinyint unsigned"), column("capacity_points", "smallint unsigned"),
        column("job_points", "smallint unsigned"), column("job_points_spent", "smallint unsigned"), column("jptype0", "tinyint unsigned")])
    assert names(table) == {"capacity_points", "job_points", "job_points_spent", "jptype0"}


def test_unlocks_expose_only_verified_scalar_fields_and_keep_blobs_timestamp_read_only():
    table = TableInfo(name="char_unlocks", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("outpost_sandy", "int unsigned"),
        column("mog_locker", "int unsigned"), column("traverser_claimed", "int unsigned"),
        column("homepoints", "blob", nullable=True), column("waypoints", "blob", nullable=True),
        column("traverser_start", "timestamp", nullable=True)])
    assert names(table) == {"outpost_sandy", "mog_locker", "traverser_claimed"}


def test_variable_name_is_immutable_while_value_and_expiry_are_editable():
    table = TableInfo(name="char_vars", character_key="charid", columns=[
        column("charid", "int unsigned", key="PRI"), column("varname", "varchar(64)", key="PRI"),
        column("value", "int"), column("expiry", "int")])
    assert names(table) == {"value", "expiry"}


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
