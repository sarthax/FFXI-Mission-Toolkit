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


## Live Target GUI

The shared GUI exposes the same validation contract at `/validation/live-target`.

- Expected records use the CLI JSON shape: one `logical_type` plus normalized `records[]`.
- Target families are DSP, Topaz, Topaz-Next, and LSB through the existing server-adapter registry.
- SQLite is opened with `mode=ro`.
- MySQL/MariaDB uses `mysql-connector-python`; the password is read from the named environment variable (default `FFXI_DB_PASSWORD`) and is never stored in GUI settings, form output, or canonical validation records.
- The validator remains SELECT-only through `DBAPITargetReader`.
- Per-record states remain VERIFIED, MISSING, CONTRADICTED, AMBIGUOUS, UNKNOWN, or FAILED as produced by the existing validator.
- Persistence is explicit. When selected, only canonical ValidationRun/ValidationResult records and live-target capability evidence are stored in `workbench.db`; credentials are not persisted.
- A successful database result validates normalized database representation only. Lua execution, runtime behavior, packet/capture behavior, and client behavior remain independent validation dimensions.
