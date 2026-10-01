"""Canonical Development adapter for dual-wiki claim comparison."""
from __future__ import annotations

import sys

from workbench.devtools.reference import wiki_evidence as _canonical_evidence

_previous_evidence = sys.modules.get("wiki_evidence")
sys.modules["wiki_evidence"] = _canonical_evidence
try:
    from workbench.devtools.reference import _wiki_claim_compare_impl as _impl
finally:
    if _previous_evidence is None:
        sys.modules.pop("wiki_evidence", None)
    else:
        sys.modules["wiki_evidence"] = _previous_evidence

_impl.wiki_evidence = _canonical_evidence

if __name__ == "__main__":
    raise SystemExit(_impl.main())

# Preserve module-global mutation/monkeypatch semantics during migration.
sys.modules[__name__] = _impl
