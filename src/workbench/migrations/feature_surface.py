"""Compatibility facade for feature-surface contracts and comparison.

Neutral observation types live in ``workbench.core.contracts.feature_surface``.
Comparison logic is Validation-owned in ``workbench.validation.feature_surface``.
"""
from workbench.core.contracts.feature_surface import FeatureSurface, SurfaceArtifact, SurfaceCapability
from workbench.validation.feature_surface import FeatureSurfaceComparison, compare_feature_surfaces

__all__ = [
    "FeatureSurface",
    "SurfaceArtifact",
    "SurfaceCapability",
    "FeatureSurfaceComparison",
    "compare_feature_surfaces",
]
