#!/usr/bin/env python3
"""Regression for the FeatureSurface Core/Development/Validation boundary split."""
from pathlib import Path

from workbench.core.contracts.feature_surface import FeatureSurface, SurfaceArtifact, SurfaceCapability
from workbench.validation.feature_surface import FeatureSurfaceComparison, compare_feature_surfaces
from workbench.devtools.features.surface_graph import persist_feature_surface
from workbench.validation.surface_validation import build_feature_surface_validation

from workbench.migrations import feature_surface as legacy_surface
from workbench.core.services import feature_surface_graph as legacy_graph
from workbench.core.services import feature_surface_validation as legacy_validation


def main() -> int:
    assert legacy_surface.FeatureSurface is FeatureSurface
    assert legacy_surface.SurfaceArtifact is SurfaceArtifact
    assert legacy_surface.SurfaceCapability is SurfaceCapability
    assert legacy_surface.FeatureSurfaceComparison is FeatureSurfaceComparison
    assert legacy_surface.compare_feature_surfaces is compare_feature_surfaces
    assert legacy_graph.persist_feature_surface is persist_feature_surface
    assert legacy_validation.build_feature_surface_validation is build_feature_surface_validation

    source = FeatureSurface("feature:test", "source", artifacts=(SurfaceArtifact("root", "a.lua", "LUA"),))
    target = FeatureSurface("feature:test", "target", artifacts=(SurfaceArtifact("root", "b.lua", "LUA"),))
    comparison = compare_feature_surfaces(source, target)
    assert comparison.status == "ROLE_AND_ENTITY_COVERAGE_ALIGNED"
    assert comparison.role_path_drift

    root = Path(__file__).resolve().parents[1]
    graph_text = (root / "src/workbench/devtools/features/surface_graph.py").read_text(encoding="utf-8")
    validation_text = (root / "src/workbench/validation/surface_validation.py").read_text(encoding="utf-8")
    assert "workbench.validation" not in graph_text
    assert "workbench.core.contracts.feature_surface" in graph_text
    assert "workbench.validation.feature_surface" in validation_text

    print("feature surface component boundary self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
