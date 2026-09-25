"""Registration and composition for domain plugins."""
from __future__ import annotations

from .base import ContentArchetype, DomainPlugin


class DomainPluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, DomainPlugin] = {}
        self._archetypes: dict[str, ContentArchetype] = {}

    def register_archetype(self, archetype: ContentArchetype) -> None:
        if archetype.archetype_id in self._archetypes:
            raise ValueError(f"Duplicate archetype: {archetype.archetype_id}")
        self._archetypes[archetype.archetype_id] = archetype

    def register(self, plugin: DomainPlugin) -> None:
        pid=plugin.spec.plugin_id
        if pid in self._plugins:
            raise ValueError(f"Duplicate plugin: {pid}")
        missing=[a for a in plugin.spec.archetypes if a not in self._archetypes]
        if missing:
            raise ValueError(f"Plugin {pid} references unknown archetypes: {missing}")
        self._plugins[pid]=plugin

    def validate_composition(self) -> None:
        missing=[]
        for plugin in self._plugins.values():
            for dep in plugin.spec.framework_dependencies:
                if dep not in self._plugins:
                    missing.append((plugin.spec.plugin_id,dep))
        if missing:
            raise ValueError(f"Missing plugin framework dependencies: {missing}")

    def get(self, plugin_id: str) -> DomainPlugin:
        return self._plugins[plugin_id]

    def plugins(self) -> tuple[DomainPlugin, ...]:
        return tuple(self._plugins[k] for k in sorted(self._plugins))

    def archetypes(self) -> tuple[ContentArchetype, ...]:
        return tuple(self._archetypes[k] for k in sorted(self._archetypes))

    def plugins_for_archetype(self, archetype_id: str) -> tuple[DomainPlugin, ...]:
        return tuple(
            plugin for plugin in self.plugins()
            if archetype_id in plugin.spec.archetypes
        )
