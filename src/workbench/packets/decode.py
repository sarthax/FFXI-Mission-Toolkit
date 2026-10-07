"""Canonical packet decoder adapter.

The mature decoder implementation remains staged byte-for-byte in ``_decode_impl``. This adapter
establishes the repository-owned Packetlyzer vendor path before importing that implementation,
then rebinds its path globals to canonical runtime paths while preserving the implementation
module object for legacy monkeypatch/import behavior.
"""
from __future__ import annotations

import io
import sys

from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT

_PACKETLYZER_ROOT = VENDOR_ROOT / "Packetlyzer"
if str(_PACKETLYZER_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKETLYZER_ROOT))

from workbench.packets import _decode_impl as _impl  # noqa: E402

_impl.TOOLS_ROOT = REPO_ROOT
_impl.PACKETLYZER_ROOT = _PACKETLYZER_ROOT
_impl.DB_XML = _PACKETLYZER_ROOT / "packetlyzer_db.xml"
_impl.EXT_JSON = _PACKETLYZER_ROOT / "packetlyzer_ext.json"
_impl.LOOKUP_DIR = _PACKETLYZER_ROOT / "lookup"

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(_impl.main())

sys.modules[__name__] = _impl
