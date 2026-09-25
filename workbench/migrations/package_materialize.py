"""Materialize a planned migration package from a Workbench package manifest.

Only copies explicitly planned Lua/SQL source artifacts into a package staging
directory. It never applies changes to a target repository or database.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(frozen=True)
class MaterializeResult:
    copied: tuple[str, ...]
    missing: tuple[str, ...]
    skipped: tuple[str, ...]
    status: str


def _safe_source(root: Path, relative: str) -> Path:
    root=root.resolve()
    candidate=(root/relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Artifact path escapes source root: {relative}") from exc
    return candidate


def _package_relative(path: str, backend: str) -> Path:
    normalized=path.replace("\\","/").lstrip("/")
    prefix=f"{backend}/"
    if normalized.startswith(prefix):
        normalized=normalized[len(prefix):]
    rel=Path(normalized)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Unsafe package artifact path: {path}")
    return rel


def materialize_package(
    manifest: dict,
    source_root: Path,
    package_root: Path,
    *,
    overwrite: bool = False,
) -> MaterializeResult:
    migration=manifest.get("migration",{})
    if migration.get("status")=="BLOCKED":
        raise ValueError("Cannot materialize a BLOCKED migration package plan")

    copied=[]
    missing=[]
    skipped=[]
    for step in manifest.get("execution",{}).get("steps",[]):
        backend=step.get("backend")
        path=step.get("path")
        if backend not in {"lua","sql"} or not path:
            continue

        src=_safe_source(source_root,str(path))
        rel=_package_relative(str(path),backend)
        dst=(package_root/backend/rel).resolve()
        package_base=(package_root/backend).resolve()
        try:
            dst.relative_to(package_base)
        except ValueError as exc:
            raise ValueError(f"Artifact destination escapes package root: {path}") from exc

        if not src.is_file():
            missing.append(str(path))
            continue
        if dst.exists() and not overwrite:
            skipped.append(dst.relative_to(package_root).as_posix())
            continue
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        copied.append(dst.relative_to(package_root).as_posix())

    if missing:
        status="INCOMPLETE"
    elif skipped:
        status="PARTIAL"
    else:
        status="MATERIALIZED"
    return MaterializeResult(
        copied=tuple(copied),
        missing=tuple(missing),
        skipped=tuple(skipped),
        status=status,
    )
