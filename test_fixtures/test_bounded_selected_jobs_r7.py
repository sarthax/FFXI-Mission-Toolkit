"""Entirely synthetic bounded-job observation tests: no DB, DSP, client or packet access."""
import pytest
from fastapi import HTTPException
from workbench.server_admin.feature_testing import bounded_selected_jobs as jobs


class Cursor:
    def __init__(self, rows=None, character=True, error=None):
        self.rows = [{"mjob": 1, "sjob": 0, "mlvl": 99, "slvl": 0}] if rows is None else rows
        self.character = character
        self.error = error
        self.statements = []
        self.closed = False

    def execute(self, sql, args):
        assert sql.startswith("SELECT "), "readback must contain no write SQL"
        assert args == (7,), "character scope must be fixed and bound"
        assert ("FROM chars WHERE charid = %s" in sql or
                "FROM char_stats WHERE charid = %s LIMIT 2" in sql)
        self.statements.append((sql, args))
        if self.error is not None:
            raise self.error

    def fetchone(self):
        return {"charid": 7} if self.character else None

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class Connection:
    def __init__(self):
        self.rolled_back = False
        self.closed = False

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def observe(monkeypatch, *, rows=None, character=True, error=None):
    connection, cursor = Connection(), Cursor(rows, character, error)
    monkeypatch.setattr(jobs, "_approved_connection", lambda charid: (connection, cursor))
    return jobs.selected_jobs_snapshot(7), connection, cursor


def test_persisted_ids_levels_zero_preserved_and_source_unknown(monkeypatch):
    result, conn, cur = observe(monkeypatch)
    assert result["selected_jobs"] == {
        "main_job_id": 1, "support_job_id": 0, "main_level": 99, "support_level": 0}
    assert result["supported_fields_complete"] is True
    assert result["complete"] is False
    assert result["status"] == "PERSISTED_FIELDS_OBSERVED"
    assert result["snapshot_kind"] == "persisted_db_not_live_memory"
    assert result["source_revision"] == result["client_agreement"] == "UNKNOWN"
    assert result["job_unlock_status"] == result["quest_status"] == result["currencies"] == "UNSUPPORTED"
    assert conn.closed and conn.rolled_back and cur.closed
    assert len(cur.statements) == 2


def test_tuple_row_from_connector_supported(monkeypatch):
    result, _, _ = observe(monkeypatch, rows=[(2, 1, 70, 35)])
    assert result["selected_jobs"] == {
        "main_job_id": 2, "support_job_id": 1, "main_level": 70, "support_level": 35}


def test_nonexistent_character(monkeypatch):
    result, conn, cur = observe(monkeypatch, character=False)
    assert result["status"] == "UNKNOWN_CHARACTER"
    assert result["selected_jobs"] is None and not result["supported_fields_complete"]
    assert len(cur.statements) == 1 and conn.rolled_back


def test_missing_stats_row_not_fabricated(monkeypatch):
    result, _, _ = observe(monkeypatch, rows=[])
    assert result["status"] == "INCOMPLETE_MISSING_CHAR_STATS"
    assert result["selected_jobs"] is None


def test_duplicate_stats_rows_not_accepted(monkeypatch):
    result, _, _ = observe(monkeypatch, rows=[(1, 2, 20, 10), (1, 2, 20, 10)])
    assert result["status"] == "INCOMPLETE_AMBIGUOUS_CHAR_STATS"
    assert result["supported_fields_complete"] is False


@pytest.mark.parametrize("invalid", [
    (None, 1, 10, 10), (True, 1, 10, 10), ("1", 1, 10, 10),
    (-1, 1, 10, 10), (256, 1, 10, 10), (1, 1, 10.5, 10),
    (1, 1, 10), {"mjob": 1, "sjob": 0, "mlvl": 10},
])
def test_invalid_null_unexpected_type_and_shape_fail_closed(monkeypatch, invalid):
    result, _, _ = observe(monkeypatch, rows=[invalid])
    assert result["status"] == "INCOMPLETE_INVALID_PERSISTED_FIELDS"
    assert result["selected_jobs"] is None
    assert result["complete"] is False


def test_all_zero_persisted_values_do_not_imply_job_unlock(monkeypatch):
    result, _, _ = observe(monkeypatch, rows=[(0, 0, 0, 0)])
    assert result["selected_jobs"]["main_job_id"] == 0
    assert result["selected_jobs"]["main_level"] == 0
    assert result["job_unlock_status"] == "UNSUPPORTED"
    assert result["complete"] is False


def test_db_unconfigured_reports_unavailable(monkeypatch):
    monkeypatch.setattr(jobs, "_approved_connection", lambda charid: None)
    result = jobs.selected_jobs_snapshot(7)
    assert result["status"] == "UNAVAILABLE" and result["selected_jobs"] is None


def test_disallowed_character_rejected(monkeypatch):
    def reject(charid):
        raise ValueError("character not approved for supervisor diagnostics")
    monkeypatch.setattr(jobs, "_approved_connection", reject)
    with pytest.raises(ValueError, match="not approved"):
        jobs.selected_jobs_snapshot(100)


@pytest.mark.parametrize("error", [PermissionError("SELECT denied"), RuntimeError("unknown column")])
def test_database_grant_and_schema_errors_sanitized_with_cleanup(monkeypatch, error):
    connection, cursor = Connection(), Cursor(error=error)
    monkeypatch.setattr(jobs, "_approved_connection", lambda charid: (connection, cursor))
    with pytest.raises(RuntimeError, match="selected-jobs observation unavailable") as err:
        jobs.selected_jobs_snapshot(7)
    assert "unknown column" not in str(err.value)
    assert "SELECT denied" not in str(err.value)
    assert connection.rolled_back and connection.closed and cursor.closed


def test_connection_failure_is_sanitized(monkeypatch):
    def fail(charid):
        raise PermissionError("connection secret and user must not be exposed")
    monkeypatch.setattr(jobs, "_approved_connection", fail)
    with pytest.raises(RuntimeError, match="database connection failed") as err:
        jobs.selected_jobs_snapshot(7)
    assert "secret" not in str(err.value)


def test_route_registration_and_bearer_denial_before_db(monkeypatch):
    from workbench.server_admin.feature_testing import supervisor

    paths = {route.path: route for route in supervisor.router.routes}
    for path in ("/api/supervisor/test-character-inventory-v2",
                 "/api/supervisor/test-character-progression",
                 "/api/supervisor/test-character-selected-jobs"):
        assert path in paths and paths[path].methods == {"GET"}

    assert paths["/api/supervisor/test-character-selected-jobs"].operation_id == (
        "supervisor_test_character_selected_jobs"
    )
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "z" * 40)

    def fail(*args, **kwargs):
        raise AssertionError("must authenticate before DB access")

    monkeypatch.setattr(supervisor, "selected_jobs_snapshot", fail)
    for authorization in (None, "Bearer bad"):
        with pytest.raises(HTTPException) as exc:
            supervisor.test_character_selected_jobs(7, authorization=authorization)
        assert exc.value.status_code == 403


def test_route_invalid_character_vs_db_error_classification(monkeypatch):
    from workbench.server_admin.feature_testing import supervisor
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "z" * 40)
    token = "Bearer " + "z" * 40

    def invalid(*args):
        raise ValueError("character not approved for supervisor diagnostics")

    monkeypatch.setattr(supervisor, "selected_jobs_snapshot", invalid)
    with pytest.raises(HTTPException) as exc:
        supervisor.test_character_selected_jobs(7, authorization=token)
    assert exc.value.status_code == 400

    def unavailable(*args):
        raise RuntimeError("selected-jobs observation unavailable")

    monkeypatch.setattr(supervisor, "selected_jobs_snapshot", unavailable)
    with pytest.raises(HTTPException) as exc:
        supervisor.test_character_selected_jobs(7, authorization=token)
    assert exc.value.status_code == 503


@pytest.mark.parametrize("failure_at", ["SET TRANSACTION READ ONLY", "START TRANSACTION"])
def test_real_connection_helper_cleans_up_on_transaction_setup_failure(monkeypatch, failure_at):
    """The actual shared helper must not leak a cursor/socket before it returns."""
    from workbench.server_admin.feature_testing import database_diagnostics as db

    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "7")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_USER", "synthetic")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD", "synthetic")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_NAME", "synthetic")
    connection = Connection()

    class SetupFailCursor(Cursor):
        def execute(self, sql, args=None):
            if sql == failure_at:
                raise PermissionError("synthetic transaction privilege failure")
            assert sql in ("SET TRANSACTION READ ONLY", "START TRANSACTION")

    cursor = SetupFailCursor()
    monkeypatch.setattr(db, "_open", lambda user, password, database, port: (connection, cursor))
    # Import in selected_jobs resolves the actual function; its _open global
    # remains patchable without a real DB driver or socket.
    with pytest.raises(RuntimeError, match="database connection failed") as error:
        jobs.selected_jobs_snapshot(7)
    assert "privilege failure" not in str(error.value)
    assert connection.rolled_back and connection.closed and cursor.closed


def test_real_helper_closes_socket_even_if_rollback_fails(monkeypatch):
    """Best effort cleanup must preserve the original setup error."""
    from workbench.server_admin.feature_testing import database_diagnostics as db

    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "7")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_USER", "synthetic")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD", "synthetic")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DB_NAME", "synthetic")

    class BadRollback(Connection):
        def rollback(self):
            raise RuntimeError("cleanup rollback failure")

    class BadSetup(Cursor):
        def execute(self, sql, args=None):
            raise PermissionError("original setup permission failure")

    connection, cursor = BadRollback(), BadSetup()
    monkeypatch.setattr(db, "_open", lambda user, password, database, port: (connection, cursor))
    with pytest.raises(RuntimeError, match="database connection failed") as error:
        jobs.selected_jobs_snapshot(7)
    assert isinstance(error.value.__cause__, PermissionError)
    assert connection.closed and cursor.closed


def test_connection_helper_closes_socket_on_cursor_creation_failure(monkeypatch):
    """Driver connection succeeds but cursor creation fails before _open returns."""
    import sys
    import types
    from workbench.server_admin.feature_testing import database_diagnostics as db

    connection = Connection()

    def fail_cursor(**kwargs):
        raise PermissionError("synthetic cursor initialization failure")

    connection.cursor = fail_cursor
    driver = types.ModuleType("pymysql")
    driver.cursors = types.SimpleNamespace(DictCursor=object())
    driver.connect = lambda **kwargs: connection
    monkeypatch.setitem(sys.modules, "pymysql", driver)
    with pytest.raises(PermissionError, match="cursor initialization failure"):
        db._open("synthetic", "synthetic", "synthetic", 3306)
    assert connection.closed
