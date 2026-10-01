"""Component capability registry primitives.

Registration is intentionally declarative: Core knows component names and metadata, but
never imports product implementations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Iterable


@dataclass(frozen=True)
class ComponentCapability:
    name: str
    provides: FrozenSet[str] = field(default_factory=frozenset)
    optional_dependencies: FrozenSet[str] = field(default_factory=frozenset)


def capability(name: str, *, provides: Iterable[str] = (), optional_dependencies: Iterable[str] = ()) -> ComponentCapability:
    return ComponentCapability(
        name=name,
        provides=frozenset(provides),
        optional_dependencies=frozenset(optional_dependencies),
    )


CORE = capability("core", provides=("evidence-contracts", "identity-contracts", "component-registry"))
CLIENT_SHARED = capability("client_shared", provides=("client-evidence",))
CAPTURES = capability("captures", provides=("capture-evidence", "packet-evidence"), optional_dependencies=("client_shared", "devtools_reference_contract"))
VALIDATION_PACKAGES = capability("validation_packages", provides=("validation", "packages"), optional_dependencies=("captures_contract", "client_shared", "devtools_contract"))
DEVTOOLS = capability("devtools", provides=("development-evidence", "reference-evidence"), optional_dependencies=("captures_contract", "client_shared"))
EDITORS = capability("editors", provides=("editing",), optional_dependencies=("client_shared", "devtools_contract"))

ALL_COMPONENTS = {
    item.name: item
    for item in (CORE, CLIENT_SHARED, CAPTURES, VALIDATION_PACKAGES, DEVTOOLS, EDITORS)
}
