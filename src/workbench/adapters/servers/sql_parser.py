"""Small cross-platform SQL INSERT tokenizer for FFXI dump adapters."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Iterator

_INSERT_RE=re.compile(r"^INSERT INTO `(\w+)` VALUES\s*\((.*)\);\s*$")
_TRAILING_COMMENT_RE=re.compile(r"\);\s*--.*$")

def split_sql_values(paren_body: str) -> list[str]:
    fields=[]; buf=[]; in_quote=False; i=0
    while i < len(paren_body):
        ch=paren_body[i]
        if in_quote:
            if ch=="\\" and i+1 < len(paren_body) and paren_body[i+1]=="'":
                buf.append("\\'"); i+=2; continue
            if ch=="'" and i+1 < len(paren_body) and paren_body[i+1]=="'":
                buf.append("''"); i+=2; continue
            if ch=="'":
                in_quote=False
            buf.append(ch); i+=1; continue
        if ch=="'":
            in_quote=True; buf.append(ch); i+=1; continue
        if ch==",":
            fields.append("".join(buf).strip()); buf=[]; i+=1; continue
        buf.append(ch); i+=1
    if buf:
        fields.append("".join(buf).strip())
    return fields

def unquote(value: str):
    if value=="NULL":
        return None
    if len(value)>=2 and value[0]=="'" and value[-1]=="'":
        return value[1:-1].replace("''","'").replace("\\'","'")
    return value

def iter_insert_rows(path: Path, expected_table: str, columns: tuple[str,...] | list[str]) -> Iterator[dict[str,str]]:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
        cleaned=_TRAILING_COMMENT_RE.sub(");",line).strip()
        match=_INSERT_RE.match(cleaned)
        if not match or match.group(1)!=expected_table:
            continue
        values=split_sql_values(match.group(2))
        if len(values)!=len(columns):
            continue
        yield dict(zip(columns,values))
