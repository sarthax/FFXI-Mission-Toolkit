# Source Snapshot Fingerprints

`source_snapshot.py` creates a deterministic SHA-256 fingerprint from relative file paths and file
content. Git metadata is intentionally excluded from the content hash.

Snapshots are evidence identifiers, not claims that two trees are semantically equivalent. They let
an audit result say exactly which external source state was analyzed and make later comparisons
reproducible.

Ignored directories are common generated/environment directories only; server-specific generated
files should remain included unless the caller intentionally supplies a separate source root.
