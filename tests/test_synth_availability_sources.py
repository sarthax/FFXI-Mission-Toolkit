from workbench.server_admin.synth import recipes as R


def _fake_rows(rate_col):
    def rows(conn, sql, params=()):
        if sql.startswith("SHOW COLUMNS FROM mob_droplist"):
            return [("x",)] if params and params[0] == rate_col else []
        if "FROM mob_droplist" in sql and "JOIN" not in sql:
            assert f"`{rate_col}`>0" in sql
            return [(100,)]
        if "JOIN mob_groups" in sql:
            assert f"d.`{rate_col}`>0" in sql
            return [(100, "Goblin", 5, 1)]
        if "FROM synth_recipes" in sql:
            return []
        return []
    return rows


def test_rate_zero_drops_are_filtered_for_both_column_names(monkeypatch):
    for col in ("itemRate", "dropRate"):
        R._AVAIL_CACHE.clear()
        monkeypatch.setattr(R, "_rows", _fake_rows(col))
        monkeypatch.setattr(R, "table_columns", lambda conn: {"Desynth"})
        out = R._sources(object(), None)
        assert set(out["drops"]) == {100}
    R._AVAIL_CACHE.clear()
