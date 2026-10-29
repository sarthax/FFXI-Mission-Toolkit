"""Active-environment adapter for the mature Zone Plot backend.

The underlying Zone Plot implementation still accepts explicit ``topaz``/``dsp`` selectors for
legacy callers and comparison workflows.  Generic GUI/admin callers should import this module
instead: with no explicit server argument it resolves the named active server profile introduced
by the Server Environments work.

Importing this adapter patches the mature module's runtime globals in-place so existing Zone Plot
functions (``zone_data``, ``zone_list``, ``_db``, nav helpers, etc.) all resolve the same active
profile without duplicating the backend implementation.
"""
from __future__ import annotations

import sys

from workbench.devtools.spatial import zone_plot as _impl
from workbench.runtime import server_env
from workbench.runtime.server_env import (  # noqa: F401  (re-exported compatibility surface)
    get_environment, get_environment_key, get_server, set_server,
)

_server_root = server_env.server_root

# Patch the mature implementation's runtime globals so all of its existing functions use the
# active-profile resolver when invoked through this adapter (and by later imports in this process).
_impl._server_root = _server_root
_impl.get_server = get_server
_impl.set_server = set_server
_impl.get_environment = get_environment
_impl.get_environment_key = get_environment_key

# Make this module a true compatibility alias to the patched mature implementation.
sys.modules[__name__] = _impl
