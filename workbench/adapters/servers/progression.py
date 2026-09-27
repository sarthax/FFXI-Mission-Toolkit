"""Representation-neutral progression record producers.

Legacy Topaz/DSP store merit definitions in SQL while modern LSB moved them to
data/merits.yaml. This module emits the same logical merits record type without
pretending those physical representations are interchangeable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .base import LogicalRecord


def load_lsb_merits(path: Path) -> list[LogicalRecord]:
    """Load modern LSB merit YAML as source-neutral logical merit records."""
    path=Path(path)
    raw=yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    merits_root=raw.get("merits") or {}
    categories=merits_root.get("categories") or {}
    out: list[LogicalRecord]=[]

    for category_key, category in categories.items():
        if not isinstance(category,dict):
            continue
        category_id=category.get("id")
        category_jobs=category.get("jobs")
        max_upgrades=category.get("max_upgrades")
        merit_rows=category.get("merits") or {}
        if not isinstance(merit_rows,dict):
            continue

        for merit_name, merit in merit_rows.items():
            if not isinstance(merit,dict) or merit.get("id") is None:
                continue
            merit_id=int(merit["id"])
            jobs=merit.get("jobs",category_jobs)
            if isinstance(jobs,list):
                jobs=tuple(str(x) for x in jobs)
            elif jobs is not None:
                jobs=(str(jobs),)
            fields: dict[str,Any]={
                "merit_id":merit_id,
                "name":str(merit_name),
                "value":merit.get("value"),
                "upgrade":None,
                "jobs_mask":None,
                "upgrade_id":None,
                "legacy_category_id":None,
                "upgrade_cost_key":merit.get("upgrade_cost"),
                "lsb_category_key":str(category_key),
                "lsb_category_id":int(category_id) if category_id is not None else None,
                "category_max_upgrades":max_upgrades,
                "job_names":jobs,
            }
            out.append(LogicalRecord(
                logical_type="merits",
                identity=(("merit_id",merit_id),),
                fields=fields,
                source_family="LSB",
                source_table="data/merits.yaml",
                notes=(
                    "Modern LSB merit definition loaded from YAML after the legacy merits SQL table was dropped.",
                    "Legacy SQL-only upgrade/jobs-mask/category-index fields remain unset rather than inferred.",
                ),
            ))
    return sorted(out,key=lambda row:int(dict(row.identity)["merit_id"]))
