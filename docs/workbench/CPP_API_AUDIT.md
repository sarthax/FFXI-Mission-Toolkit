# C++ API / Engine Analysis

## Scope

The Workbench does not contain the external DSP/Topaz/LSB C++ trees. Engine analysis therefore accepts an explicit external source root rather than assuming a server layout.

## Implemented

`cpp_api_index.py` provides a conservative first-pass index of:
- C++ declarations/definitions
- functions/methods and lightweight signatures
- `SOL_REGISTER` and `LUNAR_DECLARE_METHOD` bindings
- C++ enums and `#define` constants
- exact binding-to-symbol matches where extraction permits
- standardized `Finding` and `AnalysisResult` output

The analyzer deliberately records unresolved or ambiguous cases as UNKNOWN. It does not claim that regex extraction is a complete C++ parser.

## Binding compatibility consequence

The existing binding index proves registration-name differences, but the Workbench must also compare:
1. Lua name
2. binding system
3. bound C++ symbol
4. declaration
5. definition
6. signature
7. enum/constant dependencies
8. build inclusion

A name match alone is not sufficient. The existing `GetNPCByID` evidence is a concrete project-local example of why.

## Build integration

Build analysis is the next layer. It must inspect the external root for CMake, Makefiles, source manifests, generated-source rules, and conditional compilation. A copied implementation that is not compiled is an unresolved migration dependency, not an implemented feature.

## Limits

- Macro-heavy or templated C++ may be misparsed.
- Out-of-class definitions may not inherit class context reliably.
- Enum values using expressions are retained as expressions; only simple implicit sequencing is tracked.
- The analyzer does not infer packet handlers or runtime semantics yet.
