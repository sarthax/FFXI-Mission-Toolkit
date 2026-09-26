# Validation Pipeline

`validation_pipeline.py` provides a common envelope for existing validators without replacing them.

Independent validation dimensions remain separate: Lua, SQL, bindings, C++, client, packets, and
runtime captures. A successful result in one dimension does not imply the others are verified.

`VERIFIED` means the wrapped tool completed with its documented success exit code. `FAILED`
means it reported failure. Unsupported or insufficient evidence remains `UNKNOWN`.


## Live target database validation

`workbench.migrations.live_target_validation` validates normalized expected server records against
the current state of a live target database through the selected server adapter. It is read-only:
the generic reader issues only `SELECT` statements.

The CLI entry point is:

`python -m workbench.cli.live_target_validation`

Inputs are a JSON payload containing one `logical_type` and normalized `records[]`, plus a
target server family. SQLite can be used for deterministic/local testing. MySQL/MariaDB requires
the optional `mysql-connector-python` package. For MySQL/MariaDB the password is read from an
environment variable, defaulting to `FFXI_DB_PASSWORD`; credentials are not written into
Workbench validation records.

With `--graph-db`, results are persisted as canonical `ValidationRun` and
`ValidationResult` records. This validates database representation only; runtime behavior,
packets, captures, Lua execution, and client behavior remain independent validation dimensions.

The specialized `backport_sql_live_check.py` tool remains available for package-specific live
collision and content-duplication checks such as `mob_groups`. The generic validator does not
replace specialized MariaDB health/admin tooling.
