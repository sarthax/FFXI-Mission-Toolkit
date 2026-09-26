# Engine Migration Classification

`engine_migration_compare.py` compares two analyzer outputs without assuming identical server layouts.

It classifies:
- exact function/signature matches as `COMPATIBLE / NOT_REQUIRED`
- same symbols with differing signatures as `MANUAL_REQUIRED / PATCH`
- source-only symbols as `MANUAL_REQUIRED / IMPLEMENT`
- binding name matches whose C++ target differs as `MANUAL_REQUIRED / PATCH`

These are migration actions, not claims that the resulting implementation is correct. Build inclusion, runtime behavior, packet semantics, and generated code remain separate validation dimensions.
