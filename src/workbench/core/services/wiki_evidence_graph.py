"""Compatibility import for Development wiki evidence graph persistence."""
import sys

from workbench.devtools.reference import wiki_evidence_graph as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
