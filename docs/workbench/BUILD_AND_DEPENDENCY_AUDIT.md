# Build Integration / C++ Dependency Audit

Two conservative analyzers now extend the C++ pass:

- `build_integration_index.py` scans an explicit external server root for common CMake/Make/source-manifest evidence. It never treats "file exists" as "compiled".
- `cpp_dependency_index.py` extracts direct includes, namespace-qualified symbol uses, and packet-related references into generic `DependencyEdge` records.

Both are evidence passes, not compilers or C++ semantic parsers. Conditional compilation, generated sources, globbing, macros, templates, and indirect build inclusion can remain UNKNOWN.

## Migration implication

A backported C++ implementation is not complete merely because its source file exists or a binding is registered. The target must also expose a declaration/definition and include the implementation in the applicable build target/configuration.

The next layer should combine these findings with engine-change records and classify migration actions such as COPY, PATCH, IMPLEMENT, or MANUAL_REVIEW.
