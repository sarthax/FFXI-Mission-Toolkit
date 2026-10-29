# Synthetic Headless execution-contract fixtures — Toolkit consumer (#110)

These eight source files (seven scenario fixtures plus `MANIFEST.json`) are copied **byte-for-byte** from [XIHeadless `docs/protocol/fixtures/`](https://github.com/sarthax/xiheadless-dsp/tree/main/docs/protocol/fixtures) as inspected on **2026-10-28**. The matching source Git blob SHAs are pinned in [the Toolkit pytest module](../test_xi_test_execution_conformance_110.py). `.gitattributes` preserves LF on Windows; the test checks both the source Git blob SHA-1 and each manifest-declared raw-byte SHA-256 and byte length. The files are not regenerated or prettified in Toolkit.

Protocol: `xi-test-execution/1.0.0-draft.1`. **Working draft, not an approved or deployed endpoint.** Every fixture is explicitly `synthetic: true`; names, revision omissions, source/oracle claims and PASS/FAIL examples are made-up regression data, not real DSP acceptance or authorized evidence.

The Toolkit test independently checks the consumer's required safety boundaries without importing or duplicating the Headless Python validator: unknown core semantics fail, optional additive fields are not treated as gameplay evidence, accepted/finished is distinct from assertion verdict, cancel acknowledgement is not a completed cancellation, unknown provenance remains explicit, and a wire bundle is not a valid direct legacy-v1 importer report. Toolkit's current v1 importer can structurally represent `UNKNOWN`, but this fact alone does **not** authorize importing synthetic wire messages or manufacture missing source revisions and oracles.

Run from the Toolkit repository root with local offline prerequisites installed:

```sh
python -m pytest -q test_fixtures/test_xi_test_execution_conformance_110.py
```

This exercises fixture integrity and synthetic consumer behavior only; it does not call Headless MCP, the server, Mission Toolkit's live runner, a database, or a client. Commit/update fixtures only together with a deliberate upstream revision and matching pins/manifest changes. Mirror drift or a breaking field change should fail these tests.

**Not included:** a production execution adapter, producer authentication, end-to-end import, local/live acceptance, or a sign-off for Headless #105. Headless #110 remains open until both sides have completed reviewed conformance and final-head test evidence.
