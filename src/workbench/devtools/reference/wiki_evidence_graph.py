"""Canonical Development adapter for wiki evidence graph persistence."""
from __future__ import annotations

import sys

from workbench.devtools.reference import wiki_claim_compare as _canonical_compare
from workbench.devtools.reference import wiki_evidence as _canonical_evidence

_previous_evidence = sys.modules.get("wiki_evidence")
_previous_compare = sys.modules.get("wiki_claim_compare")
sys.modules["wiki_evidence"] = _canonical_evidence
sys.modules["wiki_claim_compare"] = _canonical_compare
try:
    from workbench.devtools.reference import _wiki_evidence_graph_impl as _impl
finally:
    if _previous_evidence is None:
        sys.modules.pop("wiki_evidence", None)
    else:
        sys.modules["wiki_evidence"] = _previous_evidence
    if _previous_compare is None:
        sys.modules.pop("wiki_claim_compare", None)
    else:
        sys.modules["wiki_claim_compare"] = _previous_compare

_impl.wiki_evidence = _canonical_evidence
_impl.wiki_claim_compare = _canonical_compare

if __name__ == "__main__":
    raise SystemExit(_impl.main())

sys.modules[__name__] = _impl
