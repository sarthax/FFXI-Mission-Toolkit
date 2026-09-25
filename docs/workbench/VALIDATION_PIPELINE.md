# Validation Pipeline

`validation_pipeline.py` provides a common envelope for existing validators without replacing them.

Independent validation dimensions remain separate: Lua, SQL, bindings, C++, client, packets, and
runtime captures. A successful result in one dimension does not imply the others are verified.

`VERIFIED` means the wrapped tool completed with its documented success exit code. `FAILED`
means it reported failure. Unsupported or insufficient evidence remains `UNKNOWN`.
