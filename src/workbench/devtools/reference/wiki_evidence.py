"""Canonical Development adapter for claim-level wiki evidence tooling."""
from __future__ import annotations

import sys

from workbench.devtools.reference import wiki_lookup as _canonical_lookup
from workbench.runtime.paths import DATABASE_PATH, VENDOR_ROOT

_previous_lookup = sys.modules.get("wiki_lookup")
sys.modules["wiki_lookup"] = _canonical_lookup
try:
    from workbench.devtools.reference import _wiki_evidence_impl as _impl
finally:
    if _previous_lookup is None:
        sys.modules.pop("wiki_lookup", None)
    else:
        sys.modules["wiki_lookup"] = _previous_lookup

_impl.wiki_lookup = _canonical_lookup
_impl.DB_PATH = DATABASE_PATH
_impl.BG_DUMP_PATH = VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

DB_PATH = _impl.DB_PATH
BG_DUMP_PATH = _impl.BG_DUMP_PATH
wiki_lookup = _canonical_lookup
