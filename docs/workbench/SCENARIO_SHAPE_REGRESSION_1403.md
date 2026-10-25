# #1403 Scenario Developer shape regression characterization

Test-only slice; synthetic inputs, no server/client or browser runtime. Base: main at `7bb970af4a21b5ffd4d31d4646528e33ad88b3a8`.

Run `node --test test_fixtures/scenario_shape_1403.test.cjs`. The harness extracts and executes the real current JavaScript functions `renderSteps`, `render`, and `parseAdvanced` with minimal synthetic DOM elements. It deliberately asserts current errors, so green characterization **does not mean the product bugs are fixed**.

- **KNOWN FAIL / source-reproduced**: missing `steps` causes `renderSteps` TypeError; wrong-typed `cleanup` causes `render` TypeError. These are documented by passing `assert.throws` tests.
- **KNOWN FAIL / source-reproduced**: `parseAdvanced` checks schema/status but accepts `cleanup: "x"`.
- **PASS control**: valid empty `steps` renders without throwing, and syntax-invalid JSON rejects without changing original input.
- **PENDING acceptance**: two `todo` tests represent intended no-throw/field-specific shape rejection. A product fix must change these into passing ordinary tests, not delete them or weaken the checks.
- **NOT_RUN**: genuine fork request, full Guided/Advanced DOM transition, dirty/CAS revision guard, validation clear, unsaved-change prompt, native beforeunload, BFCache and browser focus. These require owner-authorized browser acceptance and separate implementation scope.

No shared production editor JavaScript/templates or other agents' helpers modified. Follow-up owner should add full interactive browser coverage and fix shape validation non-destructively; this narrow harness does not prove those behaviors.
