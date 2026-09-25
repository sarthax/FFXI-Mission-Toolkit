"""Reversible file apply operations for staged migration packages.

This service is explicit and deterministic. It only copies staged files into a target
root when called, records backups and hashes, and can roll them back from the journal.
It does not apply SQL to a live database.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe(root: Path, relative: str) -> Path:
    root=root.resolve()
    candidate=(root/relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes root: {relative}") from exc
    return candidate


def apply_staged_files(
    package_root: Path,
    target_root: Path,
    relative_paths: list[str] | tuple[str, ...],
    journal_path: Path,
) -> dict:
    backup_root=journal_path.parent/(journal_path.stem+"_backups")
    entries=[]

    for relative in relative_paths:
        src=_safe(package_root,relative)
        dst=_safe(target_root,relative)
        if not src.is_file():
            raise FileNotFoundError(src)

        existed=dst.exists()
        before_hash=_sha256(dst) if existed and dst.is_file() else None
        backup_path=None
        if existed:
            backup_path=_safe(backup_root,relative)
            backup_path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dst,backup_path)

        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        entries.append({
            "path":relative.replace("\\","/"),
            "target_existed":existed,
            "before_sha256":before_hash,
            "after_sha256":_sha256(dst),
            "backup_path":str(backup_path.relative_to(journal_path.parent).as_posix()) if backup_path else None,
        })

    payload={
        "schema":1,
        "kind":"WORKBENCH_APPLY_JOURNAL",
        "target_root":str(target_root.resolve()),
        "entries":entries,
        "status":"APPLIED",
    }
    journal_path.parent.mkdir(parents=True,exist_ok=True)
    journal_path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def rollback_apply(journal_path: Path) -> dict:
    payload=json.loads(journal_path.read_text(encoding="utf-8"))
    if payload.get("kind")!="WORKBENCH_APPLY_JOURNAL":
        raise ValueError("Unsupported apply journal")
    target_root=Path(payload["target_root"])

    restored=[]
    removed=[]
    for entry in reversed(payload.get("entries",[])):
        relative=entry["path"]
        dst=_safe(target_root,relative)
        if entry.get("target_existed"):
            backup_rel=entry.get("backup_path")
            if not backup_rel:
                raise ValueError(f"Missing backup for {relative}")
            backup=_safe(journal_path.parent,backup_rel)
            if not backup.is_file():
                raise FileNotFoundError(backup)
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(backup,dst)
            restored.append(relative)
        else:
            if dst.exists():
                dst.unlink()
            removed.append(relative)

    payload["status"]="ROLLED_BACK"
    payload["rollback"]={"restored":restored,"removed":removed}
    journal_path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload
