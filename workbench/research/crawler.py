"""Bounded, read-only source crawler for evidence-aware research sessions."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import fnmatch
import os
from typing import Iterable


DEFAULT_EXTENSIONS=(
    ".lua",".sql",".cpp",".cc",".cxx",".h",".hpp",".hh",".hxx",
    ".py",".json",".yaml",".yml",".md",".txt",".xml",".cmake",
)


@dataclass(frozen=True)
class CrawlPolicy:
    roots: tuple[Path, ...]
    include_globs: tuple[str, ...] = ("**/*",)
    exclude_globs: tuple[str, ...] = (
        ".git/**","**/.git/**","**/__pycache__/**","**/.venv/**","**/venv/**",
        "**/.env","**/*.key","**/*secret*","**/node_modules/**",
    )
    allowed_extensions: tuple[str, ...] = DEFAULT_EXTENSIONS
    max_files: int = 200
    max_total_bytes: int = 2_000_000
    max_file_bytes: int = 250_000

    def __post_init__(self):
        if not self.roots:
            raise ValueError("CrawlPolicy requires at least one configured root.")
        if self.max_files <= 0 or self.max_total_bytes <= 0 or self.max_file_bytes <= 0:
            raise ValueError("Crawler limits must be positive.")


class BoundedSourceCrawler:
    def __init__(self, policy: CrawlPolicy):
        self.policy=policy
        self.roots=tuple(Path(root).resolve() for root in policy.roots)

    def _resolve_under_root(self, path: Path) -> tuple[Path,Path]:
        resolved=Path(path).resolve()
        for root in self.roots:
            try:
                rel=resolved.relative_to(root)
                return root,rel
            except ValueError:
                continue
        raise PermissionError(f"Path is outside configured crawler roots: {resolved}")

    def _allowed_rel(self, rel: Path) -> bool:
        rels=rel.as_posix()
        if rel.suffix.lower() not in self.policy.allowed_extensions:
            return False
        if not any(fnmatch.fnmatch(rels,pat) for pat in self.policy.include_globs):
            return False
        if any(fnmatch.fnmatch(rels,pat) for pat in self.policy.exclude_globs):
            return False
        return True

    def iter_files(self) -> Iterable[tuple[Path,Path,Path]]:
        yielded=0
        total=0
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                rel=path.relative_to(root)
                if not self._allowed_rel(rel):
                    continue
                try:
                    size=path.stat().st_size
                except OSError:
                    continue
                if size > self.policy.max_file_bytes:
                    continue
                if yielded >= self.policy.max_files:
                    return
                if total + size > self.policy.max_total_bytes:
                    return
                yielded+=1
                total+=size
                yield root,rel,path

    def read(self, path: str, *, max_chars: int = 12000) -> dict:
        requested=Path(path)
        if not requested.is_absolute():
            matches=[]
            for root in self.roots:
                candidate=(root/requested).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    continue
                if candidate.is_file():
                    matches.append(candidate)
            if len(matches)!=1:
                return {
                    "status":"ERROR",
                    "error":f"Relative path resolved to {len(matches)} files; expected exactly one.",
                }
            requested=matches[0]

        try:
            root,rel=self._resolve_under_root(requested)
        except PermissionError as exc:
            return {"status":"DENIED","error":str(exc)}
        if not requested.is_file():
            return {"status":"ERROR","error":f"No such file: {requested}"}
        if not self._allowed_rel(rel):
            return {"status":"DENIED","error":f"File is excluded by crawler policy: {rel.as_posix()}"}
        size=requested.stat().st_size
        if size > self.policy.max_file_bytes:
            return {
                "status":"DENIED",
                "error":f"File exceeds max_file_bytes ({size} > {self.policy.max_file_bytes}).",
            }
        text=requested.read_text(encoding="utf-8",errors="replace")
        truncated=len(text)>max_chars
        if truncated:
            text=text[:max_chars]
        return {
            "status":"OK",
            "root":str(root),
            "path":rel.as_posix(),
            "size_bytes":size,
            "content":text,
            "truncated":truncated,
        }

    def search(self, query: str, *, limit: int = 50, case_sensitive: bool = False) -> dict:
        if not query:
            return {"status":"ERROR","error":"query is required"}
        needle=query if case_sensitive else query.lower()
        matches=[]
        scanned_files=0
        scanned_bytes=0
        for root,rel,path in self.iter_files():
            try:
                text=path.read_text(encoding="utf-8",errors="replace")
            except OSError:
                continue
            scanned_files+=1
            scanned_bytes+=path.stat().st_size
            hay=text if case_sensitive else text.lower()
            if needle not in hay:
                continue
            for line_no,line in enumerate(text.splitlines(),1):
                check=line if case_sensitive else line.lower()
                if needle in check:
                    matches.append({
                        "root":str(root),
                        "path":rel.as_posix(),
                        "line":line_no,
                        "text":line[:500],
                    })
                    if len(matches)>=limit:
                        return {
                            "status":"OK",
                            "query":query,
                            "matches":matches,
                            "truncated":True,
                            "scanned_files":scanned_files,
                            "scanned_bytes":scanned_bytes,
                        }
        return {
            "status":"OK",
            "query":query,
            "matches":matches,
            "truncated":False,
            "scanned_files":scanned_files,
            "scanned_bytes":scanned_bytes,
        }
